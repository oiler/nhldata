import numpy as np
import pandas as pd
import pytest

from v2.goalies.repeatability import component_repeatability, tandem_table


def test_component_repeatability_perfect_and_filtered():
    terms = {
        2023: pd.DataFrame({"goalie_id": [1, 2, 3, 4], "layer": ["freeze"] * 4,
                            "term_indep": [0.3, 0.1, -0.1, 5.0],
                            "n_shots": [1000, 1000, 1000, 100]}),
        2024: pd.DataFrame({"goalie_id": [1, 2, 3, 4], "layer": ["freeze"] * 4,
                            "term_indep": [0.6, 0.2, -0.2, -5.0],
                            "n_shots": [1000, 1000, 1000, 100]}),
    }
    r = component_repeatability(terms)
    row = r[(r["layer"] == "freeze") & (r["pair"] == "2023-2024")].iloc[0]
    assert row["r"] == pytest.approx(1.0)       # goalie 4 under min_shots, excluded
    assert row["n_goalies"] == 3


def test_tandem_table_pairs_and_b2b():
    gg = pd.DataFrame({
        "season": [2023] * 6, "game_id": [1, 2, 3, 1, 2, 3],
        "goalie_id": [1, 1, 2, 3, 3, 3],
        "team_abbrev": ["EDM", "EDM", "EDM", "CGY", "CGY", "CGY"],
        "game_date": ["2023-11-01", "2023-11-02", "2023-11-03"] * 2,
    })
    shots_xg = pd.DataFrame({
        "season": [2023] * 4, "game_id": [1, 3, 1, 2], "goalie_id": [1, 2, 3, 3],
        "game_date": ["2023-11-01", "2023-11-03", "2023-11-01", "2023-11-02"],
        "fenwick_flag": [True] * 4, "xg": [0.1] * 4,
        "is_goal": [False, True, False, False],
    })
    terms = {2023: pd.DataFrame({"goalie_id": [1, 2], "layer": ["goal"] * 2,
                                 "term_indep": [-0.2, 0.3], "n_shots": [900, 800]})}
    t = tandem_table(gg, shots_xg, terms, min_fenwick=1)
    edm = t[t["team"] == "EDM"].iloc[0]         # CGY has one goalie -> excluded
    assert len(t) == 1
    assert edm["gsax_gap"] > 0                   # goalie 1 saved, goalie 2 scored on
    # goalie 1 played 11-02, day after team game 11-01 -> b2b share 0.5
    assert edm["b2b_share_hi"] == pytest.approx(0.5)
