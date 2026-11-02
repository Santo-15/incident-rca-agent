# Incident report
**Root cause:** postgres_down (confidence medium)
**Summary:** PostgreSQL became unreachable, causing the API’s connection pool to exhaust, which led to timeouts, high latency and 5xx errors across product and checkout endpoints.

**Alerts fired:** ShopHigh5xxRatio since 06:29:22 UTC, ShopHighLatency{path=/products/{product_id}} since 06:30:07 UTC, ShopHighLatency{path=/users/{user_id}/checkout} since 06:30:22 UTC, ShopHighLatency{path=/products} since 06:30:22 UTC, ShopHighLatency{path=/users/{user_id}/cart} since 06:30:22 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- pg_exporter_up metric dropped to 0 at 06:25:07 indicating the exporter could not reach Postgres
- shop_api_up metric also fell to 0 at the same time, showing the API lost its DB connection and could not report health
- Logs contain many "DB connection pool exhausted" errors with timeout messages on all DB‑dependent paths
- High latency and 5xx alerts fire a few minutes after the exporter/API metrics went down

**Silent signals:** The PostgresDown alert stayed silent because the monitoring rule only fires on the postgres_up metric, not on the exporter; the exporter outage is the evidence of the DB being unreachable.
**Deploy:** not deploy-related
**Suggested fix (playbook):** docker compose start postgres; shop-api reconnects (pool_pre_ping)

_Critic: weak: postgres_down needs one of alerts ['PostgresDown'] or abnormal metrics ['pg_up']; none is present · correlator runs: 2 · LLM calls: 4_