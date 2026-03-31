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
    Per-game avg TOI: 600s/game; team_toi per game = 600s (only skater on team).
    avg_toi_share = mean(5 × 600 / 600) = 5.0 across all 6 games.

    New formula: wPPI = (PPI - mean_PPI) × avg_toi_share.
    mean_PPI = mean(198/72, 220/74, 180/70) across the 3 eligible players.
    wPPI = (180/70 - mean_PPI) × 5.0
    """
    conn = _setup_db()
    build_player_metrics_table(conn)
    row = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 3").fetchone()
    assert row is not None
    ppi_p3 = 180 / 70
    mean_ppi = (198 / 72 + 220 / 74 + 180 / 70) / 3
    avg_toi_share = 5.0  # 5 × 600 / 600 = 5.0 per game
    expected = (ppi_p3 - mean_ppi) * avg_toi_share
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

def _make_comp_row(pid, team, game, position, toi, total_toi, line_number=None, deployment_score=None):
    """Build a full competition row with zeros for non-essential columns."""
    return {
        "gameId": game, "playerId": pid, "team": team, "position": position,
        "toi_seconds": toi, "total_toi_seconds": total_toi,
        "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
        "comp_fwd": 0, "comp_def": 0,
        "height_in": 72, "weight_lbs": 198,
        "heaviness": 0, "weighted_forward_heaviness": 0,
        "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0,
        "line_number": line_number,
        "deployment_score": deployment_score,
    }


# ---------------------------------------------------------------------------
# Elite Forwards v2
# ---------------------------------------------------------------------------

def _ef_comp_rows(pid, team, games, toi, total_toi, line_number, filler_d_toi):
    """Return competition rows for one target forward + one filler defenseman.

    filler_d_toi is set so that team_total = toi + filler_d_toi, giving a
    deterministic tTOI% = 5 * toi / (toi + filler_d_toi) * 100.
    """
    rows = []
    for game in games:
        rows.append({
            "gameId": game, "playerId": pid, "team": team, "position": "F",
            "toi_seconds": toi, "total_toi_seconds": total_toi,
            "line_number": line_number, "deployment_score": None,
            "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
            "comp_fwd": 0, "comp_def": 0, "height_in": 72, "weight_lbs": 198,
            "heaviness": 0, "weighted_forward_heaviness": 0,
            "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0,
        })
        rows.append({
            "gameId": game, "playerId": pid + 1000, "team": team, "position": "D",
            "toi_seconds": filler_d_toi, "total_toi_seconds": filler_d_toi,
            "line_number": None, "deployment_score": None,
            "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
            "comp_fwd": 0, "comp_def": 0, "height_in": 72, "weight_lbs": 198,
            "heaviness": 0, "weighted_forward_heaviness": 0,
            "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0,
        })
    return rows


def _ef_pts_rows(pid, game_ids, total_pts):
    """Distribute total_pts across game_ids for player pid.

    Multiple points may land in the same game (rows aggregate via SUM in points_5v5).
    """
    rows = []
    for i in range(total_pts):
        gid = game_ids[i % len(game_ids)]
        rows.append({"gameId": gid, "playerId": pid, "goals": 1, "assists": 0, "points": 1})
    return rows


def test_ef_phase1_no_elite_under_10_gp():
    """Phase 1: player with 8 GP never gets elite status regardless of stats."""
    conn = sqlite3.connect(":memory:")
    # toi=900, filler_d=9100 → team_total=10000, tTOI%=5*900/10000*100=45% ≥28%
    # iTOI%=900/1200*100=75% <83%
    # DPL=1.0 ≤2.5
    # P/60=10*3600/7200=5.0 ≥2.3 — great stats but too few games
    games = list(range(1, 9))
    rows = _ef_comp_rows(pid=1, team="EDM", games=games, toi=900, total_toi=1200,
                         line_number=1.0, filler_d_toi=9100)
    pd.DataFrame(rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(_ef_pts_rows(1, games, total_pts=10)).to_sql(
        "points_5v5", conn, index=False, if_exists="replace")

    build_elite_forwards_table(conn)

    rows_out = conn.execute("SELECT * FROM elite_forwards").fetchall()
    assert rows_out == [], f"Expected empty, got {rows_out}"


def test_ef_phase2_full_season_only_no_blend():
    """Phase 2: 15 GP uses full-season values; l20_* columns are NULL."""
    conn = sqlite3.connect(":memory:")
    # tTOI%=5*900/10000*100=45%, iTOI%=75%, DPL=1.0 → all 3 deployment signals pass
    # P/60=10*3600/13500=2.67 ≥2.3
    games = list(range(1, 16))
    rows = _ef_comp_rows(pid=1, team="EDM", games=games, toi=900, total_toi=1200,
                         line_number=1.0, filler_d_toi=9100)
    pd.DataFrame(rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(_ef_pts_rows(1, games, total_pts=10)).to_sql(
        "points_5v5", conn, index=False, if_exists="replace")

    build_elite_forwards_table(conn)

    row = conn.execute("SELECT * FROM elite_forwards WHERE playerId = 1").fetchone()
    assert row is not None, "Player with 15 GP and qualifying stats should be elite"

    cols = [d[0] for d in conn.execute("SELECT * FROM elite_forwards LIMIT 1").description]
    data = dict(zip(cols, row))
    assert data["l20_p60"] is None, "l20_p60 should be NULL for GP < 20"
    assert data["l20_dpl"] is None
    assert data["l20_ttoi_pct"] is None
    assert data["l20_itoi_pct"] is None
    # Full-season P/60 = 10 pts * 3600 / (15 * 900s) = 2.667
    assert abs(data["weighted_p60"] - 10 * 3600 / 13500) < 0.01
    assert abs(data["fs_p60"] - data["weighted_p60"]) < 0.001, "Phase 2 should use full-season value unchanged"


def test_ef_phase3_blend_applied():
    """Phase 3: 80/20 blend applied to P/60 and DPL."""
    conn = sqlite3.connect(":memory:")
    # 30 games total: games 1-10 use line_number=3, games 11-30 use line_number=1
    # All games: toi=900, total_toi=1200, filler_d=9100 → team_total=10000
    games_early = list(range(1, 11))   # 10 games, line 3
    games_late  = list(range(11, 31))  # 20 games, line 1
    rows = (
        _ef_comp_rows(pid=1, team="EDM", games=games_early, toi=900, total_toi=1200,
                      line_number=3.0, filler_d_toi=9100)
        + _ef_comp_rows(pid=1, team="EDM", games=games_late, toi=900, total_toi=1200,
                        line_number=1.0, filler_d_toi=9100)
    )
    pd.DataFrame(rows).to_sql("competition", conn, index=False, if_exists="replace")

    # Points: 12 in first 10 games, 9 in last 20 → total=21
    # fs_p60 = 21 * 3600 / (30*900) = 21*3600/27000 = 2.8
    # l20_p60 = 9 * 3600 / (20*900) = 9*3600/18000 = 1.8
    # weighted_p60 = 2.8*0.8 + 1.8*0.2 = 2.6
    pts_rows = _ef_pts_rows(1, games_early, total_pts=12) + _ef_pts_rows(1, games_late, total_pts=9)
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_forwards_table(conn)

    row = conn.execute("SELECT * FROM elite_forwards WHERE playerId = 1").fetchone()
    assert row is not None, "Player should be elite (weighted_p60=2.6 ≥ 2.3)"

    cols = [d[0] for d in conn.execute("SELECT * FROM elite_forwards LIMIT 1").description]
    data = dict(zip(cols, row))

    # P/60 blend
    assert abs(data["fs_p60"] - 2.8) < 0.01, f"fs_p60={data['fs_p60']}"
    assert abs(data["l20_p60"] - 1.8) < 0.01, f"l20_p60={data['l20_p60']}"
    assert abs(data["weighted_p60"] - 2.6) < 0.01, f"weighted_p60={data['weighted_p60']}"

    # DPL blend: fs_dpl=(10*3+20*1)/30=1.6667, l20_dpl=1.0, weighted=1.6667*0.8+1.0*0.2=1.5333
    assert abs(data["fs_dpl"] - 5/3) < 0.01, f"fs_dpl={data['fs_dpl']}"
    assert abs(data["l20_dpl"] - 1.0) < 0.01, f"l20_dpl={data['l20_dpl']}"
    assert abs(data["weighted_dpl"] - (5/3 * 0.8 + 1.0 * 0.2)) < 0.01

    # tTOI% and iTOI% are constant across all 30 games, so blend = full-season value
    assert abs(data["weighted_ttoi_pct"] - data["fs_ttoi_pct"]) < 0.01, "tTOI% blend should equal fs value when constant"
    assert abs(data["weighted_itoi_pct"] - data["fs_itoi_pct"]) < 0.01, "iTOI% blend should equal fs value when constant"


def test_ef_two_of_three_deployment():
    """2-of-3 deployment: players with exactly 2 signals pass; 0 or 1 signal fails.

    All players have GP=20, P/60 ≥ 2.3.
    Team total per game = 10000s (target_toi + filler_d_toi = 10000).

    Player  team  toi  filler_d  total_toi  tTOI%   iTOI%   DPL   signals
    1       T1    700  9300      700        35%     100%    1.0   DPL+tTOI  → IN
    2       T2    500  9500      700        25%     71.4%   1.0   DPL+iTOI  → IN
    3       T3    700  9300      900        35%     77.8%   3.0   tTOI+iTOI → IN
    4       T4    500  9500      500        25%     100%    3.0   none      → OUT
    5       T5    500  9500      500        25%     100%    1.0   DPL only  → OUT
    """
    conn = sqlite3.connect(":memory:")
    games = list(range(1, 21))  # 20 games each

    # Each player on their own team to avoid interaction
    setup = [
        (1, "T1", 700, 9300, 700,  1.0),  # DPL + tTOI pass
        (2, "T2", 500, 9500, 700,  1.0),  # DPL + iTOI pass
        (3, "T3", 700, 9300, 900,  3.0),  # tTOI + iTOI pass
        (4, "T4", 500, 9500, 500,  3.0),  # none pass
        (5, "T5", 500, 9500, 500,  1.0),  # DPL only (1-of-3)
    ]
    comp_rows = []
    pts_rows = []
    for pid, team, toi, filler_d_toi, total_toi, line_number in setup:
        comp_rows.extend(_ef_comp_rows(pid, team, games, toi, total_toi,
                                       line_number, filler_d_toi))
        # 10 pts over 20 games: P/60 = 10 * 3600 / (20 * toi)
        # For toi=700: 10*3600/14000 = 2.57 ≥ 2.3 ✓
        # For toi=500: 10*3600/10000 = 3.6 ≥ 2.3 ✓
        pts_rows.extend(_ef_pts_rows(pid, games, total_pts=10))

    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_forwards_table(conn)

    elite_pids = {r[0] for r in conn.execute("SELECT playerId FROM elite_forwards").fetchall()}
    assert 1 in elite_pids, "pid 1 (DPL + tTOI) should be elite"
    assert 2 in elite_pids, "pid 2 (DPL + iTOI) should be elite"
    assert 3 in elite_pids, "pid 3 (tTOI + iTOI) should be elite"
    assert 4 not in elite_pids, "pid 4 (no signals) should not be elite"
    assert 5 not in elite_pids, "pid 5 (DPL only, 1-of-3) should not be elite"


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

def _ed_comp_rows(pid, team, game_ids, toi, total_toi, deploy_score=None):
    """Return one competition row per game for a D player."""
    return [
        _make_comp_row(pid, team, gid, "D", toi, total_toi,
                       deployment_score=deploy_score)
        for gid in game_ids
    ]


def test_ed_gp_gate():
    """D with < 20 GP never designated elite regardless of stats.

    Player 1: 15 GP, P/60 = 6.0, tTOI% ≈ 71%, DPS+ would be 100 → excluded by GP gate.
    Player 2: 20 GP, same stats per game → included.

    Setup per game: 4 filler F (500s each) + 4 filler D (450s each)
    team_total = 4*500 + 600 + 4*450 = 4400s
    ttoi_frac = 5.0 * 600 / 4400 = 0.6818  → tTOI% = 68.2% (> 35% ✓)
    P/60 = 1 pt/game * 3600 / 600 = 6.0 (> 1.2 ✓)
    deploy_score = 100 for both → DPS+ = 100 (fails > 120 ✗ — only one player so avg=100)

    To pass DPS+: need two players with different deploy_score so normalization works.
    Give player 2 deploy=200, add a filler D3 (pid=3) with deploy=100 for 20 games.
    league_avg = (200 + 100) / 2 = 150
    Player 2 DPS+ = 200/150*100 = 133 ✓
    Player 3 DPS+ = 100/150*100 = 67 ✗ (only 20 GP, deploy=100 — used for normalization only)

    Player 1 (15 GP) must not appear even though same stats as player 2.
    """
    conn = sqlite3.connect(":memory:")
    game_ids_15 = list(range(1, 16))
    game_ids_20 = list(range(1, 21))

    filler_rows = []
    for gid in game_ids_20:
        for fid in range(1001, 1005):
            filler_rows.append(_make_comp_row(fid, "TMA", gid, "F", 500, 600))
        for did in range(1005, 1009):
            filler_rows.append(_make_comp_row(did, "TMA", gid, "D", 450, 600))

    comp_rows = (
        _ed_comp_rows(1, "TMA", game_ids_15, toi=600, total_toi=800, deploy_score=200)
        + _ed_comp_rows(2, "TMA", game_ids_20, toi=600, total_toi=800, deploy_score=200)
        + _ed_comp_rows(3, "TMA", game_ids_20, toi=600, total_toi=800, deploy_score=100)
    )
    pts_rows = (
        [{"gameId": gid, "playerId": 1, "goals": 1, "assists": 0, "points": 1} for gid in game_ids_15]
        + [{"gameId": gid, "playerId": 2, "goals": 1, "assists": 0, "points": 1} for gid in game_ids_20]
        + [{"gameId": gid, "playerId": 3, "goals": 1, "assists": 0, "points": 1} for gid in game_ids_20]
    )

    pd.DataFrame(filler_rows + comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_defensemen_table(conn)

    pids = {r[0] for r in conn.execute("SELECT playerId FROM elite_defensemen").fetchall()}
    assert 1 not in pids, "Player 1 (15 GP) must not qualify"
    assert 2 in pids, "Player 2 (20 GP, DPS+ 133) must qualify"


def test_ed_all_three_gates_required():
    """All three signals required: P/60 > 1.2, tTOI% > 35%, DPS+ > 120.

    4 players, all 20 GP, each missing exactly one gate:
      Player 1: P/60 fails (0.5), tTOI% ✓, DPS+ ✓ → excluded
      Player 2: P/60 ✓ (2.0), tTOI% fails (30%), DPS+ ✓ → excluded
      Player 3: P/60 ✓ (2.0), tTOI% ✓, DPS+ fails (80) → excluded
      Player 4: P/60 ✓ (2.0), tTOI% ✓, DPS+ ✓ → included

    Setup: 4 filler F (500s each) per game.
    team_total for tTOI% calc varies by player toi.

    For tTOI% > 35%: need 5 * toi / team_total > 0.35
    team_total = 4*500 + 300+300+300+300 = 3200 per game (all 4 D at 300s)
      tTOI% = 5*300/3200*100 = 46.9% ✓ for all at same toi

    Players 1,3,4: toi=300s/game → tTOI% = 46.9% ✓
    Player 2 (tTOI% fails): toi=180s/game → team_total = 4*500+180+300+300+300=3080
      tTOI% = 5*180/3080*100 = 29.2% ✗

    iTOI%: total_toi=400s for all → not used in gate

    P/60:
      Player 1 (P/60 fails): 0 pts → 0.0 ✗
      Players 2,3,4: 2 pts/game * 3600 / (300*20) = 7200/6000 = 1.2 ... need > 1.2
      Use 3 pts/game: 3*3600/(300*20) = 10800/6000 = 1.8 ✓

    deploy_score per game:
      Players 1,2,4: deploy=200
      Player 3: deploy=50
      league_avg of qualifying GP≥20 players = (200+200+200+50)/4 = 162.5
      P1 DPS+ = 200/162.5*100 = 123.1 ✓ (but fails P/60)
      P2 DPS+ = 200/162.5*100 = 123.1 ✓ (but fails tTOI%)
      P3 DPS+ = 50/162.5*100  = 30.8 ✗
      P4 DPS+ = 200/162.5*100 = 123.1 ✓
    """
    conn = sqlite3.connect(":memory:")
    game_ids = list(range(1, 21))

    filler_rows = []
    for gid in game_ids:
        for fid in range(1001, 1005):
            filler_rows.append(_make_comp_row(fid, "TMA", gid, "F", 500, 600))

    comp_rows = (
        _ed_comp_rows(1, "TMA", game_ids, toi=300, total_toi=400, deploy_score=200)  # P/60 fails
        + _ed_comp_rows(2, "TMA", game_ids, toi=180, total_toi=400, deploy_score=200)  # tTOI% fails
        + _ed_comp_rows(3, "TMA", game_ids, toi=300, total_toi=400, deploy_score=50)   # DPS+ fails
        + _ed_comp_rows(4, "TMA", game_ids, toi=300, total_toi=400, deploy_score=200)  # all pass
    )
    pts_rows = []
    for gid in game_ids:
        # Player 1: 0 pts (P/60 fails)
        for pid in [2, 3, 4]:
            pts_rows.append({"gameId": gid, "playerId": pid, "goals": 3, "assists": 0, "points": 3})

    pd.DataFrame(filler_rows + comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_defensemen_table(conn)

    pids = {r[0] for r in conn.execute("SELECT playerId FROM elite_defensemen").fetchall()}
    assert 4 in pids,     "Player 4 (all gates pass) must be elite"
    assert 1 not in pids, "Player 1 (P/60 fails) must be excluded"
    assert 2 not in pids, "Player 2 (tTOI% fails) must be excluded"
    assert 3 not in pids, "Player 3 (DPS+ fails) must be excluded"


def test_ed_dps_plus_normalization():
    """DPS+ is normalized to 100 = league average of qualifying D.

    Two players, 20 GP each:
      Player 1: deploy_score=200/game → avg=200
      Player 2: deploy_score=100/game → avg=100
      league_avg = (200+100)/2 = 150
      P1 DPS+ = 200/150*100 = 133.3
      P2 DPS+ = 100/150*100 = 66.7

    Both pass P/60 and tTOI%. Only P1 passes DPS+ > 120.
    """
    conn = sqlite3.connect(":memory:")
    game_ids = list(range(1, 21))

    filler_rows = []
    for gid in game_ids:
        for fid in range(1001, 1005):
            filler_rows.append(_make_comp_row(fid, "TMA", gid, "F", 500, 600))

    comp_rows = (
        _ed_comp_rows(1, "TMA", game_ids, toi=300, total_toi=400, deploy_score=200)
        + _ed_comp_rows(2, "TMA", game_ids, toi=300, total_toi=400, deploy_score=100)
    )
    pts_rows = [
        {"gameId": gid, "playerId": pid, "goals": 2, "assists": 0, "points": 2}
        for gid in game_ids for pid in [1, 2]
    ]

    pd.DataFrame(filler_rows + comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_defensemen_table(conn)

    col_names = [d[0] for d in conn.execute("SELECT * FROM elite_defensemen").description]
    rows = {r[0]: dict(zip(col_names, r))
            for r in conn.execute("SELECT * FROM elite_defensemen").fetchall()}

    assert 1 in rows, "Player 1 (DPS+ 133) must be elite"
    assert 2 not in rows, "Player 2 (DPS+ 67) must not be elite"
    assert abs(rows[1]["dps_plus"] - 133.3) < 0.5


def test_ed_traded_player_combined():
    """Traded D has season stats combined across teams; team = where they played most GP.

    Player 1: 12 GP on VAN (games 1-12) + 20 GP on MIN (games 13-32)
    Combined GP = 32 → qualifies (≥ 20).
    Stats are combined across both stints.
    Team displayed = MIN (more games).
    """
    conn = sqlite3.connect(":memory:")
    game_ids_van = list(range(1, 13))   # 12 GP on VAN
    game_ids_min = list(range(13, 33))  # 20 GP on MIN

    filler_rows = []
    for gid in range(1, 33):
        for fid in range(1001, 1005):
            filler_rows.append(_make_comp_row(fid, "TMA", gid, "F", 500, 600))

    # Player 1 on two teams — same per-game stats throughout
    comp_rows = (
        _ed_comp_rows(1, "VAN", game_ids_van, toi=300, total_toi=400, deploy_score=200)
        + _ed_comp_rows(1, "MIN", game_ids_min, toi=300, total_toi=400, deploy_score=200)
        # Player 2 needed to set normalization base (20 GP, lower deploy)
        + _ed_comp_rows(2, "TMA", list(range(1, 21)), toi=300, total_toi=400, deploy_score=100)
    )
    pts_rows = (
        [{"gameId": gid, "playerId": 1, "goals": 2, "assists": 0, "points": 2} for gid in range(1, 33)]
        + [{"gameId": gid, "playerId": 2, "goals": 2, "assists": 0, "points": 2} for gid in range(1, 21)]
    )

    pd.DataFrame(filler_rows + comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_defensemen_table(conn)

    rows = conn.execute(
        "SELECT playerId, team, gp FROM elite_defensemen WHERE playerId = 1"
    ).fetchall()
    assert len(rows) == 1, "Traded player should appear exactly once"
    assert rows[0][1] == "MIN", f"Expected team MIN (most GP), got {rows[0][1]}"
    assert rows[0][2] == 32, f"Expected combined GP=32, got {rows[0][2]}"


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
         "weighted_p60": 2.4, "weighted_dpl": 1.5,
         "weighted_ttoi_pct": 33.0, "weighted_itoi_pct": 75.0},
        {"playerId": 2, "team": "EDM", "gp": 25, "toi_min_gp": 14.0,
         "weighted_p60": 2.0, "weighted_dpl": 1.3,
         "weighted_ttoi_pct": 31.0, "weighted_itoi_pct": 77.0},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus",
        "is_production", "is_deployment", "is_full_elite",
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
         "weighted_p60": 2.4, "weighted_dpl": 1.5,
         "weighted_ttoi_pct": 33.0, "weighted_itoi_pct": 75.0},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus",
        "is_production", "is_deployment", "is_full_elite",
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
         "weighted_p60": 2.4, "weighted_dpl": 1.5,
         "weighted_ttoi_pct": 33.0, "weighted_itoi_pct": 75.0},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus",
        "is_production", "is_deployment", "is_full_elite",
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 1, "firstName": "Connor", "lastName": "McDavid",
         "currentTeamAbbrev": "EDM", "position": "F", "shootsCatches": "L",
         "heightInInches": 73, "weightInPounds": 194},
    ]).to_sql("players", conn, index=False, if_exists="replace")

    _log_elite_changes(old_fwd, old_def, conn, str(csv_path))
    conn.close()

    assert not csv_path.exists()


def test_elite_changelog_def_no_type_changes(tmp_path):
    """No type-change entry when defenseman's designation is unchanged."""
    csv_path = tmp_path / "elite_changelog.csv"
    old_def = pd.DataFrame([
        {"playerId": 10, "playerName": "Evan Bouchard", "team": "EDM", "type": "Production"},
    ])
    old_fwd = pd.DataFrame(columns=["playerId", "playerName", "team"])

    conn = sqlite3.connect(":memory:")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp",
        "weighted_p60", "weighted_dpl", "weighted_ttoi_pct", "weighted_itoi_pct",
        "fs_p60", "fs_dpl", "fs_ttoi_pct", "fs_itoi_pct",
        "l20_p60", "l20_dpl", "l20_ttoi_pct", "l20_itoi_pct",
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 10, "team": "EDM", "gp": 25, "toi_min_gp": 22.0,
         "p60": 1.6, "ttoi_pct": 40.0, "dps_plus": 130.0,
         "is_production": 1, "is_deployment": 0, "is_full_elite": 0},
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 10, "firstName": "Evan", "lastName": "Bouchard",
         "currentTeamAbbrev": "EDM", "position": "D", "shootsCatches": "R",
         "heightInInches": 74, "weightInPounds": 197},
    ]).to_sql("players", conn, index=False, if_exists="replace")

    _log_elite_changes(old_fwd, old_def, conn, str(csv_path))
    conn.close()

    assert not csv_path.exists(), "No changelog entry when elite D designation unchanged"


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
         "weighted_p60": 2.4, "weighted_dpl": 1.5,
         "weighted_ttoi_pct": 33.0, "weighted_itoi_pct": 75.0},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus",
        "is_production", "is_deployment", "is_full_elite",
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


