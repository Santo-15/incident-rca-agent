"""Phase 11 S5: two baselines vs the agent, run OFFLINE on the findings saved in the results files (no new outages).
rules  = plain if-rules written from docs/playbook.md (covers the 5 known incidents only)
single = ONE LLM call on the same evidence: no correlator rules, no memory, no critic loop
agent  = the agent's saved answer (`got`)"""
import argparse                                      # --refresh flag
import json                                          # cache file is JSON lines
import re                                            # pull numbers out of finding text
from pathlib import Path                             # file paths

from eval.metrics import KINDS, V1, V2, merge, pct   # KEY: same merged rows as S4, so all three are scored on identical incidents

EVAL = Path(__file__).parent
CACHE = EVAL / "baselines.jsonl"                     # single-call answers saved here, so a rerun costs 0 LLM calls
OUT = EVAL / "baselines.md"                          # comparison table for the README


# ---------- rule-based baseline ----------
def _metric(findings: list[dict], name: str) -> dict | None:
    return next((f for f in findings if f["source"] == "metrics" and f["signal"] == name), None)   # one metric finding, e.g. pg_up


def _z(f: dict | None) -> float:
    m = re.search(r"z=([+-]?[\d.]+)", f["detail"]) if f else None   # detail looks like "baseline 1 -> peak 0 (z=-10.0), ..."
    return float(m.group(1)) if m else 0.0                         # no finding = nothing abnormal = 0


def _deploy_minutes(findings: list[dict]) -> float | None:
    mins = [float(m.group(1)) for f in findings if f["source"] == "deploys"
            for m in [re.search(r"([\d.]+) min before the first alert", f["detail"])] if m]
    return min(mins) if mins else None               # newest deploy before the alert; None = "no recent deploy"


def rules(findings: list[dict]) -> str:              # KEY: an engineer's playbook as code; order = most specific rule first
    logs = " ".join(f["detail"] for f in findings if f["source"] == "logs")    # raw grouped error text
    diff = " ".join(f["detail"] for f in findings if f["source"] == "diff")    # what the deploy changed
    mins = _deploy_minutes(findings)
    recent_deploy = mins is not None and mins <= 5   # playbook: a deploy matters only if it is right before the alert

    if recent_deploy and "DB_POOL_SIZE" in diff:     # bad_pool_config row of the decision table
        return "db_pool_exhausted"
    if _z(_metric(findings, "pg_up")) < 0:           # kill_db row: postgres DOWN
        return "postgres_down"
    if _z(_metric(findings, "redis_up")) < 0:        # redis_down row: redis DOWN
        return "redis_down"
    if "QueuePool limit" in logs:                    # bad_pool_config log line, without the deploy
        return "db_pool_exhausted"
    if _z(_metric(findings, "rss_mib")) > 3 and _z(_metric(findings, "restarts")) > 0:   # memory_leak row: RSS up + restarts up
        return "memory_leak"
    p95 = [f for f in findings if f["source"] == "metrics" and f["signal"].startswith("p95_by_path") and _z(f) > 3]
    if p95 and all("path=/products}" in f["signal"] for f in p95) and "zero 'request failed'" in logs:   # slow_query row
        return "slow_query"
    return "other"                                   # KEY: rules have no answer for anything the playbook never saw


# ---------- single-call LLM baseline ----------
SINGLE_SYSTEM = ("You are an on-call engineer for a small online shop (FastAPI shop-api, Postgres, Redis, "
                 "deployed with git tags). From the incident evidence, pick the single root cause.")   # KEY: no correlator rules, no traps list
SINGLE_HUMAN = ("Alerts fired: {alerts}\nAlerts silent: {silent}\nLogs (grouped errors): {logs}\n"
                "Metrics: {metrics}\nDeploys near the first alert (and what their diff changed): {deploys}")


def single_call(row: dict) -> str:
    from langchain_core.prompts import ChatPromptTemplate   # imported here so the rules part runs without the agent's packages
    from agent.llm import get_llm
    from agent.nodes.correlator import evidence              # KEY: exact same evidence text the agent's correlator saw
    from agent.schemas import CorrelatorAnswer, Finding

    state = {"alerts": row["alerts"], "silent": row["silent"], "findings": [Finding(**f) for f in row["findings"]]}
    prompt = ChatPromptTemplate.from_messages([("system", SINGLE_SYSTEM), ("human", SINGLE_HUMAN)])
    try:
        ans = get_llm("correlator", schema=CorrelatorAnswer).invoke(prompt.invoke(evidence(state)))   # KEY: one call, same model as the agent
        return ans.cause
    except Exception as exc:                         # both LLMs failed: count as a miss, don't crash
        return f"error: {type(exc).__name__}"


def load_cache() -> dict:
    if not CACHE.exists():
        return {}
    rows = [json.loads(line) for line in CACHE.read_text().splitlines() if line.strip()]
    return {(r["scenario"], r["started"]): r["single"] for r in rows}   # KEY: key includes `started`, so the v2 rerun is a new entry


# ---------- compare ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and call the LLM again")
    args = ap.parse_args()

    rows = [r for r in merge(V1, V2) if r.get("got") is not None]   # only incidents the agent diagnosed (slow_query never alerted)
    cache = {} if args.refresh else load_cache()
    with CACHE.open("a", encoding="utf-8") as fh:
        for r in rows:
            r["rules"] = rules(r["findings"])
            key = (r["scenario"], r["started"])
            if key not in cache:                     # LLM only for rows not answered before
                cache[key] = single_call(r)
                fh.write(json.dumps({"scenario": r["scenario"], "started": r["started"], "single": cache[key]}) + "\n")
            r["single"] = cache[key]

    methods = {"rules": "rules", "single": "single", "agent": "got"}   # column name -> field holding the answer
    out = ["# Baselines vs agent (offline, same saved findings, 50 users, 1 run each)", "",
           "| kind | rules | single LLM call | agent |", "|---|---|---|---|"]
    for k in (*KINDS, "all"):                        # KEY: the story is per kind: rules should win on known, agent on variant/unseen
        sub = rows if k == "all" else [r for r in rows if r["kind"] == k]
        cells = [pct(sum(r[f] == r["expected"] for r in sub), len(sub)) for f in methods.values()]
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    out += ["", "| scenario | kind | expected | rules | single | agent |", "|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (KINDS.index(r["kind"]), r["scenario"])):
        marks = [f"{r[f]} {'✅' if r[f] == r['expected'] else '❌'}" for f in methods.values()]
        out.append(f"| {r['scenario']} | {r['kind']} | {r['expected']} | " + " | ".join(marks) + " |")
    text = "\n".join(out) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()