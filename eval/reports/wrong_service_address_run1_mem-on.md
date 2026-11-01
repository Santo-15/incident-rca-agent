# Incident report
**Root cause:** wrong_service_address (confidence high)
**Summary:** A recent deploy pointed shop‑api at the wrong Redis port, causing connection‑refused errors and a surge of 5xx responses on cart and checkout endpoints.

**Alerts fired:** ShopApiRestarted since 21:15:52 UTC, ShopHigh5xxRatio since 21:17:52 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopHighLatency, ShopApiHighMemory

**Evidence**
- Deploy at 21:15:29 changed REDIS_URL from port 6379 to 6380
- Logs show 944x ‘redis connection refused’ errors on /cart and /checkout endpoints
- 5xx_rate_by_path spikes for /users/{user_id}/checkout right after the deploy
- ShopApiRestarted alert fires at the same time, indicating the process handled the failure
- Redis metrics remain up (redis_up=1), meaning Redis itself is healthy

**Silent signals:** The lack of PostgresDown, ShopApiDown, and ShopHighLatency alerts fits because the API process stayed alive and the database was unaffected; only the mis‑addressed Redis caused the observed 5xx errors.
**Deploy:** deploy-20261101-211529
**Suggested fix (playbook):** git revert <bad commit> + ./deploy.sh "rollback ..."

_Critic: ok · correlator runs: 1 · LLM calls: 4_