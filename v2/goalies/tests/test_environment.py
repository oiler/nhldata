import pandas as pd
import pytest

from v2.goalies.environment import arena_freeze_offsets, team_environment


def test_b2b_uses_game_date_not_id():
    games = pd.DataFrame({
        "season": [2021] * 3, "game_id": [500, 100, 300],  # ids out of order on purpose
        "goalie_id": [1, 1, 1], "difficulty_pct": [50.0] * 3,
        "xg_per60": [2.5] * 3, "hd_share": [0.2] * 3,
        "shots_faced": [30] * 3, "crossice_shots": [2] * 3, "toi_s": [3600] * 3,
    })
    gg = pd.DataFrame({
        "season": [2021] * 3, "game_id": [500, 100, 300], "goalie_id": [1] * 3,
        "team_abbrev": ["EDM"] * 3,
        "game_date": ["2021-11-03", "2021-11-01", "2021-11-02"],
    })
    shots = pd.DataFrame({
        "season": [2021] * 2, "game_id": [500, 100], "goalie_id": [1, 1],
        "shot_type": ["tip-in", "wrist"], "shooter_position": ["D", "F"],
        "on_net": [True, True], "is_goal": [False, False], "froze": [1.0, 0.0],
        "goalie_is_home": [True, True], "home_abbrev": ["EDM", "EDM"],
    })
    env = team_environment(games, gg, shots).iloc[0]
    # dates 11-01, 11-02, 11-03 are consecutive: two back-to-backs
    assert env["b2b_games"] == 2
    assert env["gp"] == 3 and env["tip_share"] == pytest.approx(0.5)
    assert env["d_shot_share"] == pytest.approx(0.5)


def test_arena_freeze_offsets_sign():
    # arena AAA freezes visiting goalies' saves at 0.6; their away baseline is 0.4
    rows = []
    for arena, n_frozen, n in (("AAA", 60, 100), ("BBB", 40, 100)):
        for i in range(n):
            rows.append({"home_abbrev": arena, "goalie_is_home": False,
                         "goalie_id": 7, "on_net": True, "is_goal": False,
                         "froze": 1.0 if i < n_frozen else 0.0})
    off = arena_freeze_offsets(pd.DataFrame(rows)).set_index("home_abbrev")
    assert off.loc["AAA", "freeze_offset"] == pytest.approx(0.1)
    assert off.loc["BBB", "freeze_offset"] == pytest.approx(-0.1)
