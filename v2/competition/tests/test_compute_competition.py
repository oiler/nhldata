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
    required = {"gameId", "playerId", "team", "position", "toi_seconds",
                "comp_fwd", "comp_def", "pct_vs_top_fwd", "pct_vs_top_def",
                "height_in", "weight_lbs", "heaviness",
                "weighted_forward_heaviness", "weighted_defense_heaviness", "weighted_team_heaviness"}
    assert required.issubset(set(rows[0].keys())), f"Missing columns: {required - set(rows[0].keys())}"

    # comp_fwd and comp_def must be non-negative (0.0 is valid for edge cases)
    for row in rows:
        assert float(row["comp_fwd"]) >= 0.0, f"Player {row['playerId']} has negative comp_fwd"
        assert float(row["comp_def"]) >= 0.0, f"Player {row['playerId']} has negative comp_def"

    # position values must be F or D (no goalies in output)
    for row in rows:
        assert row["position"] in {"F", "D"}, f"Unexpected position value: {row['position']}"

    # pct columns must be in [0.0, 1.0]
    for row in rows:
        assert 0.0 <= float(row["pct_vs_top_fwd"]) <= 1.0, \
            f"Player {row['playerId']} pct_vs_top_fwd out of range: {row['pct_vs_top_fwd']}"
        assert 0.0 <= float(row["pct_vs_top_def"]) <= 1.0, \
            f"Player {row['playerId']} pct_vs_top_def out of range: {row['pct_vs_top_def']}"

    # At least one player must have a non-zero pct (catches silent all-zero regressions)
    assert any(float(row["pct_vs_top_fwd"]) > 0.0 for row in rows), \
        "Expected at least one player with non-zero pct_vs_top_fwd"

    # heaviness columns must be >= 0.0; at least one player should have non-zero values
    for row in rows:
        assert float(row["heaviness"]) >= 0.0, \
            f"Player {row['playerId']} has negative heaviness"
        assert float(row["weighted_forward_heaviness"]) >= 0.0, \
            f"Player {row['playerId']} has negative weighted_forward_heaviness"
        assert float(row["weighted_defense_heaviness"]) >= 0.0, \
            f"Player {row['playerId']} has negative weighted_defense_heaviness"
        assert float(row["weighted_team_heaviness"]) >= 0.0, \
            f"Player {row['playerId']} has negative weighted_team_heaviness"

    assert any(float(row["heaviness"]) > 0.0 for row in rows), \
        "Expected at least one player with non-zero heaviness"
    assert any(float(row["weighted_team_heaviness"]) > 0.0 for row in rows), \
        "Expected at least one player with non-zero weighted_team_heaviness"


from compute_competition import build_top_competition


def test_build_top_competition_top6_fwd_top4_def():
    """Top-6 forwards and top-4 defensemen selected per team by TOI."""
    toi = {
        # EDM forwards — 17 has lowest TOI, excluded from top-6
        11: 1000, 12: 900, 13: 800, 14: 700, 15: 600, 16: 500, 17: 100,
        # EDM defense — 25 has lowest TOI, excluded from top-4
        21: 1000, 22: 900, 23: 800, 24: 700, 25: 100,
        # FLA forwards
        31: 1000, 32: 900, 33: 800, 34: 700, 35: 600, 36: 500, 37: 100,
        # FLA defense
        41: 1000, 42: 900, 43: 800, 44: 700, 45: 100,
    }
    positions = {
        11: "F", 12: "F", 13: "F", 14: "F", 15: "F", 16: "F", 17: "F",
        21: "D", 22: "D", 23: "D", 24: "D", 25: "D",
        31: "F", 32: "F", 33: "F", 34: "F", 35: "F", 36: "F", 37: "F",
        41: "D", 42: "D", 43: "D", 44: "D", 45: "D",
    }
    teams = {
        11: "EDM", 12: "EDM", 13: "EDM", 14: "EDM", 15: "EDM", 16: "EDM", 17: "EDM",
        21: "EDM", 22: "EDM", 23: "EDM", 24: "EDM", 25: "EDM",
        31: "FLA", 32: "FLA", 33: "FLA", 34: "FLA", 35: "FLA", 36: "FLA", 37: "FLA",
        41: "FLA", 42: "FLA", 43: "FLA", 44: "FLA", 45: "FLA",
    }

    top = build_top_competition(toi, positions, teams)

    assert top["EDM"]["top_fwd"] == {11, 12, 13, 14, 15, 16}  # not 17
    assert top["EDM"]["top_def"] == {21, 22, 23, 24}           # not 25
    assert top["FLA"]["top_fwd"] == {31, 32, 33, 34, 35, 36}  # not 37
    assert top["FLA"]["top_def"] == {41, 42, 43, 44}           # not 45


