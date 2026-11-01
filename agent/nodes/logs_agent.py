# logs_agent: grouped + normalised errors from the log backend -> findings. Raw log lines never reach the LLM.
import logging
import re
from collections import defaultdict
from agent.llm import get_llm
from agent.prompts.logs import LOGS_PROMPT
from agent.schemas import Finding, FindingList
from agent.state import RCAState
from agent.tools.base import get_logs

logger = logging.getLogger("agent.logs")
MAX_GROUPS = 10
NOISE = [   # KEY: strip parts that differ per request so the same error groups together; small numbers (pool size 1, timeout 30.00) stay
    (re.compile(r"\s*\(Background on this error at:[^)]*\)"), ""),
    (re.compile(r"0x[0-9a-fA-F]+"), "0x?"),
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "<uuid>"),
    (re.compile(r"\d{5,}"), "<n>"),
]


def normalise(error: str) -> str:
    lines = error.strip().splitlines()
    msg = lines[0] if lines else "unknown"   # KEY: first line only; the stack trace (~13 KB) is dropped
    for pattern, repl in NOISE:
        msg = pattern.sub(repl, msg)
    return msg[:200]


def group_errors(rows: list[tuple[str, str, int]]) -> list[tuple[str, int, set[str]]]:
    groups = defaultdict(lambda: [0, set()])
    for path, error, count in rows:
        g = groups[normalise(error)]
        g[0] += count
        g[1].add(path)
    ranked = sorted(groups.items(), key=lambda kv: -kv[1][0])[:MAX_GROUPS]
    return [(err, n, paths) for err, (n, paths) in ranked]


def logs_agent(state: RCAState) -> dict:
    start, end = state["window_start"], state["window_end"]
    try:
        logs = get_logs()
        groups = group_errors(logs.error_groups(start, end))
        slow = logs.slow_requests(start, end)
    except Exception as exc:   # KEY: a broken tool becomes a finding, not a crashed graph
        logger.warning("logs unavailable: %s", exc)
        return {"findings": [Finding(source="logs", signal="logs unavailable", detail=f"log backend error: {exc}", severity="low")]}

    findings = []
    if slow:
        findings.append(Finding(source="logs", signal="slow requests (>1 s)",
                                detail=", ".join(f"{p} {n}x" for p, n in slow[:5]), severity="medium"))
    if not groups:   # KEY: no LLM call when there is nothing to summarise; "no errors" is itself evidence
        findings.append(Finding(source="logs", signal="no error logs",
                                detail="zero 'request failed' lines in the incident window", severity="low"))
        return {"findings": findings}

    text = "\n".join(f"{n}x on {', '.join(sorted(paths)[:4])}: {err}" for err, n, paths in groups)
    try:
        drafts = get_llm("logs", schema=FindingList).invoke(LOGS_PROMPT.invoke({"groups": text})).findings[:5]
        findings += [Finding(source="logs", **d.model_dump()) for d in drafts]
    except Exception as exc:   # both LLMs failed: fall back to one finding per group
        logger.warning("logs LLM failed, using raw groups: %s", exc)
        findings += [Finding(source="logs", signal=err[:60], detail=f"{n}x on {', '.join(sorted(paths)[:4])}: {err}",
                             severity="high" if n >= 50 else "medium") for err, n, paths in groups[:5]]
    return {"findings": findings, "llm_calls": 1}
