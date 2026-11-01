# Incident report
**Root cause:** code_exception (confidence high)
**Summary:** A recent deploy introduced a type change that caused KeyError exceptions in the checkout endpoint, leading to a surge in 5xx errors.

**Alerts fired:** ShopApiRestarted since 21:34:07 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopHigh5xxRatio, ShopHighLatency, ShopApiHighMemory

**Evidence**
- KeyError exceptions on /users/{id}/checkout appearing right after the deploy
- 5xx rate for /users/{user_id}/checkout spiked from 0 to >2 shortly after the deploy
- ShopApiRestarted alert fired, but ShopApiDown remained silent, indicating the process stayed alive
- Deploy diff changed total calculation key type from int to str, affecting checkout logic

**Silent signals:** The lack of ShopApiDown, PostgresDown, and RedisDown alerts fits a code exception that crashes only the checkout handler while the service process remains running.
**Deploy:** deploy-20261101-213340
**Suggested fix (playbook):** git revert <bad commit> + ./deploy.sh "rollback ..."

_Critic: ok · correlator runs: 1 · LLM calls: 4_