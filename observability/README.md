# Observability

How we see inside the shop. The RCA agent reads the same signals a human on-call engineer would.

## Signals we collect

| Signal | Tool | Source in our stack | Answers |
|---|---|---|---|
| Metrics | Prometheus | shop-api `/metrics`, postgres-exporter, redis-exporter, cAdvisor | Is something wrong? How bad? Since when? |
| Logs | Loki + Promtail | shop-api JSON logs (`request_id`, `duration_ms`, error) | What exactly happened? Why? |
| Traces | not used | — | — |

**Why no traces:** shop-api is the only app service, so a request does not cross services. `request_id` in every log line already links one request's lines. OpenTelemetry + Tempo would add containers and RAM for little gain. The agent's tool interface (`get_logs()`, `get_metrics()`) allows a `get_traces()` adapter later.

## Rules
- Metric labels must have few possible values (endpoint, method, status). Never `user_id` or `order_id` (high cardinality). Those go in logs.
- Alert on rates and p95 latency, not averages.

## Expected evidence per chaos scenario (to verify in Phase 7)

| Scenario | Metric signal | Log signal |
|---|---|---|
| kill_db | 5xx rate up, postgres exporter shows DB down | ERROR "failed to resolve host 'postgres'" (verified in Phase 5) |
| bad_pool_config | p95 latency up, DB connections stuck at pool size | ERROR pool timeout lines |
| slow_query | p95 latency up on `GET /products`, no 5xx | high `duration_ms` on `/products` |
| memory_leak | shop-api container memory keeps climbing (cAdvisor) | few or none until the container restarts |
| redis_down | redis exporter shows Redis down, 5xx on cart/checkout | ERROR Redis connection lines |