# Evaluation results

## Setup
- 12 chaos scenarios: 5 known (playbook written from them), 2 variants (docker pause instead of stop), 5 unseen.
- 50 Locust users, 1 run per scenario (no ± range; LLM answers can differ between runs).
- Agent runs live during the outage, triggered by the first Alertmanager alert.
- Numbers: `python -m eval.metrics` → `eval/metrics.md`; baselines: `python -m eval.baselines` → `eval/baselines.md`.

## Headline (final = v1 + v2 reruns)
| metric | target | result |
|---|---|---|
| top-1 accuracy (scenarios that alerted) | ≥ 70% | **10/11 = 91%** (10/12 = 83% counting slow_query as a miss) |
| time to diagnosis (alert → report) | < 5 min | median 4.6 s, max 7.2 s |
| LLM calls per incident | ≤ 15 | mean 3.45, max 4 |
| cost | ₹0 | ₹0 (Groq + Gemini free tiers) |
| critic correction rate | ≥ 40% | 1 of 2 (postgres_hang); too few cases to call it a rate |
| deploy named correctly | – | 11/11 |

Alert wait (fault → first alert) is detection by Prometheus, not the agent: median 60 s, max 280 s.

## Baselines (same saved findings, offline)
| kind | rules (playbook if-rules) | single LLM call | agent |
|---|---|---|---|
| known | 4/4 | 4/4 | 4/4 |
| variant | 0/2 | 1/2 | 2/2 |
| unseen | 0/5 | 4/5 | 4/5 |
| all | 4/11 = 36% | 9/11 = 82% | 10/11 = 91% |

- Rules are perfect on what the playbook saw and fail on everything new.
- One LLM call on the specialists' findings already gets 82%: most of the work is the specialist agents turning raw logs/metrics into clean findings.
- The agent's extra gain (correlator rules + critic) is postgres_hang only: 1 incident out of 11.
- The single-call baseline still uses specialist findings, so it compares one reasoning call vs correlator + critic + memory, not raw logs in one prompt.

## Failure analysis
### v1: 7/11 = 64%
| scenario | expected | got | root cause of the miss |
|---|---|---|---|
| postgres_hang | postgres_down | db_pool_exhausted | Postgres frozen (docker pause): the exporter's scrapes timed out, so `pg_up` kept its old value 1. Agent saw "Postgres healthy" + QueuePool timeouts → blamed the pool. |
| redis_hang | redis_down | insufficient_evidence | Same stale-metric problem: `redis_up` stayed 1 while logs showed Redis timeouts. Critic saw the contradiction and downgraded a correct first answer (critic made it worse). |
| db_lock | db_lock | db_pool_exhausted | Requests waiting on the table lock held all pool connections → QueuePool errors. The exporter's own stats queries were blocked by the lock, so lock metrics were stale too. |
| redis_oom | redis_out_of_memory | code_exception | Logs unavailable: `\| json` turned every field into a Loki label and the error text contained ids (`HINCRBY cart:510 …`) → >500 series → Loki 400. With no logs the agent guessed. |
| slow_query | slow_query | – | No alert fired at 50 users (p95 stays under the 1 s latency alert). Alert gap, not an agent error. |

### v2 fixes (generic, not per scenario)
1. **Stale metrics:** added `pg_exporter_up` / `redis_exporter_up` signals + correlator rule: "exporter not answering = its metrics are stale; the component is not answering".
2. **Loki:** extract only `path` and `error` from JSON, replace digits in the error with N, filter `duration_ms` lines before parsing numbers, raise Loki's error text instead of failing silently.

### v2: reran the 4 misses + kill_db, redis_down (regression checks)
postgres_hang ✅, redis_hang ✅, redis_oom ✅, kill_db ✅, redis_down ✅, db_lock ❌ (still db_pool_exhausted).

## Known limitations
- **db_lock** still wrong: the only lock evidence comes through the blocked exporter. Fix idea: a direct `pg_stat_activity` check for `wait_event_type = 'Lock'` that doesn't go through the exporter.
- **slow_query** never alerts at 50 users: alert threshold gap.
- **1 run per scenario**, 11 incidents: small sample; a 1-incident change moves accuracy by 9 points.
- **Fixes were found by looking at failures on the same test set**, and v2 reran only 6 of 12 scenarios. The fixes are generic (stale exporters, Loki label blow-up), but a fresh set of scenarios would be the honest next test.
- **Memory:** not yet run with `--memory off`, so the gain from past-incident memory is not measured.
- **Load choice:** a first attempt at 200 users overloaded even a healthy shop (pool 20), so every scenario looked like pool exhaustion; the eval uses 50 users.