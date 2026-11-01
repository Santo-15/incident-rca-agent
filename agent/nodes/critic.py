# critic: free rule checks first, then an LLM check. "weak" sends the hypothesis back to the correlator.
import json
import logging
from agent.llm import get_llm
from agent.nodes.correlator import evidence
from agent.prompts.critic import CRITIC_PROMPT
from agent.schemas import CriticVerdict
from agent.state import MAX_LOOPS, RCAState

logger = logging.getLogger("agent.critic")

REQUIRED = {   # KEY: cause -> (alerts, metric signals); at least one must be present or the cause has no support
    "postgres_down": ({"PostgresDown"}, {"pg_up"}),
    "redis_down": ({"RedisDown"}, {"redis_up"}),
    "memory_leak": ({"ShopApiHighMemory", "ShopApiRestarted"}, {"rss_mib", "restarts"}),
    "slow_query": ({"ShopHighLatency"}, {"p95_by_path", "seq_tup_read_products"}),
    "db_pool_exhausted": ({"ShopHighLatency", "ShopHigh5xxRatio"}, {"p95_by_path", "pg_connections_by_state", "5xx_rate_by_path"}),
}


def rule_problems(h: dict, state: RCAState) -> list[str]:
    problems = []
    fired = {a.split(" ")[0].split("{")[0] for a in state.get("alerts", [])}
    abnormal = {f.signal.split("{")[0] for f in state.get("findings", [])
                if f.source == "metrics" and f.signal not in ("normal signals", "metrics unavailable")}
    if h["cause"] in REQUIRED:
        alerts, signals = REQUIRED[h["cause"]]
        if not (fired & alerts or abnormal & signals):
            problems.append(f"{h['cause']} needs one of alerts {sorted(alerts)} or abnormal metrics {sorted(signals)}; none is present")
    tags = {d["tag"] for d in state.get("deploys", [])}
    if h.get("deploy_tag") and h["deploy_tag"] not in tags:   # KEY: catches an invented or too-old deploy tag
        problems.append(f"deploy_tag {h['deploy_tag']} is not a deploy near the first alert (near: {sorted(tags) or 'none'})")
    if h["confidence"] == "low" and h["cause"] != "insufficient_evidence":
        problems.append("confidence is low: either find the signal that confirms the cause or answer insufficient_evidence")
    return problems


def critic(state: RCAState) -> dict:
    h = state["hypothesis"]
    problems = rule_problems(h, state)
    if problems:   # KEY: rules failed -> no LLM call needed
        return {"critique": "weak: " + "; ".join(problems)}
    if state.get("loop_count", 0) >= MAX_LOOPS:   # KEY: last allowed pass; an LLM verdict couldn't change anything, save the call
        return {"critique": "ok (rule checks only, loop limit reached)"}
    try:
        v = get_llm("critic", schema=CriticVerdict).invoke(
            CRITIC_PROMPT.invoke(evidence(state) | {"hypothesis": json.dumps(h)}))
        critique = "ok" if v.verdict == "ok" or not v.problems else "weak: " + "; ".join(v.problems)
    except Exception as exc:
        logger.warning("critic LLM failed, accepting hypothesis: %s", exc)
        critique = "ok (critic LLM unavailable, rule checks passed)"
    return {"critique": critique, "llm_calls": 1}
