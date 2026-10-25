#!/usr/bin/env bash
# The line above (the "shebang") tells Linux to run this file with bash, wherever bash is installed.
# Deploys shop-api: tag the current commit, push the tag to GitHub, rebuild and restart shop-api, check /health.
# Usage (Ubuntu terminal, repo root):  ./deploy.sh "what this deploy changes"

set -euo pipefail                      # -e stop on the first failing command, -u error on unset variables, -o pipefail a failing piped command counts as a failure

cd "$(dirname "$0")"                 

MSG="${1:-}"                           
if [ -z "$MSG" ]; then                 
  echo "Usage: ./deploy.sh \"what this deploy changes\""   
  exit 1                              
fi

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then   
  echo "Refusing to deploy: you have uncommitted changes. Commit them first."   
  git status --short --untracked-files=no                          
  exit 1
fi

NEW_APP_FILES="$(git ls-files --others --exclude-standard shop/app)"  
if [ -n "$NEW_APP_FILES" ]; then       
  echo "Refusing to deploy: untracked files in shop/app:"
  echo "$NEW_APP_FILES"                
  exit 1
fi

TAG="deploy-$(date +%Y%m%d-%H%M%S)"   
COMMIT="$(git rev-parse --short HEAD)" 

echo "Deploying $COMMIT as $TAG: $MSG" 

git tag -a "$TAG" -m "$MSG"            
git push origin "$TAG"                 
                                       

docker compose up -d --build shop-api  

for i in $(seq 1 30); do               
  if curl -fsS http://127.0.0.1:8000/health > /dev/null; then   
    echo "OK: $TAG is live and /health answers."
    exit 0                            
  fi
  sleep 1     
done                        

echo "FAILED: /health did not answer within 30 s. $TAG stays on GitHub as the deploy record."   
exit 1