#!/usr/bin/env bash
# shop_api_down scenario: stop shop-api for N seconds (process gone, so no logs at all), then start it again.
set -euo pipefail                                   # stop on any error, unset variable or failed pipe

DOWN_SECONDS="${1:-600}"                            # how long shop-api stays down; default 600 s = 10 min
cd "$(dirname "$0")/.."                             # run from the repo root so docker compose finds docker-compose.yml

now() { TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST'; }   # IST timestamps to match Grafana and alerts

restore() {                                         # brings shop-api back; runs on normal end AND on Ctrl+C
  echo "[$(now)] starting shop-api again"
  docker compose start shop-api                     # same container and image; no rebuild, no deploy tag
  echo "$(now) shop_api_down end" >> chaos/runs.log # true end time (eval answer key, gitignored)
}

echo "$(now) shop_api_down start down=${DOWN_SECONDS}s" >> chaos/runs.log   # true start time
echo "[$(now)] stopping shop-api (no grace period, like a crash)"
docker compose stop -t 0 shop-api                   # KEY: "stop" = Docker treats it as stopped on purpose, so "restart: unless-stopped" won't bring it back; -t 0 = no graceful shutdown
trap restore EXIT                                   # from now on, however the script ends, restore() runs
trap 'exit 130' INT                                 # Ctrl+C ends cleanly, which triggers the EXIT trap
echo "[$(now)] shop-api down for ${DOWN_SECONDS}s. Ctrl+C brings it back early."
sleep "$DOWN_SECONDS"                               # keep it down while alerts fire and you investigate