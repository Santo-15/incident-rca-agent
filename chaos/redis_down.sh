#!/usr/bin/env bash
# redis_down scenario: crash Redis, keep it down for N seconds, then bring it back.  # what this file is for
set -euo pipefail                                   # stop on any error, unset variable or failed pipe

DOWN_SECONDS="${1:-600}"                            # how long Redis stays dead; default 600 s = 10 min
cd "$(dirname "$0")/.."                             # run from the repo root so docker compose finds docker-compose.yml

now() { TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST'; }   # IST timestamps to match Grafana and alerts

restore() {                                         # brings Redis back; runs on normal end AND on Ctrl+C
  echo "[$(now)] starting redis again"              # recovery start time for the timeline
  docker compose start redis                        # same container; carts come back from the AOF file in the redisdata volume
  echo "$(now) redis_down end" >> chaos/runs.log    # true end time (eval answer key, gitignored)
}

echo "$(now) redis_down start down=${DOWN_SECONDS}s" >> chaos/runs.log   # true start time
echo "[$(now)] killing redis (SIGKILL, like a crash)"
docker compose kill redis                           # SIGKILL: no clean shutdown, like a real crash
trap restore EXIT                                   # from now on, however the script ends, restore() runs
trap 'exit 130' INT                                 # Ctrl+C ends cleanly, which triggers the EXIT trap
echo "[$(now)] redis down for ${DOWN_SECONDS}s. Ctrl+C brings it back early."
sleep "$DOWN_SECONDS"                               # keep Redis dead while alerts fire and you investigate