# Webhook API: Alertmanager POSTs here when alerts fire. Receive + de-duplicate + store, then diagnose in a background worker.
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
import json                       # read eval/ground_truth.json
import signal                     # SIGINT = Ctrl+C for the chaos script
import subprocess                 # run chaos/<id>.sh
from pathlib import Path          # repo-root paths
import httpx                      # set Locust load

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from agent.graph import build_graph
from agent.run import live_payload, tracing_config                    # same helpers the eval runner used
from agent.llm import ROLES  

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")   # shows "primary failed" / fallback lines
logger = logging.getLogger("agent.api")

app = FastAPI(title="Incident RCA agent")

INCIDENTS: dict[str, dict] = {}   # KEY: incident id -> record; in memory, so a restart empties it (fine for the demo)
OPEN: dict[str, str] = {}         # KEY: Alertmanager groupKey -> id of the incident still open for that group

SETTLE_S = int(os.getenv("RCA_SETTLE_S", "90"))                       # KEY: wait for related alerts before diagnosing
WORKER = ThreadPoolExecutor(max_workers=1)                            # KEY: one diagnosis at a time = free-tier LLM limits stay safe
GRAPH = build_graph()                                                 # compile the LangGraph once, reuse for every incident


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")   # one time format everywhere


class Webhook(BaseModel):         # KEY: Alertmanager webhook body (version 4); we validate only what we use
    model_config = ConfigDict(extra="allow")                          # keep extra fields (groupLabels, externalURL...) without failing
    groupKey: str                                                     # same value for every notification of one alert group
    status: Literal["firing", "resolved"]                             # "resolved" only when ALL alerts in the group are resolved
    alerts: list[dict] = Field(default_factory=list)                  # raw alerts; triage already parses this exact shape


NODE_ROLE = {"logs_agent": "logs", "diff_agent": "diff", "correlator": "correlator", "critic": "critic"}   # nodes that may call an LLM


def describe(node: str, upd: dict) -> str:                            # one human-readable line per finished node
    f = upd.get("findings") or []
    if node == "triage":
        return f"{len(upd.get('alerts', []))} alert(s) firing · {len(upd.get('silent', []))} known alerts silent"
    if node == "correlator":
        h = upd.get("hypothesis") or {}
        return f"hypothesis → {h.get('cause')} ({h.get('confidence')} confidence): {h.get('summary', '')}"
    if node == "critic":
        return f"verdict → {upd.get('critique')}"                     # KEY: "ok" or "weak: ..." = the self-check that can force a retry
    if node == "reporter":
        return "incident report written"
    high = [x.signal for x in f if x.severity == "high"][:3]
    return f"{len(f)} finding(s)" + (f" · high: {'; '.join(high)}" if high else "")


class TraceLog(logging.Handler):                                      # catches "fallback role=..." warnings from agent/llm.py
    def __init__(self, inc: dict, t0: float):
        super().__init__(logging.WARNING)
        self.inc, self.t0 = inc, t0

    def emit(self, record):
        msg = record.getMessage()
        if msg.startswith("fallback role="):                          # KEY: a hidden fallback becomes a visible trace line
            self.inc["trace"].append({"t": round(time.perf_counter() - self.t0, 1), "node": "llm", "text": msg[:220], "llm": None})


