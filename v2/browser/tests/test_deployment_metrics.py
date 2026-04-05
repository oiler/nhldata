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
    """Build a ppi_df DataFrame from a list of dicts with playerId, ppi, ppi_plus, wppi, wppi_plus."""
    return pd.DataFrame(rows)


# --- Fixtures ---

def _standard_data():
    """
    3 eligible players on FLA (6 games each), 1 ineligible (3 games):
      Player 1: F, 900s/game, PPI=2.75, PPI+=100.0, wPPI=90000, wPPI+=106.26
      Player 2: D, 1000s/game, PPI=2.97, PPI+=108.0, wPPI=108000, wPPI+=127.51
      Player 3: F, 600s/game, PPI=2.57, PPI+=93.5, wPPI=56100, wPPI+=66.23
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
        {"playerId": 1, "ppi": 2.75, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 106.26},
        {"playerId": 2, "ppi": 2.97, "ppi_plus": 108.0, "wppi": 108000.0, "wppi_plus": 127.51},
        {"playerId": 3, "ppi": 2.57, "ppi_plus": 93.5,  "wppi": 56100.0,  "wppi_plus": 66.23},
        {"playerId": 4, "ppi": 2.57, "ppi_plus": 93.5,  "wppi": 56100.0,  "wppi_plus": 66.23},
    ]
    return _make_comp(comp_rows), _make_ppi(ppi_rows)


# --- Empty / edge-case inputs ---

def test_empty_comp_returns_empty():
    comp = pd.DataFrame(columns=["playerId", "team", "gameId", "position", "toi_seconds"])
    ppi = _make_ppi([{"playerId": 1, "ppi": 2.75, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0}])
    result = compute_deployment_metrics(comp, ppi)
    assert result.empty


def test_empty_ppi_returns_empty():
    comp = _make_comp([{"playerId": 1, "team": "FLA", "gameId": 1, "position": "F", "toi_seconds": 900}])
    ppi = pd.DataFrame(columns=["playerId", "ppi", "ppi_plus", "wppi", "wppi_plus"])
    result = compute_deployment_metrics(comp, ppi)
    assert result.empty


def test_no_eligible_players_returns_empty():
    """All players have < 5 games → no eligible players."""
    comp_rows = [
        {"playerId": 1, "team": "FLA", "gameId": g, "position": "F", "toi_seconds": 900}
        for g in range(1, 4)
    ]
    ppi_rows = [{"playerId": 1, "ppi": 2.75, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0}]
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
    assert list(result.columns) == ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate", "fwd_deployment_rate"]


# --- PPI pass-through ---

def test_ppi_values_passed_through():
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    assert abs(result.loc[1, "ppi"] - 2.75) < 0.001
    assert abs(result.loc[2, "ppi"] - 2.97) < 0.001
    assert abs(result.loc[1, "ppi_plus"] - 100.0) < 0.001


# --- wPPI / wPPI+ pass-through ---

def test_wppi_passed_through_from_ppi_df():
    """wPPI and wPPI+ come from ppi_df unchanged — not recomputed from the filtered window."""
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    assert abs(result.loc[1, "wppi"] - 90000.0) < 0.001
    assert abs(result.loc[1, "wppi_plus"] - 106.26) < 0.001
    assert abs(result.loc[2, "wppi"] - 108000.0) < 0.001
    assert abs(result.loc[2, "wppi_plus"] - 127.51) < 0.001
    assert abs(result.loc[3, "wppi"] - 56100.0) < 0.001
    assert abs(result.loc[3, "wppi_plus"] - 66.23) < 0.001


def test_wppi_plus_stable_across_different_windows():
    """Same player in two different filtered windows gets the same wPPI+ (stored value)."""
    ppi_rows = [
        {"playerId": 1, "ppi": 2.75, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 112.5},
        {"playerId": 2, "ppi": 2.97, "ppi_plus": 108.0, "wppi": 108000.0, "wppi_plus": 135.0},
        {"playerId": 3, "ppi": 2.57, "ppi_plus": 93.5,  "wppi": 56100.0,  "wppi_plus": 70.0},
    ]

    # Window A: 6 games, all players
    comp_a = []
    for game in range(1, 7):
        comp_a.append({"playerId": 1, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 900})
        comp_a.append({"playerId": 2, "team": "FLA", "gameId": game, "position": "D", "toi_seconds": 1000})
        comp_a.append({"playerId": 3, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 600})

    # Window B: games 1-5 only (player 3 still eligible, avg TOI different mix)
    comp_b = [r for r in comp_a if r["gameId"] <= 5]

    result_a = compute_deployment_metrics(_make_comp(comp_a), _make_ppi(ppi_rows))
    result_b = compute_deployment_metrics(_make_comp(comp_b), _make_ppi(ppi_rows))

    # wPPI+ must be identical regardless of filtered window
    assert abs(result_a.loc[1, "wppi_plus"] - result_b.loc[1, "wppi_plus"]) < 0.001
    assert abs(result_a.loc[2, "wppi_plus"] - result_b.loc[2, "wppi_plus"]) < 0.001


# --- avg_toi_share (still computed from filtered window) ---

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

    ppi_rows = [{"playerId": pid, "ppi": 2.75, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0}
                for pid in range(1, 11)]
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
    ppi_rows = [{"playerId": 1, "ppi": 2.75, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0}]
    result = compute_deployment_metrics(_make_comp(comp_rows), _make_ppi(ppi_rows))
    # team_total = 900 + 600 = 1500. share = 5 * 900 / 1500 = 3.0
    assert abs(result.loc[1, "avg_toi_share"] - 5 * 900 / 1500) < 0.001


# ---------------------------------------------------------------------------
# Deployment Rate
# ---------------------------------------------------------------------------

def test_deployment_rate_normalization():
    """D with higher avg deployment_score gets rate > 100; mean = 100."""
    comp_rows = (
        [{"playerId": 1, "team": "EDM", "gameId": g, "position": "D",
          "toi_seconds": 1000, "deployment_score": 5000} for g in range(1, 11)]
      + [{"playerId": 2, "team": "EDM", "gameId": g, "position": "D",
          "toi_seconds": 900,  "deployment_score": 3000} for g in range(1, 11)]
    )
    ppi_rows = [
        {"playerId": 1, "ppi": 3.0, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 110.0},
        {"playerId": 2, "ppi": 2.9, "ppi_plus": 98.0,  "wppi": 88000.0, "wppi_plus": 90.0},
    ]
    result = compute_deployment_metrics(pd.DataFrame(comp_rows), pd.DataFrame(ppi_rows))

    assert result.loc[1, "deployment_rate"] > 100
    assert result.loc[2, "deployment_rate"] < 100
    assert abs(result["deployment_rate"].mean() - 100.0) < 0.001


def test_deployment_rate_forwards_null():
    """Forward players receive NaN for deployment_rate; D receives a value."""
    comp_rows = (
        [{"playerId": 1, "team": "EDM", "gameId": g, "position": "F",
          "toi_seconds": 900, "deployment_score": None} for g in range(1, 11)]
      + [{"playerId": 2, "team": "EDM", "gameId": g, "position": "D",
          "toi_seconds": 1000, "deployment_score": 5000} for g in range(1, 11)]
    )
    ppi_rows = [
        {"playerId": 1, "ppi": 3.0, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0},
        {"playerId": 2, "ppi": 3.0, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0},
    ]
    result = compute_deployment_metrics(pd.DataFrame(comp_rows), pd.DataFrame(ppi_rows))

    assert pd.isna(result.loc[1, "deployment_rate"])       # forward → NaN
    assert not pd.isna(result.loc[2, "deployment_rate"])   # D → has value


def test_fwd_deployment_rate_normalization():
    """F with higher avg deployment_score gets rate > 100; mean = 100."""
    comp_rows = (
        [{"playerId": 1, "team": "EDM", "gameId": g, "position": "F",
          "toi_seconds": 900, "deployment_score": 4000} for g in range(1, 11)]
      + [{"playerId": 2, "team": "EDM", "gameId": g, "position": "F",
          "toi_seconds": 900, "deployment_score": 2000} for g in range(1, 11)]
    )
    ppi_rows = [
        {"playerId": 1, "ppi": 3.0, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 110.0},
        {"playerId": 2, "ppi": 2.9, "ppi_plus": 98.0,  "wppi": 88000.0, "wppi_plus": 90.0},
    ]
    result = compute_deployment_metrics(pd.DataFrame(comp_rows), pd.DataFrame(ppi_rows))
    assert result.loc[1, "fwd_deployment_rate"] > 100
    assert result.loc[2, "fwd_deployment_rate"] < 100
    assert abs(result["fwd_deployment_rate"].mean() - 100.0) < 0.001


def test_fwd_deployment_rate_defense_null():
    """D players receive NaN for fwd_deployment_rate; F receives a value."""
    comp_rows = (
        [{"playerId": 1, "team": "EDM", "gameId": g, "position": "F",
          "toi_seconds": 900, "deployment_score": 4000} for g in range(1, 11)]
      + [{"playerId": 2, "team": "EDM", "gameId": g, "position": "D",
          "toi_seconds": 1000, "deployment_score": 5000} for g in range(1, 11)]
    )
    ppi_rows = [
        {"playerId": 1, "ppi": 3.0, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0},
        {"playerId": 2, "ppi": 3.0, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0},
    ]
    result = compute_deployment_metrics(pd.DataFrame(comp_rows), pd.DataFrame(ppi_rows))
    assert not pd.isna(result.loc[1, "fwd_deployment_rate"])   # F → has value
    assert pd.isna(result.loc[2, "fwd_deployment_rate"])       # D → NaN


def test_fwd_deployment_rate_all_null_scores():
    """fwd_deployment_rate is None/NaN when all F deployment_scores are null."""
    comp_rows = (
        [{"playerId": 1, "team": "EDM", "gameId": g, "position": "F",
          "toi_seconds": 900, "deployment_score": None} for g in range(1, 11)]
      + [{"playerId": 2, "team": "EDM", "gameId": g, "position": "D",
          "toi_seconds": 1000, "deployment_score": 5000} for g in range(1, 11)]
    )
    ppi_rows = [
        {"playerId": 1, "ppi": 3.0, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0},
        {"playerId": 2, "ppi": 3.0, "ppi_plus": 100.0, "wppi": 90000.0, "wppi_plus": 100.0},
    ]
    result = compute_deployment_metrics(pd.DataFrame(comp_rows), pd.DataFrame(ppi_rows))
    assert pd.isna(result.loc[1, "fwd_deployment_rate"])
    assert not pd.isna(result.loc[2, "deployment_rate"])
