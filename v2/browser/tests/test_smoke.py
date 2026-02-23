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
