# Incident: products price index dropped (slow_query)

## Timeline (IST, 27 Oct 2026)
- 16:37 baseline: p95 on /products ~10 ms, Locust 10 users
- 16:38:15 index ix_products_price dropped (run 1, 10 users, products table ~16 M rows)
- ~16:39 p95 on /products jumps to ~400-460 ms; other paths unchanged; full-scan rows read on products jump from 0 to ~10-16 M rows/s
- 16:38 first /products requests over 1 s in logs (1001 ms, 1161 ms)
- 16:48:15 index rebuilt; p95 back to ~10 ms by ~16:52
- 16:53:27 index dropped again (run 2, Locust 50 users)
- ~16:57:30 p95 on /products passes 1 s; 1.8 s by 16:59
- 16:59:34 stopped early (Ctrl+C), index rebuilt; ShopHighLatency was still pending and never fired

## Root cause
The index on products.price was dropped directly in Postgres (no deploy). Requests sorted by price (30% of /products) changed from reading 10 rows through the index (0.05 ms) to scanning all ~16 M rows and sorting them (~400 ms when idle, over 1 s under load).

## Evidence
- p95 rose on /products only; /products/{id}, cart and checkout stayed at 10-40 ms
- 5xx stayed at 0: slow requests still succeed with 200
- Logs: no ERROR lines; only INFO "request done" lines with high duration_ms, all on /products
- Prometheus: rate(pg_stat_user_tables_seq_tup_read{relname="products"}[1m]) jumped from 0 to ~10-16 M rows/s at the break
- EXPLAIN ANALYZE: Index Scan using ix_products_price (0.05 ms) vs Parallel Seq Scan on products (~400 ms idle)
- No deploy: newest tag deploy-20261027-051827 at 10:48, six hours earlier
- PostgresDown, RedisDown, ShopApiDown, ShopApiRestarted, ShopApiHighMemory did NOT fire: everything was up, nothing restarted
- ShopHighLatency did NOT fire: at 10 users p95 stayed ~460 ms (below 1 s); at 50 users it passed 1 s only ~2 min before the run was stopped

## Time to diagnosis
No alert fired, so detection came only from watching the dashboard. Once p95 was seen, the cause was clear in ~5 min (one path slow + seq scans jumped + no deploy).

## Fix
Rebuild the index: CREATE INDEX ix_products_price ON products (price);

## Follow-up
- Gap: a slow query under the 1 s threshold slows the shop with no alert. Consider a lower /products threshold or an alert on seq_tup_read for products.
- For eval runs, run this scenario at 50 Locust users for the full 10 min so the alert fires.