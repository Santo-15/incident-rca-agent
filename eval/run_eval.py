# Eval runner: for each scenario, break the shop, wait for alerts, run the agent DURING the outage, restore, save the result.
# Usage (Ubuntu terminal, repo root, venv on):
#   python -m eval.run_eval                                         -> all 12 scenarios, 1 run each (~8 h)
#   python -m eval.run_eval --runs 3                                -> the real eval (3 runs each)
#   python -m eval.run_eval --only kill_db --cooldown 60 --settle 60   -> quick smoke test
import argparse
import json
import logging
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

GT = json.loads(Path("eval/ground_truth.json").read_text())   # answer key; the agent never reads this folder
RESULTS = Path("eval/results.jsonl")                            # one JSON line per run, appended
REPORTS = Path("eval/reports")                                  # full markdown report per run, for failure analysis (Step 6)
LOCUST_URL = os.getenv("LOCUST_URL", "http://127.0.0.1:8089")
log = logging.getLogger("eval")

live_payload = tracing_config = build_graph = None   # filled in main() AFTER RCA_MEMORY is set (see the KEY line there)


class FallbackCounter(logging.Handler):   # KEY: counts "primary failed" log lines = how often Groq failed and Gemini answered instead
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.count = 0

    def emit(self, record):
        if "primary failed" in record.getMessage():
            self.count += 1


def firing() -> list[str]:   # names of alerts active right now in Alertmanager
    return sorted({a["labels"]["alertname"] for a in live_payload()["alerts"]})


def wait_until(cond, timeout: float, every: float = 10) -> bool:   # poll cond() every 10 s until true or timeout
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(every)
    return False


def wait_healthy(seconds: int):
    if not wait_until(lambda: not firing(), 1800):   # previous outage must be fully over first
        raise SystemExit(f"alerts still firing after 30 min: {firing()}. Fix the stack, then rerun.")
    print(f"  healthy; waiting {seconds}s for a clean baseline")
    time.sleep(seconds)   # KEY: metrics_agent's baseline = 30 min before onset; it must contain no earlier outage


def set_load(users: int):   # KEY: same Locust load for every scenario, via Locust's web API
    httpx.post(f"{LOCUST_URL}/swarm", data={"user_count": users, "spawn_rate": 20}, timeout=10).raise_for_status()


def start_scenario(sid: str, seconds: int) -> subprocess.Popen:
    return subprocess.Popen(["bash", f"chaos/{sid}.sh", str(seconds)], start_new_session=True)   # KEY: own process group, so Ctrl+C on the runner doesn't hit the script; we stop it ourselves


def stop_scenario(proc: subprocess.Popen):
    if proc.poll() is None:   # still running = shop still broken
        os.killpg(proc.pid, signal.SIGINT)   # KEY: like pressing Ctrl+C on the script: its trap runs restore() (start container / rollback deploy)
    try:
        proc.wait(timeout=900)   # restore can take minutes (a rollback deploy rebuilds shop-api)
    except subprocess.TimeoutExpired:
        log.error("restore did not finish in 15 min: check the stack by hand")


def cause_of(h) -> str:   # hypotheses may be dicts or Pydantic objects
    return h["cause"] if isinstance(h, dict) else h.cause


