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


def test_game_rows_flag_recompute_matches_features():
    # One game, one goalie, 5 shots — each row isolates one of rush/rebound/
    # crossice per the CURRENT features.py:46-48 definitions:
    #   is_rebound = (dt<=3) & same_team & prev_type in CORSI_PREV
    #   is_rush    = (dt<=4) & (prev_x_norm < 25)                (no same-team requirement)
    #   is_crossice_quick = (dt<=3) & same_team & (prev_y*y < 0) & (|prev_y| >= 5)
    rows = [
        # (a) rebound only: dt<=3, same team, prev_type is a CORSI event;
        #     prev_x_norm kept >=25 to avoid also tripping rush.
        {"dt_prev": 2, "prev_type": "blocked-shot", "prev_same_team": True,
         "prev_x_norm": 50.0, "prev_y_norm": 1.0, "y_norm": 1.0},
        # (b) non-rebound control: dt_prev=5 defeats rebound despite a CORSI
        #     type + same team, and defeats rush despite prev_x_norm < 25.
        {"dt_prev": 5, "prev_type": "goal", "prev_same_team": True,
         "prev_x_norm": 10.0, "prev_y_norm": 1.0, "y_norm": 1.0},
        # (c) rush only: dt<=4, prev_x_norm<25, and NOT same team — proves
        #     rush has no same-team requirement while it also suppresses
        #     rebound/crossice for this row.
        {"dt_prev": 3, "prev_type": "missed-shot", "prev_same_team": False,
         "prev_x_norm": 10.0, "prev_y_norm": 1.0, "y_norm": 1.0},
        # (d) crossice only: dt<=3, same team, opposite sides of center,
        #     |prev_y_norm|>=5; prev_type not a CORSI event and prev_x_norm
        #     >=25 keep rebound/rush both false.
        {"dt_prev": 2, "prev_type": "wrap-around", "prev_same_team": True,
         "prev_x_norm": 50.0, "prev_y_norm": -10.0, "y_norm": 8.0},
        # (e) no prior shot (period/game start) — all NaN, all flags false.
        {"dt_prev": np.nan, "prev_type": np.nan, "prev_same_team": np.nan,
         "prev_x_norm": np.nan, "prev_y_norm": np.nan, "y_norm": 5.0},
    ]
    shots = pd.DataFrame(rows)
    shots["season"] = 2023
    shots["game_id"] = 1
    shots["goalie_id"] = 900
    shots["distance_adj"] = 20.0

    xg = np.full(len(shots), 0.05)
    toi = pd.DataFrame([{"season": 2023, "game_id": 1, "goalie_id": 900, "toi_s": 1200}])

    g = game_rows(shots, xg, toi).set_index("game_id")
    assert g.loc[1, "rebound_shots"] == 1
    assert g.loc[1, "rush_shots"] == 1
    assert g.loc[1, "crossice_shots"] == 1


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
