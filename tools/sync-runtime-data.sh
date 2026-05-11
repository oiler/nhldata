#!/usr/bin/env bash
# Copy the runtime files the deployed app reads from the data/ pipeline tree
# into v2/browser/runtime_data/ so the Docker build can pick them up.
#
# Run after rebuilding any of the source DBs/CSVs:
#   python v2/browser/build_league_db.py 2025
#   python v2/browser/build_edm_db.py
#   ./tools/sync-runtime-data.sh
#   fly deploy
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/data"
DST="$REPO_ROOT/v2/browser/runtime_data"

mkdir -p "$DST/2024" "$DST/2025"

cp "$SRC/2024/generated/browser/league.db"        "$DST/2024/league.db"
cp "$SRC/2025/generated/browser/league.db"        "$DST/2025/league.db"
cp "$SRC/2025/generated/browser/edm.db"           "$DST/2025/edm.db"
cp "$SRC/2025/generated/edge/player_bursts.csv"   "$DST/2025/player_bursts.csv"

echo "Synced runtime_data:"
ls -lh "$DST/2024" "$DST/2025"
