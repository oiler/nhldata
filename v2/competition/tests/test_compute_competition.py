# v2/competition/tests/test_compute_competition.py
import csv
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compute_competition import build_lookups


def test_build_lookups_positions():
    plays_data = {
        "homeTeam": {"id": 1, "abbrev": "EDM"},
        "awayTeam": {"id": 2, "abbrev": "CGY"},
        "rosterSpots": [
            {"playerId": 100, "positionCode": "C",  "teamId": 1},
            {"playerId": 200, "positionCode": "L",  "teamId": 1},
            {"playerId": 300, "positionCode": "R",  "teamId": 2},
            {"playerId": 400, "positionCode": "D",  "teamId": 2},
            {"playerId": 500, "positionCode": "G",  "teamId": 1},
        ],
    }
    positions, teams = build_lookups(plays_data)

    assert positions[100] == "F"  # C → F
    assert positions[200] == "F"  # L → F
    assert positions[300] == "F"  # R → F
    assert positions[400] == "D"  # D → D
    assert positions[500] == "G"  # G kept as-is


def test_build_lookups_teams():
    plays_data = {
        "homeTeam": {"id": 1, "abbrev": "EDM"},
        "awayTeam": {"id": 2, "abbrev": "CGY"},
        "rosterSpots": [
            {"playerId": 100, "positionCode": "C", "teamId": 1},
            {"playerId": 400, "positionCode": "D", "teamId": 2},
        ],
    }
    positions, teams = build_lookups(plays_data)

    assert teams[100] == "EDM"
    assert teams[400] == "CGY"


def test_build_lookups_unknown_position_defaults_to_forward():
    plays_data = {
        "homeTeam": {"id": 1, "abbrev": "EDM"},
        "awayTeam": {"id": 2, "abbrev": "CGY"},
        "rosterSpots": [
            {"playerId": 999, "positionCode": "X", "teamId": 1},  # unknown code
            {"playerId": 998, "teamId": 1},                        # missing key
        ],
    }
    positions, teams = build_lookups(plays_data)
    assert positions[999] == "F", "Unknown code should default to F"
    assert positions[998] == "F", "Missing positionCode should default to F"


from compute_competition import compute_game_toi


def test_compute_game_toi_counts_seconds():
    # 3 identical rows — each player should accumulate 3 seconds
    row = {
        "situationCode": "1551",
        "awaySkaters": "1|2|3|4|5",
        "homeSkaters": "6|7|8|9|10",
    }
    rows = [row, row, row]
    toi = compute_game_toi(rows)

    for pid in range(1, 11):
        assert toi[pid] == 3, f"Player {pid} expected 3s, got {toi.get(pid)}"


def test_compute_game_toi_ignores_non_5v5():
    rows = [
        {"situationCode": "1441", "awaySkaters": "1|2|3|4",   "homeSkaters": "6|7|8|9"},
        {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|8|9|10"},
    ]
    toi = compute_game_toi(rows)

    # Player 5 and 10 only appear in the 1551 row → 1 second each
    assert toi.get(5) == 1
    assert toi.get(10) == 1
    # Players 1-4 and 6-9 appear in both rows but only 1551 is scored → 1 second each
    assert toi.get(1) == 1


from compute_competition import score_game


def test_score_game_single_row():
    rows = [{
        "situationCode": "1551",
        "awaySkaters": "1|2|3|4|5",
        "homeSkaters": "6|7|8|9|10",
    }]
    toi = {1: 10, 2: 8, 3: 6, 4: 12, 5: 9,
           6: 20, 7: 15, 8: 5, 9: 18, 10: 14}
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 8: "F", 9: "D", 10: "D"}

    result = score_game(rows, toi, positions)

    # Away player 1: opp fwd mean=(20+15+5)/3, opp def mean=(18+14)/2
    assert abs(result[1]["comp_fwd"] - 40/3) < 0.001
    assert abs(result[1]["comp_def"] - 16.0) < 0.001

    # Home player 6: opp fwd mean=(10+8+6)/3, opp def mean=(12+9)/2
    assert abs(result[6]["comp_fwd"] - 8.0) < 0.001
    assert abs(result[6]["comp_def"] - 10.5) < 0.001


def test_score_game_skips_non_5v5():
    rows = [
        {"situationCode": "1441", "awaySkaters": "1|2|3|4",   "homeSkaters": "6|7|8|9"},
        {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|8|9|10"},
    ]
    toi = {i: 10 for i in range(1, 11)}
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 8: "F", 9: "D", 10: "D"}

    result = score_game(rows, toi, positions)

    # Player 5 only appears in the 1551 row, so result should exist
    assert 5 in result
    assert 1 in result
    # Score only reflects the 1551 row (3 opposing forwards each at 10s)
    assert abs(result[5]["comp_fwd"] - (10 + 10 + 10) / 3) < 0.001


from compute_competition import run_game


def test_run_game_produces_output():
    """Integration test using real 2025 game data.

    NOTE: This test must be run from the project root (the directory containing data/)
    because DATA_DIR = Path("data") is relative to the working directory.
    """
    game_number = 1
    season = "2025"
    output_path = Path("data/2025/generated/competition/2025020001.csv")

    # Clean up before test
    if output_path.exists():
        output_path.unlink()

    run_game(game_number, season)

    assert output_path.exists(), "Output CSV was not created"

    with open(output_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) > 0, "Output CSV is empty"

    # Check required columns
    required = {"gameId", "playerId", "team", "position", "toi_seconds", "comp_fwd", "comp_def"}
    assert required.issubset(set(rows[0].keys())), f"Missing columns: {required - set(rows[0].keys())}"

    # comp_fwd and comp_def must be non-negative (0.0 is valid for edge cases)
    for row in rows:
        assert float(row["comp_fwd"]) >= 0.0, f"Player {row['playerId']} has negative comp_fwd"
        assert float(row["comp_def"]) >= 0.0, f"Player {row['playerId']} has negative comp_def"

    # position values must be F or D (no goalies in output)
    for row in rows:
        assert row["position"] in {"F", "D"}, f"Unexpected position value: {row['position']}"
