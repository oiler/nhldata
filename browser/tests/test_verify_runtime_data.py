import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from verify_runtime_data import (
    burst_coverage, main, verify_birthdates, verify_burst_csv, verify_tables,
)


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


_BROWSER_TABLES = ["games", "points_5v5", "events_5v5", "onice_5v5", "elite_forwards",
                   "elite_defensemen", "player_metrics", "constants"]


def _add_browser_tables(path, skip=()):
    con = sqlite3.connect(path)
    for t in _BROWSER_TABLES:
        if t not in skip:
            con.execute(f"CREATE TABLE {t} (x INTEGER)")
    con.commit()
    con.close()


def _make_players(path, rows, with_column=True):
    con = sqlite3.connect(path)
    if with_column:
        con.execute("CREATE TABLE players (playerId INTEGER, birthDate TEXT)")
        con.executemany("INSERT INTO players VALUES (?, ?)", rows)
    else:
        con.execute("CREATE TABLE players (playerId INTEGER)")
        con.executemany("INSERT INTO players VALUES (?)", [(r[0],) for r in rows])
    con.commit()
    con.close()


def test_birthdates_ok(tmp_path):
    db = _make_db(tmp_path / "l.db", list(range(20)))
    _make_players(db, [(i, "2000-01-01") for i in range(20)])
    ok, _ = verify_birthdates(db)
    assert ok


def test_birthdates_missing_column(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, None), (2, None)], with_column=False)
    ok, msg = verify_birthdates(db)
    assert not ok
    assert "birthDate" in msg


def test_birthdates_low_coverage(tmp_path):
    db = _make_db(tmp_path / "l.db", list(range(20)))
    _make_players(db, [(i, "2000-01-01") for i in range(18)] + [(18, None), (19, "")])
    ok, msg = verify_birthdates(db)
    assert not ok
    assert "90.0%" in msg


def test_tables_all_present(tmp_path):
    db = _make_db(tmp_path / "l.db", [1])
    _make_players(db, [(1, "2000-01-01")])
    _add_browser_tables(db)
    ok, _ = verify_tables(db)
    assert ok


def test_tables_missing_one(tmp_path):
    db = _make_db(tmp_path / "l.db", [1])
    _make_players(db, [(1, "2000-01-01")])
    _add_browser_tables(db, skip=("points_5v5",))
    ok, msg = verify_tables(db)
    assert not ok
    assert "points_5v5" in msg


def test_main_passes_complete_db(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, "2000-01-01"), (2, "2000-01-01")])
    _add_browser_tables(db)
    csv = _make_csv(tmp_path / "b.csv", [1, 2])
    assert main([str(csv), str(db)]) == 0


def test_main_fails_when_birthdates_fail(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, None), (2, None)], with_column=False)
    _add_browser_tables(db)
    csv = _make_csv(tmp_path / "b.csv", [1, 2])
    assert main([str(csv), str(db)]) == 1


def test_main_fails_on_partial_db(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, "2000-01-01"), (2, "2000-01-01")])
    _add_browser_tables(db, skip=("player_metrics",))
    csv = _make_csv(tmp_path / "b.csv", [1, 2])
    assert main([str(csv), str(db)]) == 1


# Listed here, not read from REQUIRED_TABLES, so dropping a table from the
# code's list fails this test.
_EXPECTED_TABLES = ("competition", "players", "games", "points_5v5", "events_5v5", "onice_5v5",
                    "elite_forwards", "elite_defensemen", "player_metrics", "constants")


@pytest.mark.parametrize("missing", _EXPECTED_TABLES)
def test_tables_each_required_table_is_checked(tmp_path, missing):
    db = _make_db(tmp_path / "l.db", [1])
    _make_players(db, [(1, "2000-01-01")])
    _add_browser_tables(db)
    con = sqlite3.connect(db)
    con.execute(f"DROP TABLE {missing}")
    con.commit()
    con.close()
    ok, msg = verify_tables(db)
    assert not ok
    assert missing in msg


def test_main_stops_at_table_check(tmp_path, capsys):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, "2000-01-01"), (2, "2000-01-01")])
    _add_browser_tables(db, skip=("constants",))
    csv = _make_csv(tmp_path / "b.csv", [1, 2])
    assert main([str(csv), str(db)]) == 1
    out = capsys.readouterr()
    assert "FAIL: league.db missing tables constants" in out.err
    assert "burst coverage" not in out.out + out.err


def test_main_fails_when_bursts_fail(tmp_path, capsys):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, "2000-01-01"), (2, "2000-01-01")])
    _add_browser_tables(db)
    csv = _make_csv(tmp_path / "b.csv", [99])
    assert main([str(csv), str(db)]) == 1
    out = capsys.readouterr()
    assert "FAIL: burst coverage" in out.err
    assert "OK: birthDate coverage" in out.out


def test_birthdates_count_only_skaters(tmp_path):
    db = _make_db(tmp_path / "l.db", list(range(19)))
    con = sqlite3.connect(db)
    con.executemany("INSERT INTO competition VALUES (?, 'G')", [(98,), (99,)])
    con.commit()
    con.close()
    # Counting the two goalies would give 19/21 = 90.5%, below the threshold.
    _make_players(db, [(i, "2000-01-01") for i in range(19)] + [(98, None), (99, None)])
    ok, msg = verify_birthdates(db)
    assert ok, msg


def test_birthdates_no_skaters_fails(tmp_path):
    db = _make_db(tmp_path / "l.db", [])
    _make_players(db, [])
    ok, msg = verify_birthdates(db)
    assert not ok
    assert "no skaters" in msg


def test_birthdates_exactly_at_threshold_passes(tmp_path):
    db = _make_db(tmp_path / "l.db", list(range(20)))
    _make_players(db, [(i, "2000-01-01") for i in range(19)] + [(19, None)])
    ok, msg = verify_birthdates(db)
    assert ok, msg
