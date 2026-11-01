#!/usr/bin/env bash
# redis_hang scenario: freeze Redis (container alive, never answers) for N seconds, then unfreeze it.
set -euo pipefail                                   # stop on any error, unset variable or failed pipe

DOWN_SECONDS="${1:-600}"                            # how long Redis stays frozen; default 600 s = 10 min
cd "$(dirname "$0")/.."                             # run from the repo root

now() { TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST'; }   # IST timestamps

restore() {                                         # unfreezes Redis; runs on normal end AND on Ctrl+C
  echo "[$(now)] unpausing redis"
  docker compose unpause redis
  echo "$(now) redis_hang end" >> chaos/runs.log
}

echo "$(now) redis_hang start down=${DOWN_SECONDS}s" >> chaos/runs.log
echo "[$(now)] pausing redis (frozen, not dead)"
docker compose pause redis                          # KEY: shop-api's 2 s socket_timeout turns this into "Timeout reading from socket", not "Error -2 connecting" like redis_down
trap restore EXIT
trap 'exit 130' INT
echo "[$(now)] redis frozen for ${DOWN_SECONDS}s. Ctrl+C unfreezes early."
sleep "$DOWN_SECONDS"