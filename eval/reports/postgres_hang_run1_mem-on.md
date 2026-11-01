# Incident report
**Root cause:** db_pool_exhausted (confidence high)
**Summary:** The DB connection pool was exhausted, causing requests to block, latency to hit 30 s, 5xx errors to rise, and the API to appear down.

**Alerts fired:** ShopHigh5xxRatio since 19:45:37 UTC, ShopHighLatency{path=/users/{user_id}/cart} since 19:46:07 UTC, ShopHighLatency{path=/products/{product_id}} since 19:46:22 UTC, ShopHighLatency{path=/products} since 19:46:37 UTC, ShopHighLatency{path=/users/{user_id}/checkout} since 19:47:07 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- High‑severity logs: "DB connection pool exhausted" 260× across all affected paths
- p95 latency spikes to 30 s on every affected endpoint (products, cart, checkout)
- 5xx ratio climbs to ~0.2‑0.47 on those paths
- shop_api_up metric drops from 1 to 0 at 19:41 UTC
- No deploy tag within minutes before the first alert

**Silent signals:** The ShopApiDown alert is silent because the monitoring rule likely requires a longer outage window; the metric already shows the API is down, matching the pool exhaustion that stalls request handling.
**Deploy:** not deploy-related
**Suggested fix (playbook):** git revert <bad commit> + ./deploy.sh "rollback ..."

_Critic: ok · correlator runs: 1 · LLM calls: 3_