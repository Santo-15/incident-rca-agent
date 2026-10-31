from typing import TypedDict

class RCAState(TypedDict, total=False):
    alerts: list[str]
    hypothesis: dict
    critique: str
    loop_count: int
    report: str