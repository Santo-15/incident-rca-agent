import operator
from typing import Annotated, TypedDict
from agent.schemas import Finding

class RCAState(TypedDict, total=False):
    alerts: list[str]
    findings: Annotated[list[Finding], operator.add]  # KEY: reducer = old list + new list, so parallel agents append instead of overwrite
    hypothesis: dict
    critique: str
    loop_count: int
    report: str
