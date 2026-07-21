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
