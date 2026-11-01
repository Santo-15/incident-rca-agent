#!/usr/bin/env bash
# memory_leak scenario: a deploy keeps every /products response in memory. Logic lives in bad_deploy.sh.
exec "$(dirname "$0")/bad_deploy.sh" memory_leak "$@"