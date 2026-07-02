import numpy as np
import pandas as pd
import pytest

from v2.goalies.difficulty import LAYERS, LayerFit, fit_layer, layer_frame


def _synthetic_shots(n_per_goalie=3000, seed=11):
    """Two goalies, identical shot mix; goalie 2 allows goals at +0.8 logits."""
    rng = np.random.default_rng(seed)
    rows = []
    for gid, skill in ((900, 0.0), (901, 0.8)):
        dist = rng.uniform(5, 60, n_per_goalie)
        eta = 0.5 - 0.09 * dist + skill
        p = 1 / (1 + np.exp(-eta))
        goals = rng.uniform(size=n_per_goalie) < p
        for d, g in zip(dist, goals):
            rows.append({
                "goalie_id": gid, "is_goal": bool(g), "on_net": True,
                "froze": np.nan if g else float(rng.uniform() < 0.3),
                "rebound_generated": np.nan if g else 0.0,
                "distance_adj": d, "angle": 15.0, "shot_type": "wrist",
                "strength": "EV", "score_diff": 0, "goalie_is_home": True,
                "dt_prev": np.nan, "prev_type": np.nan, "prev_same_team": np.nan,
                "prev_x_norm": np.nan, "prev_y_norm": np.nan, "y_norm": 5.0,
            })
    return pd.DataFrame(rows)


def test_layer_frame_subsets():
    df = _synthetic_shots(200)
    assert len(layer_frame(df, "onnet")) == len(df)
    goal_frame = layer_frame(df, "goal")
    assert (goal_frame["on_net"] == True).all()  # noqa: E712
    saves = layer_frame(df, "freeze")
    assert not saves["is_goal"].any() and saves["froze"].notna().all()


def test_goalie_terms_recover_ordering_and_shrink():
    df = _synthetic_shots()
    fit = fit_layer(df, "goal", goalie_prior_shots=1000.0)
    terms = fit.goalie_terms.set_index("goalie_id")["term"]
    assert terms[901] > terms[900]              # worse goalie has higher goal term
    assert 0.05 < (terms[901] - terms[900]) < 0.8   # shrunken below true 0.8 gap
    assert fit.goalie_terms.set_index("goalie_id").loc[900, "n_shots"] == 3000


def test_blind_fit_has_no_goalie_terms():
    df = _synthetic_shots(500)
    fit = fit_layer(df, "goal", include_goalies=False)
    assert fit.goalie_terms.empty
    assert fit.structure["dist"] < 0            # farther = fewer goals


def test_prior_centers_pull_estimates():
    df = _synthetic_shots(300)
    anchored = fit_layer(df, "goal", goalie_prior_shots=100000.0,
                         prior_centers={900: -0.5, 901: -0.5})
    terms = anchored.goalie_terms.set_index("goalie_id")["term"]
    assert terms[900] == pytest.approx(-0.5, abs=0.05)
    assert terms[901] == pytest.approx(-0.5, abs=0.05)
