# v2/browser/tests/test_build_goalies_db.py
"""Tests for build_goalies_db.build_goalie_seasons() and freeze_percentile()."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_goalies_db import build_goalie_seasons, freeze_percentile


def _gg():
    return pd.DataFrame({
        "season": [2025] * 3, "game_id": [1, 2, 3], "goalie_id": [9, 9, 9],
        "team_abbrev": ["EDM", "EDM", "CGY"], "opp_abbrev": ["CGY", "VAN", "EDM"],
        "game_date": ["2025-10-01", "2025-10-03", "2025-11-01"], "toi_s": [3600, 3000, 3600],
    })


def _gsax():
    return pd.DataFrame({"goalie_id": [9], "shots": [90], "xga": [7.5], "ga": [6],
                         "gsax": [1.5], "gsax_per100": [1.67]})


def _shots():
    rows = []
    for froze in ([1.0] * 6 + [0.0] * 14):
        rows.append({"season": 2025, "goalie_id": 9, "on_net": True,
                     "is_goal": False, "froze": froze})
    rows.append({"season": 2025, "goalie_id": 9, "on_net": True, "is_goal": True,
                 "froze": np.nan})
    return pd.DataFrame(rows)


def _terms():
    return pd.DataFrame({"goalie_id": [9, 9], "layer": ["rebound", "goal"],
                         "term_indep": [0.25, -0.1], "n_shots": [800, 900]})


def _ledger():
    return pd.DataFrame({
        "season": [2025] * 3, "game_id": [1, 2, 3], "goalie_id": [9] * 3,
        "perf_z": [1.0, -0.5, np.nan], "difficulty_pct": [40.0, 60.0, np.nan],
        "lev_value": [0.1, -0.05, 0.02],
    })


def test_build_goalie_seasons_aggregates():
    row = build_goalie_seasons(_gg(), _gsax(), _shots(), _terms(), _ledger()).iloc[0]
    assert row["teams"] == "EDM/CGY"                      # first-appearance order
    assert row["gp"] == 3 and row["toi_s"] == 10200
    assert row["freeze_rate"] == pytest.approx(0.3)       # 6/20 saves
    assert row["rebound_term_indep"] == pytest.approx(-0.25)   # oriented: negative here
    assert row["mean_perf_z"] == pytest.approx(0.25)      # NaN dropped
    assert row["mean_difficulty_pct"] == pytest.approx(50.0)
    assert row["lev_value_sum"] == pytest.approx(0.07)
    assert row["gsax"] == pytest.approx(1.5)


def test_freeze_percentile_floor_and_rank():
    # freeze_percentile returns a Series indexed like `rates` (its default
    # RangeIndex here: 0->goalie1, 1->goalie2, 2->goalie3, 3->goalie4).
    rates = pd.DataFrame({
        "goalie_id": [1, 2, 3, 4],
        "freeze_rate": [0.25, 0.30, 0.35, 0.99],
        "n_saves": [800, 900, 1000, 100],      # goalie 4 (index 3) under floor
    })
    pct = freeze_percentile(rates)
    assert pct[2] > pct[1] > pct[0]            # ordering among eligible goalies
    assert np.isnan(pct[3])                    # below the 500-save floor -> NaN
    assert pct[2] == pytest.approx(100.0)      # highest eligible rate -> top percentile
