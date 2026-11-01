#!/usr/bin/env bash
# postgres_hang scenario: freeze Postgres (container alive, never answers) for N seconds, then unfreeze it.
set -euo pipefail                                   # stop on any error, unset variable or failed pipe

DOWN_SECONDS="${1:-600}"                            # how long Postgres stays frozen; default 600 s = 10 min
cd "$(dirname "$0")/.."                             # run from the repo root

now() { TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST'; }   # IST timestamps

restore() {                                         # unfreezes Postgres; runs on normal end AND on Ctrl+C
  echo "[$(now)] unpausing postgres"
  docker compose unpause postgres                   # processes continue exactly where they stopped; nothing restarts
  echo "$(now) postgres_hang end" >> chaos/runs.log # true end time
}

echo "$(now) postgres_hang start down=${DOWN_SECONDS}s" >> chaos/runs.log
echo "[$(now)] pausing postgres (frozen, not dead)"
docker compose pause postgres                       # KEY: pause freezes every process in the container; the hostname still resolves and connections open, but no reply ever comes (kill_db = container gone, DNS fails)
trap restore EXIT
trap 'exit 130' INT
echo "[$(now)] postgres frozen for ${DOWN_SECONDS}s. Ctrl+C unfreezes early."
sleep "$DOWN_SECONDS"