#!/usr/bin/env bash
# Sync curated Hermes state into this repo, commit, and push.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

python3 sync.py "$HOME/.hermes" "$REPO_DIR"

git add -A
if git diff --cached --quiet; then
  echo "no changes to push"
  exit 0
fi

git commit -m "sync: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
# reconcile with remote (never force) before pushing
git pull --rebase origin main >/dev/null 2>&1 || true
git push origin main
echo "pushed"
