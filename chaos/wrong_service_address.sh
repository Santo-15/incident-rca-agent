#!/usr/bin/env bash
# wrong_service_address scenario: a deploy points shop-api at redis:6380. Logic lives in bad_deploy.sh.
exec "$(dirname "$0")/bad_deploy.sh" wrong_service_address "$@"