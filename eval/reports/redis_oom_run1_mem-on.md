# Incident report
**Root cause:** redis_out_of_memory (confidence high)
**Summary:** Redis hit its maxmemory limit, rejecting write commands for cart operations, which caused a surge of 5xx errors on the cart endpoint while the rest of the system appeared healthy.

**Alerts fired:** ShopHigh5xxRatio since 07:25:37 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopHighLatency, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- High 5xx rate on /users/{user_id}/cart starting at 07:23:22 UTC (peak 4.6)
- Log entries showing "redis memory limit exceeded" and OutOfMemoryError on cart endpoint
- Redis exporter reports redis_up=1 (exporter still up despite memory issue)
- Other paths (/products, checkout) show no 5xx spikes, indicating issue isolated to Redis usage

**Silent signals:** ShopApiDown, PostgresDown, RedisDown, ShopHighLatency, ShopApiHighMemory, ShopApiRestarted remained silent because the API process stayed alive, PostgreSQL was healthy, and Redis exporter kept reporting up even though Redis refused writes due to memory exhaustion.
**Deploy:** not deploy-related
**Suggested fix (playbook):** redis-cli CONFIG SET maxmemory 0 (or raise it), then find what filled Redis

_Critic: ok · correlator runs: 1 · LLM calls: 3_