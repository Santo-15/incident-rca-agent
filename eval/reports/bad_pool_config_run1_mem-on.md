# Incident report
**Root cause:** db_pool_exhausted (confidence high)
**Summary:** A deploy reduced the DB connection pool to a single slot, exhausting it and blocking all API workers, causing the service to appear down until it was restarted.

**Alerts fired:** ShopApiRestarted since 18:00:37 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopHigh5xxRatio, ShopHighLatency, ShopApiHighMemory

**Evidence**
- Deploy at 18:00:06 lowered DB_POOL_SIZE from 20 to 1 (few minutes before first alert)
- shop_api_up metric dropped from 1 to 0 at 18:00:22
- ShopApiRestarted alert fired at 18:00:37 (31 s after deploy)
- No error logs or 5xx responses during the incident window
- pg_connections_by_state idle dropped dramatically, indicating no active DB usage

**Silent signals:** The absence of error logs, 5xx rates and latency spikes fits a pool exhaustion where workers are blocked waiting for a DB connection rather than crashing or raising exceptions.
**Deploy:** deploy-20261101-180006
**Suggested fix (playbook):** git revert <bad commit> + ./deploy.sh "rollback ..."

_Critic: ok (rule checks only, loop limit reached) · correlator runs: 2 · LLM calls: 4_