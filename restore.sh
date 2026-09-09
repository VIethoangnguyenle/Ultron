#!/usr/bin/env bash
# Restore curated Hermes state from this repo into ~/.hermes (run on a NEW machine).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

mkdir -p "$HERMES_HOME/memories" "$HERMES_HOME/scripts" "$HERMES_HOME/skills" "$HERMES_HOME/cron"

[ -d "$REPO_DIR/memories" ] && cp -r "$REPO_DIR/memories/." "$HERMES_HOME/memories/"
[ -d "$REPO_DIR/scripts" ]  && cp -r "$REPO_DIR/scripts/."  "$HERMES_HOME/scripts/"
[ -d "$REPO_DIR/skills" ]   && cp -r "$REPO_DIR/skills/."   "$HERMES_HOME/skills/"
[ -f "$REPO_DIR/cron/jobs.json" ] && cp -f "$REPO_DIR/cron/jobs.json" "$HERMES_HOME/cron/jobs.json"

for f in SOUL.md config.yaml; do
  [ -f "$REPO_DIR/$f" ] && cp -f "$REPO_DIR/$f" "$HERMES_HOME/$f"
done

echo "Restored into $HERMES_HOME"
