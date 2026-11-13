#!/usr/bin/env bash
# reset: put the demo back to a clean, healthy state. Runs before the RCA API starts (systemd ExecStartPre), or by hand.
set -uo pipefail                                    # no -e: one step failing (e.g. nothing paused) must not skip the rest
cd "$(dirname "$0")/.."                             # repo root

git checkout --quiet --force main                   # KEY: leave a bad-deploy commit if a run was cut off
docker compose unpause postgres redis > /dev/null 2>&1   # undo postgres_hang / redis_hang; errors if nothing is paused, which is fine
docker compose up -d --build --wait --wait-timeout 120   # KEY: start anything killed/stopped; rebuild shop-api from main (recreated only if code changed)
docker compose exec -T redis redis-cli CONFIG SET maxmemory 0 > /dev/null              # undo redis_oom (0 = no limit, Redis default)
docker compose exec -T redis redis-cli CONFIG SET maxmemory-policy noeviction > /dev/null   # Redis default policy
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qc "$1"' sh \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = 'chaos_db_lock';" > /dev/null   # undo db_lock
echo "reset done"