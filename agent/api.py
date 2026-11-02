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


def diagnose(iid: str):                                               # KEY: runs in the worker thread, never inside the request
    inc = INCIDENTS[iid]
    try:
        time.sleep(SETTLE_S)                                          # let the other alerts of this outage fire too
        payload = live_payload()                                      # KEY: current alerts from Alertmanager, like the eval
        if not payload["alerts"]:                                     # outage already over: use what the webhook sent
            payload = inc["payload"]
        inc["status"] = "running"
        inc["started_at"] = now()
        t0 = time.perf_counter()
        out = GRAPH.invoke({"payload": payload}, config=tracing_config())   # KEY: same call as python -m agent.run
        inc.update({
            "status": "done",
            "agent_s": round(time.perf_counter() - t0, 1),
            "hypothesis": out["hypothesis"],                          # cause, confidence, deploy_tag, evidence...
            "llm_calls": out.get("llm_calls"),
            "findings": [f.model_dump() for f in out.get("findings", [])],   # Finding objects -> plain dicts for JSON
            "report": out["report"],
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
CHAOS = {"proc": None, "id": None, "started": None, "done_at": None}  # the one chaos run we allow at a time


def chaos_state() -> dict:
    p = CHAOS["proc"]
    running = p is not None and p.poll() is None                      # poll() is None = script still running = shop still broken
    if p is not None and not running and CHAOS["done_at"] is None and p.returncode in (0, 130):
        CHAOS["done_at"] = time.time()                                # first time we notice it finished: cooldown starts now
    left = 0 if CHAOS["done_at"] is None else max(0, int(COOLDOWN_S - (time.time() - CHAOS["done_at"])))
    return {"running": CHAOS["id"] if running else None, "started": CHAOS["started"], "chaos_s": CHAOS_S,
            "cooldown_left_s": 0 if running else left,
            "last_exit": None if running or p is None else p.returncode}


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
    try:                                                              # same load as the eval (50 users), best effort
        httpx.post(f"{LOCUST_URL}/swarm", data={"user_count": GT["locust_users"], "spawn_rate": 20}, timeout=5)
    except httpx.HTTPError:
        logger.warning("could not set Locust load")
    log = open("/tmp/rca_chaos.log", "w")                             # script output, for debugging a failed run
    CHAOS.update(proc=subprocess.Popen(["bash", f"chaos/{sid}.sh", str(CHAOS_S)], cwd=ROOT, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True),   # KEY: own process group, so killpg stops only the script
                 id=sid, started=now(), done_at=None)
    return {"action": "breaking", "scenario": sid, "seconds": CHAOS_S}