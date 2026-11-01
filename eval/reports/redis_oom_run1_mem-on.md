# Incident report
**Root cause:** code_exception (confidence medium)
**Summary:** A code change (or existing bug) causes the /users/{user_id}/cart endpoint to raise an exception, resulting in a sharp rise in 5xx errors while the rest of the system stays healthy.

**Alerts fired:** ShopHigh5xxRatio since 20:59:07 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopHighLatency, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- 5xx_rate_by_path spikes only for /users/{user_id}/cart (4.69) while other DB‑backed paths stay at 0
- pg_up=1 but pg_connections_by_state shows 0 active and 0 disabled connections
- No latency increase on the affected path (p95 0.0228 s) indicating requests fail immediately
- No deploy in the minutes before the alert, so no config change caused it
- Logs unavailable due to log backend error, so the API error details are missing

**Silent signals:** Alerts for ShopApiDown, PostgresDown, RedisDown, HighLatency, HighMemory, and Restarts are silent because the shop‑api process remains up and the database is reachable; only the cart endpoint raises an exception, producing 5xx without affecting overall service health.
**Deploy:** not deploy-related
**Suggested fix (playbook):** git revert <bad commit> + ./deploy.sh "rollback ..."

_Critic: ok (rule checks only, loop limit reached) · correlator runs: 2 · LLM calls: 3_