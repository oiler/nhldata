#!/usr/bin/env bash
# Bring the laptop's data/ up to date with mininet, the machine that runs the
# daily pipeline (Decision Queue D76).
#
#   pull  every season folder, mininet -> laptop. mininet is the only writer
#         of data/<season>/, and the laptop's copy is a read-only mirror.
#   push  data/generated/, laptop -> mininet. The laptop is the only writer of
#         the cross-season research outputs, such as goalies.db.
#
# Nothing is ever deleted on either side. Files that exist only in the
# laptop's season folders are listed, so they can be looked at.
#
# Run it by hand, before a deploy or before reading current data:
#   ./pipeline/mirror-data.sh             # mirror
#   ./pipeline/mirror-data.sh --dry-run   # show what would change
#
# Tailscale must be connected, and may ask for a browser check.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${NHL_MIRROR_HOST:-mininet}"
# Relative to the home folder on mininet.
REMOTE="${NHL_MIRROR_REMOTE:-nhl-data}"
# Always the repository's data/, never $NHL_DATA_DIR: that variable points
# laptop work at a scratch copy, and the mirror must not land there.
LOCAL="${NHL_MIRROR_LOCAL:-$REPO_ROOT/data}"

DRY=()
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY=(--dry-run)
    echo "DRY RUN: nothing will be copied"
elif [[ $# -gt 0 ]]; then
    echo "usage: $0 [--dry-run]" >&2
    exit 2
fi

# build_league_db.py deletes league.db and rebuilds it, so a copy taken while
# the pipeline runs could hold a partial database.
state="$(ssh "$HOST" systemctl --user is-active nhl-pipeline.service || true)"
case "$state" in
    active|activating)
        echo "ERROR: the pipeline is running on $HOST ($state). Try again when it finishes." >&2
        exit 1 ;;
    inactive|failed) ;;
    *)
        echo "ERROR: couldn't read the pipeline's state on $HOST (got '$state')." >&2
        exit 1 ;;
esac
if [[ "$state" == "failed" ]]; then
    echo "WARNING: the last pipeline run on $HOST failed. See: journalctl --user -u nhl-pipeline.service" >&2
fi

# Until the runner sends its own notification, this is how a missed run shows.
newest="$(ssh "$HOST" "ls $REMOTE/*/logs/20??-??-??.md 2>/dev/null | sed 's#.*/##; s#\.md\$##' | sort | tail -1")"
if [[ "$newest" == "$(date +%F)" ]]; then
    echo "mininet's newest run log: $newest (today)"
else
    echo "WARNING: mininet's newest run log is ${newest:-missing}, not today's. The daily run may not have happened." >&2
fi

echo "pull: $HOST:$REMOTE/ -> $LOCAL/ (season folders)"
rsync -a --stats ${DRY[@]+"${DRY[@]}"} --exclude '/generated/' "$HOST:$REMOTE/" "$LOCAL/" | grep -E '^(Number of|Total transferred)' || true

echo "push: $LOCAL/generated/ -> $HOST:$REMOTE/generated/"
rsync -a --stats ${DRY[@]+"${DRY[@]}"} "$LOCAL/generated/" "$HOST:$REMOTE/generated/" | grep -E '^(Number of|Total transferred)' || true

# Season folders that mininet has: a file in one of them that only the laptop
# has was written here, against the one-writer rule, or predates the move.
only_here="$(ssh "$HOST" "ls -d $REMOTE/[0-9][0-9][0-9][0-9] 2>/dev/null | sed 's#.*/##'" | while read -r season; do
    rsync -a --dry-run --delete --itemize-changes "$HOST:$REMOTE/$season/" "$LOCAL/$season/" \
        | sed -n "s#^\*deleting  *#$season/#p"
done | sort -u)"
if [[ -n "$only_here" ]]; then
    count="$(printf '%s\n' "$only_here" | wc -l | tr -d ' ')"
    echo "NOTE: $count path(s) exist only on the laptop, in season folders mininet owns:"
    printf '%s\n' "$only_here" | head -20 | sed 's/^/  /'
    [[ "$count" -gt 20 ]] && echo "  ... and $((count - 20)) more"
fi
echo "done"
