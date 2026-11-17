#!/usr/bin/env bash
# Copy the runtime files the deployed app reads from the data/ pipeline tree
# into v2/browser/runtime_data/ so the Docker build can pick them up.
#
# Seasons come in two tiers:
#   required — any missing or failing file refuses the deploy (exit non-zero),
#              and the last good copy in runtime_data/ stays untouched.
#   optional — a missing or failing file leaves the season out of the image
#              with one WARNING line; the browser shows it as not available.
# Rollover: a season leaving the required tier moves to OPTIONAL_SEASONS,
# never out of both lists.
#
# Run after rebuilding any of the source DBs/CSVs:
#   python v2/browser/build_league_db.py 2025
#   python v2/browser/build_league_db.py 2026
#   python v2/browser/build_edm_db.py
#   python v2/browser/build_goalies_db.py
#   ./tools/sync-runtime-data.sh
#   fly deploy
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# SYNC_SRC/SYNC_DST exist for the tests (tests/test_sync_runtime_data.py).
SRC="${SYNC_SRC:-$REPO_ROOT/data}"
DST="${SYNC_DST:-$REPO_ROOT/v2/browser/runtime_data}"
VERIFY="$REPO_ROOT/v2/browser/verify_runtime_data.py"
if [[ -n "${SYNC_SRC:-}${SYNC_DST:-}" ]]; then
    echo "NOTE: SYNC_SRC/SYNC_DST override in effect" >&2
fi
echo "sync: $SRC -> $DST"

REQUIRED_SEASONS=("2025")
OPTIONAL_SEASONS=("2026")

# Everything is staged under one temp dir and checked there. runtime_data/
# changes only after every required check passes, so a failed sync leaves the
# last good required files untouched. The trap removes the staging area on any
# exit, including Ctrl-C.
STAGE_ROOT="$(mktemp -d)"
trap 'rm -rf "$STAGE_ROOT"' EXIT

# Stage a season's league.db and player_bursts.csv and run every check there.
# On success print the staging dir; on failure print the reason and return 1.
stage_season() {
    local season="$1" stage out
    stage="$(mktemp -d "$STAGE_ROOT/$season.XXXXXX")"
    if ! cp "$SRC/$season/generated/browser/league.db" "$stage/league.db" 2>/dev/null \
       || ! cp "$SRC/$season/generated/edge/player_bursts.csv" "$stage/player_bursts.csv" 2>/dev/null; then
        echo "league.db or player_bursts.csv is missing"
        return 1
    fi
    if [[ ! -s "$stage/league.db" || ! -s "$stage/player_bursts.csv" ]]; then
        echo "league.db or player_bursts.csv is empty"
        return 1
    fi
    if ! out="$(python3 "$VERIFY" "$stage/player_bursts.csv" "$stage/league.db" 2>&1)"; then
        echo "${out//$'\n'/; }"
        return 1
    fi
    echo "$stage"
}

# 1. Required seasons: stage and check, without touching runtime_data/.
# ${arr[@]+"${arr[@]}"} keeps an empty list from tripping set -u on bash 3.2.
required_staged=""
for season in ${REQUIRED_SEASONS[@]+"${REQUIRED_SEASONS[@]}"}; do
    if ! result="$(stage_season "$season")"; then
        echo "ERROR: required season $season failed: $result — refusing to ship. runtime_data/ is unchanged." >&2
        exit 1
    fi
    required_staged="$required_staged $season=$result"
done

# 2. Files outside the season tiers: named explicitly, all required, staged
# and checked the same way.
OTHER="$STAGE_ROOT/other"
mkdir -p "$OTHER/2024" "$OTHER/2025"
for pair in "2024/generated/browser/league.db:2024/league.db" \
            "2025/generated/browser/edm.db:2025/edm.db" \
            "generated/browser/goalies.db:goalies.db"; do
    from="${pair%%:*}"; to="${pair#*:}"
    if ! cp "$SRC/$from" "$OTHER/$to" 2>/dev/null || [[ ! -s "$OTHER/$to" ]]; then
        echo "ERROR: $SRC/$from is missing or empty — refusing to ship. runtime_data/ is unchanged." >&2
        exit 1
    fi
done

# goalies.db must carry BOTH situation cuts — a stale single-cut db would
# blank the 5v5 dropdown in prod while looking superficially healthy.
if ! python3 - "$OTHER/goalies.db" <<'EOF'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
n = dict(conn.execute(
    "SELECT situation, COUNT(*) FROM goalie_seasons GROUP BY situation"))
assert set(n) == {"all", "5v5"} and min(n.values()) > 0, \
    f"goalies.db situation coverage broken: {n}"
print(f"goalies.db situation coverage OK: {n}")
EOF
then
    echo "ERROR: goalies.db failed its check — refusing to ship. runtime_data/ is unchanged." >&2
    exit 1
fi

# 3. Every required check passed: replace the required files.
for entry in $required_staged; do
    season="${entry%%=*}"; stage="${entry#*=}"
    mkdir -p "$DST/$season"
    mv "$stage/league.db" "$stage/player_bursts.csv" "$DST/$season/"
done
mkdir -p "$DST/2024" "$DST/2025"
mv "$OTHER/2024/league.db" "$DST/2024/league.db"
mv "$OTHER/2025/edm.db"    "$DST/2025/edm.db"
mv "$OTHER/goalies.db"     "$DST/goalies.db"

# 4. Optional seasons: any earlier copy is removed first, so a stale season
# never ships beside a failed one.
shipped=""
skipped=""
for season in ${OPTIONAL_SEASONS[@]+"${OPTIONAL_SEASONS[@]}"}; do
    rm -rf "${DST:?}/$season"
    if result="$(stage_season "$season")"; then
        mkdir -p "$DST/$season"
        mv "$result/league.db" "$result/player_bursts.csv" "$DST/$season/"
        shipped="$shipped, $season (optional)"
    else
        echo "WARNING: $season not synced — $result. The browser will show it as not available." >&2
        skipped="$skipped $season"
    fi
done

echo "Synced runtime_data:"
ls -lh "$DST"/*/
echo "Seasons in image: ${REQUIRED_SEASONS[*]} (required)${shipped}${skipped:+ | skipped:$skipped}"
