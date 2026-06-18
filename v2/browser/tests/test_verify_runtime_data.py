import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from verify_runtime_data import burst_coverage, verify_burst_csv


def _make_db(path, player_ids):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE competition (playerId INTEGER, position TEXT)")
    con.executemany("INSERT INTO competition VALUES (?, 'F')", [(i,) for i in player_ids])
    con.commit()
    con.close()
    return path


def _make_csv(path, player_ids):
    n = len(player_ids)
    pd.DataFrame({
        "playerId": player_ids,
        "bursts_per_60": [1.0] * n,
        "speed_max_mph": [20.0] * n,
        "birth_date": ["2000-01-01"] * n,
    }).to_csv(path, index=False)
    return path


def test_burst_coverage_full():
    assert burst_coverage(pd.DataFrame({"playerId": [1, 2, 3]}), [1, 2, 3]) == 1.0


def test_burst_coverage_partial():
    assert burst_coverage(pd.DataFrame({"playerId": [1, 2]}), [1, 2, 3, 4]) == 0.5


def test_burst_coverage_no_skaters():
    assert burst_coverage(pd.DataFrame({"playerId": [1]}), []) == 0.0


def test_verify_passes_full_coverage(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2, 3])
    csv = _make_csv(tmp_path / "b.csv", [1, 2, 3])
    ok, msg = verify_burst_csv(csv, db)
    assert ok, msg


def test_verify_fails_missing_csv(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2, 3])
    ok, msg = verify_burst_csv(tmp_path / "nope.csv", db)
    assert not ok
    assert "missing" in msg.lower()


def test_verify_fails_empty_csv(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2, 3])
    csv = _make_csv(tmp_path / "b.csv", [])
    ok, msg = verify_burst_csv(csv, db)
    assert not ok
    assert "empty" in msg.lower()


def test_verify_fails_low_coverage_stale_file(tmp_path):
    db = _make_db(tmp_path / "l.db", list(range(1, 11)))  # 10 skaters
    csv = _make_csv(tmp_path / "b.csv", [1, 2])           # only 2 covered = 20%
    ok, msg = verify_burst_csv(csv, db, min_overlap=0.8)
    assert not ok
    assert "coverage" in msg.lower()
