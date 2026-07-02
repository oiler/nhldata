import numpy as np
import pandas as pd
import pytest

from v2.goalies.features import STRUCTURE_COLS, build_features


def _row(**over):
    base = {
        "distance_adj": 30.0, "angle": 20.0, "shot_type": "wrist",
        "strength": "EV", "score_diff": 0, "goalie_is_home": True,
        "dt_prev": np.nan, "prev_type": np.nan, "prev_same_team": np.nan,
        "prev_x_norm": np.nan, "prev_y_norm": np.nan, "y_norm": 10.0,
    }
    base.update(over)
    return base


def test_column_order_and_intercept():
    X = build_features(pd.DataFrame([_row()]))
    assert list(X.columns) == STRUCTURE_COLS
    assert X.iloc[0]["intercept"] == 1.0
    assert X.dtypes.unique().tolist() == [np.dtype("float64")]


def test_distance_clamped_and_logged():
    X = build_features(pd.DataFrame([_row(distance_adj=-0.099)]))
    assert X.iloc[0]["dist"] == 0.0
    assert X.iloc[0]["log1p_dist"] == 0.0


def test_shot_type_dummies():
    X = build_features(pd.DataFrame([
        _row(shot_type="wrist"), _row(shot_type="snap"), _row(shot_type="tip-in"),
        _row(shot_type="deflected"), _row(shot_type="poke"),
    ]))
    assert X["snap"].tolist() == [0, 1, 0, 0, 0]
    assert X["tip_deflect"].tolist() == [0, 0, 1, 1, 0]
    assert X["other_type"].tolist() == [0, 0, 0, 0, 1]


def test_strength_and_score_dummies():
    X = build_features(pd.DataFrame([
        _row(strength="PP", score_diff=-3), _row(strength="SH", score_diff=1),
    ]))
    assert X.iloc[0][["pp", "sh", "trail2", "lead1"]].tolist() == [1, 0, 1, 0]
    assert X.iloc[1][["pp", "sh", "trail2", "lead1"]].tolist() == [0, 1, 0, 1]


def test_rebound_rush_crossice_flags():
    X = build_features(pd.DataFrame([
        _row(dt_prev=2, prev_same_team=True, prev_type="shot-on-goal",
             prev_x_norm=80.0, prev_y_norm=-8.0, y_norm=10.0),   # rebound + crossice, not rush
        _row(dt_prev=3, prev_same_team=False, prev_type="giveaway",
             prev_x_norm=10.0, prev_y_norm=2.0),                  # rush only (x<25, dt<=4)
        _row(),                                                    # all NaN -> all False
    ]))
    assert X["is_rebound"].tolist() == [1, 0, 0]
    assert X["is_crossice_quick"].tolist() == [1, 0, 0]
    assert X["is_rush"].tolist() == [0, 1, 0]
