#!/usr/bin/env bash
set -e
# Usage: bash scripts/init_git.sh <github-repo-url>
REPO_URL=${1:?"Usage: $0 <github-repo-url>"}
cd "$(dirname "$0")/.."
git init
git add .
git commit -m "feat: initial AIOps VCF monorepo structure"
git branch -M main
git remote add origin "$REPO_URL"
git push -u origin main
echo "Pushed to $REPO_URL"