def diagnose(iid: str):                                               # KEY: runs in the worker thread, never inside the request
    inc = INCIDENTS[iid]
    try:
        inc["settle_until"] = time.time() + SETTLE_S                  # the UI shows a countdown from this
        time.sleep(SETTLE_S)                                          # let the other alerts of this outage fire too
        payload = live_payload()                                      # KEY: current alerts from Alertmanager, like the eval
        if not payload["alerts"]:                                     # outage already over: use what the webhook sent
            payload = inc["payload"]
        inc.update(status="running", started_at=now(), trace=[])
        t0 = time.perf_counter()
        handler = TraceLog(inc, t0)
        logging.getLogger().addHandler(handler)
        final = {}
        try:
            for mode, chunk in GRAPH.stream({"payload": payload}, config=tracing_config(),
                                            stream_mode=["updates", "values"]):   # KEY: "updates" = what each node just returned; "values" = full state so far
                if mode == "values":
                    final = chunk                                     # the last one is the final state (same as invoke() returned)
                    continue
                for node, upd in chunk.items():
                    upd = upd or {}
                    role = NODE_ROLE.get(node)
                    inc["trace"].append({
                        "t": round(time.perf_counter() - t0, 1),      # seconds since the agent started
                        "node": node,
                        "text": describe(node, upd),
                        "count": len(upd.get("findings") or []),
                        "high": [x.signal for x in (upd.get("findings") or []) if x.severity == "high"][:3],
                        "cause": (upd.get("hypothesis") or {}).get("cause"),
                        "confidence": (upd.get("hypothesis") or {}).get("confidence"),
                        "llm": ROLES[role][0][1].split("/")[-1] if role and upd.get("llm_calls") else None,
                        "llm": ROLES[role][0][1].split("/")[-1] if role and upd.get("llm_calls") else None,   # primary model name, only if this node called an LLM
                    })
                    hits = upd.get("similar") or []
                    if node == "correlator" and hits and not any(e["node"] == "memory" for e in inc["trace"]):
                        inc["trace"].append({"t": inc["trace"][-1]["t"], "node": "memory",   # KEY: past-incident recall from Chroma
                                             "text": "similar past incident: " + ", ".join(f"{h['scenario']} → {h['cause']} (distance {h['distance']})" for h in hits),
                                             "llm": None})
        finally:
            logging.getLogger().removeHandler(handler)
        inc.update({
            "status": "done",
            "agent_s": round(time.perf_counter() - t0, 1),
            "hypothesis": final["hypothesis"],
            "hypotheses": final.get("hypotheses", []),                # every correlator attempt, first -> last
            "critique": final.get("critique"),
            "llm_calls": final.get("llm_calls"),
            "findings": [f.model_dump() for f in final.get("findings", [])],
            "report": final["report"],
        })
    except Exception as exc:                                          # KEY: a failed diagnosis is recorded, the API keeps running
        logger.exception("diagnosis failed for %s", iid)
        inc.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        inc["finished_at"] = now()
        if os.getenv("LANGFUSE_PUBLIC_KEY"):                          # send trace spans now, not "someday"
            from langfuse import get_client
            get_client().flush()


@app.get("/health")
def health():
    return {"ok": True, "open": len(OPEN), "settle_s": SETTLE_S}      # quick "is the API up" check


@app.post("/alerts", status_code=202)                                 # KEY: 202 Accepted = "got it, work happens later", not "done"
def receive(hook: Webhook):
    key = hook.groupKey
    if hook.status == "resolved":                                     # outage over: close the open incident
        iid = OPEN.pop(key, None)
        if iid:
            INCIDENTS[iid]["resolved_at"] = now()
        return {"action": "resolved", "incident": iid}

    if key in OPEN:                                                   # KEY: Alertmanager re-sends every group_interval (1 min); diagnose once, not every minute
        INCIDENTS[OPEN[key]]["updates"] += 1
        return {"action": "duplicate", "incident": OPEN[key]}

    iid = uuid4().hex[:8]                                             # short id for URLs, e.g. 3f9a1c2e
    INCIDENTS[iid] = {
        "id": iid,
        "status": "queued",                                           # queued -> running -> done / failed
        "received_at": now(),
        "resolved_at": None,
        "group_key": key,
        "updates": 0,                                                 # how many duplicate notifications came after the first
        "payload": hook.model_dump(),                                 # fallback if the alerts are gone by the time we run
        "report": None,
    }
    OPEN[key] = iid
    WORKER.submit(diagnose, iid)                                      # KEY: hand off and return immediately
    return {"action": "queued", "incident": iid}


@app.get("/incidents")
def list_incidents():
    rows = sorted(INCIDENTS.values(), key=lambda r: r["received_at"], reverse=True)   # newest first, for the UI later
    return [{k: r.get(k) for k in ("id", "status", "received_at", "resolved_at", "updates", "agent_s")}
            | {"cause": (r.get("hypothesis") or {}).get("cause")}   # cause in the list, for the UI
            for r in rows]


@app.get("/incidents/{iid}")
def get_incident(iid: str):
    if iid not in INCIDENTS:
        raise HTTPException(status_code=404, detail="no such incident")
    return INCIDENTS[iid]