def test_build_top_competition_fewer_than_threshold():
    """If a team has fewer players than the threshold, all qualify."""
    toi = {1: 500, 2: 400, 3: 300}
    positions = {1: "F", 2: "F", 3: "F"}
    teams = {1: "EDM", 2: "EDM", 3: "EDM"}

    top = build_top_competition(toi, positions, teams)

    assert top["EDM"]["top_fwd"] == {1, 2, 3}
    assert top["EDM"]["top_def"] == set()


from compute_competition import score_game_pct


def test_score_game_pct_single_row():
    rows = [{"situationCode": "1551",
             "awaySkaters": "1|2|3|4|5",
             "homeSkaters": "6|7|20|9|10"}]
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 20: "F", 9: "D", 10: "D",
                 50: "F", 51: "F", 52: "F", 53: "F"}
    teams = {1: "EDM", 2: "EDM", 3: "EDM", 4: "EDM", 5: "EDM",
             6: "FLA", 7: "FLA", 20: "FLA", 9: "FLA", 10: "FLA",
             50: "FLA", 51: "FLA", 52: "FLA", 53: "FLA"}
    # FLA has 7 forwards: {6,7,50,51,52,53,20}. Top-6 by TOI = {6,7,50,51,52,53}; 20 (TOI=100) is excluded.
    # EDM top_fwd = {1,2,3} (only 3 EDM fwds, all qualify), EDM top_def = {4,5}
    toi = {1: 1000, 2: 900, 3: 800, 4: 700, 5: 600,
           6: 1000, 7: 900, 20: 100, 9: 800, 10: 700,
           50: 800, 51: 750, 52: 700, 53: 650}
    top_comp = build_top_competition(toi, positions, teams)

    result = score_game_pct(rows, positions, teams, top_comp)

    # Away player 1: opp fwds on ice = [6, 7, 20]; in top_fwd: 6 and 7 → 2/3
    assert abs(result[1]["pct_vs_top_fwd"] - 2/3) < 0.001
    assert abs(result[1]["pct_vs_top_def"] - 1.0) < 0.001

    # Home player 6: opp fwds [1,2,3], all in EDM top_fwd (EDM has only 3 fwds) → 1.0
    assert abs(result[6]["pct_vs_top_fwd"] - 1.0) < 0.001
    assert abs(result[6]["pct_vs_top_def"] - 1.0) < 0.001


def test_score_game_pct_skips_non_5v5():
    rows = [
        {"situationCode": "1441", "awaySkaters": "1|2|3|4",   "homeSkaters": "6|7|8|9"},
        {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|20|9|10"},
    ]
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 20: "F", 9: "D", 10: "D",
                 8: "F",
                 50: "F", 51: "F", 52: "F", 53: "F"}
    teams = {1: "EDM", 2: "EDM", 3: "EDM", 4: "EDM", 5: "EDM",
             6: "FLA", 7: "FLA", 20: "FLA", 8: "FLA", 9: "FLA", 10: "FLA",
             50: "FLA", 51: "FLA", 52: "FLA", 53: "FLA"}
    toi = {1: 1000, 2: 900, 3: 800, 4: 700, 5: 600,
           6: 1000, 7: 900, 20: 100, 9: 800, 10: 700,
           50: 800, 51: 750, 52: 700, 53: 650}
    top_comp = build_top_competition(toi, positions, teams)

    result = score_game_pct(rows, positions, teams, top_comp)

    # Player 5 only appears in the 1551 row — must be in result
    assert 5 in result
    # Player 1 appears in both rows but only 1551 is scored — opp fwds [6,7,20], 2 of 3 in top_fwd
    assert abs(result[1]["pct_vs_top_fwd"] - 2/3) < 0.001


