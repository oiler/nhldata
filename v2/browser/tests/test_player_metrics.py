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
    build_elite_defensemen_table, recompute_pct_vs_elite_def,
    backfill_vs_elite_def_to_forwards,
    _read_old_elites, _log_elite_changes,
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
      F3 (3): toi=800, total=1000, iTOI=80.0%,  8 pts  → P/60=1.44  FAILS P/60 (< 2.0)
      F4 (4): toi=820, total=820,  iTOI=100%,  10 pts  → FAILS iTOI (specialist)
      F5-F12 (5-12): toi=500, total=600 — bottom-six (tTOI < 28%)
    EDM defence (pid 13-18): toi=1000, total=1300

    COL forwards (pid 21-32):
      F21 (21): toi=900, total=1200, 15 pts → P/60=2.40  rank 1
      F22 (22): toi=850, total=1100, 12 pts → P/60=2.03  rank 2
      F23 (23): toi=800, total=1000,  8 pts → P/60=1.44  FAILS P/60 (< 2.0)
      F24 (24): toi=830, total=1050, 11 pts → P/60~1.91  FAILS P/60 (< 2.0)
      F25 (25): toi=810, total=1020,  6 pts → P/60~1.07  FAILS P/60 (< 2.0)
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
    """EDM should have 2 elite forwards (pid 1,2). pid 3 fails P/60. pid 4 fails iTOI. pid 5-12 fail tTOI."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    edm = conn.execute("SELECT playerId FROM elite_forwards WHERE team = 'EDM' ORDER BY playerId").fetchall()
    assert [r[0] for r in edm] == [1, 2]


def test_elite_forwards_specialist_excluded():
    """pid 4 has tTOI > 28% but iTOI = 100% — excluded."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    row = conn.execute("SELECT * FROM elite_forwards WHERE playerId = 4").fetchone()
    assert row is None


def test_elite_forwards_p60_threshold():
    """COL pid 23 (P/60=1.44), pid 24 (P/60=1.91), pid 25 (P/60=1.07) all fail P/60 >= 2.0."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    col = conn.execute("SELECT playerId FROM elite_forwards WHERE team = 'COL' ORDER BY playerId").fetchall()
    pids = [r[0] for r in col]
    assert pids == [21, 22], f"Only pid 21,22 should pass P/60 >= 2.0, got {pids}"


def test_elite_forwards_rank_by_p60():
    """Within EDM, rank 1 = highest P/60 (pid 1), rank 2 = next (pid 2)."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    rows = conn.execute("SELECT playerId, rank FROM elite_forwards WHERE team = 'EDM' ORDER BY rank").fetchall()
    assert rows[0] == (1, 1)
    assert rows[1] == (2, 2)


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


# ---------------------------------------------------------------------------
# Elite Defensemen
# ---------------------------------------------------------------------------

