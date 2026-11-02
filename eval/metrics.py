"""Phase 11 S4: eval metrics computed OFFLINE from saved results files (no outages, no LLM calls)."""
import json
import statistics
from pathlib import Path

EVAL = Path(__file__).parent
V1 = EVAL / "results_v1.jsonl"
V2 = EVAL / "results.jsonl" 
OUT = EVAL / "metrics.md"
KINDS = ("known", "variant", "unseen") 

def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]   # skip blank lines


def merge(*files: Path) -> list[dict]:
    rows = {}
    for f in files:                                           # KEY: later file wins → v2 row replaces v1 row
        for r in load(f):
            rows[(r["scenario"], r["run"])] = r               # KEY: key = (scenario, run), so --runs N still works
    return list(rows.values())


def pct(a: int, b: int) -> str:
    return f"{a}/{b} = {100 * a / b:.0f}%" if b else "n/a"     # "10/11 = 91%"; n/a avoids divide-by-zero


def ran(rows):                                                # rows where the agent actually gave an answer
    return [r for r in rows if r.get("got") is not None]      # KEY: "no alert fired" or a crash → got is missing


def summarise(title: str, rows: list[dict]) -> str:
    done = ran(rows)
    ok = sum(r["correct"] for r in done)
    out = [f"## {title}", ""]

    # 1. top-1 accuracy, two honest denominators
    out.append(f"- top-1, scenarios that alerted: {pct(ok, len(done))}")
    out.append(f"- top-1, all scenarios (no alert / crash = miss): {pct(ok, len(rows))}")   # KEY: slow_query counts as a miss here
    for k in KINDS:                                           # KEY: known vs variant vs unseen = does it generalise?
        k_rows = [r for r in rows if r["kind"] == k]
        k_ok = sum(bool(r.get("correct")) for r in k_rows)
        out.append(f"  - {k}: {pct(k_ok, len(k_rows))} (alerted: {len(ran(k_rows))})")

    # 2. time: agent time is ours; alert wait is Prometheus/Alertmanager detection, not the agent
    t = [r["agent_s"] for r in done]
    w = [r["alert_wait_s"] for r in done]
    out.append(f"- agent time (alert → report): median {statistics.median(t):.1f} s, max {max(t):.1f} s")
    out.append(f"- alert wait (fault → first alert): median {statistics.median(w):.0f} s, max {max(w):.0f} s")

    # 3. LLM calls per incident (target ≤ 15)
    c = [r["llm_calls"] for r in done]
    out.append(f"- LLM calls per incident: mean {sum(c) / len(c):.2f}, max {max(c)}")

    # 4. critic correction: first correlator answer vs final answer
    first_wrong = [r for r in done if r["hypotheses"][0] != r["expected"]]                       # KEY: correlator's 1st try was wrong
    fixed = [r["scenario"] for r in first_wrong if r["correct"]]                                 # KEY: critic loop turned it right
    broke = [r["scenario"] for r in done if r["hypotheses"][0] == r["expected"] and not r["correct"]]   # KEY: critic turned right → wrong
    out.append(f"- critic correction rate (first answer wrong → final right): {pct(len(fixed), len(first_wrong))} {fixed}")
    out.append(f"- critic made it worse (first right → final wrong): {len(broke)} {broke}")

    # 5. deploy attribution + hidden fallbacks
    d_ok = sum(r["deploy_correct"] for r in done)
    out.append(f"- deploy named correctly (named only when a deploy caused it): {pct(d_ok, len(done))}")
    out.append(f"- primary LLM failures (Groq → Gemini fallback): {sum(r['primary_failures'] for r in done)}")   # KEY: a fallback must never be hidden

    # 6. per-scenario table
    out += ["", "| scenario | kind | expected | got | correct | hypotheses | agent s | LLM calls |",
            "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (KINDS.index(r["kind"]), r["scenario"])):
        if r.get("got") is None:                              # no answer: show why
            out.append(f"| {r['scenario']} | {r['kind']} | {r['expected']} | – | {r.get('error')} | – | – | – |")
        else:
            out.append(f"| {r['scenario']} | {r['kind']} | {r['expected']} | {r['got']} | {'✅' if r['correct'] else '❌'} "
                       f"| {' → '.join(r['hypotheses'])} | {r['agent_s']} | {r['llm_calls']} |")
    return "\n".join(out) + "\n"


def main():
    v1 = load(V1)
    final = merge(V1, V2)                                     # KEY: final = v1 with the 6 rerun scenarios replaced by v2
    text = ("# Eval metrics (50 Locust users, 1 run per scenario)\n\n"
            "v2 reran 6 scenarios (4 v1 misses + kill_db, redis_down as regression checks); the other 6 are v1 rows.\n\n"
            + summarise("v1 (before fixes)", v1) + "\n"
            + summarise("final (v1 + v2 reruns)", final))
    OUT.write_text(text, encoding="utf-8")                    # utf-8 so ✅/❌/→ save fine
    print(text)


if __name__ == "__main__":
    main()