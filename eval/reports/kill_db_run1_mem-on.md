# Incident report
**Root cause:** postgres_down (confidence high)
**Summary:** PostgreSQL became unreachable (DNS resolution and connection failures), causing the shop‑api to time out and return 5xx errors on all database‑backed paths.

**Alerts fired:** PostgresDown since 05:50:37 UTC, ShopHigh5xxRatio since 05:52:07 UTC
**Alerts silent:** ShopApiDown, RedisDown, ShopHighLatency, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- PostgresDown alert fired at 05:50:37 UTC
- pg_up metric dropped to 0 starting at 05:50:07 UTC
- Hundreds of OperationalError logs: failed to resolve host 'postgres' and connection refused
- Sharp rise in p95 latency and 5xx rates on all DB‑dependent endpoints beginning at 05:50:07 UTC

**Silent signals:** ShopApiDown stayed silent because the API process remained alive; it could not serve requests but did not crash, matching a downstream database outage.
**Deploy:** not deploy-related
**Suggested fix (playbook):** docker compose start postgres; shop-api reconnects (pool_pre_ping)

_Critic: ok · correlator runs: 1 · LLM calls: 3_