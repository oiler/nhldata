# v2/browser/db.py
from pathlib import Path
import sqlite3
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # nhl/

_DB_PATHS = {
    "2025": _PROJECT_ROOT / "data" / "2025" / "generated" / "browser" / "edm.db",
    "2024": _PROJECT_ROOT / "data" / "2024" / "generated" / "browser" / "edm.db",
}


def query(season: str, sql: str) -> pd.DataFrame:
    """Run sql against the season DB. Returns empty DataFrame if DB is missing."""
    db_path = _DB_PATHS.get(season)
    if db_path is None or not db_path.exists():
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
