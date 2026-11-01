# Incident report
**Root cause:** redis_down (confidence high)
**Summary:** Redis became unreachable (DNS resolution failure), causing the shop‑api to return high latency and 5xx errors on cart and checkout endpoints while the API and database remained operational.

**Alerts fired:** RedisDown since 19:23:37 UTC, ShopHigh5xxRatio since 19:25:22 UTC, ShopHighLatency{path=/users/{user_id}/checkout} since 19:25:37 UTC, ShopHighLatency{path=/users/{user_id}/cart} since 19:25:37 UTC
**Alerts silent:** ShopApiDown, PostgresDown, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- RedisDown alert fired at 19:23:37 UTC
- High rate of DNS resolution errors to redis (Error -2 / Error -3) on /cart and /checkout endpoints
- Redis_up metric dropped to 0 starting at 19:23:07 UTC
- Sharp increase in latency and 5xx rates for /users/{user_id}/cart and /checkout coinciding with Redis failure

**Silent signals:** ShopApiDown, PostgresDown, ShopApiHighMemory and ShopApiRestarted remained silent because the API process stayed up and PostgreSQL stayed healthy; only the Redis dependency was unavailable, causing the observed errors.
**Deploy:** not deploy-related
**Suggested fix (playbook):** docker compose start redis; carts return from AOF

_Critic: ok · correlator runs: 1 · LLM calls: 3_