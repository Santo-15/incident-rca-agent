# Incident: Redis crashed (redis_down)

## Timeline (IST, 27 Oct 2026)
- ~17:07:20 Redis container killed (SIGKILL); Locust at 50 users
- 17:07:52 RedisDown fires (redis_up = 0)
- 17:09:37 ShopHigh5xxRatio fires (5xx share ~25%)
- 17:09:52 ShopHighLatency fires on /users/{user_id}/cart and /users/{user_id}/checkout (p95 ~4-5 s)
- 17:11 deploys checked: newest tag deploy-20261027-051827 at 10:48, over 6 hours earlier
- ~17:16:30 Redis started again; brief "BusyLoadingError: Redis is loading the dataset in memory" while it replayed the AOF file
- after 17:16:30 errors stop, without restarting shop-api; Redis keys 199 (201 before)

## Root cause
The Redis container crashed. Cart and checkout read and write carts in Redis, so every one of those requests failed with 500 because the host `redis` no longer existed on the Docker network. Browsing (/products, /products/{id}) does not use Redis and kept working.

## Evidence
- Dashboard: redis DOWN while shop-api and postgres stayed UP
- 5xx per path (sum by (path) of http_requests_total with status 5xx): only cart and checkout; Locust: /products 0 failures
- Logs: mostly "ConnectionError: Error -2 connecting to redis:6379. Name or service not known"; a few "Error 111 Connection refused", "Error -5" and "Timeout connecting to server" around the kill
- Cart/checkout p95 ~4 s, not the 2 s connect timeout: the DNS lookup is not covered by that timeout, and the Redis client most likely retries
- Side effect (cascading failure risk): cart/checkout first take a Postgres connection, then wait ~4 s on Redis while holding it. "Idle in transaction" connections rose to 10-17 of the pool's 20. A bit more traffic would have drained the pool and broken /products too
- No deploy near the alerts, so it was infra, not code
- PostgresDown, ShopApiDown, ShopApiRestarted, ShopApiHighMemory did NOT fire: Postgres and shop-api were healthy, nothing restarted
- ShopHighLatency fired only on cart and checkout, a side effect of waiting on dead Redis, not a slow query

## Time to diagnosis
~4 min (RedisDown 17:07:52 -> paths and logs confirmed, deploy ruled out ~17:11). The "Is it up?" panel pointed at Redis immediately.

## Fix
Start Redis again (`docker compose start redis`). Carts came back from the AOF file; shop-api reconnected by itself.

## Follow-up
- Shorter Redis timeouts, or a fallback (e.g. an "add to cart unavailable" response), so a Redis outage can't hold Postgres connections and spread to other paths.