# Incident report
**Root cause:** db_pool_exhausted (confidence high)
**Summary:** The shop‑api ran out of database connections, causing requests to time out and the API to go down.

**Alerts fired:** none
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopHigh5xxRatio, ShopHighLatency, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- High number of DB connection pool exhausted errors (193) on key endpoints
- pg_connections_by_state active peaked at 25 and idle‑in‑transaction at 20
- pg_longest_tx_s peaked at 90.8 s indicating long‑running transactions
- shop_api_up metric dropped to 0, indicating the API stopped responding

**Silent signals:** The lack of alerts for ShopApiDown and ShopHigh5xxRatio fits because the API became unresponsive due to exhausted DB connections rather than explicit 5xx errors, so the monitoring rules did not fire.
**Deploy:** not deploy-related
**Suggested fix (playbook):** git revert <bad commit> + ./deploy.sh "rollback ..."

_Critic: ok · correlator runs: 1 · LLM calls: 4_