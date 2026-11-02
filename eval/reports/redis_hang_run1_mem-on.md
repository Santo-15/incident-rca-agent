# Incident report
**Root cause:** redis_down (confidence high)
**Summary:** Redis became unavailable, causing API requests that depend on it (/cart, /checkout) to time out and return 5xx errors, leading to high latency and error alerts.

**Alerts fired:** ShopHigh5xxRatio since 06:46:37 UTC, ShopHighLatency{path=/users/{user_id}/checkout} since 06:46:52 UTC, ShopHighLatency{path=/users/{user_id}/cart} since 06:46:52 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- high number of redis connection timeout errors on /cart and /checkout endpoints
- redis_exporter_up metric dropped to 0 starting at 06:44:22 UTC
- ShopHigh5xxRatio and ShopHighLatency alerts fire for the same paths that hit Redis
- no recent deploy that could have changed code or config

**Silent signals:** RedisDown alert is silent, but the exporter stopped reporting (redis_exporter_up=0) indicating the exporter (and likely Redis) is unreachable, which explains the missing alert.
**Deploy:** not deploy-related
**Suggested fix (playbook):** docker compose start redis; carts return from AOF

_Critic: weak: redis_down needs one of alerts ['RedisDown'] or abnormal metrics ['redis_up']; none is present · correlator runs: 2 · LLM calls: 3_