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