def _setup_elite_def_db():
    """In-memory DB with 3 teams (TMA, TMB, TMC), 25 games each, defensemen
    designed to test production/deployment/full-elite designation paths.

    TMA — separate production + deployment (gap > 1.5pp):
      D1 (213): toi=1100, total=1500 (iTOI=73.3%), pct_vs_top_fwd=0.30, 12 pts → P/60=1.57. Production elite.
      D2 (214): toi=1050, total=1200 (iTOI=87.5%), pct_vs_top_fwd=0.32. Deployment elite (fails prod: iTOI>=83).
      Gap = 2.0pp → too large for full elite.
      D3 (215): toi=1000, total=1200 (iTOI=83.3%), pct_vs_top_fwd=0.15, 10 pts. Fails iTOI for production.
      12 forwards (201-212): toi=700, total=850
      3 more D (216-218): toi=800, total=950 — below 33% tTOI

    TMB — full elite via gap rule (gap < 1.5pp):
      D1 (313): toi=1100, total=1500 (iTOI=73.3%), pct_vs_top_fwd=0.34, 12 pts → P/60=1.57. Production elite.
      D2 (314): toi=1000, total=1200 (iTOI=83.3%), pct_vs_top_fwd=0.35. Deployment elite (highest vs_ef).
      Gap = 1.0pp → pair plays together → 313 promoted to full elite.
      12 forwards (301-312): toi=700, total=850
      4 more D (315-318): toi=900, total=1100 — below 33% tTOI

    TMC — no production elite (deployment only):
      D1 (413): toi=1050, total=1200 (iTOI=87.5%), pct_vs_top_fwd=0.28. Deployment only (fails prod: iTOI>=83).
      D2 (414): toi=1000, total=1200 (iTOI=83.3%), pct_vs_top_fwd=0.20. Fails everything.
      12 forwards (401-412): toi=700, total=850
      4 more D (415-418): toi=800, total=950
    """
    conn = sqlite3.connect(":memory:")
    comp_rows = []

    # --- TMA: 25 games (gameId 1-25) ---
    for game in range(1, 26):
        # 12 forwards
        for pid in range(201, 213):
            comp_rows.append(_make_comp_row(pid, "TMA", game, "F", 700, 850))
        # D1 (213): production elite candidate
        comp_rows.append(_make_comp_row(213, "TMA", game, "D", 1100, 1500))
        # D2 (214): deployment elite candidate (iTOI=87.5%)
        comp_rows.append(_make_comp_row(214, "TMA", game, "D", 1050, 1200))
        # D3 (215): iTOI=83.3% — fails production
        comp_rows.append(_make_comp_row(215, "TMA", game, "D", 1000, 1200))
        # D4-D6 (216-218): low tTOI
        for pid in range(216, 219):
            comp_rows.append(_make_comp_row(pid, "TMA", game, "D", 800, 950))

    # --- TMB: 25 games (gameId 101-125) ---
    for game in range(101, 126):
        for pid in range(301, 313):
            comp_rows.append(_make_comp_row(pid, "TMB", game, "F", 700, 850))
        # D1 (313): full elite candidate
        comp_rows.append(_make_comp_row(313, "TMB", game, "D", 1100, 1500))
        # D2 (314): iTOI=83.3% — fails production
        comp_rows.append(_make_comp_row(314, "TMB", game, "D", 1000, 1200))
        # D3-D6 (315-318): low tTOI
        for pid in range(315, 319):
            comp_rows.append(_make_comp_row(pid, "TMB", game, "D", 900, 1100))

    # --- TMC: 25 games (gameId 201-225) ---
    for game in range(201, 226):
        for pid in range(401, 413):
            comp_rows.append(_make_comp_row(pid, "TMC", game, "F", 700, 850))
        # D1 (413): deployment only (iTOI=87.5%)
        comp_rows.append(_make_comp_row(413, "TMC", game, "D", 1050, 1200))
        # D2 (414): fails everything (iTOI=83.3%)
        comp_rows.append(_make_comp_row(414, "TMC", game, "D", 1000, 1200))
        # D3-D6 (415-418): low tTOI
        for pid in range(415, 419):
            comp_rows.append(_make_comp_row(pid, "TMC", game, "D", 800, 950))

    df = pd.DataFrame(comp_rows)
    # Set pct_any_elite_fwd values for deployment selection (binary metric)
    df["pct_any_elite_fwd"] = 0.0
    df.loc[df["playerId"] == 213, "pct_any_elite_fwd"] = 0.30
    df.loc[df["playerId"] == 214, "pct_any_elite_fwd"] = 0.32
    df.loc[df["playerId"] == 215, "pct_any_elite_fwd"] = 0.15
    df.loc[df["playerId"] == 313, "pct_any_elite_fwd"] = 0.34
    df.loc[df["playerId"] == 314, "pct_any_elite_fwd"] = 0.35
    df.loc[df["playerId"] == 413, "pct_any_elite_fwd"] = 0.28
    df.loc[df["playerId"] == 414, "pct_any_elite_fwd"] = 0.20
    df.to_sql("competition", conn, index=False, if_exists="replace")

    # --- Points (5v5) ---
    point_rows = []
    # TMA D1 (213): 12 pts
    for i in range(12):
        point_rows.append({"gameId": (i % 25) + 1, "playerId": 213,
                           "goals": 1, "assists": 0, "points": 1})
    # TMB D1 (313): 12 pts
    for i in range(12):
        point_rows.append({"gameId": (i % 25) + 101, "playerId": 313,
                           "goals": 1, "assists": 0, "points": 1})
    # TMA D3 (215): 10 pts
    for i in range(10):
        point_rows.append({"gameId": (i % 25) + 1, "playerId": 215,
                           "goals": 1, "assists": 0, "points": 1})
    pd.DataFrame(point_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    return conn


def test_elite_defensemen_table_created():
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "elite_defensemen" in tables


def test_elite_def_production_selected():
    """TMA pid 213 is production elite (iTOI=73.3%, P/60=1.57). pid 214 is not (iTOI=100%)."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row213 = conn.execute(
        "SELECT is_production FROM elite_defensemen WHERE playerId = 213"
    ).fetchone()
    assert row213 is not None
    assert row213[0] == 1
    row214 = conn.execute(
        "SELECT is_production FROM elite_defensemen WHERE playerId = 214"
    ).fetchone()
    # 214 may or may not be in the table, but if present, is_production must be 0
    if row214 is not None:
        assert row214[0] == 0


def test_elite_def_deployment_selected():
    """TMA pid 214 has highest vs_ef (0.32) among D with tTOI>=33. pid 213 does not get deployment."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row214 = conn.execute(
        "SELECT is_deployment FROM elite_defensemen WHERE playerId = 214"
    ).fetchone()
    assert row214 is not None
    assert row214[0] == 1
    row213 = conn.execute(
        "SELECT is_deployment FROM elite_defensemen WHERE playerId = 213"
    ).fetchone()
    assert row213 is not None
    assert row213[0] == 0


