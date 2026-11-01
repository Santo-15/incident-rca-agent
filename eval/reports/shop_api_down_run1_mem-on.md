# Incident report
**Root cause:** shop_api_down (confidence high)
**Summary:** The shop‑api process stopped running, causing the ShopApiDown alert and halting all traffic while leaving dependent services healthy.

**Alerts fired:** ShopApiDown since 20:22:07 UTC
**Alerts silent:** PostgresDown, RedisDown, ShopHigh5xxRatio, ShopHighLatency, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- ShopApiDown alert fired at 20:22:07 UTC
- shop_api_up metric dropped from 1 to 0 at 20:21:37 UTC
- pg_connections_by_state{state=idle} fell from ~21 to 1 at the same time
- No error logs or request‑failed lines during the incident window

**Silent signals:** Silence of PostgresDown, RedisDown, high‑latency and 5xx alerts fits a dead shop‑api process because no requests reach the service, so no errors, latency spikes, or downstream failures are recorded.
**Deploy:** not deploy-related
**Suggested fix (playbook):** docker compose start shop-api

_Critic: ok (rule checks only, loop limit reached) · correlator runs: 2 · LLM calls: 3_