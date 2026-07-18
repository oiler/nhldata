import numpy as np
import pandas as pd
import pytest

from v2.goalies.era_probe import era_shift, verdict


def _saves(n_per_era, rate_a, rate_b, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for season, rate in ((2021, rate_a), (2024, rate_b)):
        for i in range(n_per_era):
            rows.append({
                "season": season, "on_net": True, "is_goal": False,
                "froze": float(rng.random() < rate),
                "distance_adj": 30.0, "angle": 20.0, "shot_type": "wrist",
                "strength": "ev", "score_diff": 0, "goalie_is_home": True,
                "dt_prev": np.nan, "prev_type": np.nan, "prev_same_team": np.nan,
                "prev_x_norm": np.nan, "prev_y_norm": np.nan, "y_norm": 0.0,
                "x_norm": 60.0, "period": 1, "time_s": 300,
            })
    return pd.DataFrame(rows)


def test_era_shift_detects_injected_offset():
    r = era_shift(_saves(4000, 0.30, 0.40), "froze")
    assert r["coef"] > 0.2                      # ~0.44 logit injected
    assert r["rate_b"] > r["rate_a"]


def test_era_shift_near_zero_when_stable():
    r = era_shift(_saves(4000, 0.31, 0.31), "froze")
    assert abs(r["coef"]) < 0.1


def test_verdict_thresholds():
    assert verdict(0.03) == "stable"
    assert verdict(-0.04) == "stable"
    assert verdict(0.09) == "sensitivity"
    assert verdict(0.30) == "normalize"
