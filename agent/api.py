# Webhook API: Alertmanager POSTs here when alerts fire. S1 = receive + de-duplicate + store; S2 runs the agent in the background.
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Incident RCA agent")

INCIDENTS: dict[str, dict] = {}   # KEY: incident id -> record; in memory, so a restart empties it (fine for the demo)
OPEN: dict[str, str] = {}         # KEY: Alertmanager groupKey -> id of the incident still open for that group


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")   # one time format everywhere


class Webhook(BaseModel):         # KEY: Alertmanager webhook body (version 4); we validate only what we use
    model_config = ConfigDict(extra="allow")                          # keep extra fields (groupLabels, externalURL...) without failing
    groupKey: str                                                     # same value for every notification of one alert group
    status: Literal["firing", "resolved"]                             # "resolved" only when ALL alerts in the group are resolved
    alerts: list[dict] = Field(default_factory=list)                  # raw alerts; triage already parses this exact shape


@app.get("/health")
def health():
    return {"ok": True, "open": len(OPEN)}                            # quick "is the API up" check


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
        "status": "queued",                                           # S2 moves it: queued -> running -> done / failed
        "received_at": now(),
        "resolved_at": None,
        "group_key": key,
        "updates": 0,                                                 # how many duplicate notifications came after the first
        "payload": hook.model_dump(),                                 # KEY: the exact body the agent graph will get as state["payload"]
        "report": None,
    }
    OPEN[key] = iid
    return {"action": "queued", "incident": iid}


@app.get("/incidents")
def list_incidents():
    rows = sorted(INCIDENTS.values(), key=lambda r: r["received_at"], reverse=True)   # newest first, for the UI later
    return [{k: r[k] for k in ("id", "status", "received_at", "resolved_at", "updates")} for r in rows]


@app.get("/incidents/{iid}")
def get_incident(iid: str):
    if iid not in INCIDENTS:
        raise HTTPException(status_code=404, detail="no such incident")
    return INCIDENTS[iid]