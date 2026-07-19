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


def test_ridge_linear_collinear_columns_no_warning():
    import warnings
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(100), np.full(100, 30.0), np.log1p(np.full(100, 30.0)),
                         np.full(100, 20.0), np.ones(100), rng.random(100)])
    y = 0.02 + rng.normal(scale=0.005, size=100)
    penalty = np.array([1e-6, 1.0, 1.0, 1.0, 1.0, 1e-6])
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        beta, se = ridge_linear(X, y, penalty)
    assert np.all(np.isfinite(se))


from v2.goalies.freeze_value import freeze_effect, season_value


def _saves_frame(n, froze_effect, goalie_bias=0.0, seed=5):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        gid = i % 4
        froze = float(rng.random() < 0.3 + (0.2 if goalie_bias and gid < 2 else 0.0))
        rows.append({
            "goalie_id": gid, "froze": froze,
            "distance_adj": 30.0, "angle": 20.0, "shot_type": "wrist",
            "strength": "ev", "score_diff": 0, "goalie_is_home": True,
            "dt_prev": np.nan, "prev_type": np.nan, "prev_same_team": np.nan,
            "prev_x_norm": np.nan, "prev_y_norm": np.nan, "y_norm": 0.0,
            "x_norm": 60.0, "period": 1, "time_s": 300,
            "on_net": True, "is_goal": False,
        })
    df = pd.DataFrame(rows)
    y = (0.02 + froze_effect * df["froze"].to_numpy()
         + (goalie_bias * (df["goalie_id"] < 2).to_numpy())
         + rng.normal(scale=0.005, size=n))
    return df, y


def test_freeze_effect_recovers_injected_delta():
    df, y = _saves_frame(8000, froze_effect=-0.010)
    r = freeze_effect(df, y)
    assert r["coef"] == pytest.approx(-0.010, abs=0.002)
    assert abs(r["coef"]) > 2 * r["se"]


def test_freeze_effect_within_goalie_removes_goalie_confound():
    # goalies 0-1 both freeze more AND face higher baseline xGA (no true effect)
    df, y = _saves_frame(8000, froze_effect=0.0, goalie_bias=0.02)
    raw = freeze_effect(df, y)
    demeaned = freeze_effect(df, y, demean_by_goalie=True)
    assert abs(demeaned["coef"]) < abs(raw["coef"])
    assert abs(demeaned["coef"]) < 2 * demeaned["se"]


def test_season_value_scales_by_rate_spread():
    v = season_value(-0.001, rate_lo=0.27, rate_hi=0.35, saves_per_season=1000)
    assert v["goals_low"] == pytest.approx(-0.27)
    assert v["goals_high"] == pytest.approx(-0.35)


from v2.goalies.freeze_value import tandem_bound


def test_tandem_bound_team_driven_vs_independent():
    # Pair labeling must be by workload (starter/backup), never by the outcome:
    # sorting hi/lo on gsax_rate itself puts corr(max, min) ~= 0.467 under full
    # independence (order-statistic floor), which would swamp any team signal.
    rng = np.random.default_rng(7)
    # team-driven: partners share a team effect -> high partner_r, high between_share
    rows_team, rows_indep = [], []
    for i in range(200):
        team_eff = rng.normal(scale=0.01)
        for g, n in ((i * 2, 1400), (i * 2 + 1, 900)):
            base = {"season": 2023, "team": f"T{i}", "goalie_id": g, "n": n}
            rows_team.append({**base, "gsax_rate": team_eff + rng.normal(scale=0.002)})
            rows_indep.append({**base, "gsax_rate": rng.normal(scale=0.01)})
    driven = tandem_bound(pd.DataFrame(rows_team))
    indep = tandem_bound(pd.DataFrame(rows_indep))
    assert driven["partner_r"] > 0.6 and abs(indep["partner_r"]) < 0.2
    assert driven["between_share"] > indep["between_share"]
    assert driven["n_pairs"] == 200
