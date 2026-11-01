# Incident report
**Root cause:** insufficient_evidence (confidence medium)
**Summary:** Evidence points to severe Redis timeouts causing high latency and 5xx errors, but without a RedisDown alert or abnormal redis_up metric the root cause cannot be definitively identified.

**Alerts fired:** ShopHighLatency{path=/users/{user_id}/checkout} since 20:03:37 UTC, ShopHigh5xxRatio since 20:03:37 UTC, ShopHighLatency{path=/users/{user_id}/cart} since 20:03:37 UTC
**Alerts silent:** ShopApiDown, PostgresDown, RedisDown, ShopApiHighMemory, ShopApiRestarted

**Evidence**
- High number of Redis connection and read timeouts on /cart and /checkout endpoints
- Sharp rise in 5xx rates and latency for those same endpoints starting at 20:01:22 UTC
- RedisUp metric remains normal (redis_up=1) and no RedisDown alert was fired
- No recent deploy that touched relevant code or config

**Silent signals:** The absence of a RedisDown alert and a normal redis_up metric means the incident cannot be conclusively attributed to Redis being down; similarly, no DB‑pool exhaustion signals (e.g., connection errors or pool‑size alerts) are present, so that cause is also unsupported.
**Deploy:** not deploy-related
**Suggested fix (playbook):** no fix suggested: check the deciding signal named in the summary

_Critic: ok (rule checks only, loop limit reached) · correlator runs: 2 · LLM calls: 3_