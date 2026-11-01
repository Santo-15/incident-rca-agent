from typing import Literal
from pydantic import BaseModel, Field

Cause = Literal[
    "db_pool_exhausted",
    "postgres_down",
    "redis_down",
    "memory_leak",
    "slow_query",
    "insufficient_evidence",
]

class CorrelatorAnswer(BaseModel):
    cause: Cause = Field(description="The single root cause, chosen from the allowed values.")
    summary: str = Field(description="One sentence describing what broke and its effect on the shop.")
    evidence: list[str] = Field(description="2 to 5 short facts from the evidence that support the cause.")
    silent_signals: str = Field(description="One sentence on why the silent alerts fit this cause.")
    deploy_tag: str | None = Field(description="The deploy tag that triggered the incident, or null if no deploy caused it.")
    confidence: Literal["low", "medium", "high"] = Field(description="How strongly the evidence supports the cause.")

Source = Literal["logs", "metrics", "deploys", "diff"]  # KEY: which specialist agent produced the finding

class Finding(BaseModel):  # KEY: one fact found by a specialist agent; the shared unit the correlator reads
    source: Source = Field(description="The agent that found this: logs, metrics, deploys or diff.")
    signal: str = Field(description="Short name of what was checked, e.g. 'pg_up' or 'QueuePool limit reached'.")
    detail: str = Field(description="One line with the real values, e.g. 'pg_up = 0 since 10:42 UTC'.")
    severity: Literal["low", "medium", "high"] = Field(default="medium", description="How abnormal the signal is.")  # KEY: default so tools only set it when they know better
