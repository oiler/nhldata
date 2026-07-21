import pandas as pd

from v2.goalies.switch_registry import (fenwick_by_game, nonswitch_pseudo_cases,
                                        stint_table, switch_cases)


def _gg(rows):
    return pd.DataFrame(rows, columns=["season", "game_id", "goalie_id",
                                       "team_abbrev", "game_date"])


def _fw(gg, per_game=40):
    return gg[["season", "game_id", "goalie_id"]].assign(fenwick=per_game)


def test_offseason_switch_and_floor():
    rows = ([(2021, i, 1, "EDM", f"2021-11-{i:02d}") for i in range(1, 21)]
            + [(2022, 100 + i, 1, "CGY", f"2022-11-{i:02d}") for i in range(1, 21)])
    stints = stint_table(_gg(rows), _fw(_gg(rows)))
    cases = switch_cases(stints)
    assert len(cases) == 1
    c = cases.iloc[0]
    assert c["switch_type"] == "offseason" and c["switch_date"] == "2022-11-01"
    assert c["pre_team"] == "EDM" and c["post_team"] == "CGY"
    assert c["pre_fenwick"] == 800 and c["post_fenwick"] == 800 and c["weight"] == 800
    assert c["last_pre_season"] == 2021 and c["first_post_season"] == 2022


def test_midseason_switch_classified_and_low_workload_excluded():
    rows = ([(2023, i, 2, "TOR", f"2023-11-{i:02d}") for i in range(1, 21)]
            + [(2023, 50 + i, 2, "VAN", f"2023-12-{i:02d}") for i in range(1, 21)]
            + [(2023, 90 + i, 3, "BOS", f"2023-11-{i:02d}") for i in range(1, 3)]
            + [(2023, 95 + i, 3, "SEA", f"2023-12-{i:02d}") for i in range(1, 3)])
    gg = _gg(rows)
    cases = switch_cases(stint_table(gg, _fw(gg)))
    assert len(cases) == 1                      # goalie 3 fails the 600 floor
    assert cases.iloc[0]["switch_type"] == "midseason"
    assert cases.iloc[0]["goalie_id"] == 2


def test_pre_fenwick_is_cumulative_over_all_prior_stints():
    rows = ([(2021, i, 4, "EDM", f"2021-11-{i:02d}") for i in range(1, 11)]
            + [(2022, 30 + i, 4, "CGY", f"2022-11-{i:02d}") for i in range(1, 11)]
            + [(2023, 60 + i, 4, "VAN", f"2023-11-{i:02d}") for i in range(1, 21)])
    gg = _gg(rows)
    cases = switch_cases(stint_table(gg, _fw(gg)))
    van = cases[cases["post_team"] == "VAN"].iloc[0]
    assert van["pre_fenwick"] == 800            # EDM 400 + CGY 400 pooled


def test_nonswitch_pseudo_cases():
    rows = ([(2021, i, 5, "EDM", f"2021-11-{i:02d}") for i in range(1, 21)]
            + [(2022, 100 + i, 5, "EDM", f"2022-11-{i:02d}") for i in range(1, 21)])
    gg = _gg(rows)
    fw = _fw(gg)
    pseudo = nonswitch_pseudo_cases(stint_table(gg, fw), gg, fw)
    assert len(pseudo) == 1
    p = pseudo.iloc[0]
    assert p["switch_type"] == "nonswitch" and p["switch_date"] == "2022-11-01"
    assert p["pre_team"] == "EDM" and p["post_team"] == "EDM"
    assert p["pre_fenwick"] == 800 and p["post_fenwick"] == 800


def test_return_to_former_team_forms_new_stint():
    rows = ([(2021, i, 6, "EDM", f"2021-11-{i:02d}") for i in range(1, 21)]
            + [(2022, 100 + i, 6, "CGY", f"2022-11-{i:02d}") for i in range(1, 21)]
            + [(2023, 200 + i, 6, "EDM", f"2023-11-{i:02d}") for i in range(1, 21)])
    gg = _gg(rows)
    cases = switch_cases(stint_table(gg, _fw(gg)))
    assert len(cases) == 2
    edm_return = cases[cases["post_team"] == "EDM"].iloc[0]
    assert edm_return["pre_fenwick"] == 1600     # EDM 800 + CGY 800 pooled


def test_pseudo_gap_year_labels_actual_last_played_season():
    rows = ([(2021, i, 7, "EDM", f"2021-11-{i:02d}") for i in range(1, 21)]
            + [(2023, 200 + i, 7, "EDM", f"2023-11-{i:02d}") for i in range(1, 21)])
    gg = _gg(rows)
    fw = _fw(gg)
    pseudo = nonswitch_pseudo_cases(stint_table(gg, fw), gg, fw)
    assert len(pseudo) == 1
    p = pseudo.iloc[0]
    assert p["last_pre_season"] == 2021           # actual last played, not the gap year
    assert p["first_post_season"] == 2023


def test_switch_cases_floor_parameter():
    # two stints of 550 fenwick each: below the 600 floor, above a 500 floor
    stints = pd.DataFrame({
        "goalie_id": [1, 1], "stint_id": [1, 2], "team": ["EDM", "CGY"],
        "start": ["2023-10-01", "2024-10-01"], "end": ["2024-04-01", "2025-04-01"],
        "first_season": [2023, 2024], "last_season": [2023, 2024],
        "fenwick": [550, 550],
    })
    assert len(switch_cases(stints)) == 0                 # default 600 floor
    assert len(switch_cases(stints, floor=500)) == 1


def test_fenwick_by_game_excludes_blocked():
    shots = pd.DataFrame({
        "season": [2023] * 3, "game_id": [1] * 3, "goalie_id": [9] * 3,
        "event": ["shot-on-goal", "blocked-shot", "missed-shot"],
    })
    fw = fenwick_by_game(shots)
    assert fw.iloc[0]["fenwick"] == 2