from compute_competition import load_player_physicals, compute_heaviness


def test_load_player_physicals_returns_height_weight():
    """Load height/weight for a known player from real data files.

    NOTE: Must be run from project root (data/ is relative to cwd).
    Uses Connor McDavid (8478402) as a known stable test case.
    """
    physicals = load_player_physicals([8478402], "2025")
    assert 8478402 in physicals
    assert physicals[8478402]["height_in"] > 0
    assert physicals[8478402]["weight_lbs"] > 0


def test_load_player_physicals_missing_player_skipped():
    """A player ID with no file is silently skipped, not an error."""
    physicals = load_player_physicals([999999999], "2025")
    assert 999999999 not in physicals


def test_compute_heaviness_200lbs_72in():
    """200 / 72 = 2.7778"""
    assert abs(compute_heaviness(72, 200) - 200 / 72) < 0.0001


def test_compute_heaviness_zero_height_returns_zero():
    """Guard against division by zero when height is missing."""
    assert compute_heaviness(0, 200) == 0.0


from compute_competition import compute_team_heaviness


def test_compute_team_heaviness_toi_weighted_average():
    """Team heaviness is the TOI-weighted mean split by position."""
    toi       = {1: 600, 2: 300, 3: 500}
    positions = {1: "F", 2: "F", 3: "D"}
    teams     = {1: "EDM", 2: "EDM", 3: "EDM"}
    physicals = {
        1: {"height_in": 72, "weight_lbs": 200},
        2: {"height_in": 74, "weight_lbs": 220},
        3: {"height_in": 76, "weight_lbs": 230},
    }
    result = compute_team_heaviness(toi, positions, teams, physicals)
    h1, h2, h3 = 200 / 72, 220 / 74, 230 / 76
    expected_fwd = (h1 * 600 + h2 * 300) / (600 + 300)
    expected_def = h3  # only one D
    expected_all = (h1 * 600 + h2 * 300 + h3 * 500) / (600 + 300 + 500)
    assert abs(result["EDM"]["fwd"] - expected_fwd) < 0.0001
    assert abs(result["EDM"]["def"] - expected_def) < 0.0001
    assert abs(result["EDM"]["all"] - expected_all) < 0.0001


def test_compute_team_heaviness_skips_missing_physicals():
    """Players with no physicals entry are excluded from the average."""
    toi       = {1: 600, 2: 300}
    positions = {1: "F", 2: "F"}
    teams     = {1: "EDM", 2: "EDM"}
    physicals = {1: {"height_in": 72, "weight_lbs": 200}}  # player 2 absent
    result    = compute_team_heaviness(toi, positions, teams, physicals)
    assert abs(result["EDM"]["fwd"] - 200 / 72) < 0.0001
    assert abs(result["EDM"]["all"] - 200 / 72) < 0.0001


def test_compute_team_heaviness_skips_goalies():
    """Goalies are excluded even if they have physicals."""
    toi       = {1: 600, 99: 1200}
    positions = {1: "F", 99: "G"}
    teams     = {1: "EDM", 99: "EDM"}
    physicals = {
        1:  {"height_in": 72, "weight_lbs": 200},
        99: {"height_in": 75, "weight_lbs": 215},
    }
    result = compute_team_heaviness(toi, positions, teams, physicals)
    assert abs(result["EDM"]["fwd"] - 200 / 72) < 0.0001
    assert result["EDM"]["def"] == 0.0  # no D skaters
    assert abs(result["EDM"]["all"] - 200 / 72) < 0.0001


def test_compute_team_heaviness_two_teams():
    """Produces separate entries for each team."""
    toi       = {1: 600, 2: 600}
    positions = {1: "F", 2: "F"}
    teams     = {1: "EDM", 2: "CGY"}
    physicals = {
        1: {"height_in": 72, "weight_lbs": 200},
        2: {"height_in": 76, "weight_lbs": 240},
    }
    result = compute_team_heaviness(toi, positions, teams, physicals)
    assert abs(result["EDM"]["fwd"] - 200 / 72) < 0.0001
    assert abs(result["CGY"]["fwd"] - 240 / 76) < 0.0001
