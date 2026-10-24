# Observability

How we see inside the shop. The RCA agent reads the same signals a human on-call engineer would.

## Signals we collect

| Signal | Tool | Source in our stack | Answers |
|---|---|---|---|
| Metrics | Prometheus | shop-api `/metrics`, postgres-exporter, redis-exporter | Is something wrong? How bad? Since when? |
| Logs | Loki + Alloy | shop-api JSON logs (`request_id`, `duration_ms`, error) | What exactly happened? Why? |
| Traces | not used | — | — |

**Why no traces:** shop-api is the only app service, so a request does not cross services. `request_id` in every log line already links one request's lines. OpenTelemetry + Tempo would add containers and RAM for little gain. The agent's tool interface (`get_logs()`, `get_metrics()`) allows a `get_traces()` adapter later.

## Rules
- Metric labels must have few possible values (endpoint, method, status). Never `user_id` or `order_id` (high cardinality). Those go in logs.
- Alert on rates and p95 latency, not averages.

## Expected evidence per chaos scenario 

| Scenario | Metric signal | Log signal |
|---|---|---|
| kill_db | 5xx rate up, postgres exporter shows DB down | ERROR "failed to resolve host 'postgres'" (verified in Phase 5) |
| bad_pool_config | p95 latency up, DB connections stuck at pool size | ERROR pool timeout lines |
| slow_query | p95 latency up on `GET /products`, no 5xx | high `duration_ms` on `/products` |
| redis_down | redis exporter shows Redis down, 5xx on cart/checkout | ERROR Redis connection lines |

## Saved LogQL queries (used by Grafana and logs_agent)

| Purpose | Query |
|---|---|
| Error lines (the why) | `{service="shop-api"} \|= "request failed" \| json \| line_format "{{.request_id}} {{.path}} {{.error}}"` |
| One request's story | `{service="shop-api"} \|= "<request_id>"` |
| Slow requests | `{service="shop-api"} \| json \| duration_ms > 1000` |
| Top errors by message | `sum by (error) (count_over_time({service="shop-api"} \|= "request failed" \| json [10m]))` |
| Dependency's own logs | `{service="postgres"}` or `{service="redis"}` |

## Alerts
Rules in `prometheus/rules/alerts.yml`, routing in `alertmanager/alertmanager.yml` (all alerts grouped into one webhook = one incident).

| Alert | Fires when | Scenario |
|---|---|---|
| ShopApiDown | shop-api not scraped for 30 s | memory_leak (OOM kill) |
| PostgresDown | pg_up = 0 for 30 s | kill_db |
| RedisDown | redis_up = 0 for 30 s | redis_down |
| ShopHigh5xxRatio | 5xx > 5% for 1 min | any outage |
| ShopHighLatency | p95 > 1 s on a path for 2 min | slow_query, bad_pool_config |