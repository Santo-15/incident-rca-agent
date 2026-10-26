# Incident: DB pool size reduced to 1 (bad_pool_config)

## Timeline (IST, 26 Oct 2026)
- 22:09  deploy-20261026-163908 goes live ("reduce db pool size"), Locust at 200 users
- ~22:13 ShopHighLatency fires (p95 = 30 s on 4 paths)
- ~22:13 ShopHigh5xxRatio fires (~92% of requests fail)
- 22:24  dashboard: 5xx jump at ~22:13, p95 flat at 30 s, Postgres connections drop from ~20 to 1
- 22:24  logs: "TimeoutError: QueuePool limit of size 1 overflow 0 reached, connection timed out, timeout 30.00"
- ~22:25 ShopApiDown fires (misleading, see evidence)
- 22:27  deploys: newest tag 22:09, just before the alerts
- 22:28  diff: DB_POOL_SIZE "20" -> "1" in docker-compose.yml
- 22:29  rollback deployed: deploy-20261026-165909

## Root cause
Deploy at 22:09 lowered DB_POOL_SIZE from 20 to 1. At ~100 req/s about 1.9 requests need a DB connection at once, so requests queued, waited the 30 s pool timeout and failed with 500.

## Evidence
- Logs: QueuePool limit of size 1 ... timeout 30.00
- p95 = 30 s, same as DB_POOL_TIMEOUT
- Postgres connections flat at 1
- PostgresDown and RedisDown did not fire: DB and Redis were healthy
- Deploy tag 4 min before alerts; diff shows only the pool line
- ShopApiDown was misleading: all 40 worker threads were stuck waiting for the one connection, so /metrics could not answer Prometheus. The process never crashed (RSS never reset).

## Time to diagnosis
~15 min (first alert ~22:13 -> diff found 22:28), slowed by the Grafana dashboard not loading after the laptop restart.

## Fix
git revert + deploy.sh. Follow-up: the comment next to DB_POOL_SIZE in compose is outdated.