def test_elite_def_full_elite():
    """TMB pid 313 is production elite with vs_ef gap < 1.5pp to deployment elite (314) → is_full_elite=1."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row = conn.execute(
        "SELECT is_production, is_deployment, is_full_elite FROM elite_defensemen WHERE playerId = 313"
    ).fetchone()
    assert row is not None
    assert row[0] == 1  # is_production
    assert row[1] == 0  # is_deployment (314 has highest vs_ef)
    assert row[2] == 1  # is_full_elite (gap = 1.0pp < 1.5pp)


def test_elite_def_gap_too_large():
    """TMA pid 213 is production elite but gap to deployment elite (214) is 2.0pp > 1.5pp → NOT full elite."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row = conn.execute(
        "SELECT is_production, is_deployment, is_full_elite FROM elite_defensemen WHERE playerId = 213"
    ).fetchone()
    assert row is not None
    assert row[0] == 1  # is_production
    assert row[1] == 0  # is_deployment
    assert row[2] == 0  # NOT full elite (gap too large)


def test_elite_def_no_production():
    """TMC has 0 production elite, 1 deployment elite (pid 413)."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    prod = conn.execute(
        "SELECT COUNT(*) FROM elite_defensemen WHERE team = 'TMC' AND is_production = 1"
    ).fetchone()[0]
    assert prod == 0
    dep = conn.execute(
        "SELECT COUNT(*) FROM elite_defensemen WHERE team = 'TMC' AND is_deployment = 1"
    ).fetchone()[0]
    assert dep == 1
    dep_pid = conn.execute(
        "SELECT playerId FROM elite_defensemen WHERE team = 'TMC' AND is_deployment = 1"
    ).fetchone()[0]
    assert dep_pid == 413


def test_elite_def_itoi_filter():
    """pid 214 (iTOI=87.5%) excluded from production despite having tTOI and vs_ef."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row = conn.execute(
        "SELECT is_production FROM elite_defensemen WHERE playerId = 214"
    ).fetchone()
    assert row is not None
    assert row[0] == 0, "iTOI=100% should disqualify from production"


