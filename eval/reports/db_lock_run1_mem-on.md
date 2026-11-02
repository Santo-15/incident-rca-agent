# Incident report
**Root cause:** db_pool_exhausted (confidence medium)
**Summary:** The API’s database connection pool was exhausted, causing requests to block, latency to rise to 30 s, 5xx errors to increase, and the API health check to report down.

**Alerts fired:** ShopHigh5xxRatio since 07:08:07 UTC, ShopHighLatency{path=/users/{user_id}/cart} since 07:08:52 UTC, ShopHighLatency{path=/products} since 07:09:07 UTC, ShopHighLatency{path=/products/{product_id}} since 07:09:07 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- High‑frequency logs: “DB connection pool exhausted” (240×) on all affected paths
- p95 latency spikes to 30 s for /products, /products/{id}, /users/{id}/cart, /users/{id}/checkout starting at 07:04
- ShopHigh5xxRatio and multiple ShopHighLatency alerts fire shortly after the latency spikes
- shop_api_up metric drops to 0 at 07:03:52 while pg_up remains 1, indicating the API health check fails but the DB is still reachable

**Silent signals:** ShopApiDown did not fire because the alert is based on explicit downtime detection, while the API process was still running but its workers were blocked by a exhausted DB pool, causing the health‑check metric to go to 0; PostgresDown stayed silent because PostgreSQL remained reachable (pg_up=1) even though connections could not be obtained.
**Deploy:** not deploy-related
**Suggested fix (playbook):** git revert <bad commit> + ./deploy.sh "rollback ..."

_Critic: ok (rule checks only, loop limit reached) · correlator runs: 2 · LLM calls: 4_