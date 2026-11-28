# browser/tests/test_smoke.py

import pytest


def test_db_import():
    """db module is importable."""
    from browser import db  # noqa: F401


def test_query_returns_dataframe():
    """query() always returns a DataFrame, even for missing DB."""
    import pandas as pd
    from browser.db import query
    result = query("2099", "SELECT 1")  # season with no DB
    assert isinstance(result, pd.DataFrame)


def test_app_initializes():
    """App object exists and has a layout."""
    import browser.app as app_module
    assert app_module.app is not None
    assert app_module.app.layout is not None


def test_pages_registered():
    """Home and Games pages are in the page registry."""
    import dash
    import browser.app as _  # noqa: F401 — triggers page discovery
    paths = [p["relative_path"] for p in dash.page_registry.values()]
    assert "/" in paths, "Home page not registered"
    assert "/games" in paths, "Games page not registered"


@pytest.mark.requires_data
def test_league_db_exists():
    """league.db has been built and contains the three expected tables."""
    from pathlib import Path
    db_path = Path(__file__).resolve().parents[2] / "data" / "2025" / "generated" / "browser" / "league.db"
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
    from browser.db import league_query
    result = league_query("SELECT 1", season="2099")  # nonexistent season
    assert isinstance(result, pd.DataFrame)


def test_skaters_page_registered():
    """Skaters page is registered at /skaters."""
    import dash
    import browser.app as _  # noqa: F401
    paths = [p["relative_path"] for p in dash.page_registry.values()]
    assert "/skaters" in paths, "Skaters page not registered"


def test_team_page_registered():
    """Team page is registered with path template /team/<abbrev>."""
    import dash
    import browser.app as _  # noqa: F401
    templates = [p.get("path_template", "") for p in dash.page_registry.values()]
    assert "/team/<abbrev>" in templates, "Team page not registered"


def test_game_page_registered():
    """Game page is registered with path template /game/<game_id>."""
    import dash
    import browser.app as _  # noqa: F401
    templates = [p.get("path_template", "") for p in dash.page_registry.values()]
    assert "/game/<game_id>" in templates, "Game page not registered"


def test_pages_declare_a_phone_viewport():
    # Without it, phones lay the page out about 980px wide and shrink it, so no
    # phone-width CSS applies and the header and tables are out of reach.
    import browser.app as app_module
    html = app_module.app.server.test_client().get("/").get_data(as_text=True)
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
