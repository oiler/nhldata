import numpy as np
import pandas as pd
import pytest

from v2.goalies.game_difficulty import add_difficulty_pct, game_rows


def _shots():
    rows = []
    for gid, goalie, n, dist in ((1, 900, 20, 10.0), (2, 900, 10, 40.0)):
        for _ in range(n):
            rows.append({"season": 2023, "game_id": gid, "goalie_id": goalie,
                         "distance_adj": dist, "dt_prev": np.nan, "prev_type": np.nan,
                         "prev_same_team": np.nan, "prev_x_norm": np.nan,
                         "prev_y_norm": np.nan, "y_norm": 5.0})
    return pd.DataFrame(rows)


def _toi():
    return pd.DataFrame([
        {"season": 2023, "game_id": 1, "goalie_id": 900, "toi_s": 3600},
        {"season": 2023, "game_id": 2, "goalie_id": 900, "toi_s": 1800},
    ])


def test_game_rows_aggregates_and_rates():
    shots = _shots()
    xg = np.where(shots["distance_adj"] < 15, 0.15, 0.03)
    g = game_rows(shots, xg, _toi()).set_index("game_id")
    assert g.loc[1, "shots_faced"] == 20 and g.loc[1, "hd_share"] == 1.0
    assert g.loc[1, "xg_faced"] == pytest.approx(3.0)
    assert g.loc[1, "xg_per60"] == pytest.approx(3.0)          # 3.0 xg in 60 min
    assert g.loc[2, "xg_per60"] == pytest.approx(0.6)          # 0.3 xg in 30 min


def test_difficulty_pct_ranks_and_toi_floor():
    games = pd.DataFrame({
        "xg_per60": [1.0, 2.0, 3.0, 4.0, 99.0],
        "toi_s": [3600, 3600, 3600, 3600, 600],   # last one under the floor
    })
    out = add_difficulty_pct(games)
    ranked = out["difficulty_pct"].tolist()
    assert ranked[3] > ranked[2] > ranked[1] > ranked[0]
    assert np.isnan(ranked[4])
    assert ranked[3] == pytest.approx(100.0)
