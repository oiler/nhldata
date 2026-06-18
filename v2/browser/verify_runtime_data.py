"""Pre-deploy check that the synced player_bursts.csv actually covers the
season's skaters.

tools/sync-runtime-data.sh runs this against the files it copied into
runtime_data/ so an empty, stale, or mismatched burst CSV fails the sync
*before* `fly deploy` — instead of silently shipping blank Age/SB-a60/Max-MPH
columns (the exact failure this guards against).

CLI:  python verify_runtime_data.py <burst_csv> <league_db> [min_overlap]
Exit 0 if coverage is acceptable, 1 otherwise.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

DEFAULT_MIN_OVERLAP = 0.80


def burst_coverage(burst_df: pd.DataFrame, competition_player_ids) -> float:
    """Fraction of competition skaters that have a row in the burst CSV."""
    skaters = set(competition_player_ids)
    if not skaters:
        return 0.0
    have = set(burst_df["playerId"])
    return len(skaters & have) / len(skaters)


def verify_burst_csv(csv_path, db_path, min_overlap: float = DEFAULT_MIN_OVERLAP):
    """Return (ok, message). ok is False when the CSV is missing, empty, or
    covers fewer than `min_overlap` of the league.db's skaters."""
    csv_path, db_path = Path(csv_path), Path(db_path)

    if not csv_path.exists():
        return False, f"missing burst CSV: {csv_path}"

    df = pd.read_csv(csv_path)
    if df.empty:
        return False, f"empty burst CSV: {csv_path}"
    if "playerId" not in df.columns:
        return False, f"burst CSV has no playerId column: {csv_path}"

    con = sqlite3.connect(db_path)
    try:
        ids = pd.read_sql_query(
            "SELECT DISTINCT playerId FROM competition WHERE position IN ('F', 'D')", con
        )["playerId"]
    finally:
        con.close()

    cov = burst_coverage(df, ids)
    if cov < min_overlap:
        return False, (
            f"burst coverage {cov:.1%} below required {min_overlap:.0%} "
            f"({csv_path} vs {db_path}) — stale, empty, or mismatched file"
        )
    return True, f"burst coverage {cov:.1%} ({len(df)} rows)"


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: verify_runtime_data.py <burst_csv> <league_db> [min_overlap]", file=sys.stderr)
        return 2
    min_overlap = float(argv[2]) if len(argv) > 2 else DEFAULT_MIN_OVERLAP
    ok, msg = verify_burst_csv(argv[0], argv[1], min_overlap)
    print(("OK: " if ok else "FAIL: ") + msg, file=sys.stderr if not ok else sys.stdout)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
