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