def test_recompute_pct_vs_elite_def(tmp_path, monkeypatch):
    """
    Game 2001: TMA (away) vs TMB (home).
    Away skaters: 3F (201,202,203) + D213 (deployment elite) + D214 (not elite)
    Home skaters: 3F (301,302,303) + D313 (deployment elite) + D314 (not elite)

    For any away skater: opposing D are 313 (elite) and 314 (not) → fraction = 1/2
    For any home skater: opposing D are 213 (elite) and 214 (not) → fraction = 1/2
    """
    import build_league_db

    conn = sqlite3.connect(":memory:")

    # competition table — one game, 10 skaters
    comp_rows = []
    for pid, team, pos in [
        (201, "TMA", "F"), (202, "TMA", "F"), (203, "TMA", "F"),
        (213, "TMA", "D"), (214, "TMA", "D"),
        (301, "TMB", "F"), (302, "TMB", "F"), (303, "TMB", "F"),
        (313, "TMB", "D"), (314, "TMB", "D"),
    ]:
        comp_rows.append({"playerId": pid, "team": team, "gameId": 2001,
                          "position": pos, "toi_seconds": 100,
                          "total_toi_seconds": 120, "pct_vs_top_fwd": 0.0,
                          "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                          "height_in": 72, "weight_lbs": 198,
                          "heaviness": 0, "weighted_forward_heaviness": 0,
                          "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")

    # elite_defensemen table — 213 and 313 are deployment elite
    pd.DataFrame([
        {"playerId": 213, "team": "TMA", "gp": 25, "toi_min_gp": 18.0,
         "ttoi_pct": 40.0, "itoi_pct": 73.0, "p60": 1.5, "vs_ef_pct": 0.30,
         "is_production": 1, "is_deployment": 1, "is_full_elite": 1, "rank": 1, "is_carryover": 0},
        {"playerId": 313, "team": "TMB", "gp": 25, "toi_min_gp": 18.0,
         "ttoi_pct": 40.0, "itoi_pct": 73.0, "p60": 1.5, "vs_ef_pct": 0.35,
         "is_production": 1, "is_deployment": 1, "is_full_elite": 1, "rank": 1, "is_carryover": 0},
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")

    # Write a minimal timeline CSV — 3 seconds of 5v5 with identical lineups
    timelines_dir = tmp_path / "generated" / "timelines" / "csv"
    timelines_dir.mkdir(parents=True)
    timeline = timelines_dir / "2001.csv"
    timeline.write_text(
        "period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,"
        "awayGoalie,awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters\n"
        "1,0,0,1551,5v5,99,5,201|202|203|213|214,5,98,301|302|303|313|314\n"
        "1,1,1,1551,5v5,99,5,201|202|203|213|214,5,98,301|302|303|313|314\n"
        "1,2,2,1551,5v5,99,5,201|202|203|213|214,5,98,301|302|303|313|314\n"
    )

    monkeypatch.setattr(build_league_db, "SEASON_DIR", str(tmp_path))
    recompute_pct_vs_elite_def(conn)

    # Away forward pid=201: opposing D are 313 (elite), 314 (not) → 1/2
    row201 = conn.execute(
        "SELECT pct_vs_top_def FROM competition WHERE playerId = 201"
    ).fetchone()
    assert abs(row201[0] - 0.5) < 0.001, f"Expected 0.5, got {row201[0]}"

    # Home forward pid=301: opposing D are 213 (elite), 214 (not) → 1/2
    row301 = conn.execute(
        "SELECT pct_vs_top_def FROM competition WHERE playerId = 301"
    ).fetchone()
    assert abs(row301[0] - 0.5) < 0.001, f"Expected 0.5, got {row301[0]}"

    # Away D pid=213: opposing D are 313 (elite), 314 (not) → 1/2
    row213 = conn.execute(
        "SELECT pct_vs_top_def FROM competition WHERE playerId = 213"
    ).fetchone()
    assert abs(row213[0] - 0.5) < 0.001, f"Expected 0.5, got {row213[0]}"

    # Binary metric: every second has at least one elite D → pct_any_elite_def = 1.0
    bin201 = conn.execute(
        "SELECT pct_any_elite_def FROM competition WHERE playerId = 201"
    ).fetchone()
    assert abs(bin201[0] - 1.0) < 0.001, f"Expected 1.0, got {bin201[0]}"


def test_pct_any_elite_def_binary_metric(tmp_path, monkeypatch):
    """Binary metric: 2 seconds with elite D present, 2 without → 0.5."""
    import build_league_db

    conn = sqlite3.connect(":memory:")

    comp_rows = []
    for pid, team, pos in [
        (501, "AAA", "F"), (502, "AAA", "F"), (503, "AAA", "D"), (504, "AAA", "D"),
        (601, "BBB", "F"), (602, "BBB", "F"), (603, "BBB", "D"), (604, "BBB", "D"),
    ]:
        comp_rows.append({"playerId": pid, "team": team, "gameId": 3001,
                          "position": pos, "toi_seconds": 100,
                          "total_toi_seconds": 120, "pct_vs_top_fwd": 0.0,
                          "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                          "height_in": 72, "weight_lbs": 198,
                          "heaviness": 0, "weighted_forward_heaviness": 0,
                          "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")

    # Only pid 603 is deployment elite (not 604)
    pd.DataFrame([
        {"playerId": 603, "team": "BBB", "gp": 25, "toi_min_gp": 18.0,
         "ttoi_pct": 40.0, "itoi_pct": 73.0, "p60": 1.5, "vs_ef_pct": 0.30,
         "is_production": 0, "is_deployment": 1, "is_full_elite": 0, "rank": 0, "is_carryover": 0},
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")

    # Timeline: 2 seconds with elite D (603) on ice, 2 seconds without
    timelines_dir = tmp_path / "generated" / "timelines" / "csv"
    timelines_dir.mkdir(parents=True)
    (timelines_dir / "3001.csv").write_text(
        "period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,"
        "awayGoalie,awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters\n"
        "1,0,0,1551,5v5,99,4,501|502|503|504,4,98,601|602|603|604\n"
        "1,1,1,1551,5v5,99,4,501|502|503|504,4,98,601|602|603|604\n"
        "1,2,2,1551,5v5,99,4,501|502|503|504,4,98,601|602|604|605\n"
        "1,3,3,1551,5v5,99,4,501|502|503|504,4,98,601|602|604|605\n"
    )

    monkeypatch.setattr(build_league_db, "SEASON_DIR", str(tmp_path))
    recompute_pct_vs_elite_def(conn)

    # Away F pid=501: 2 seconds facing D 603(elite)+604, 2 seconds facing D 604+605(neither elite)
    row = conn.execute(
        "SELECT pct_any_elite_def FROM competition WHERE playerId = 501"
    ).fetchone()
    assert abs(row[0] - 0.5) < 0.001, f"Expected 0.5, got {row[0]}"


def test_backfill_vs_elite_def_to_forwards():
    """backfill_vs_elite_def_to_forwards adds vs_ed_pct column to elite_forwards."""
    conn = sqlite3.connect(":memory:")

    # competition with pct_any_elite_def already set
    comp_rows = []
    for game in range(1, 4):
        comp_rows.append({"playerId": 1, "team": "EDM", "gameId": game,
                          "position": "F", "toi_seconds": 900,
                          "total_toi_seconds": 1200, "pct_vs_top_fwd": 0.0,
                          "pct_vs_top_def": 0.0, "pct_any_elite_def": 0.6,
                          "comp_fwd": 0, "comp_def": 0, "height_in": 72, "weight_lbs": 198,
                          "heaviness": 0, "weighted_forward_heaviness": 0,
                          "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")

    # elite_forwards table
    pd.DataFrame([
        {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1, "is_carryover": 0},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")

    backfill_vs_elite_def_to_forwards(conn)

    row = conn.execute("SELECT vs_ed_pct FROM elite_forwards WHERE playerId = 1").fetchone()
    assert row is not None
    assert abs(row[0] - 0.6) < 0.001, f"Expected 0.6, got {row[0]}"


# ---------------------------------------------------------------------------
# Elite Changelog
# ---------------------------------------------------------------------------

def test_read_old_elites_from_existing_db(tmp_path):
    """_read_old_elites returns DataFrames of primary elite players from an existing DB."""
    db_path = tmp_path / "league.db"
    conn = sqlite3.connect(str(db_path))
    pd.DataFrame([
        {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1,
         "is_carryover": 0, "vs_ed_pct": 0.5},
        {"playerId": 2, "team": "EDM", "gp": 25, "toi_min_gp": 14.0,
         "ttoi_pct": 31.0, "itoi_pct": 77.0, "p60": 2.0, "rank": 2,
         "is_carryover": 0, "vs_ed_pct": 0.4},
        {"playerId": 1, "team": "COL", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 0,
         "is_carryover": 1, "vs_ed_pct": 0.5},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 10, "team": "EDM", "gp": 25, "toi_min_gp": 22.0,
         "ttoi_pct": 40.0, "itoi_pct": 73.0, "p60": 1.5, "vs_ef_pct": 0.30,
         "is_production": 1, "is_deployment": 1, "is_full_elite": 1,
         "rank": 1, "is_carryover": 0},
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 1, "firstName": "Connor", "lastName": "McDavid",
         "currentTeamAbbrev": "EDM", "position": "F", "shootsCatches": "L",
         "heightInInches": 73, "weightInPounds": 194},
        {"playerId": 2, "firstName": "Leon", "lastName": "Draisaitl",
         "currentTeamAbbrev": "EDM", "position": "F", "shootsCatches": "L",
         "heightInInches": 74, "weightInPounds": 208},
        {"playerId": 10, "firstName": "Evan", "lastName": "Bouchard",
         "currentTeamAbbrev": "EDM", "position": "D", "shootsCatches": "R",
         "heightInInches": 74, "weightInPounds": 197},
    ]).to_sql("players", conn, index=False, if_exists="replace")
    conn.close()

    old_fwd, old_def = _read_old_elites(str(db_path))
    # Should exclude carry-over rows
    assert len(old_fwd) == 2
    assert set(old_fwd["playerId"]) == {1, 2}
    assert len(old_def) == 1
    assert old_def.iloc[0]["playerId"] == 10
    assert old_def.iloc[0]["type"] == "Full Elite"


def test_read_old_elites_no_db():
    """_read_old_elites returns empty DataFrames when DB doesn't exist."""
    old_fwd, old_def = _read_old_elites("/nonexistent/path/league.db")
    assert old_fwd.empty
    assert old_def.empty


def test_elite_changelog_addition(tmp_path):
    """New elite player appears as 'added' in changelog CSV."""
    csv_path = tmp_path / "elite_changelog.csv"
    # Old: pid 1 only
    old_fwd = pd.DataFrame([
        {"playerId": 1, "playerName": "Connor McDavid", "team": "EDM"},
    ])
    old_def = pd.DataFrame(columns=["playerId", "playerName", "team", "type"])

    # New DB: pid 1 + pid 2
    conn = sqlite3.connect(":memory:")
    pd.DataFrame([
        {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1,
         "is_carryover": 0, "vs_ed_pct": 0.5},
        {"playerId": 2, "team": "EDM", "gp": 25, "toi_min_gp": 14.0,
         "ttoi_pct": 31.0, "itoi_pct": 77.0, "p60": 2.0, "rank": 2,
         "is_carryover": 0, "vs_ed_pct": 0.4},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
        "p60", "vs_ef_pct", "is_production", "is_deployment", "is_full_elite",
        "rank", "is_carryover",
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 1, "firstName": "Connor", "lastName": "McDavid",
         "currentTeamAbbrev": "EDM", "position": "F", "shootsCatches": "L",
         "heightInInches": 73, "weightInPounds": 194},
        {"playerId": 2, "firstName": "Leon", "lastName": "Draisaitl",
         "currentTeamAbbrev": "EDM", "position": "F", "shootsCatches": "L",
         "heightInInches": 74, "weightInPounds": 208},
    ]).to_sql("players", conn, index=False, if_exists="replace")

    _log_elite_changes(old_fwd, old_def, conn, str(csv_path))
    conn.close()

    result = pd.read_csv(str(csv_path))
    assert len(result) == 1
    assert result.iloc[0]["playerId"] == 2
    assert result.iloc[0]["playerName"] == "Leon Draisaitl"
    assert result.iloc[0]["action"] == "added"
    assert result.iloc[0]["position"] == "F"


def test_elite_changelog_removal(tmp_path):
    """Removed elite player appears as 'removed' in changelog CSV."""
    csv_path = tmp_path / "elite_changelog.csv"
    # Old: pid 1 + pid 2
    old_fwd = pd.DataFrame([
        {"playerId": 1, "playerName": "Connor McDavid", "team": "EDM"},
        {"playerId": 2, "playerName": "Leon Draisaitl", "team": "EDM"},
    ])
    old_def = pd.DataFrame(columns=["playerId", "playerName", "team", "type"])

    # New DB: pid 1 only
    conn = sqlite3.connect(":memory:")
    pd.DataFrame([
        {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1,
         "is_carryover": 0, "vs_ed_pct": 0.5},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
        "p60", "vs_ef_pct", "is_production", "is_deployment", "is_full_elite",
        "rank", "is_carryover",
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 1, "firstName": "Connor", "lastName": "McDavid",
         "currentTeamAbbrev": "EDM", "position": "F", "shootsCatches": "L",
         "heightInInches": 73, "weightInPounds": 194},
    ]).to_sql("players", conn, index=False, if_exists="replace")

    _log_elite_changes(old_fwd, old_def, conn, str(csv_path))
    conn.close()

    result = pd.read_csv(str(csv_path))
    assert len(result) == 1
    assert result.iloc[0]["playerId"] == 2
    assert result.iloc[0]["action"] == "removed"


def test_elite_changelog_no_changes(tmp_path):
    """No CSV created when elite sets are identical."""
    csv_path = tmp_path / "elite_changelog.csv"
    old_fwd = pd.DataFrame([
        {"playerId": 1, "playerName": "Connor McDavid", "team": "EDM"},
    ])
    old_def = pd.DataFrame(columns=["playerId", "playerName", "team", "type"])

    conn = sqlite3.connect(":memory:")
    pd.DataFrame([
        {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1,
         "is_carryover": 0, "vs_ed_pct": 0.5},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
        "p60", "vs_ef_pct", "is_production", "is_deployment", "is_full_elite",
        "rank", "is_carryover",
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 1, "firstName": "Connor", "lastName": "McDavid",
         "currentTeamAbbrev": "EDM", "position": "F", "shootsCatches": "L",
         "heightInInches": 73, "weightInPounds": 194},
    ]).to_sql("players", conn, index=False, if_exists="replace")

    _log_elite_changes(old_fwd, old_def, conn, str(csv_path))
    conn.close()

    assert not csv_path.exists()


def test_elite_changelog_def_type_change(tmp_path):
    """Defenseman changing designation (Production → Full Elite) logged as type change."""
    csv_path = tmp_path / "elite_changelog.csv"
    old_fwd = pd.DataFrame(columns=["playerId", "playerName", "team"])
    old_def = pd.DataFrame([
        {"playerId": 10, "playerName": "Evan Bouchard", "team": "EDM", "type": "Production"},
    ])

    conn = sqlite3.connect(":memory:")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
        "p60", "rank", "is_carryover", "vs_ed_pct",
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 10, "team": "EDM", "gp": 25, "toi_min_gp": 22.0,
         "ttoi_pct": 40.0, "itoi_pct": 73.0, "p60": 1.5, "vs_ef_pct": 0.30,
         "is_production": 1, "is_deployment": 1, "is_full_elite": 1,
         "rank": 1, "is_carryover": 0},
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 10, "firstName": "Evan", "lastName": "Bouchard",
         "currentTeamAbbrev": "EDM", "position": "D", "shootsCatches": "R",
         "heightInInches": 74, "weightInPounds": 197},
    ]).to_sql("players", conn, index=False, if_exists="replace")

    _log_elite_changes(old_fwd, old_def, conn, str(csv_path))
    conn.close()

    result = pd.read_csv(str(csv_path))
    assert len(result) == 1
    assert result.iloc[0]["playerId"] == 10
    assert result.iloc[0]["action"] == "Production → Full Elite"
    assert result.iloc[0]["position"] == "D"


