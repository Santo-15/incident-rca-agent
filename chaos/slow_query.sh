#!/usr/bin/env bash
# slow_query scenario: drop the products price index for N seconds, then rebuild it.  # what this file is for
set -euo pipefail                                   # stop on any error, unset variable or failed pipe

DOWN_SECONDS="${1:-600}"                            # how long the index stays gone; default 600 s = 10 min
cd "$(dirname "$0")/.."                             # run from the repo root so docker compose finds docker-compose.yml

now() { TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST'; }   # IST timestamps to match Grafana and alerts

sql() {                                             # runs one SQL statement inside the postgres container
  docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "$1"' sh "$1"
}                                                   # -T = no keyboard needed; ON_ERROR_STOP makes a failed SQL fail the script; sh "$1" hands our SQL text to the inner shell

restore() {                                         # puts the index back; runs on normal end AND on Ctrl+C
  echo "[$(now)] rebuilding index ix_products_price"   # recovery start time for the timeline
  sql "CREATE INDEX IF NOT EXISTS ix_products_price ON products (price);"   # rebuilds the sorted price list; IF NOT EXISTS = safe to run twice
  echo "$(now) slow_query end" >> chaos/runs.log    # true end time (eval answer key, gitignored)
}

echo "$(now) slow_query start down=${DOWN_SECONDS}s" >> chaos/runs.log   # true start time
echo "[$(now)] dropping index ix_products_price"   # on-screen note
sql "DROP INDEX ix_products_price;"                 # the break: like someone's manual "unused index cleanup", no git trace
trap restore EXIT                                   # from now on, however the script ends, restore() runs
trap 'exit 130' INT                                 # Ctrl+C ends cleanly, which triggers the EXIT trap
echo "[$(now)] index gone for ${DOWN_SECONDS}s. Ctrl+C rebuilds it early."
sleep "$DOWN_SECONDS"                               # keep it broken while alerts fire and you investigate