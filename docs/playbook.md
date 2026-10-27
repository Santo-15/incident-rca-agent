# Ravi's playbook: shop incidents

Use this when an alert fires. Go top to bottom; most incidents are clear by step 3.
All times IST. Alertmanager shows UTC (add 5:30).

## Links
- Alerts: http://127.0.0.1:9093
- Dashboard: http://127.0.0.1:3000/d/shop-overview
- Logs: http://127.0.0.1:3000/explore (Loki, Code mode)
- Metrics: http://127.0.0.1:9090 (Query)
- Load: http://127.0.0.1:8089

## Order of checks

### 1. Alerts: what fired, when, and what is silent
Write down every firing alert with its start time. Silent alerts are evidence too.

### 2. Is it up?
Dashboard "Is it up?" panel: shop-api, postgres, redis.

### 3. Deploys: was there one just before the first alert?
```bash
TZ=Asia/Kolkata git tag -l "deploy-*" --sort=-creatordate --format='%(refname:short)  %(creatordate:format-local:%Y-%m-%d %H:%M IST)' | head -3
git diff <previous-tag> <newest-tag> --stat
git diff <previous-tag> <newest-tag>
```
Tag a few minutes before the alert -> suspect the code/config change in the diff.
No tag near the alert -> infra (a dependency, data, the database itself).

### 4. Which paths are hurt
Dashboard: p95 by path, 5xx ratio. 5xx split by path:
```
sum by (path) (rate(http_requests_total{job="shop-api", status=~"5.."}[1m]))
```

### 5. Logs
Top errors:
```
sum by (error) (count_over_time({service="shop-api"} |= "request failed" | json [10m]))
```
Slow requests (when there are no errors):
```
{service="shop-api"} | json | duration_ms > 1000
```

### 6. Deeper metrics (only if still unclear)
- Memory: dashboard RSS panel; restarts: `docker inspect --format 'Restarts={{.RestartCount}} Started={{.State.StartedAt}}' incident-rca-agent-shop-api-1`
- Full-table scans on products: `rate(pg_stat_user_tables_seq_tup_read{relname="products"}[1m])`
- Query plan: `EXPLAIN ANALYZE SELECT id, name, price FROM products ORDER BY price LIMIT 10;` in psql (`docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'`)

## Decision table (from real runs)

| Scenario | Fires | Silent | Deploy? | Paths hurt | Logs | Key extra signal |
|---|---|---|---|---|---|---|
| bad_pool_config | ShopHighLatency, ShopHigh5xxRatio, later ShopApiDown | PostgresDown, RedisDown | yes, diff changes DB_POOL_SIZE | all DB paths (~92% 5xx) | `QueuePool limit of size 1 ... timeout 30.00` | p95 flat at 30 s = pool timeout; Postgres connections stuck at pool size |
| kill_db | PostgresDown, ShopHigh5xxRatio | ShopApiDown, RedisDown | no | all DB paths (~90% 5xx) | `failed to resolve host 'postgres'` | postgres DOWN on dashboard; p95 up from DNS timeouts |
| memory_leak | ShopApiHighMemory, ShopApiRestarted | 5xx, latency, ShopApiDown | yes, diff adds an unbounded list | none (requests cut off during each ~3 s restart) | nothing | RSS sawtooth up to the 256 MiB limit; RestartCount goes up |
| slow_query | ShopHighLatency on /products only (needs load; at low load nothing fires) | 5xx, all Down alerts | no | /products (sorted requests) | no errors; only high `duration_ms` on /products | seq_tup_read on products jumps from 0 to millions/s; EXPLAIN shows Seq Scan |
| redis_down | RedisDown, ShopHigh5xxRatio, ShopHighLatency on cart/checkout | PostgresDown, ShopApiDown | no | cart, checkout only (~25% 5xx) | `Error -2 connecting to redis:6379` | /products 0 failures; Postgres "idle in transaction" rises |

## Don't be fooled
- **ShopApiDown can lie.** In bad_pool_config the process was alive, but all worker threads waited on the pool, so /metrics timed out.
- **ShopApiRestarted can be a deploy.** It only means a crash when no deploy tag is near it.
- **Latency can be a side effect.** DNS timeouts (kill_db) and waiting on dead Redis (redis_down) raise p95; the cause is the dead dependency.
- **A slow query can look like pool exhaustion.** Check which path got slow first: one path (slow_query) vs all DB paths at once (bad_pool_config).
- **Silence is evidence.** No error logs means a killed process (memory_leak) or slow-but-working requests (slow_query), not "nothing wrong".
- **One dependency can drag down another.** Requests waiting on Redis still hold Postgres connections; more traffic would exhaust the pool and break /products too.
- **Alert gaps exist.** A slow query under 1 s p95 fires nothing; watch the dashboard, not only alerts.

## Fixes (one line each)
| Scenario | Fix |
|---|---|
| bad_pool_config | `git revert <bad commit>` + `./deploy.sh "rollback ..."` |
| kill_db | `docker compose start postgres`; shop-api reconnects (pool_pre_ping) |
| memory_leak | `git revert <bad commit>` + `./deploy.sh "rollback ..."` |
| slow_query | `CREATE INDEX ix_products_price ON products (price);` |
| redis_down | `docker compose start redis`; carts return from AOF |

## Evidence
Per-incident notes in `docs/rca/`.