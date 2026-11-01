# Incident report
**Root cause:** memory_leak (confidence high)
**Summary:** A memory leak introduced by the recent deploy caused the shop‑api process to exceed its memory limits, be killed and repeatedly restart.

**Alerts fired:** ShopApiRestarted since 18:44:37 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopHigh5xxRatio, ShopHighLatency, ShopApiHighMemory

**Evidence**
- RSS memory rose from 123 MiB to 267 MiB after the deploy
- Six rapid ShopApiRestarted alerts started at 18:44:37 UTC
- pg_connections idle dropped sharply, indicating connections were closed when the process died
- Deploy diff added an unbounded _RECENT_PAGES list that grows on each /products call

**Silent signals:** ShopApiDown stayed silent because the process kept restarting and was considered up, and latency/5xx stayed silent since requests completed quickly before the process was killed
**Deploy:** deploy-20261101-184410
**Suggested fix (playbook):** git revert <bad commit> + ./deploy.sh "rollback ..."

_Critic: ok · correlator runs: 1 · LLM calls: 3_