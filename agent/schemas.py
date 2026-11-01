from typing import Literal
from pydantic import BaseModel, Field

Cause = Literal[
    "db_pool_exhausted",
    "postgres_down",
    "redis_down",
    "memory_leak",
    "slow_query",
    "shop_api_down",          # NEW
    "db_lock",                # NEW
    "redis_out_of_memory",    # NEW
    "wrong_service_address",  # NEW
    "code_exception",         # NEW
    "insufficient_evidence",
]

CAUSE_HELP = (  # KEY: one line per label so the LLM knows where each one stops; three causes come from bad deploys, so the names alone are ambiguous
    "db_pool_exhausted = shop-api's DB connection pool is configured too small for the load; "
    "postgres_down = Postgres is dead or not answering; "
    "redis_down = Redis is dead or not answering; "
    "memory_leak = shop-api memory grows until it is killed and restarts; "
    "slow_query = a query became slow (e.g. missing index) while everything stays up; "
    "shop_api_down = the shop-api process itself is gone; "
    "db_lock = a long transaction holds a table lock and other queries wait behind it; "
    "redis_out_of_memory = Redis is up but refuses writes because it hit its memory limit; "
    "wrong_service_address = a deploy points shop-api at the wrong host or port of a healthy dependency; "
    "code_exception = a deploy added code that raises an error on an endpoint; "
    "insufficient_evidence = the evidence does not clearly point to one cause."
    " other = a clear cause that is none of the above; name it in the summary."
)

class CorrelatorAnswer(BaseModel):
    cause: Cause = Field(description=f"The single root cause, chosen from the allowed values. {CAUSE_HELP}")  # CHANGED  label meanings travel inside the JSON schema
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


class FindingDraft(BaseModel):  # what an LLM agent (logs, diff) returns; the node adds the source itself
    signal: str = Field(description="Short name of the problem, e.g. 'redis connection refused' or 'DB_POOL_SIZE lowered'.")
    detail: str = Field(description="One line with the exact counts, paths, files and old -> new values from the input.")
    severity: Literal["low", "medium", "high"] = Field(description="How likely this alone breaks the shop.")


class FindingList(BaseModel):
    findings: list[FindingDraft] = Field(description="1 to 5 findings, most important first.")


class CriticVerdict(BaseModel):
    verdict: Literal["ok", "weak"] = Field(description="ok if the evidence supports the cause and no trap applies, else weak.")
    problems: list[str] = Field(description="Concrete problems, each phrased as what the correlator must re-check. Empty if ok.")