# ---------- S4: break-it buttons ----------
ROOT = Path(__file__).resolve().parents[1]                            # repo root, so chaos/ and eval/ are found from anywhere
GT = json.loads((ROOT / "eval" / "ground_truth.json").read_text())
SCENARIOS = {s["id"]: s for s in GT["scenarios"] if s["id"] != "slow_query"}   # KEY: slow_query never alerts at 50 users, so no demo value
CHAOS_S = int(os.getenv("RCA_CHAOS_S", "420"))                        # KEY: outage length; long enough for the slow alerts (~280 s) + settle
COOLDOWN_S = int(os.getenv("RCA_CHAOS_COOLDOWN_S", "600"))            # KEY: metrics_agent needs a clean 10-min baseline before the next outage
LOCUST_URL = os.getenv("LOCUST_URL", "http://127.0.0.1:8089")
DAILY_MAX = int(os.getenv("RCA_CHAOS_DAILY_MAX", "8"))               # KEY: max outages per 24 h, protects the free LLM quota
RUNS: list[float] = []                                               # start times of recent outages (in memory; restart clears it)
CHAOS = {"proc": None, "id": None, "started": None, "done_at": None}  # the one chaos run we allow at a time


def chaos_state() -> dict:
    p = CHAOS["proc"]
    running = p is not None and p.poll() is None                      # poll() is None = script still running = shop still broken
    if p is not None and not running and CHAOS["done_at"] is None and p.returncode in (0, 130):
        CHAOS["done_at"] = time.time()                                # first time we notice it finished: cooldown starts now
    left = 0 if CHAOS["done_at"] is None else max(0, int(COOLDOWN_S - (time.time() - CHAOS["done_at"])))
    return {"running": CHAOS["id"] if running else None, "started": CHAOS["started"], "chaos_s": CHAOS_S,
            "cooldown_left_s": 0 if running else left,
            "last_exit": None if running or p is None else p.returncode,
            "runs_left": max(0, DAILY_MAX - len([t for t in RUNS if t > time.time() - 86400]))}


@app.get("/chaos")
def chaos_info():
    return chaos_state() | {"scenarios": [{"id": s["id"], "kind": s["kind"], "note": s["note"]} for s in SCENARIOS.values()]}


@app.post("/chaos/stop")                                              # KEY: declared BEFORE /chaos/{sid}, or "stop" would be read as a scenario id
def chaos_stop():
    p = CHAOS["proc"]
    if p is None or p.poll() is not None:
        raise HTTPException(status_code=409, detail="nothing is broken right now")
    os.killpg(p.pid, signal.SIGINT)                                   # KEY: like Ctrl+C on the script: its trap runs restore()
    return {"action": "restoring", "scenario": CHAOS["id"]}


@app.post("/chaos/{sid}", status_code=202)
def chaos_start(sid: str):
    if sid not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"unknown scenario {sid}")
    state = chaos_state()
    if state["running"]:                                              # KEY: one outage at a time, or the agent sees two mixed incidents
        raise HTTPException(status_code=409, detail=f"{state['running']} is already running")
    if state["cooldown_left_s"]:
        raise HTTPException(status_code=409, detail=f"cooling down, {state['cooldown_left_s']} s left")
    RUNS[:] = [t for t in RUNS if t > time.time() - 86400]          # forget outages older than 24 h
    if len(RUNS) >= DAILY_MAX:                                        # KEY: daily cap reached
        wait_h = round((RUNS[0] + 86400 - time.time()) / 3600, 1)     # hours until the oldest one drops out
        raise HTTPException(status_code=429, detail=f"daily demo limit reached ({DAILY_MAX} per 24 h), next slot in {wait_h} h")
    try:                                                              # same load as the eval (50 users), best effort
        httpx.post(f"{LOCUST_URL}/swarm", data={"user_count": GT["locust_users"], "spawn_rate": 20}, timeout=5)
    except httpx.HTTPError:
        logger.warning("could not set Locust load")
    log = open("/tmp/rca_chaos.log", "w")                             # script output, for debugging a failed run
    CHAOS.update(proc=subprocess.Popen(["bash", f"chaos/{sid}.sh", str(CHAOS_S)], cwd=ROOT, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True),   # KEY: own process group, so killpg stops only the script
                 id=sid, started=now(), done_at=None)
    RUNS.append(time.time())                                          # KEY: count this outage
    return {"action": "breaking", "scenario": sid, "seconds": CHAOS_S}