# v2/browser/tests/test_smoke.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_db_import():
    """db module is importable."""
    import db  # noqa: F401


def test_query_returns_dataframe():
    """query() always returns a DataFrame, even for missing DB."""
    import pandas as pd
    from db import query
    result = query("2099", "SELECT 1")  # season with no DB
    assert isinstance(result, pd.DataFrame)


def test_app_initializes():
    """App object exists and has a layout."""
    import app as app_module
    assert app_module.app is not None
    assert app_module.app.layout is not None


def test_pages_registered():
    """Home and Games pages are in the page registry."""
    import dash
    import app as _  # noqa: F401 — triggers page discovery
    paths = [p["relative_path"] for p in dash.page_registry.values()]
    assert "/" in paths, "Home page not registered"
    assert "/games" in paths, "Games page not registered"


def test_league_db_exists():
    """league.db has been built and contains the three expected tables."""
    from pathlib import Path
    db_path = Path(__file__).resolve().parents[3] / "data" / "2025" / "generated" / "browser" / "league.db"
    assert db_path.exists(), f"league.db not found at {db_path}. Run build_league_db.py first."
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "competition" in tables
    assert "players" in tables
    assert "games" in tables
    assert "player_metrics" in tables


def test_league_query_returns_dataframe():
    """league_query() always returns a DataFrame, even for missing DB."""
    import pandas as pd
    from db import league_query
    result = league_query("SELECT 1", season="2099")  # nonexistent season
    assert isinstance(result, pd.DataFrame)


def test_skaters_page_registered():
    """Skaters page is registered at /skaters."""
    import dash
    import app as _  # noqa: F401
    paths = [p["relative_path"] for p in dash.page_registry.values()]
    assert "/skaters" in paths, "Skaters page not registered"


def test_team_page_registered():
    """Team page is registered with path template /team/<abbrev>."""
    import dash
    import app as _  # noqa: F401
    templates = [p.get("path_template", "") for p in dash.page_registry.values()]
    assert "/team/<abbrev>" in templates, "Team page not registered"


def test_game_page_registered():
    """Game page is registered with path template /game/<game_id>."""
    import dash
    import app as _  # noqa: F401
    templates = [p.get("path_template", "") for p in dash.page_registry.values()]
    assert "/game/<game_id>" in templates, "Game page not registered"
