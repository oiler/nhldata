# browser/db.py
import sqlite3
import pandas as pd

from runtime_paths import league_db, edm_db, goalies_db
from seasons import DEFAULT_SEASON, SEASONS


def query(season: str, sql: str) -> pd.DataFrame:
    """Run sql against the season DB. Returns empty DataFrame if DB is missing.

    IMPORTANT: Only pass string literals as sql. Never interpolate user input.
    """
    db_path = edm_db(season)
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def available_teams(season: str) -> list[str]:
    """Return sorted list of team abbreviations found in the season DB."""
    df = query(season, "SELECT DISTINCT opponent FROM games ORDER BY opponent")
    if df.empty:
        return []
    return df["opponent"].tolist()


def league_query(sql: str, params=(), season: str = DEFAULT_SEASON) -> pd.DataFrame:
    """Run parameterized sql against the league DB. Returns empty DataFrame if DB is missing.

    IMPORTANT: Only pass string literals as sql. Never interpolate user input.
    """
    db_path = league_db(season)
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(sql, conn, params=list(params))
    finally:
        conn.close()


def all_teams(season: str = DEFAULT_SEASON) -> list[str]:
    """Return sorted list of all team abbreviations present in the competition table."""
    df = league_query("SELECT DISTINCT team FROM competition ORDER BY team", season=season)
    if df.empty:
        return []
    return df["team"].tolist()


def goalies_query(sql: str, params=()) -> pd.DataFrame:
    """Run parameterized sql against the cross-season goalies DB.

    IMPORTANT: Only pass string literals as sql. Never interpolate user input.
    """
    db_path = goalies_db()
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(sql, conn, params=list(params))
    finally:
        conn.close()


_META_SQL = """
SELECT firstName, lastName, currentTeamAbbrev, position
FROM players WHERE playerId = ?
"""


def player_meta(pid: int, seasons=SEASONS):
    """Newest season's players row for `pid`, or None if no season has it."""
    for season in reversed(seasons):
        df = league_query(_META_SQL, params=(pid,), season=season)
        if not df.empty:
            return df.iloc[0]
    return None
