import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import runtime_paths


def test_goalies_query_parameterized_and_missing_db(tmp_path, monkeypatch):
    # missing file -> empty frame, no exception
    monkeypatch.setattr(runtime_paths, "goalies_db", lambda: tmp_path / "absent.db")
    monkeypatch.setattr(db, "goalies_db", lambda: tmp_path / "absent.db")
    assert db.goalies_query("SELECT 1").empty

    # real file -> parameterized read works
    p = tmp_path / "goalies.db"
    conn = sqlite3.connect(str(p))
    pd.DataFrame({"goalie_id": [9], "name": ["Test Goalie"]}).to_sql(
        "goalie_seasons", conn, index=False)
    conn.close()
    monkeypatch.setattr(db, "goalies_db", lambda: p)
    out = db.goalies_query("SELECT name FROM goalie_seasons WHERE goalie_id = ?", (9,))
    assert out.iloc[0]["name"] == "Test Goalie"
