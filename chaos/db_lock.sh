#!/usr/bin/env bash
# db_lock scenario: a transaction locks the products table for N seconds, so every query on products waits behind it.
set -euo pipefail                                   # stop on any error, unset variable or failed pipe

DOWN_SECONDS="${1:-600}"                            # how long the lock is held; default 600 s = 10 min
cd "$(dirname "$0")/.."                             # run from the repo root

now() { TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST'; }   # IST timestamps

sql() {                                             # runs one SQL text inside the postgres container (same as slow_query.sh)
  docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "$1"' sh "$1"
}

lock_holder() {                                     # the "bad migration": opens a transaction, takes the lock, then just sits there
  docker compose exec -T -e PGAPPNAME=chaos_db_lock postgres \
    sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "$1"' sh \
    "BEGIN; LOCK TABLE products IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(${DOWN_SECONDS}); COMMIT;"   # KEY: ACCESS EXCLUSIVE blocks even plain SELECTs until COMMIT
}                                                   # PGAPPNAME tags the connection so restore() can find and kill exactly this one

HOLDER_PID=""                                       # local PID of the background lock_holder; empty until it starts

restore() {                                         # releases the lock; runs on normal end AND on Ctrl+C
  echo "[$(now)] releasing the lock"
  sql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = 'chaos_db_lock';" > /dev/null   # KEY: kill the server-side session; killing only the local docker process can leave the lock held inside Postgres
  if [ -n "$HOLDER_PID" ]; then kill "$HOLDER_PID" 2>/dev/null || true; wait "$HOLDER_PID" 2>/dev/null || true; fi   # tidy up the background job; || true because it already died with an error
  echo "$(now) db_lock end" >> chaos/runs.log
}

echo "$(now) db_lock start down=${DOWN_SECONDS}s" >> chaos/runs.log
trap restore EXIT                                   # set BEFORE breaking: restore is safe to run even if the lock never started
trap 'exit 130' INT
echo "[$(now)] locking table products (ACCESS EXCLUSIVE)"
lock_holder > /dev/null 2>&1 &                      # KEY: run in the background (&) so the lock stays held while this script sleeps
HOLDER_PID=$!                                       # $! = PID of the last background job
echo "[$(now)] products locked for ${DOWN_SECONDS}s. Ctrl+C releases early."
sleep "$DOWN_SECONDS"