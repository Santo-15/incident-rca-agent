#!/usr/bin/env bash
# bad_pool_config scenario: a deploy drops the DB pool to 1. Logic lives in bad_deploy.sh.
exec "$(dirname "$0")/bad_deploy.sh" bad_pool_config "$@"   # exec = replace this shell with bad_deploy.sh; "$@" passes the seconds on