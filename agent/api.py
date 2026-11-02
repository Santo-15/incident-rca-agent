# Webhook API: Alertmanager POSTs here when alerts fire. Receive + de-duplicate + store, then diagnose in a background worker.
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor                    # NEW
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from agent.graph import build_graph                                   # NEW
from agent.run import live_payload, tracing_config                    # NEW: same helpers the eval runner used

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")   # NEW: shows "primary failed" / fallback lines
logger = logging.getLogger("agent.api")

app = FastAPI(title="Incident RCA agent")

INCIDENTS: dict[str, dict] = {}   # KEY: incident id -> record; in memory, so a restart empties it (fine for the demo)
OPEN: dict[str, str] = {}         # KEY: Alertmanager groupKey -> id of the incident still open for that group

SETTLE_S = int(os.getenv("RCA_SETTLE_S", "90"))                       # NEW KEY: wait for related alerts before diagnosing
WORKER = ThreadPoolExecutor(max_workers=1)                            # NEW KEY: one diagnosis at a time = free-tier LLM limits stay safe
GRAPH = build_graph()                                                 # NEW: compile the LangGraph once, reuse for every incident


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")   # one time format everywhere


class Webhook(BaseModel):         # KEY: Alertmanager webhook body (version 4); we validate only what we use
    model_config = ConfigDict(extra="allow")                          # keep extra fields (groupLabels, externalURL...) without failing
    groupKey: str                                                     # same value for every notification of one alert group
    status: Literal["firing", "resolved"]                             # "resolved" only when ALL alerts in the group are resolved
    alerts: list[dict] = Field(default_factory=list)                  # raw alerts; triage already parses this exact shape


def diagnose(iid: str):                                               # NEW KEY: runs in the worker thread, never inside the request
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
    WORKER.submit(diagnose, iid)                                      # NEW KEY: hand off and return immediately
    return {"action": "queued", "incident": iid}


@app.get("/incidents")
def list_incidents():
    rows = sorted(INCIDENTS.values(), key=lambda r: r["received_at"], reverse=True)   # newest first, for the UI later
    return [{k: r.get(k) for k in ("id", "status", "received_at", "resolved_at", "updates", "agent_s")}
            | {"cause": (r.get("hypothesis") or {}).get("cause")}   # NEW: cause in the list, for the UI
            for r in rows]


@app.get("/incidents/{iid}")
def get_incident(iid: str):
    if iid not in INCIDENTS:
        raise HTTPException(status_code=404, detail="no such incident")
    return INCIDENTS[iid]