import numpy as np
import pandas as pd
import pytest

from v2.goalies.portability import (case_outcome, eb_rate, pre_gsax, pre_perf,
                                    term_lookup)


def _case():
    return {"case_id": "S1-2023-01-15", "goalie_id": 1, "switch_type": "midseason",
            "switch_date": "2023-01-15", "pre_team": "TOR", "post_team": "VAN",
            "last_pre_season": 2023, "first_post_season": 2023}


def _shots_xg():
    rows = []
    for i, (date, goal) in enumerate((("2023-01-10", 1), ("2023-01-10", 0),
                                      ("2023-01-20", 0), ("2023-01-20", 0))):
        rows.append({"season": 2023, "game_id": 100 + i // 2, "goalie_id": 1,
                     "game_date": date, "fenwick_flag": True, "xg": 0.10,
                     "is_goal": bool(goal)})
    return pd.DataFrame(rows)


def _gg():
    return pd.DataFrame({
        "season": [2023] * 2, "game_id": [100, 101], "goalie_id": [1, 1],
        "team_abbrev": ["TOR", "VAN"],
        "game_date": ["2023-01-10", "2023-01-20"],
    })


def test_case_outcome_post_stint_only():
    r = case_outcome(_case(), _shots_xg(), _gg())
    assert r["n_post"] == 2
    assert r["outcome"] == pytest.approx((0.2 - 0.0) / 2)


def test_pre_gsax_and_naive():
    r = pre_gsax(_case(), _shots_xg())
    assert r["n_pre"] == 2
    assert r["gsax_sum"] == pytest.approx(0.2 - 1.0)
    assert r["naive_rate"] == pytest.approx(-0.4)


def test_eb_rate_shrinks_toward_zero():
    assert eb_rate(-0.8, 2, 0) == pytest.approx(-0.4)
    assert abs(eb_rate(-0.8, 2, 1000)) < 0.001


def test_term_lookup_signs_and_normalize():
    terms = {2023: pd.DataFrame({
        "goalie_id": [1, 2, 3], "layer": ["goal"] * 3,
        "term": [0.2, 0.0, -0.2],
    })}
    t = term_lookup(_case(), terms, normalize=set())
    assert t["stopping"] == pytest.approx(-0.2)      # positive goal term = bad
    tz = term_lookup(_case(), terms, normalize={"goal"})
    assert tz["stopping"] == pytest.approx(-0.2 / np.std([0.2, 0.0, -0.2]))
    assert np.isnan(t["freeze"])                     # layer absent from frame


def test_pre_perf_uses_dated_games():
    ledger = pd.DataFrame({
        "goalie_id": [1, 1, 1], "game_date": ["2023-01-05", "2023-01-10", "2023-01-20"],
        "perf_z": [1.0, 0.0, 5.0],
    })
    assert pre_perf(_case(), ledger) == pytest.approx(0.5)


from v2.goalies.portability import (apply_composite, fit_composite, fit_k,
                                    incremental_beta, paired_bootstrap_dr,
                                    weighted_r, weighted_spearman)


def test_weighted_r_matches_numpy_when_uniform():
    rng = np.random.default_rng(0)
    x, y = rng.normal(size=50), rng.normal(size=50)
    w = np.ones(50)
    assert weighted_r(x, y, w) == pytest.approx(np.corrcoef(x, y)[0, 1])


def test_weighted_r_zero_weight_case_ignored():
    x = np.array([1.0, 2.0, 3.0, 100.0])
    y = np.array([1.0, 2.0, 3.0, -100.0])
    w = np.array([1.0, 1.0, 1.0, 0.0])
    assert weighted_r(x, y, w) == pytest.approx(1.0)


def test_weighted_r_drops_nan_pairs():
    x = np.array([1.0, 2.0, np.nan, 3.0])
    y = np.array([1.0, 2.0, 5.0, 3.0])
    w = np.ones(4)
    assert weighted_r(x, y, w) == pytest.approx(1.0)


def test_paired_bootstrap_recovers_sign():
    rng = np.random.default_rng(1)
    y = rng.normal(size=200)
    cand = y + rng.normal(scale=0.5, size=200)      # r ~ 0.9
    base = y + rng.normal(scale=2.0, size=200)      # r ~ 0.45
    r = paired_bootstrap_dr(cand, base, y, np.ones(200), n_boot=2000)
    assert r["dr"] > 0.2
    assert r["lo90"] > 0                            # CI excludes zero


def test_paired_bootstrap_degenerate_resamples_return_nan_bounds():
    cand = np.array([1.0, 2.0])
    base = np.array([1.0, 2.0])
    y = np.array([0.0, 0.0])
    w = np.array([1.0, 1.0])
    r = paired_bootstrap_dr(cand, base, y, w, n_boot=100)
    assert np.isnan(r["lo90"])
    assert np.isnan(r["hi90"])
    assert r["n_cases"] == 2


def test_incremental_beta_zero_when_candidate_is_noise():
    rng = np.random.default_rng(2)
    y = rng.normal(size=500)
    base = y + rng.normal(scale=0.5, size=500)
    noise = rng.normal(size=500)
    assert abs(incremental_beta(noise, base, y, np.ones(500))) < 0.1


def test_fit_k_prefers_heavy_shrinkage_for_noisy_signal():
    rng = np.random.default_rng(3)
    n = np.concatenate([np.full(300, 500), np.full(300, 4000)])
    true = rng.normal(scale=0.003, size=600)
    pseudo = pd.DataFrame({
        "n_pre": n,
        "gsax_sum": true * n + rng.normal(scale=np.sqrt(0.06 * n)),
        "outcome": true + rng.normal(scale=0.0055, size=600),
        "weight": np.ones(600),
    })
    assert fit_k(pseudo) >= 1000


def test_composite_recovers_dominant_column():
    rng = np.random.default_rng(4)
    n = 300
    a, b = rng.normal(size=n), rng.normal(size=n)
    pseudo = pd.DataFrame({
        "stopping": a, "freeze": b, "rebound_control": rng.normal(size=n),
        "perf": rng.normal(size=n),
        "outcome": a * 0.01 + rng.normal(scale=0.001, size=n),
        "weight": np.ones(n),
    })
    params = fit_composite(pseudo)
    assert abs(params["beta"]["stopping"]) > 3 * abs(params["beta"]["freeze"])
    row = {"stopping": 1.0, "freeze": 0.0, "rebound_control": 0.0, "perf": 0.0}
    assert apply_composite(row, params) != 0.0
