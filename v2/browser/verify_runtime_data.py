"""Pre-deploy checks on a season's synced runtime files.

tools/sync-runtime-data.sh runs this against each season's staged files so a
bad season fails the sync *before* `fly deploy`:

- league.db has every table the browser reads (a build that died partway
  leaves a file that passes the other checks but breaks pages);
- player_bursts.csv covers the season's skaters (an empty, stale, or
  mismatched CSV would ship blank SB/a60 and Max MPH columns);
- players.birthDate exists and covers the skaters (the skaters Age column
  reads it).

CLI:  python verify_runtime_data.py <burst_csv> <league_db> [min_overlap]
Exit 0 if every check passes, 1 otherwise.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

DEFAULT_MIN_OVERLAP = 0.80

DEFAULT_MIN_BIRTHDATE_COVERAGE = 0.95

# Every table a browser page reads. Keep in sync with FROM/JOIN targets under pages/.
REQUIRED_TABLES = ("competition", "players", "games", "points_5v5", "events_5v5", "onice_5v5",
                   "elite_forwards", "elite_defensemen", "player_metrics", "constants")


def verify_tables(db_path):
    """Return (ok, message). ok is False when any table the browser reads is
    missing: a build that died partway (timeout, exception, or a sync during
    the 08:00 rebuild) leaves a file that passes the coverage checks."""
    con = sqlite3.connect(db_path)
    try:
        have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    missing = [t for t in REQUIRED_TABLES if t not in have]
    if missing:
        return False, f"league.db missing tables {', '.join(missing)}: {db_path} — partial or failed build"
    return True, "all browser tables present"


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


def verify_birthdates(db_path, min_coverage: float = DEFAULT_MIN_BIRTHDATE_COVERAGE):
    """Return (ok, message). ok is False when players has no birthDate column
    (a league.db built before the column existed) or fewer than `min_coverage`
    of competition skaters have one."""
    db_path = Path(db_path)
    con = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(players)")}
        if "birthDate" not in cols:
            return False, f"players table has no birthDate column: {db_path} — rebuild with build_league_db.py"
        skaters = set(pd.read_sql_query(
            "SELECT DISTINCT playerId FROM competition WHERE position IN ('F', 'D')", con
        )["playerId"])
        have = set(pd.read_sql_query(
            "SELECT playerId FROM players WHERE birthDate IS NOT NULL AND birthDate != ''", con
        )["playerId"])
    finally:
        con.close()

    if not skaters:
        return False, f"no skaters in competition: {db_path}"
    cov = len(skaters & have) / len(skaters)
    if cov < min_coverage:
        return False, f"birthDate coverage {cov:.1%} below required {min_coverage:.0%} ({db_path})"
    return True, f"birthDate coverage {cov:.1%}"


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: verify_runtime_data.py <burst_csv> <league_db> [min_overlap]", file=sys.stderr)
        return 2
    min_overlap = float(argv[2]) if len(argv) > 2 else DEFAULT_MIN_OVERLAP
    ok, msg = verify_tables(argv[1])
    if not ok:
        print("FAIL: " + msg, file=sys.stderr)
        return 1
    results = [verify_burst_csv(argv[0], argv[1], min_overlap), verify_birthdates(argv[1])]
    for ok, msg in results:
        print(("OK: " if ok else "FAIL: ") + msg, file=sys.stdout if ok else sys.stderr)
    return 0 if all(ok for ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
