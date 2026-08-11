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


def test_nan_toi_games_excluded_from_crossice_rate():
    # A NaN toi_s means "no timeline for that goalie-game" (2021's five defective
    # source games), not "zero ice time". Summing crossice_shots with pandas'
    # NaN-skipping sum would keep the shots in the numerator while the TOI never
    # reaches the denominator, inflating the rate.
    games = pd.DataFrame({
        "season": [2021] * 2, "game_id": [100, 200], "goalie_id": [1, 1],
        "difficulty_pct": [50.0, float("nan")], "xg_per60": [2.5, float("nan")],
        "hd_share": [0.2, 0.2], "shots_faced": [30, 30],
        "crossice_shots": [2, 8], "toi_s": [3600.0, float("nan")],
    })
    gg = pd.DataFrame({
        "season": [2021] * 2, "game_id": [100, 200], "goalie_id": [1] * 2,
        "team_abbrev": ["EDM"] * 2, "game_date": ["2021-11-01", "2021-11-05"],
    })
    shots = pd.DataFrame({
        "season": [2021], "game_id": [100], "goalie_id": [1],
        "shot_type": ["wrist"], "shooter_position": ["F"],
        "on_net": [True], "is_goal": [False], "froze": [0.0],
        "goalie_is_home": [True], "home_abbrev": ["EDM"],
    })
    env = team_environment(games, gg, shots).iloc[0]
    assert env["crossice_per60"] == pytest.approx(2.0)
    # The no-timeline game is still a game played, and the NaN-skipping means
    # stay as they are — only the rate's numerator/denominator pair is filtered.
    assert env["gp"] == 2
    assert env["mean_xg_faced_per60"] == pytest.approx(2.5)


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
