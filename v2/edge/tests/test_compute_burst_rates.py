"""Tests for v2/edge/compute_burst_rates.py."""

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest


def _make_test_db(tmp_path: Path) -> Path:
    """Create a synthetic league.db with a competition table for tests."""
    db_path = tmp_path / "league.db"
    con = sqlite3.connect(db_path)
    con.execute(
        """
        CREATE TABLE competition (
            gameId INTEGER, playerId INTEGER, team TEXT, position TEXT,
            toi_seconds INTEGER, total_toi_seconds INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TABLE players (
            playerId INTEGER PRIMARY KEY, currentTeamAbbrev TEXT,
            firstName TEXT, lastName TEXT, position TEXT,
            heightInInches INTEGER, weightInPounds INTEGER, shootsCatches TEXT
        )
        """
    )
    rows = [
        # playerId 1: 3 games for EDM
        (2025020001, 1, "EDM", "C", 600, 1200),
        (2025020002, 1, "EDM", "C", 700, 1300),
        (2025020003, 1, "EDM", "C", 650, 1250),
        # playerId 2: 1 game for COL
        (2025020001, 2, "COL", "D", 800, 1500),
        # playerId 3: 2 games for VAN, 1 for FLA (traded)
        (2025020005, 3, "VAN", "L", 500, 900),
        (2025020006, 3, "VAN", "L", 550, 950),
        (2025020010, 3, "FLA", "L", 600, 1000),
    ]
    con.executemany(
        "INSERT INTO competition VALUES (?,?,?,?,?,?)", rows
    )
    con.executemany(
        "INSERT INTO players (playerId, firstName, lastName, position, currentTeamAbbrev) VALUES (?,?,?,?,?)",
        [
            (1, "Test", "One", "C", "EDM"),
            (2, "Test", "Two", "D", "COL"),
            (3, "Test", "Three", "L", "FLA"),
        ],
    )
    con.commit()
    con.close()
    return db_path


def test_list_skater_ids_returns_distinct_skaters(tmp_path):
    from v2.edge.compute_burst_rates import list_skater_ids

    db_path = _make_test_db(tmp_path)
    ids = list_skater_ids(db_path)
    assert sorted(ids) == [1, 2, 3]


def test_get_player_season_totals_aggregates_all_games(tmp_path):
    from v2.edge.compute_burst_rates import get_player_season_totals

    db_path = _make_test_db(tmp_path)
    totals = get_player_season_totals(db_path)
    # playerId 1: 3 games, total_toi 1200+1300+1250 = 3750
    assert totals[1]["gp"] == 3
    assert totals[1]["total_toi_seconds"] == 3750
    # playerId 3: 3 games (2 VAN + 1 FLA), total_toi 900+950+1000 = 2850
    assert totals[3]["gp"] == 3
    assert totals[3]["total_toi_seconds"] == 2850
    # name + position propagated from players table
    assert totals[1]["name"] == "Test One"
    assert totals[1]["position"] == "C"


def test_extract_edge_fields_picks_burst_and_speed():
    from v2.edge.compute_burst_rates import extract_edge_fields

    payload = {
        "player": {"id": 8478402, "team": {"abbrev": "EDM"}, "birthDate": "1997-01-13"},
        "skatingSpeed": {
            "burstsOver20": {"value": 681, "percentile": 1.0,
                             "leagueAvg": {"value": 75.2}},
            "speedMax": {"imperial": 24.6119, "metric": 39.6089},
        },
        "totalDistanceSkated": {"imperial": 330.2671},
    }
    out = extract_edge_fields(payload)
    assert out["bursts_over_20"] == 681
    assert out["speed_max_mph"] == pytest.approx(24.6119)
    assert out["distance_miles"] == pytest.approx(330.2671)
    assert out["current_team"] == "EDM"
    assert out["birth_date"] == "1997-01-13"


def test_extract_edge_fields_returns_none_for_missing_fields():
    from v2.edge.compute_burst_rates import extract_edge_fields

    # Player with no EDGE data — minimal payload
    payload = {"player": {"id": 1, "team": {"abbrev": "XXX"}}}
    out = extract_edge_fields(payload)
    assert out["bursts_over_20"] is None
    assert out["speed_max_mph"] is None
    assert out["distance_miles"] is None
    assert out["current_team"] == "XXX"
    assert out["birth_date"] is None


def test_bursts_per_60_basic():
    from v2.edge.compute_burst_rates import bursts_per_60

    # 681 bursts over 113088 seconds = 21.6787 per 60 min
    assert bursts_per_60(681, 113088) == pytest.approx(21.6787, abs=1e-3)


def test_bursts_per_60_returns_none_when_inputs_missing():
    from v2.edge.compute_burst_rates import bursts_per_60

    assert bursts_per_60(None, 1000) is None
    assert bursts_per_60(50, None) is None
    assert bursts_per_60(50, 0) is None  # avoid div-by-zero


def _write_edge_json(dir_path: Path, player_id: int, bursts: int | None,
                    speed: float | None, team: str = "EDM") -> None:
    payload = {
        "player": {"id": player_id, "team": {"abbrev": team}},
        "skatingSpeed": {},
        "totalDistanceSkated": {},
    }
    if bursts is not None:
        payload["skatingSpeed"]["burstsOver20"] = {"value": bursts}
    if speed is not None:
        payload["skatingSpeed"]["speedMax"] = {"imperial": speed}
    (dir_path / f"{player_id}.json").write_text(json.dumps(payload))


def test_build_burst_table_joins_edge_and_toi(tmp_path):
    from v2.edge.compute_burst_rates import build_burst_table

    db_path = _make_test_db(tmp_path)
    edge_dir = tmp_path / "edge"
    edge_dir.mkdir()
    _write_edge_json(edge_dir, 1, bursts=100, speed=23.5, team="EDM")
    _write_edge_json(edge_dir, 2, bursts=20, speed=21.0, team="COL")
    # playerId 3 has no EDGE file — should still appear in output with Nones

    df = build_burst_table(db_path, edge_dir)

    # All three players present
    assert sorted(df["playerId"].tolist()) == [1, 2, 3]

    p1 = df.set_index("playerId").loc[1]
    # 100 bursts, total_toi 3750s → 100 * 3600 / 3750 = 96.0
    assert p1["bursts_per_60"] == pytest.approx(96.0)
    assert p1["total_toi_seconds"] == 3750
    assert p1["name"] == "Test One"

    p3 = df.set_index("playerId").loc[3]
    assert p3["bursts_per_60"] is None or pd.isna(p3["bursts_per_60"])
