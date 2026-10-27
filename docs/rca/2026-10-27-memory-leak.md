# Incident: shop-api memory leak, OOM kill (memory_leak)

## Timeline (IST, 27 Oct 2026)
- 10:32 setup deploy deploy-20261027-050212: 256m memory limit + memory/restart alerts
- 10:37 bad deploy deploy-20261027-050702 "add request history for debugging"; RSS starts climbing from ~110 MiB
- ~10:37 ShopApiRestarted fires (this one is the deploy restart, not the crash)
- ~10:40 ShopApiHighMemory fires (RSS > 200 MiB for 1 min)
- 10:41:30 RSS hits ~256 MiB, kernel kills shop-api, Docker restarts it (RestartCount=1)
- ~10:42 RSS starts climbing again from ~110 MiB (the leak comes back after every restart)
- ~10:46 second OOM kill (sawtooth repeats)
- 10:48:27 rollback deployed deploy-20261027-051827 (git revert 3378b1a); memory stops climbing

## Root cause
The deploy at 10:37 added REQUEST_HISTORY in the request middleware: every request appends a ~128 KB entry to a list that is never trimmed. At ~5 req/s memory grew ~0.6 MB/s, hit the 256m container limit in ~4 min, and the kernel killed the process (exit 137). Docker restarted it, and the same code started leaking again.

## Evidence
- Dashboard: RSS climbs in a straight line from the deploy time, drops at the limit, then climbs again (sawtooth)
- ShopApiHighMemory then a restart; docker inspect RestartCount=1, StartedAt 10:41:30
- Deploy tag right before the climb; diff between the last two tags shows only the REQUEST_HISTORY lines in shop/app/main.py (plus whitespace)
- Logs: no ERROR lines. A killed process can't log, and the leak itself throws no exception
- ShopApiDown did NOT fire: the restart takes ~3 s, and the alert needs 30 s of failed scrapes
- ShopHigh5xxRatio did NOT fire: requests cut off by the kill never got a 500 response, and the new process starts its counters from zero
- ShopHighLatency did NOT fire: p95 stayed at 10-40 ms; the leak costs memory, not speed
- PostgresDown / RedisDown did NOT fire: both healthy
- ShopApiRestarted alone is ambiguous (a deploy also trips it); it only means a crash when there is no deploy tag at that moment

## Time to diagnosis
~6 min (ShopApiHighMemory ~10:40 -> deploy tag + diff 10:46)

## Fix
git revert of the request history commit + deploy.sh. Real-world fix: cap the list (e.g. collections.deque(maxlen=1000)) or don't keep request data in process memory.