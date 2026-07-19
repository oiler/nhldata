import numpy as np
import pandas as pd
import pytest

from v2.goalies.freeze_value import ridge_linear, window_xga


def _shots():
    # one game, defending side True; times chosen to probe the window edges
    rows = [
        {"game_id": 1, "goalie_is_home": True,  "period": 1, "time_s": 100, "xg": 0.10},
        {"game_id": 1, "goalie_is_home": True,  "period": 1, "time_s": 120, "xg": 0.20},
        {"game_id": 1, "goalie_is_home": True,  "period": 1, "time_s": 131, "xg": 0.40},  # outside 30s of t=100
        {"game_id": 1, "goalie_is_home": False, "period": 1, "time_s": 110, "xg": 0.80},  # other side
        {"game_id": 1, "goalie_is_home": True,  "period": 2, "time_s": 105, "xg": 0.80},  # other period
        {"game_id": 1, "goalie_is_home": True,  "period": 3, "time_s": 1195, "xg": 0.05},
        {"game_id": 1, "goalie_is_home": True,  "period": 3, "time_s": 1199, "xg": 0.07},
    ]
    return pd.DataFrame(rows)


def test_window_xga_same_side_same_period_strict_and_bounded():
    saves = pd.DataFrame([
        {"game_id": 1, "goalie_is_home": True, "period": 1, "time_s": 100},
    ])
    out = window_xga(_shots(), saves, window_s=30)
    # includes t=120 (0.2); excludes the save's own t=100 (strict), t=131 (> t+30),
    # the away-side shot, and the period-2 shot
    assert out[0] == pytest.approx(0.20)


def test_window_xga_truncates_at_period_end():
    saves = pd.DataFrame([
        {"game_id": 1, "goalie_is_home": True, "period": 3, "time_s": 1190},
    ])
    out = window_xga(_shots(), saves, window_s=30)
    # window is (1190, 1200]: includes 1195 and 1199 only
    assert out[0] == pytest.approx(0.12)


def test_window_xga_row_order_preserved():
    saves = pd.DataFrame([
        {"game_id": 1, "goalie_is_home": True, "period": 3, "time_s": 1190},
        {"game_id": 1, "goalie_is_home": True, "period": 1, "time_s": 100},
    ])
    out = window_xga(_shots(), saves, window_s=30)
    assert out[0] == pytest.approx(0.12) and out[1] == pytest.approx(0.20)


def test_ridge_linear_matches_ols_at_tiny_penalty():
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(200), rng.normal(size=200)])
    beta_true = np.array([0.5, -1.2])
    y = X @ beta_true + rng.normal(scale=0.1, size=200)
    beta, se = ridge_linear(X, y, np.full(2, 1e-9))
    ols = np.linalg.lstsq(X, y, rcond=None)[0]
    assert beta == pytest.approx(ols, abs=1e-6)
    assert se[1] == pytest.approx(0.1 / np.sqrt(((X[:, 1] - 0) ** 2).sum()), rel=0.2)


def test_ridge_linear_penalty_shrinks():
    rng = np.random.default_rng(1)
    X = np.column_stack([np.ones(50), rng.normal(size=50)])
    y = X[:, 1] * 2.0 + rng.normal(scale=0.1, size=50)
    b_small, _ = ridge_linear(X, y, np.array([1e-9, 1e-9]))
    b_big, _ = ridge_linear(X, y, np.array([1e-9, 1e6]))
    assert abs(b_big[1]) < abs(b_small[1]) and abs(b_big[1]) < 0.01
