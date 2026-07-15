import pandas as pd
import pytest

from v2.goalies.leverage import leverage_weight, leverage_weight_vectorized, wp_table


def _states():
    rows = []
    # tied late: 50/50; up 1 late: 80/20 — 300 samples each so n-guard passes
    for won, n in ((1, 150), (0, 150)):
        rows += [{"score_diff": 0, "period": 3, "time_s": 900, "won": won}] * n
    for won, n in ((1, 240), (0, 60)):
        rows += [{"score_diff": 1, "period": 3, "time_s": 900, "won": won}] * n
    return pd.DataFrame(rows)


def test_wp_table_means_and_clipping():
    t = wp_table(_states())
    tied = t[(t.score_diff_c == 0) & (t.period_c == 3) & (t.time_bucket == 3)]
    up1 = t[(t.score_diff_c == 1) & (t.period_c == 3) & (t.time_bucket == 3)]
    assert tied.iloc[0]["wp"] == pytest.approx(0.5)
    assert up1.iloc[0]["wp"] == pytest.approx(0.8)
    assert tied.iloc[0]["n"] == 300


def test_wp_table_clips_extremes():
    df = pd.DataFrame([{"score_diff": 5, "period": 6, "time_s": 100, "won": 1}] * 3)
    t = wp_table(df)
    assert t.iloc[0]["score_diff_c"] == 3 and t.iloc[0]["period_c"] == 4


def test_leverage_weight_is_wp_drop_of_a_goal_against():
    t = wp_table(_states())
    row = {"score_diff": 1, "period": 3, "time_s": 900}
    # up 1 late (wp .8) -> tied late (wp .5): a goal against costs .3
    assert leverage_weight(row, t) == pytest.approx(0.3)


def test_leverage_weight_missing_cell_returns_zero():
    t = wp_table(_states())
    assert leverage_weight({"score_diff": -2, "period": 1, "time_s": 0}, t) == 0.0


def test_leverage_weight_vectorized_matches_row_loop():
    t = wp_table(_states())
    grid = pd.DataFrame([
        {"score_diff": 0, "period": 3, "time_s": 900},   # in-range, tied
        {"score_diff": 1, "period": 3, "time_s": 900},   # in-range, up 1
        {"score_diff": -5, "period": 3, "time_s": 900},  # out-of-range score_diff
        {"score_diff": 0, "period": 6, "time_s": 900},   # out-of-range period
        {"score_diff": -2, "period": 1, "time_s": 0},    # sub-MIN_CELL / missing cell
    ])
    expected = grid.apply(lambda row: leverage_weight(row, t), axis=1).to_numpy()
    actual = leverage_weight_vectorized(grid, t)
    assert actual == pytest.approx(expected)
