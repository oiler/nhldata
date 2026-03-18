# v2/browser/tests/test_deployment_metrics.py
"""Tests for filters.compute_deployment_metrics()."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from filters import compute_deployment_metrics


def _make_comp(rows):
    """Build a competition DataFrame from a list of dicts."""
    return pd.DataFrame(rows)


def _make_ppi(rows):
    """Build a ppi_df DataFrame from a list of dicts with playerId, ppi, ppi_plus."""
    return pd.DataFrame(rows)


# --- Fixtures ---

def _standard_data():
    """
    3 eligible players on FLA (6 games each), 1 ineligible (3 games):
      Player 1: F, 900s/game, PPI=2.75, PPI+=100.0
      Player 2: D, 1000s/game, PPI=2.97, PPI+=108.0
      Player 3: F, 600s/game, PPI=2.57, PPI+=93.5
      Player 4: F, 400s/game, PPI=2.57, PPI+=93.5 (only 3 games → ineligible)
    """
    comp_rows = []
    for game in range(1, 7):
        comp_rows.append({"playerId": 1, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 900})
        comp_rows.append({"playerId": 2, "team": "FLA", "gameId": game, "position": "D", "toi_seconds": 1000})
        comp_rows.append({"playerId": 3, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 600})
    for game in range(1, 4):
        comp_rows.append({"playerId": 4, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 400})

    ppi_rows = [
        {"playerId": 1, "ppi": 2.75, "ppi_plus": 100.0},
        {"playerId": 2, "ppi": 2.97, "ppi_plus": 108.0},
        {"playerId": 3, "ppi": 2.57, "ppi_plus": 93.5},
        {"playerId": 4, "ppi": 2.57, "ppi_plus": 93.5},
    ]
    return _make_comp(comp_rows), _make_ppi(ppi_rows)


# --- Empty / edge-case inputs ---

def test_empty_comp_returns_empty():
    comp = pd.DataFrame(columns=["playerId", "team", "gameId", "position", "toi_seconds"])
    ppi = _make_ppi([{"playerId": 1, "ppi": 2.75, "ppi_plus": 100.0}])
    result = compute_deployment_metrics(comp, ppi)
    assert result.empty


def test_empty_ppi_returns_empty():
    comp = _make_comp([{"playerId": 1, "team": "FLA", "gameId": 1, "position": "F", "toi_seconds": 900}])
    ppi = pd.DataFrame(columns=["playerId", "ppi", "ppi_plus"])
    result = compute_deployment_metrics(comp, ppi)
    assert result.empty


def test_no_eligible_players_returns_empty():
    """All players have < 5 games → no eligible players."""
    comp_rows = [
        {"playerId": 1, "team": "FLA", "gameId": g, "position": "F", "toi_seconds": 900}
        for g in range(1, 4)
    ]
    ppi_rows = [{"playerId": 1, "ppi": 2.75, "ppi_plus": 100.0}]
    result = compute_deployment_metrics(_make_comp(comp_rows), _make_ppi(ppi_rows))
    assert result.empty


# --- Eligibility ---

def test_ineligible_player_excluded():
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    assert 4 not in result.index


def test_eligible_players_included():
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    assert set(result.index) == {1, 2, 3}


# --- Output columns ---

def test_output_columns():
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    assert list(result.columns) == ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]


# --- PPI pass-through ---

def test_ppi_values_passed_through():
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    assert abs(result.loc[1, "ppi"] - 2.75) < 0.001
    assert abs(result.loc[2, "ppi"] - 2.97) < 0.001
    assert abs(result.loc[1, "ppi_plus"] - 100.0) < 0.001


# --- wPPI ---

def test_wppi_single_team():
    """
    Player 1 on FLA: 900s/game.
    FLA team avg/game = (900 + 1000 + 600) / 1 player-game... no:
    team_total_toi = sum of all eligible toi for FLA across all games.
    team_unique_games = 6.
    team_avg_toi = (900*6 + 1000*6 + 600*6) / 6 = 2500.
    Player 1 avg_toi = 900. share = 900/2500 = 0.36.
    wPPI = PPI * share = 2.75 * 0.36 = 0.99.
    """
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    team_avg = (900 * 6 + 1000 * 6 + 600 * 6) / 6  # 2500
    share = 900 / team_avg
    expected_wppi = 2.75 * share
    assert abs(result.loc[1, "wppi"] - expected_wppi) < 0.001


# --- wPPI+ ---

def test_wppi_plus_mean_is_100():
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    mean_wppi_plus = result["wppi_plus"].mean()
    assert abs(mean_wppi_plus - 100.0) < 0.001


# --- Traded player ---

def test_wppi_traded_player():
    """
    Player 5: 3 games on EDM (800s/game), 3 games on VAN (800s/game).
    Only eligible player on each team → share = 1.0 on both.
    wPPI = PPI × (1.0*3 + 1.0*3) / (3+3) = PPI × 1.0.
    """
    comp_rows = []
    for game in range(1, 4):
        comp_rows.append({"playerId": 5, "team": "EDM", "gameId": game, "position": "F", "toi_seconds": 800})
    for game in range(4, 7):
        comp_rows.append({"playerId": 5, "team": "VAN", "gameId": game, "position": "F", "toi_seconds": 800})
    ppi_rows = [{"playerId": 5, "ppi": 2.60, "ppi_plus": 100.0}]
    result = compute_deployment_metrics(_make_comp(comp_rows), _make_ppi(ppi_rows))
    assert abs(result.loc[5, "wppi"] - 2.60) < 0.001


def test_wppi_traded_player_no_inflation():
    """Traded player with same per-game TOI as single-team player gets same wPPI."""
    comp_rows = []
    # Player 10: single-team ANA, 10 games, 900s/game
    for game in range(1, 11):
        comp_rows.append({"playerId": 10, "team": "ANA", "gameId": game, "position": "F", "toi_seconds": 900})
    # Player 11: traded ANA→BOS, 5+5 games, same 900s/game
    for game in range(101, 106):
        comp_rows.append({"playerId": 11, "team": "ANA", "gameId": game, "position": "F", "toi_seconds": 900})
    for game in range(201, 206):
        comp_rows.append({"playerId": 11, "team": "BOS", "gameId": game, "position": "F", "toi_seconds": 900})

    ppi_rows = [
        {"playerId": 10, "ppi": 2.75, "ppi_plus": 100.0},
        {"playerId": 11, "ppi": 2.75, "ppi_plus": 100.0},
    ]
    result = compute_deployment_metrics(_make_comp(comp_rows), _make_ppi(ppi_rows))
    assert abs(result.loc[10, "wppi"] - result.loc[11, "wppi"]) < 0.001


# --- avg_toi_share ---

def test_avg_toi_share():
    """
    10 FLA skaters per game (5 games each):
      5 high-TOI: 600s/game, 5 low-TOI: 300s/game
    team_total per game = 5*600 + 5*300 = 4500
    share = 5 * player_toi / team_total
    high: 5 * 600 / 4500 = 2/3
    low:  5 * 300 / 4500 = 1/3
    """
    comp_rows = []
    for game in range(1, 6):
        for pid in range(1, 6):
            comp_rows.append({"playerId": pid, "team": "FLA", "gameId": game,
                              "position": "F", "toi_seconds": 600})
        for pid in range(6, 11):
            comp_rows.append({"playerId": pid, "team": "FLA", "gameId": game,
                              "position": "F", "toi_seconds": 300})

    ppi_rows = [{"playerId": pid, "ppi": 2.75, "ppi_plus": 100.0} for pid in range(1, 11)]
    result = compute_deployment_metrics(_make_comp(comp_rows), _make_ppi(ppi_rows))
    assert abs(result.loc[1, "avg_toi_share"] - 2 / 3) < 0.001
    assert abs(result.loc[6, "avg_toi_share"] - 1 / 3) < 0.001


def test_avg_toi_share_uses_full_comp():
    """avg_toi_share denominator includes all comp players, not just eligible ones."""
    comp_rows = []
    # Player 1: eligible (5 games), 900s/game
    for game in range(1, 6):
        comp_rows.append({"playerId": 1, "team": "FLA", "gameId": game,
                          "position": "F", "toi_seconds": 900})
    # Player 2: ineligible (5 games in comp but NOT in ppi_df), 600s/game
    for game in range(1, 6):
        comp_rows.append({"playerId": 2, "team": "FLA", "gameId": game,
                          "position": "F", "toi_seconds": 600})

    # Only player 1 in ppi_df
    ppi_rows = [{"playerId": 1, "ppi": 2.75, "ppi_plus": 100.0}]
    result = compute_deployment_metrics(_make_comp(comp_rows), _make_ppi(ppi_rows))
    # team_total = 900 + 600 = 1500. share = 5 * 900 / 1500 = 3.0
    assert abs(result.loc[1, "avg_toi_share"] - 5 * 900 / 1500) < 0.001
