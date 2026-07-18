import numpy as np
import pandas as pd
import pytest

from v2.goalies.portability import (case_estimates, case_outcome, eb_rate,
                                    pre_gsax, pre_perf, term_lookup)


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


def test_case_estimates_nonswitch_outcome_restricted_but_real_case_untouched():
    # Registered pseudo-case post window = first_post_season only
    # (switch_registry.nonswitch_pseudo_cases); a goalie who stays on the
    # same team into season t+2 must not have those shots leak into the
    # outcome. Real cases (offseason/midseason) keep the full post-stint
    # window with no season cap -- same goalie/team shape, both seasons used.
    cases = pd.DataFrame([
        {"case_id": "N1-2023-06-01", "goalie_id": 1, "switch_type": "nonswitch",
         "switch_date": "2023-06-01", "pre_team": "TOR", "post_team": "TOR",
         "last_pre_season": 2022, "first_post_season": 2023},
        {"case_id": "S2-2023-06-01", "goalie_id": 2, "switch_type": "offseason",
         "switch_date": "2023-06-01", "pre_team": "VAN", "post_team": "TOR",
         "last_pre_season": 2022, "first_post_season": 2023},
    ])
    shots_xg = pd.DataFrame([
        {"season": 2023, "game_id": 200, "goalie_id": 1, "game_date": "2023-10-15",
         "fenwick_flag": True, "xg": 0.10, "is_goal": False},
        {"season": 2024, "game_id": 300, "goalie_id": 1, "game_date": "2024-10-15",
         "fenwick_flag": True, "xg": 0.10, "is_goal": True},
        {"season": 2023, "game_id": 400, "goalie_id": 2, "game_date": "2023-10-15",
         "fenwick_flag": True, "xg": 0.10, "is_goal": False},
        {"season": 2024, "game_id": 500, "goalie_id": 2, "game_date": "2024-10-15",
         "fenwick_flag": True, "xg": 0.10, "is_goal": True},
    ])
    gg = pd.DataFrame({
        "season": [2023, 2024, 2023, 2024], "game_id": [200, 300, 400, 500],
        "goalie_id": [1, 1, 2, 2], "team_abbrev": ["TOR", "TOR", "TOR", "TOR"],
        "game_date": ["2023-10-15", "2024-10-15", "2023-10-15", "2024-10-15"],
    })
    ledger_dated = pd.DataFrame(columns=["goalie_id", "game_date", "perf_z"])
    refits = pd.DataFrame(columns=["case_id", "layer", "term"])

    out = case_estimates(cases, shots_xg, gg, terms={}, ledger_dated=ledger_dated,
                         normalize=set(), refits=refits, k=None)
    nonswitch_row = out[out["case_id"] == "N1-2023-06-01"].iloc[0]
    real_row = out[out["case_id"] == "S2-2023-06-01"].iloc[0]

    assert nonswitch_row["n_post"] == 1
    assert nonswitch_row["outcome"] == pytest.approx(0.10)
    # Real case's post window is untouched -- spans both seasons.
    assert real_row["n_post"] == 2
    assert real_row["outcome"] == pytest.approx((0.20 - 1.0) / 2)


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


def test_midseason_refit_substitution_respects_normalize():
    case = {"case_id": "S1-2023-01-15", "goalie_id": 1, "switch_type": "midseason",
            "switch_date": "2023-01-15", "pre_team": "TOR", "post_team": "VAN",
            "last_pre_season": 2023, "first_post_season": 2023}
    cases = pd.DataFrame([case])

    shots_xg = pd.DataFrame([
        {"season": 2023, "game_id": 100, "goalie_id": 1, "game_date": "2023-01-20",
         "fenwick_flag": True, "xg": 0.10, "is_goal": False},
    ])
    gg = pd.DataFrame({
        "season": [2023], "game_id": [100], "goalie_id": [1],
        "team_abbrev": ["VAN"], "game_date": ["2023-01-20"],
    })
    terms = {2023: pd.DataFrame({
        "goalie_id": [1, 2, 3], "layer": ["rebound"] * 3,
        "term": [0.2, 0.0, -0.2], "term_indep": [0.2, 0.0, -0.2],
    })}
    refits = pd.DataFrame([
        {"case_id": case["case_id"], "layer": "goal", "term": 0.3},
        {"case_id": case["case_id"], "layer": "freeze", "term": -0.4},
        {"case_id": case["case_id"], "layer": "rebound", "term": 0.1},
    ])
    ledger_dated = pd.DataFrame(columns=["goalie_id", "game_date", "perf_z"])

    out = case_estimates(cases, shots_xg, gg, terms, ledger_dated,
                         normalize={"rebound"}, refits=refits, k=None)
    row = out.iloc[0]

    pop_std = np.std([0.2, 0.0, -0.2])  # ddof=0
    # rebound is normalized: refit term must go through the same season
    # population z-transform term_lookup uses, not the raw refit scale.
    assert row["rebound_control"] == pytest.approx(-(0.1 - 0.0) / pop_std, rel=1e-3)
    # goal/freeze are not in `normalize`: substitution keeps the raw refit term.
    assert row["stopping"] == pytest.approx(-1.0 * 0.3)
    assert row["freeze"] == pytest.approx(1.0 * -0.4)
    # rebound_control_indep is never refit mid-season (only the chained
    # `term` gets a midseason refit above); the full-season term_indep would
    # leak the goalie's post-trade shots. Must be NaN even though the season
    # frame above has a valid term_indep for this goalie.
    assert np.isnan(row["rebound_control_indep"])


def test_offseason_case_rebound_indep_still_populated():
    # Sanity check on the gate above: the NaN-out only applies to midseason
    # cases -- offseason cases keep the real term_indep lookup.
    case = {"case_id": "S2-2023-06-01", "goalie_id": 1, "switch_type": "offseason",
            "switch_date": "2023-06-01", "pre_team": "TOR", "post_team": "VAN",
            "last_pre_season": 2022, "first_post_season": 2023}
    cases = pd.DataFrame([case])
    shots_xg = pd.DataFrame([
        {"season": 2023, "game_id": 100, "goalie_id": 1, "game_date": "2023-10-20",
         "fenwick_flag": True, "xg": 0.10, "is_goal": False},
    ])
    gg = pd.DataFrame({
        "season": [2023], "game_id": [100], "goalie_id": [1],
        "team_abbrev": ["VAN"], "game_date": ["2023-10-20"],
    })
    terms = {2022: pd.DataFrame({
        "goalie_id": [1, 2, 3], "layer": ["rebound"] * 3,
        "term": [0.2, 0.0, -0.2], "term_indep": [0.2, 0.0, -0.2],
    })}
    refits = pd.DataFrame(columns=["case_id", "layer", "term"])
    ledger_dated = pd.DataFrame(columns=["goalie_id", "game_date", "perf_z"])

    out = case_estimates(cases, shots_xg, gg, terms, ledger_dated,
                         normalize=set(), refits=refits, k=None)
    assert out.iloc[0]["rebound_control_indep"] == pytest.approx(-1.0 * 0.2)


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
