# Incident report
**Root cause:** redis_down (confidence high)
**Summary:** Redis became unreachable, causing resolution and connection errors for cart and checkout requests, which led to high latency and 5xx errors while the rest of the system stayed healthy.

**Alerts fired:** RedisDown since 06:07:52 UTC, ShopHighLatency{path=/users/{user_id}/checkout} since 06:09:52 UTC, ShopHigh5xxRatio since 06:09:52 UTC, ShopHighLatency{path=/users/{user_id}/cart} since 06:09:52 UTC
**Alerts silent:** ShopApiDown, PostgresDown, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- RedisDown alert fired at 06:07:52 UTC and redis_up metric dropped to 0
- High volume of "redis host resolution failure" errors (655x) on /cart and /checkout endpoints
- High 5xx rates and latency spikes on the same endpoints starting shortly after RedisDown
- No recent deploy tag within minutes before the first alert, so no code change caused it

**Silent signals:** ShopApiDown and PostgresDown alerts remained silent because the shop‑api process stayed up and PostgreSQL stayed reachable; the failure was isolated to Redis, so those components showed no outage.
**Deploy:** not deploy-related
**Suggested fix (playbook):** docker compose start redis; carts return from AOF

_Critic: ok · correlator runs: 1 · LLM calls: 3_