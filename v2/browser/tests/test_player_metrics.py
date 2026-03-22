# v2/browser/tests/test_player_metrics.py
import json
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_league_db import (
    build_player_metrics_table, _recover_missing_players,
    build_elite_forwards_table, recompute_pct_vs_elite_fwd,
)


def _setup_db():
    """
    In-memory DB with 4 players:
      Player 1: FLA F, 6 games, 198 lbs / 72 in → PPI = 2.7500
      Player 2: FLA D, 6 games, 220 lbs / 74 in → PPI = 2.9730
      Player 3: EDM→VAN (3+3 games), 180 lbs / 70 in → PPI = 2.5714
      Player 4: EDM F, 3 games only → INELIGIBLE
    Games 1-6 used by players 1 & 2 (FLA).
    Games 11-16 used by player 3 (11-13 = EDM, 14-16 = VAN).
    Games 21-23 used by player 4 (EDM).
    """
    conn = sqlite3.connect(":memory:")
    rows = []
    for game in range(1, 7):
        rows.append({"playerId": 1, "team": "FLA", "gameId": game,      "position": "F", "toi_seconds": 900,  "height_in": 72, "weight_lbs": 198})
        rows.append({"playerId": 2, "team": "FLA", "gameId": game,      "position": "D", "toi_seconds": 1000, "height_in": 74, "weight_lbs": 220})
    for game in range(11, 17):
        team = "EDM" if game <= 13 else "VAN"
        rows.append({"playerId": 3, "team": team,  "gameId": game,      "position": "F", "toi_seconds": 600,  "height_in": 70, "weight_lbs": 180})
    for game in range(21, 24):
        rows.append({"playerId": 4, "team": "EDM", "gameId": game,      "position": "F", "toi_seconds": 400,  "height_in": 68, "weight_lbs": 175})
    df = pd.DataFrame(rows)
    df.to_sql("competition", conn, index=False, if_exists="replace")
    return conn


