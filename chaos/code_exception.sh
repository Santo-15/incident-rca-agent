#!/usr/bin/env bash
# code_exception scenario: a deploy adds a KeyError to /checkout. Logic lives in bad_deploy.sh.
exec "$(dirname "$0")/bad_deploy.sh" code_exception "$@"