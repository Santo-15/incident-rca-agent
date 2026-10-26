#!/usr/bin/env bash
# kill_db scenario: crash Postgres, keep it down for N seconds, then bring it back.  # what this file is for
set -euo pipefail                                   # stop on any error, unset variable or failed pipe, so the scenario never half-runs

DOWN_SECONDS="${1:-600}"                            # how long the DB stays dead; first argument, default 600 s = 10 min to investigate
cd "$(dirname "$0")/.."                             # jump to the repo root, so docker compose finds docker-compose.yml from any folder

now() { TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST'; }   # IST timestamp (WSL clock is UTC), to match Grafana/alert times

restore() {                                         # brings Postgres back; runs on normal end AND on Ctrl+C
  echo "[$(now)] starting postgres again"           # shows when recovery began, useful for the RCA timeline
  docker compose start postgres                     # restarts the same container; data is safe in the pgdata volume
  echo "$(now) kill_db end" >> chaos/runs.log       # records the true end time (answer key for eval later)
}

echo "$(now) kill_db start down=${DOWN_SECONDS}s" >> chaos/runs.log   # records the true start time before breaking anything
echo "[$(now)] killing postgres (SIGKILL, like a crash)"              # tells you on screen what's happening
docker compose kill postgres                        # SIGKILL: no clean shutdown, same as a real crash or OOM kill
trap restore EXIT                                   # from now on, however the script ends, restore() runs
trap 'exit 130' INT                                 # Ctrl+C ends the script cleanly, which then triggers the EXIT trap
echo "[$(now)] postgres down for ${DOWN_SECONDS}s. Ctrl+C brings it back early."   # reminder for you
sleep "$DOWN_SECONDS"                               # keep the DB dead while alerts fire and you investigate