def test_player_metrics_table_created():
    conn = _setup_db()
    build_player_metrics_table(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "player_metrics" in tables


def test_ppi_calculation():
    conn = _setup_db()
    build_player_metrics_table(conn)
    row = conn.execute("SELECT ppi FROM player_metrics WHERE playerId = 1").fetchone()
    assert row is not None
    assert abs(row[0] - 198 / 72) < 0.001


def test_ineligible_player_excluded():
    conn = _setup_db()
    build_player_metrics_table(conn)
    row = conn.execute("SELECT * FROM player_metrics WHERE playerId = 4").fetchone()
    assert row is None


def test_ppi_plus_mean_is_100():
    conn = _setup_db()
    build_player_metrics_table(conn)
    rows = conn.execute("SELECT ppi_plus FROM player_metrics").fetchall()
    values = [r[0] for r in rows]
    assert len(values) == 3
    assert abs(sum(values) / len(values) - 100.0) < 0.001


def test_wppi_traded_player():
    """
    Player 3 is the only eligible player on EDM (3 games) and VAN (3 games).
    Per-game avg TOI: 600s/game per stint; team avg also 600s/game (only player).
    So share = 1.0 on each team.
    Games-weighted average: wPPI = PPI × (1.0×3 + 1.0×3) / (3+3) = PPI × 1.0.
    """
    conn = _setup_db()
    build_player_metrics_table(conn)
    row = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 3").fetchone()
    assert row is not None
    # games-weighted average of per-game shares across stints
    expected = (180 / 70) * (1.0 * 3 + 1.0 * 3) / (3 + 3)
    assert abs(row[0] - expected) < 0.001


def test_wppi_plus_mean_is_100():
    conn = _setup_db()
    build_player_metrics_table(conn)
    rows = conn.execute("SELECT wppi_plus FROM player_metrics").fetchall()
    values = [r[0] for r in rows]
    assert len(values) == 3
    assert abs(sum(values) / len(values) - 100.0) < 0.001


def test_wppi_per_game_normalization():
    """Players with same TOI/game but different games played get the same wPPI."""
    conn = sqlite3.connect(":memory:")
    rows = []
    # Player 10: FLA F, 8 games, 900s/game
    for game in range(1, 9):
        rows.append({"playerId": 10, "team": "FLA", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    # Player 11: FLA F, 5 games, 900s/game — same per-game rate, fewer games played
    for game in range(11, 16):
        rows.append({"playerId": 11, "team": "FLA", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    df = pd.DataFrame(rows)
    df.to_sql("competition", conn, index=False, if_exists="replace")
    build_player_metrics_table(conn)
    p10 = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 10").fetchone()[0]
    p11 = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 11").fetchone()[0]
    assert abs(p10 - p11) < 0.001


def test_wppi_traded_player_no_inflation():
    """A traded player with the same per-game deployment as a single-team player
    gets the same wPPI — stints are averaged, not summed."""
    conn = sqlite3.connect(":memory:")
    rows = []
    # Player 10: single-team, ANA for 20 games, 900s/game
    for game in range(1, 21):
        rows.append({"playerId": 10, "team": "ANA", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    # Player 11: traded — 10 games on ANA (different gameIds), then 10 games on BOS
    # Same 900s/game deployment as player 10 throughout
    for game in range(101, 111):
        rows.append({"playerId": 11, "team": "ANA", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    for game in range(201, 211):
        rows.append({"playerId": 11, "team": "BOS", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    df = pd.DataFrame(rows)
    df.to_sql("competition", conn, index=False, if_exists="replace")
    build_player_metrics_table(conn)
    p10 = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 10").fetchone()[0]
    p11 = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 11").fetchone()[0]
    assert abs(p10 - p11) < 0.001, f"Traded player inflation: p10={p10:.4f}, p11={p11:.4f}"


def test_avg_toi_share():
    """
    10 FLA skaters per game (5 games each):
      5 high-TOI players: 600s/game each
      5 low-TOI  players: 300s/game each
    team_total = 5×600 + 5×300 = 4500s/game
    game_5v5   = 4500 / 5     =  900s
    high share = 600 / 900    =  2/3
    low  share = 300 / 900    =  1/3
    """
    conn = sqlite3.connect(":memory:")
    rows = []
    for game in range(1, 6):
        for pid in range(1, 6):    # high-TOI players
            rows.append({"playerId": pid, "team": "FLA", "gameId": game,
                         "position": "F", "toi_seconds": 600,
                         "height_in": 72, "weight_lbs": 198})
        for pid in range(6, 11):   # low-TOI players
            rows.append({"playerId": pid, "team": "FLA", "gameId": game,
                         "position": "F", "toi_seconds": 300,
                         "height_in": 72, "weight_lbs": 198})
    df = pd.DataFrame(rows)
    df.to_sql("competition", conn, index=False, if_exists="replace")
    build_player_metrics_table(conn)
    high = conn.execute(
        "SELECT avg_toi_share FROM player_metrics WHERE playerId = 1"
    ).fetchone()[0]
    low = conn.execute(
        "SELECT avg_toi_share FROM player_metrics WHERE playerId = 6"
    ).fetchone()[0]
    assert abs(high - 2/3) < 0.001, f"Expected 0.667, got {high}"
    assert abs(low  - 1/3) < 0.001, f"Expected 0.333, got {low}"


def _setup_recovery_db():
    """In-memory DB with one player in players table, two in competition (one missing)."""
    conn = sqlite3.connect(":memory:")
    pd.DataFrame([
        {"playerId": 1, "firstName": "Existing", "lastName": "Player",
         "currentTeamAbbrev": "FLA", "position": "F", "shootsCatches": "L",
         "heightInInches": 72, "weightInPounds": 198},
    ]).to_sql("players", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 1, "team": "FLA", "gameId": 1, "position": "F", "toi_seconds": 900,
         "height_in": 72, "weight_lbs": 198},
        {"playerId": 99999, "team": "FLA", "gameId": 1, "position": "F", "toi_seconds": 800,
         "height_in": 70, "weight_lbs": 180},
    ]).to_sql("competition", conn, index=False, if_exists="replace")
    return conn


def test_recover_missing_players_from_raw_json(tmp_path, monkeypatch):
    import build_league_db
    conn = _setup_recovery_db()
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    raw = {
        "firstName": {"default": "Test"},
        "lastName": {"default": "Recovered"},
        "currentTeamAbbrev": "FLA",
        "position": "C",
        "shootsCatches": "L",
        "heightInInches": 70,
        "weightInPounds": 180,
    }
    (players_dir / "99999.json").write_text(json.dumps(raw))
    monkeypatch.setattr(build_league_db, "SEASON_DIR", str(tmp_path))

    _recover_missing_players(conn)

    row = conn.execute("SELECT firstName, lastName FROM players WHERE playerId = 99999").fetchone()
    assert row is not None
    assert row[0] == "Test"
    assert row[1] == "Recovered"
    # Original player still intact
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 2


def test_recover_missing_players_no_json_skips(tmp_path, monkeypatch):
    import build_league_db
    conn = _setup_recovery_db()
    # Create players dir but no JSON file for the missing player
    (tmp_path / "players").mkdir()
    monkeypatch.setattr(build_league_db, "SEASON_DIR", str(tmp_path))

    _recover_missing_players(conn)

    # Only the original player remains — no crash, no phantom row
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 1
    assert conn.execute("SELECT * FROM players WHERE playerId = 99999").fetchone() is None


# ---------------------------------------------------------------------------
# Elite Forwards
# ---------------------------------------------------------------------------

def _make_comp_row(pid, team, game, position, toi, total_toi):
    """Build a full competition row with zeros for non-essential columns."""
    return {
        "gameId": game, "playerId": pid, "team": team, "position": position,
        "toi_seconds": toi, "total_toi_seconds": total_toi,
        "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
        "comp_fwd": 0, "comp_def": 0,
        "height_in": 72, "weight_lbs": 198,
        "heaviness": 0, "weighted_forward_heaviness": 0,
        "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0,
    }


def _setup_elite_db():
    """In-memory DB with 2 teams (EDM, COL), 25 games each, 18 skaters per game.

    EDM forwards (pid 1-12):
      F1 (1): toi=900, total=1200, iTOI=75.0%, 15 pts  → P/60=2.40  ELITE rank 1
      F2 (2): toi=850, total=1100, iTOI=77.3%, 12 pts  → P/60=2.03  ELITE rank 2
      F3 (3): toi=800, total=1000, iTOI=80.0%,  8 pts  → P/60=1.44  ELITE rank 3
      F4 (4): toi=820, total=820,  iTOI=100%,  10 pts  → FAILS iTOI (specialist)
      F5-F12 (5-12): toi=500, total=600 — bottom-six (tTOI < 28%)
    EDM defence (pid 13-18): toi=1000, total=1300

    COL forwards (pid 21-32):
      F21 (21): toi=900, total=1200, 15 pts → P/60=2.40  rank 1
      F22 (22): toi=850, total=1100, 12 pts → P/60=2.03  rank 2
      F23 (23): toi=800, total=1000,  8 pts → P/60=1.44  rank 3
      F24 (24): toi=830, total=1050, 11 pts → P/60~1.91  ELITE rank 4 (P/60 >= 1.7)
      F25 (25): toi=810, total=1020,  6 pts → P/60~1.07  rank 5 (P/60 < 1.7, NOT 4th)
      F26-F32 (26-32): toi=500, total=600 — bottom-six
    COL defence (pid 33-38): toi=1000, total=1300
    """
    conn = sqlite3.connect(":memory:")
    comp_rows = []

    # --- EDM: 25 games (gameId 1-25) ---
    for game in range(1, 26):
        # Forwards
        comp_rows.append(_make_comp_row(1, "EDM", game, "F", 900, 1200))
        comp_rows.append(_make_comp_row(2, "EDM", game, "F", 850, 1100))
        comp_rows.append(_make_comp_row(3, "EDM", game, "F", 800, 1000))
        comp_rows.append(_make_comp_row(4, "EDM", game, "F", 820, 820))
        for pid in range(5, 13):
            comp_rows.append(_make_comp_row(pid, "EDM", game, "F", 500, 600))
        # Defence
        for pid in range(13, 19):
            comp_rows.append(_make_comp_row(pid, "EDM", game, "D", 1000, 1300))

    # --- COL: 25 games (gameId 101-125) ---
    for game in range(101, 126):
        comp_rows.append(_make_comp_row(21, "COL", game, "F", 900, 1200))
        comp_rows.append(_make_comp_row(22, "COL", game, "F", 850, 1100))
        comp_rows.append(_make_comp_row(23, "COL", game, "F", 800, 1000))
        comp_rows.append(_make_comp_row(24, "COL", game, "F", 830, 1050))
        comp_rows.append(_make_comp_row(25, "COL", game, "F", 810, 1020))
        for pid in range(26, 33):
            comp_rows.append(_make_comp_row(pid, "COL", game, "F", 500, 600))
        # Defence
        for pid in range(33, 39):
            comp_rows.append(_make_comp_row(pid, "COL", game, "D", 1000, 1300))

    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")

    # --- Points (5v5) ---
    point_rows = []
    # EDM: F1=15pts, F2=12pts, F3=8pts, F4=10pts
    for pid, pts in [(1, 15), (2, 12), (3, 8), (4, 10)]:
        for i in range(pts):
            point_rows.append({"gameId": (i % 25) + 1, "playerId": pid, "goals": 1, "assists": 0, "points": 1})
    # COL: F21=15pts, F22=12pts, F23=8pts, F24=11pts, F25=6pts
    for pid, pts in [(21, 15), (22, 12), (23, 8), (24, 11), (25, 6)]:
        for i in range(pts):
            point_rows.append({"gameId": (i % 25) + 101, "playerId": pid, "goals": 1, "assists": 0, "points": 1})

    pd.DataFrame(point_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    return conn


def test_elite_forwards_table_created():
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "elite_forwards" in tables


def test_elite_forwards_correct_players_selected():
    """EDM should have 3 elite forwards (pid 1,2,3). pid 4 fails iTOI. pid 5-12 fail tTOI."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    edm = conn.execute("SELECT playerId FROM elite_forwards WHERE team = 'EDM' ORDER BY playerId").fetchall()
    assert [r[0] for r in edm] == [1, 2, 3]


def test_elite_forwards_specialist_excluded():
    """pid 4 has tTOI > 28% and P/60 > 1.0 but iTOI = 100% — excluded."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    row = conn.execute("SELECT * FROM elite_forwards WHERE playerId = 4").fetchone()
    assert row is None


def test_elite_forwards_fourth_slot():
    """COL pid 24 gets 4th slot (P/60 = 1.91 >= 1.7). pid 25 does not (P/60 = 1.07 < 1.7)."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    col = conn.execute("SELECT playerId FROM elite_forwards WHERE team = 'COL' ORDER BY playerId").fetchall()
    pids = [r[0] for r in col]
    assert 24 in pids, "pid 24 (P/60 1.91) should get 4th slot"
    assert 25 not in pids, "pid 25 (P/60 1.07) should NOT get 4th slot"


def test_elite_forwards_rank_by_p60():
    """Within EDM, rank 1 = highest P/60 (pid 1), rank 3 = lowest (pid 3)."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    rows = conn.execute("SELECT playerId, rank FROM elite_forwards WHERE team = 'EDM' ORDER BY rank").fetchall()
    assert rows[0] == (1, 1)
    assert rows[1] == (2, 2)
    assert rows[2] == (3, 3)


def test_elite_trade_carryover():
    """Player elite on EDM (25 GP) who also played 3 games on COL should appear as carry-over on COL."""
    conn = _setup_elite_db()
    trade_rows = []
    for game in range(201, 204):
        trade_rows.append({"playerId": 1, "team": "COL", "gameId": game,
                           "position": "F", "toi_seconds": 900, "total_toi_seconds": 1200,
                           "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
                           "comp_fwd": 0, "comp_def": 0, "height_in": 72, "weight_lbs": 198,
                           "heaviness": 0, "weighted_forward_heaviness": 0,
                           "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(trade_rows).to_sql("competition", conn, if_exists="append", index=False)
    build_elite_forwards_table(conn)
    edm_row = conn.execute("SELECT is_carryover FROM elite_forwards WHERE playerId = 1 AND team = 'EDM'").fetchone()
    assert edm_row is not None
    assert edm_row[0] == 0
    col_row = conn.execute("SELECT is_carryover FROM elite_forwards WHERE playerId = 1 AND team = 'COL'").fetchone()
    assert col_row is not None
    assert col_row[0] == 1


def test_recompute_pct_vs_elite_fwd(tmp_path, monkeypatch):
    """
    Game 1001: EDM (away) vs COL (home).
    Away skaters: pid 1 (F, elite), pid 2 (F, elite), pid 4 (F, NOT elite), pid 13 (D), pid 14 (D)
    Home skaters: pid 21 (F, elite), pid 22 (F, elite), pid 26 (F, NOT elite), pid 33 (D), pid 34 (D)

    For away F pid=1: opposing forwards are 21 (elite), 22 (elite), 26 (not) → 2/3
    For home F pid=21: opposing forwards are 1 (elite), 2 (elite), 4 (not) → 2/3
    For away D pid=13: same opposing forwards → 2/3
    """
    import build_league_db

    conn = sqlite3.connect(":memory:")

    # competition table — one game, 10 skaters
    comp_rows = []
    for pid, team, pos in [
        (1, "EDM", "F"), (2, "EDM", "F"), (4, "EDM", "F"), (13, "EDM", "D"), (14, "EDM", "D"),
        (21, "COL", "F"), (22, "COL", "F"), (26, "COL", "F"), (33, "COL", "D"), (34, "COL", "D"),
    ]:
        comp_rows.append({"playerId": pid, "team": team, "gameId": 1001,
                          "position": pos, "toi_seconds": 100,
                          "total_toi_seconds": 120, "pct_vs_top_fwd": 0.0,
                          "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                          "height_in": 72, "weight_lbs": 198,
                          "heaviness": 0, "weighted_forward_heaviness": 0,
                          "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")

    # elite_forwards table — pids 1, 2, 21, 22 are elite
    pd.DataFrame([
        {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1, "is_carryover": 0},
        {"playerId": 2, "team": "EDM", "gp": 25, "toi_min_gp": 14.0,
         "ttoi_pct": 31.0, "itoi_pct": 77.0, "p60": 2.0, "rank": 2, "is_carryover": 0},
        {"playerId": 21, "team": "COL", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1, "is_carryover": 0},
        {"playerId": 22, "team": "COL", "gp": 25, "toi_min_gp": 14.0,
         "ttoi_pct": 31.0, "itoi_pct": 77.0, "p60": 2.0, "rank": 2, "is_carryover": 0},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")

    # Write a minimal timeline CSV — 3 seconds of 5v5 with identical lineups
    timelines_dir = tmp_path / "generated" / "timelines" / "csv"
    timelines_dir.mkdir(parents=True)
    timeline = timelines_dir / "1001.csv"
    timeline.write_text(
        "period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,"
        "awayGoalie,awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters\n"
        "1,0,0,1551,5v5,99,5,1|2|4|13|14,5,98,21|22|26|33|34\n"
        "1,1,1,1551,5v5,99,5,1|2|4|13|14,5,98,21|22|26|33|34\n"
        "1,2,2,1551,5v5,99,5,1|2|4|13|14,5,98,21|22|26|33|34\n"
    )

    monkeypatch.setattr(build_league_db, "SEASON_DIR", str(tmp_path))
    recompute_pct_vs_elite_fwd(conn)

    # Away forward pid=1: opponents are F21 (elite), F22 (elite), F26 (not) → 2/3
    row1 = conn.execute(
        "SELECT pct_vs_top_fwd FROM competition WHERE playerId = 1"
    ).fetchone()
    assert abs(row1[0] - 2/3) < 0.001, f"Expected 0.667, got {row1[0]}"

    # Home forward pid=21: opponents are F1 (elite), F2 (elite), F4 (not) → 2/3
    row21 = conn.execute(
        "SELECT pct_vs_top_fwd FROM competition WHERE playerId = 21"
    ).fetchone()
    assert abs(row21[0] - 2/3) < 0.001, f"Expected 0.667, got {row21[0]}"

    # Defenseman pid=13: same opposing forwards → also 2/3
    row13 = conn.execute(
        "SELECT pct_vs_top_fwd FROM competition WHERE playerId = 13"
    ).fetchone()
    assert abs(row13[0] - 2/3) < 0.001, f"Expected 0.667, got {row13[0]}"
