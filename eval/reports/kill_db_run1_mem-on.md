# Incident report
**Root cause:** postgres_down (confidence high)
**Summary:** Postgres became unreachable (DNS resolution failures and connection refusals), causing the pg_up metric to go down and a surge of 5xx errors on all database‑backed endpoints.

**Alerts fired:** PostgresDown since 18:27:07 UTC, ShopHigh5xxRatio since 18:28:22 UTC
**Alerts silent:** ShopApiDown, RedisDown, ShopHighLatency, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- PostgresDown alert fired at 18:27:07 UTC
- pg_up metric dropped to 0 starting at 18:26:37 UTC
- High‑frequency OperationalError logs: failed to resolve host 'postgres' and connection refused
- 5xx_rate_by_path spikes on all DB‑dependent endpoints immediately after the alerts

**Silent signals:** ShopApiDown and RedisDown remained silent because the shop‑api process stayed alive and Redis stayed reachable; the failure was isolated to the Postgres service.
**Deploy:** not deploy-related
**Suggested fix (playbook):** docker compose start postgres; shop-api reconnects (pool_pre_ping)

_Critic: ok · correlator runs: 1 · LLM calls: 4_