def test_elite_changelog_appends(tmp_path):
    """Subsequent runs append to existing CSV, not overwrite."""
    csv_path = tmp_path / "elite_changelog.csv"
    # Pre-populate CSV with one row
    pd.DataFrame([{
        "date": "2026-03-22", "playerId": 99, "playerName": "Old Entry",
        "team": "TOR", "position": "F", "type": "Elite", "action": "added",
    }]).to_csv(str(csv_path), index=False)

    # Run with a new addition
    old_fwd = pd.DataFrame(columns=["playerId", "playerName", "team"])
    old_def = pd.DataFrame(columns=["playerId", "playerName", "team", "type"])

    conn = sqlite3.connect(":memory:")
    pd.DataFrame([
        {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1,
         "is_carryover": 0, "vs_ed_pct": 0.5},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
        "p60", "vs_ef_pct", "is_production", "is_deployment", "is_full_elite",
        "rank", "is_carryover",
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 1, "firstName": "Connor", "lastName": "McDavid",
         "currentTeamAbbrev": "EDM", "position": "F", "shootsCatches": "L",
         "heightInInches": 73, "weightInPounds": 194},
    ]).to_sql("players", conn, index=False, if_exists="replace")

    _log_elite_changes(old_fwd, old_def, conn, str(csv_path))
    conn.close()

    result = pd.read_csv(str(csv_path))
    assert len(result) == 2  # old row + new addition
    assert result.iloc[0]["playerName"] == "Old Entry"
    assert result.iloc[1]["playerName"] == "Connor McDavid"
