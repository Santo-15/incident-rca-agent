#!/usr/bin/env bash
# redis_oom scenario: Redis stays up but hits its memory limit, so every write fails for N seconds.
set -euo pipefail                                   # stop on any error, unset variable or failed pipe

DOWN_SECONDS="${1:-600}"                            # how long Redis stays "full"; default 600 s = 10 min
cd "$(dirname "$0")/.."                             # run from the repo root

now() { TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST'; }   # IST timestamps

rcli() { docker compose exec -T redis redis-cli --raw "$@"; }   # one redis-cli command inside the redis container; --raw = plain values

OLD_MAX="$(rcli CONFIG GET maxmemory | sed -n 2p)"            # CONFIG GET prints the name, then the value; line 2 = value (0 = no limit)
OLD_POLICY="$(rcli CONFIG GET maxmemory-policy | sed -n 2p)"  # remember the policy so we put back exactly what was there

restore() {                                         # puts the old limits back; runs on normal end AND on Ctrl+C
  echo "[$(now)] restoring maxmemory=${OLD_MAX} policy=${OLD_POLICY}"
  rcli CONFIG SET maxmemory "$OLD_MAX" > /dev/null
  rcli CONFIG SET maxmemory-policy "$OLD_POLICY" > /dev/null
  echo "$(now) redis_oom end" >> chaos/runs.log
}

echo "$(now) redis_oom start down=${DOWN_SECONDS}s" >> chaos/runs.log
trap restore EXIT                                   # set BEFORE breaking: if the second CONFIG SET fails, the first is still undone
trap 'exit 130' INT
echo "[$(now)] setting redis maxmemory to 1 byte, policy noeviction"
rcli CONFIG SET maxmemory-policy noeviction > /dev/null   # KEY: noeviction = refuse writes when full; an LRU policy would quietly delete carts instead, with no errors
rcli CONFIG SET maxmemory 1 > /dev/null             # KEY: Redis is "full" at once: HINCRBY fails with OOM, reads still work, redis_up stays 1 (RedisDown silent)
echo "[$(now)] redis full for ${DOWN_SECONDS}s. Ctrl+C restores early."
sleep "$DOWN_SECONDS"