def run_one(sc: dict, run: int, args) -> dict:
    row = {"scenario": sc["id"], "run": run, "kind": sc["kind"], "expected": sc["cause"], "expected_deploy": sc["deploy"],
           "memory": os.environ["RCA_MEMORY"], "started": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    alert_limit = GT["down_seconds"]                                     # max wait for the first alert
    proc = start_scenario(sc["id"], alert_limit + args.settle + 900)     # script's own limit is only a safety net; we stop it as soon as the agent is done
    try:
        t0 = time.time()
        if not wait_until(lambda: bool(firing()), alert_limit):          # KEY: no alert = nothing to diagnose; record it, don't run the agent
            row["error"] = "no alert fired"
            return row
        row["alert_wait_s"] = round(time.time() - t0)
        time.sleep(args.settle)                                          # let the other alerts fire too, so "silent" really means silent
        counter = FallbackCounter()
        logging.getLogger().addHandler(counter)
        t1 = time.time()
        try:
            out = build_graph().invoke({"payload": live_payload()}, config=tracing_config())   # KEY: same call as python -m agent.run, during the outage
        finally:
            logging.getLogger().removeHandler(counter)
        row["agent_s"] = round(time.time() - t1, 1)
        h = out["hypothesis"]
        calls = out.get("llm_calls", 0)
        row.update({
            "got": h["cause"],
            "correct": h["cause"] == sc["cause"],                        # KEY: top-1 accuracy = exact label match with the answer key
            "confidence": h["confidence"],
            "deploy_tag": h.get("deploy_tag"),
            "deploy_correct": bool(h.get("deploy_tag")) == sc["deploy"],  # named a deploy only when a deploy caused it
            "alerts": out.get("alerts", []),
            "silent": out.get("silent", []),
            "llm_calls": sum(calls) if isinstance(calls, list) else calls,
            "hypotheses": [cause_of(x) for x in out.get("hypotheses", [])],   # KEY: every correlator answer in order; first vs last = did the critic fix it
            "loops": out.get("loop_count"),
            "critique": out.get("critique"),
            "primary_failures": counter.count,
            "memory_hits": [(m["scenario"], m["distance"]) for m in out.get("similar", [])],
            "findings": [f.model_dump() if hasattr(f, "model_dump") else f for f in out.get("findings", [])],
        })
        (REPORTS / f"{sc['id']}_run{run}_mem-{row['memory']}.md").write_text(out["report"])
    except Exception as exc:   # one broken run must not kill an 8-hour eval
        row["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        stop_scenario(proc)    # KEY: always restore, even on error or Ctrl+C
        if os.getenv("LANGFUSE_PUBLIC_KEY"):
            from langfuse import get_client
            get_client().flush()
    return row


def main():
    global live_payload, tracing_config, build_graph
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", help="scenario ids (default: all in ground_truth.json)")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--memory", choices=["on", "off"], default="on")
    p.add_argument("--settle", type=int, default=120, help="seconds after the first alert before running the agent")
    p.add_argument("--cooldown", type=int, default=600, help="healthy seconds before each scenario (= metrics_agent BASELINE_S)")
    args = p.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    os.environ["RCA_MEMORY"] = args.memory   # KEY: set BEFORE importing the agent, in case a module reads it at import time (memory on vs off ablation)
    from agent.run import live_payload, tracing_config   # same alert fetch + Langfuse config as a manual run
    from agent.graph import build_graph

    scenarios = [s for s in GT["scenarios"] if not args.only or s["id"] in args.only]
    missing = set(args.only or []) - {s["id"] for s in scenarios}
    if missing:
        raise SystemExit(f"unknown scenario ids: {sorted(missing)}")
    REPORTS.mkdir(parents=True, exist_ok=True)
    set_load(GT["locust_users"])
    print(f"Locust set to {GT['locust_users']} users; {len(scenarios)} scenarios x {args.runs} runs, memory {args.memory}")

    for run in range(1, args.runs + 1):
        for sc in scenarios:
            print(f"[{datetime.now(ZoneInfo('Asia/Kolkata')):%H:%M}] {sc['id']} run {run}")
            wait_healthy(args.cooldown)
            row = run_one(sc, run, args)
            with RESULTS.open("a") as f:
                f.write(json.dumps(row, default=str) + "\n")   # append right away, so a crash at hour 6 keeps hours 1-5
            verdict = row.get("error") or f"got {row['got']} ({'OK' if row['correct'] else 'WRONG'}), agent {row['agent_s']}s, {row['llm_calls']} LLM calls"
            print(f"  expected {sc['cause']}: {verdict}")


if __name__ == "__main__":
    main()