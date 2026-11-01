#!/usr/bin/env bash
# bad_deploy: ship a broken change as a real deploy (git tag + rebuild), keep it live N seconds, then roll back with a second deploy.
# Usage (Ubuntu terminal, repo root): chaos/bad_deploy.sh <scenario> [seconds]
# Scenarios: bad_pool_config | memory_leak | wrong_service_address | code_exception
set -euo pipefail                                   # stop on any error, unset variable or failed pipe

SCENARIO="${1:?usage: chaos/bad_deploy.sh <scenario> [seconds]}"   # ${1:?msg} = stop with this message if no scenario is given
DOWN_SECONDS="${2:-600}"                            # how long the bad version stays live; default 600 s = 10 min
cd "$(dirname "$0")/.."                             # run from the repo root (deploy.sh and docker-compose.yml live here)

now() { TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST'; }   # IST timestamps

BRANCH="$(git rev-parse --abbrev-ref HEAD)"         # the branch to come back to (main); prints "HEAD" if already detached
if [ "$BRANCH" = "HEAD" ]; then echo "Detached HEAD: run 'git checkout main' first"; exit 1; fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then   # KEY: restore() uses checkout --force, which would wipe your own uncommitted edits
  echo "Commit your changes first: this script switches commits."; exit 1
fi

swap() {                                            # swap FILE OLD NEW: exact text replace; fails unless OLD appears exactly once
  python3 - "$@" <<'PY'
import pathlib, sys
path, old, new = sys.argv[1:4]
p = pathlib.Path(path)
text = p.read_text()
if text.count(old) != 1:
    sys.exit(f"{path}: expected exactly 1 match for {old!r}, found {text.count(old)}")
p.write_text(text.replace(old, new))
PY
}

MSG=""                                              # the innocent-looking commit/deploy message (real bad deploys never say "bug")
DEPLOYED=0                                          # 1 once deploy.sh has started, so restore knows a rollback deploy is needed

restore() {                                         # back to good code; runs on normal end AND on Ctrl+C AND on failure
  echo "[$(now)] back to ${BRANCH}"
  git checkout --quiet --force "$BRANCH"            # leave the bad commit; --force drops a half-made edit if swap() failed midway
  if [ "$DEPLOYED" = 1 ]; then
    echo "[$(now)] rollback deploy"
    ./deploy.sh "revert: ${MSG}"                    # KEY: rollback is also a deploy (new tag on main), exactly like a real git revert + deploy
  fi
  echo "$(now) ${SCENARIO} end" >> chaos/runs.log   # true end time
}

trap restore EXIT                                   # from now on, however the script ends, restore() runs
trap 'exit 130' INT                                 # Ctrl+C ends cleanly, which triggers the EXIT trap
echo "$(now) ${SCENARIO} start down=${DOWN_SECONDS}s" >> chaos/runs.log

case "$SCENARIO" in
  bad_pool_config)        # pool 20 -> 1; only hurts under load (~200 Locust users)
    MSG="tune db pool to cut idle connections"
    swap docker-compose.yml 'DB_POOL_SIZE: "20"' 'DB_POOL_SIZE: "1"' ;;
  memory_leak)            # every /products response kept forever in a module-level list
    MSG="products: keep recent pages for debugging"
    swap shop/app/main.py 'REQUEST_ID_RE = re.compile(r"[A-Za-z0-9-]{1,64}")' $'REQUEST_ID_RE = re.compile(r"[A-Za-z0-9-]{1,64}")\n_RECENT_PAGES = []'
    swap shop/app/main.py 'return [{"id": p.id, "name": p.name, "price": p.price} for p in db.scalars(stmt)]' \
      $'rows = [{"id": p.id, "name": p.name, "price": p.price} for p in db.scalars(stmt)]\n    _RECENT_PAGES.append((rows, "x" * 512 * 1024))\n    return rows' ;;   # KEY: "x" * 512 KiB really fills memory; an empty bytearray may not raise RSS
  wrong_service_address)  # redis port typo 6379 -> 6380; Redis itself stays healthy
    MSG="redis: move client settings to compose"
    swap docker-compose.yml 'REDIS_URL: redis://redis:6379/0' 'REDIS_URL: redis://redis:6380/0' ;;
  code_exception)         # cart ids are ints, new code looks them up as strings -> KeyError on every non-empty checkout
    MSG="checkout: read quantities by cart key"
    swap shop/app/main.py 'sum(p.price * qty_by_id[p.id] for p in products)' 'sum(p.price * qty_by_id[str(p.id)] for p in products)' ;;
  *) echo "unknown scenario: ${SCENARIO}"; exit 1 ;;
esac

git checkout --quiet --detach                       # KEY: leave main; the bad commit lives only on a detached HEAD + its deploy tag, so main's history stays clean
git commit --quiet -am "$MSG"                       # deploy.sh refuses uncommitted changes, and diff_agent needs a real commit to compare
DEPLOYED=1
./deploy.sh "$MSG"                                  # KEY: a real deploy: deploy-* tag pushed to GitHub + shop-api rebuilt, which is exactly what deploy_agent/diff_agent read
echo "[$(now)] bad version live for ${DOWN_SECONDS}s. Ctrl+C rolls back early."
sleep "$DOWN_SECONDS"