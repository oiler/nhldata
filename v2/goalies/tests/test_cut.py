import pandas as pd

import v2.goalies.cut as cut
from v2.goalies.cut import GEN, filter_cut, gen_dir, parse_situation


def test_parse_situation_default_flag_and_unknown_args():
    assert parse_situation([]) == "all"
    assert parse_situation(["--situation", "5v5"]) == "5v5"
    assert parse_situation(["--situation", "5v5", "--floor", "500"]) == "5v5"


def test_gen_dir():
    assert gen_dir("all") == GEN
    assert gen_dir("5v5") == GEN / "5v5"


def test_filter_cut_strict_1551_only():
    df = pd.DataFrame({"situation_code": ["1551", "1451", "0551", "1551"],
                       "x": [1, 2, 3, 4]})
    assert list(filter_cut(df, "5v5")["x"]) == [1, 4]


def test_filter_cut_handles_int_codes():
    # a plain read_csv parses "0551" as int 551 — 551 != 1551 so it still drops
    df = pd.DataFrame({"situation_code": [1551, 551, 1441], "x": [1, 2, 3]})
    assert list(filter_cut(df, "5v5")["x"]) == [1]


def test_filter_cut_all_is_identity():
    df = pd.DataFrame({"situation_code": ["1451"], "x": [1]})
    assert filter_cut(df, "all") is df


def test_load_shots_5v5_with_usecols(tmp_path, monkeypatch):
    pd.DataFrame({"season": [2025, 2025], "situation_code": ["1551", "0551"],
                  "is_goal": [False, True]}).to_csv(tmp_path / "shots_2025.csv",
                                                    index=False)
    monkeypatch.setattr(cut, "GEN", tmp_path)
    df = cut.load_shots("2025", "5v5", usecols=["season", "is_goal"])
    assert list(df.columns) == ["season", "is_goal"]
    assert len(df) == 1 and not bool(df["is_goal"].iloc[0])


def test_load_shots_all_keeps_every_row(tmp_path, monkeypatch):
    pd.DataFrame({"season": [2025, 2025], "situation_code": ["1551", "0551"],
                  "is_goal": [False, True]}).to_csv(tmp_path / "shots_2025.csv",
                                                    index=False)
    monkeypatch.setattr(cut, "GEN", tmp_path)
    assert len(cut.load_shots("2025", "all")) == 2


def _write_goalie_games(tmp_path):
    pd.DataFrame({
        "season": [2025, 2025, 2025],
        "game_id": [2025020001, 2025020001, 2025020002],
        "goalie_id": [8001, 8002, 8003],
        "team_abbrev": ["EDM", "CGY", "EDM"],
        "game_date": ["2025-10-07"] * 3,
        "starter": [True, True, True],
        "toi_s": [3600, 3600, 1800],
    }).to_csv(tmp_path / "goalie_games_2025.csv", index=False)


def test_load_toi_all_returns_boxscore_toi_unchanged(tmp_path, monkeypatch):
    _write_goalie_games(tmp_path)
    monkeypatch.setattr(cut, "GEN", tmp_path)
    df = cut.load_toi("2025", "all")
    assert list(df["toi_s"]) == [3600, 3600, 1800]
    assert list(df.columns) == list(
        pd.read_csv(tmp_path / "goalie_games_2025.csv").columns)


def test_load_toi_5v5_swaps_denominator_and_keeps_other_columns(tmp_path, monkeypatch):
    _write_goalie_games(tmp_path)
    (tmp_path / "5v5").mkdir()
    pd.DataFrame({
        "season": [2025, 2025, 2025],
        "game_id": [2025020001, 2025020001, 2025020002],
        "goalie_id": [8001, 8002, 8003],
        "toi_5v5_s": [2900, 2880, 1500],
    }).to_csv(tmp_path / "5v5" / "goalie_toi_2025.csv", index=False)
    monkeypatch.setattr(cut, "GEN", tmp_path)

    df = cut.load_toi("2025", "5v5").sort_values("goalie_id").reset_index(drop=True)
    assert list(df["toi_s"]) == [2900, 2880, 1500]
    # Consumers read these off the same frame; losing them breaks environment.py.
    assert {"team_abbrev", "game_date", "starter"} <= set(df.columns)
    assert "toi_5v5_s" not in df.columns
    assert list(df["team_abbrev"]) == ["EDM", "CGY", "EDM"]


def test_load_toi_5v5_missing_timeline_row_is_nan_not_zero(tmp_path, monkeypatch):
    # NaN means "no timeline" (a data gap); 0 means "played, saw no 5v5".
    # Collapsing them would hide missing data behind a legitimate-looking rate.
    _write_goalie_games(tmp_path)
    (tmp_path / "5v5").mkdir()
    pd.DataFrame({
        "season": [2025, 2025],
        "game_id": [2025020001, 2025020001],
        "goalie_id": [8001, 8002],
        "toi_5v5_s": [2900, 0],
    }).to_csv(tmp_path / "5v5" / "goalie_toi_2025.csv", index=False)
    monkeypatch.setattr(cut, "GEN", tmp_path)

    df = cut.load_toi("2025", "5v5").set_index("goalie_id")
    assert df.loc[8002, "toi_s"] == 0
    assert pd.isna(df.loc[8003, "toi_s"])
