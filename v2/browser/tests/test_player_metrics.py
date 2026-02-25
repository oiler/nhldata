# v2/browser/tests/test_player_metrics.py
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_league_db import build_player_metrics_table


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
