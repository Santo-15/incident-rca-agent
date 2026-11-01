import operator
from typing import Annotated, TypedDict
from agent.schemas import Finding

MAX_LOOPS = 2   # correlator runs at most this many times (first try + one retry after the critic)


class RCAState(TypedDict, total=False):
    payload: dict            # raw Alertmanager body (webhook or /api/v2/alerts)
    alerts: list[str]        # firing alerts, e.g. "PostgresDown since 05:20:15 UTC"
    silent: list[str]        # known alerts that did NOT fire (silence is evidence)
    first_alert: float       # unix ts of the earliest firing alert
    window_start: float      # evidence window used by the tools
    window_end: float
    findings: Annotated[list[Finding], operator.add]   # KEY: reducer = old list + new list, so parallel agents append instead of overwrite
    deploys: list[dict]      # suspect deploys from deploy_agent, read by diff_agent: {tag, base, time}
    hypothesis: dict         # latest CorrelatorAnswer as a dict
    hypotheses: Annotated[list[dict], operator.add]    # KEY: every correlator answer, so eval can measure critic corrections
    critique: str            # "ok" or "weak: ..."
    loop_count: int
    llm_calls: Annotated[int, operator.add]            # KEY: each LLM node adds 1; checks the <= 15 calls budget
    report: str
    similar: list[dict]      # past incidents memory found (P10); kept in state so eval can check whether memory helped