# ---------------------------------------------------------------------------
# Elite forwards: DPS+
# ---------------------------------------------------------------------------

def _setup_fwd_deployment_db(conn):
    """Set up minimal DB for testing forward DPS+ in build_elite_forwards_table."""
    comp_rows = []
    for g in range(1, 26):
        comp_rows.append({
            "playerId": 1, "team": "EDM", "gameId": g,
            "position": "F", "toi_seconds": 900, "total_toi_seconds": 1100,
            "line_number": 1, "deployment_score": 300,
            "comp_fwd": 800, "comp_def": 900,
            "pct_vs_top_fwd": 0.5, "pct_vs_top_def": 0.5,
            "pct_any_elite_fwd": 0.3, "pct_any_elite_def": 0.3,
            "height_in": 73, "weight_lbs": 194,
            "heaviness": 2.66, "weighted_forward_heaviness": 2.66,
            "weighted_defense_heaviness": 2.66, "weighted_team_heaviness": 2.66,
        })
        comp_rows.append({
            "playerId": 2, "team": "EDM", "gameId": g,
            "position": "F", "toi_seconds": 850, "total_toi_seconds": 1100,
            "line_number": 2, "deployment_score": 150,
            "comp_fwd": 750, "comp_def": 850,
            "pct_vs_top_fwd": 0.4, "pct_vs_top_def": 0.4,
            "pct_any_elite_fwd": 0.2, "pct_any_elite_def": 0.2,
            "height_in": 74, "weight_lbs": 208,
            "heaviness": 2.81, "weighted_forward_heaviness": 2.81,
            "weighted_defense_heaviness": 2.81, "weighted_team_heaviness": 2.81,
        })
    pd.DataFrame(comp_rows).to_sql("competition", conn, if_exists="replace", index=False)
    pts_rows = []
    for g in range(1, 26):
        pts_rows.append({"playerId": 1, "gameId": g, "goals": 1, "assists": 1, "points": 2})
        pts_rows.append({"playerId": 2, "gameId": g, "goals": 1, "assists": 1, "points": 2})
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, if_exists="replace", index=False)


