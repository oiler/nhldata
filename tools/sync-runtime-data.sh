#!/usr/bin/env bash
# Copy the runtime files the deployed app reads from the data/ pipeline tree
# into v2/browser/runtime_data/ so the Docker build can pick them up.
#
# Run after rebuilding any of the source DBs/CSVs:
#   python v2/browser/build_league_db.py 2025
#   python v2/browser/build_edm_db.py
#   python v2/browser/build_goalies_db.py
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
cp "$SRC/generated/browser/goalies.db"            "$DST/goalies.db"
cp "$SRC/2025/generated/edge/player_bursts.csv"   "$DST/2025/player_bursts.csv"

# Guard against shipping an image with missing/empty runtime files (the cause
# of silently-blank skater columns). set -e aborts the deploy prep on failure.
for f in "$DST/2024/league.db" "$DST/2025/league.db" "$DST/2025/edm.db" "$DST/goalies.db" "$DST/2025/player_bursts.csv"; do
    if [[ ! -s "$f" ]]; then
        echo "ERROR: $f is missing or empty — refusing to ship." >&2
        exit 1
    fi
done

# goalies.db must carry BOTH situation cuts — a stale single-cut db would
# blank the 5v5 dropdown in prod while looking superficially healthy.
python3 - "$DST/goalies.db" <<'EOF'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
n = dict(conn.execute(
    "SELECT situation, COUNT(*) FROM goalie_seasons GROUP BY situation"))
assert set(n) == {"all", "5v5"} and min(n.values()) > 0, \
    f"goalies.db situation coverage broken: {n}"
print(f"goalies.db situation coverage OK: {n}")
EOF

# Confirm the burst CSV actually covers this season's skaters (catches empty,
# stale, or wrong-season files before Age/SB-a60/Max-MPH go blank in prod).
python3 "$REPO_ROOT/v2/browser/verify_runtime_data.py" \
    "$DST/2025/player_bursts.csv" "$DST/2025/league.db"

echo "Synced runtime_data:"
ls -lh "$DST/2024" "$DST/2025"
