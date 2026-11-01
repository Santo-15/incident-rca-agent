# Incident report
**Root cause:** db_pool_exhausted (confidence high)
**Summary:** The API’s database connection pool was exhausted, causing timeouts, massive latency, and 5xx errors across all endpoints.

**Alerts fired:** ShopHigh5xxRatio since 20:41:22 UTC, ShopHighLatency{path=/users/{user_id}/cart} since 20:41:52 UTC, ShopHighLatency{path=/products} since 20:42:07 UTC, ShopHighLatency{path=/users/{user_id}/checkout} since 20:42:22 UTC, ShopHighLatency{path=/products/{product_id}} since 20:42:22 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- High‑severity log entries: "DB connection pool exhausted" 260× on all affected paths
- p95 latency spikes to 30 s on every affected endpoint starting at 20:37 UTC
- 5xx ratio climbs to >30 % on /products and other paths after 20:37 UTC
- ShopApiUp metric drops to 0 (process still running but not serving requests)
- No recent deploy – last tag was 1.9 h before the first alert

**Silent signals:** The ShopApiDown alert stayed silent because the API process was still alive; the failure was due to the connection‑pool deadlock, not a process crash, so the down‑process alert did not trigger.
**Deploy:** not deploy-related
**Suggested fix (playbook):** git revert <bad commit> + ./deploy.sh "rollback ..."

_Critic: ok · correlator runs: 1 · LLM calls: 3_