def test_elite_fwd_dps_plus_computed():
    """build_elite_forwards_table adds weighted_dps_plus; harder deployment → higher DPS+."""
    conn = sqlite3.connect(":memory:")
    _setup_fwd_deployment_db(conn)
    build_elite_forwards_table(conn)
    rows = pd.read_sql_query("SELECT * FROM elite_forwards", conn)
    conn.close()
    assert "weighted_dps_plus" in rows.columns
    row1 = rows[rows["playerId"] == 1].iloc[0]
    row2 = rows[rows["playerId"] == 2].iloc[0]
    assert row1["weighted_dps_plus"] > row2["weighted_dps_plus"]
    # League avg normalizes to 100 (exact with 2 players: mean of a/avg*100 = 100)
    assert abs(rows["weighted_dps_plus"].mean() - 100.0) < 1.0


# ---------------------------------------------------------------------------
# Elite defensemen: DPL
# ---------------------------------------------------------------------------

def test_elite_def_dpl_computed():
    """build_elite_defensemen_table adds dpl (avg pair number); pair 1 player has lower DPL.

    Three D players are used so the league average can be anchored below both
    players 10 and 11, giving both DPS+ > 120 and ensuring they appear in the output.

    deploy scores: 300 (pid 10), 250 (pid 11), 50 (pid 12 — anchor)
    league_avg = (300 + 250 + 50) / 3 = 200
    pid 10 DPS+ = 300/200*100 = 150 > 120 ✓
    pid 11 DPS+ = 250/200*100 = 125 > 120 ✓
    pid 12 DPS+ = 50/200*100  = 25  ✗  (excluded, just normalisation anchor)
    """
    conn = sqlite3.connect(":memory:")
    comp_rows = []
    for g in range(1, 26):
        comp_rows.append({
            "playerId": 10, "team": "EDM", "gameId": g,
            "position": "D", "toi_seconds": 1200, "total_toi_seconds": 1400,
            "line_number": 1, "deployment_score": 300,
            "comp_fwd": 900, "comp_def": 800,
            "pct_vs_top_fwd": 0.6, "pct_vs_top_def": 0.5,
            "pct_any_elite_fwd": 0.4, "pct_any_elite_def": 0.4,
            "height_in": 74, "weight_lbs": 200,
            "heaviness": 2.70, "weighted_forward_heaviness": 2.70,
            "weighted_defense_heaviness": 2.70, "weighted_team_heaviness": 2.70,
        })
        comp_rows.append({
            "playerId": 11, "team": "EDM", "gameId": g,
            "position": "D", "toi_seconds": 900, "total_toi_seconds": 1400,
            "line_number": 3, "deployment_score": 250,
            "comp_fwd": 750, "comp_def": 700,
            "pct_vs_top_fwd": 0.3, "pct_vs_top_def": 0.3,
            "pct_any_elite_fwd": 0.2, "pct_any_elite_def": 0.2,
            "height_in": 73, "weight_lbs": 195,
            "heaviness": 2.67, "weighted_forward_heaviness": 2.67,
            "weighted_defense_heaviness": 2.67, "weighted_team_heaviness": 2.67,
        })
        comp_rows.append({
            "playerId": 12, "team": "EDM", "gameId": g,
            "position": "D", "toi_seconds": 400, "total_toi_seconds": 1400,
            "line_number": 4, "deployment_score": 50,
            "comp_fwd": 600, "comp_def": 600,
            "pct_vs_top_fwd": 0.1, "pct_vs_top_def": 0.1,
            "pct_any_elite_fwd": 0.1, "pct_any_elite_def": 0.1,
            "height_in": 72, "weight_lbs": 190,
            "heaviness": 2.64, "weighted_forward_heaviness": 2.64,
            "weighted_defense_heaviness": 2.64, "weighted_team_heaviness": 2.64,
        })
    pd.DataFrame(comp_rows).to_sql("competition", conn, if_exists="replace", index=False)
    pts_rows = []
    for g in range(1, 26):
        pts_rows.append({"playerId": 10, "gameId": g, "goals": 0, "assists": 1, "points": 1})
        pts_rows.append({"playerId": 11, "gameId": g, "goals": 0, "assists": 1, "points": 1})
        pts_rows.append({"playerId": 12, "gameId": g, "goals": 0, "assists": 1, "points": 1})
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, if_exists="replace", index=False)
    build_elite_defensemen_table(conn)
    rows = pd.read_sql_query("SELECT * FROM elite_defensemen", conn)
    conn.close()
    assert "dpl" in rows.columns
    row10 = rows[rows["playerId"] == 10].iloc[0]
    row11 = rows[rows["playerId"] == 11].iloc[0]
    assert row10["dpl"] < row11["dpl"]   # pair 1 < pair 3
    assert abs(row10["dpl"] - 1.0) < 0.01
    assert abs(row11["dpl"] - 3.0) < 0.01


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
