import pytest

from v2.goalies.toi_5v5 import count_5v5_seconds, season_frame


def _row(code, away="8001", home="8002"):
    return {"situationCode": code, "awayGoalie": away, "homeGoalie": home}


def test_counts_only_strict_1551():
    rows = [_row("1551"), _row("1551"), _row("1451"), _row("0551")]
    assert count_5v5_seconds(rows) == {8001: 2, 8002: 2}


def test_credits_both_goalies_on_the_same_second():
    assert count_5v5_seconds([_row("1551")]) == {8001: 1, 8002: 1}


def test_empty_goalie_cell_credits_nobody():
    # Goalie pulled: the cell is blank. Nobody gains a second, and the pulled
    # goalie is not invented as a 0 row unless he appears elsewhere.
    rows = [_row("1551", away=""), _row("1551", away="")]
    assert count_5v5_seconds(rows) == {8002: 2}


def test_goalie_who_played_but_saw_no_5v5_gets_explicit_zero():
    # Appears in the game, never at 1551 -> 0, not a missing row. Downstream
    # needs to tell "played, no 5v5" apart from "no timeline at all".
    rows = [_row("1451"), _row("0651")]
    assert count_5v5_seconds(rows) == {8001: 0, 8002: 0}


def test_excludes_goalie_pulled_codes_that_the_skater_constant_includes():
    # compute_competition uses SCORED_SITUATIONS = {"1551","0651","1560"}.
    # Copying it here would pay the remaining goalie for empty-net time.
    rows = [_row("0651"), _row("1560"), _row("1551")]
    assert count_5v5_seconds(rows) == {8001: 1, 8002: 1}


def test_season_frame_grain_and_dtypes(tmp_path):
    (tmp_path / "2025020001.csv").write_text(
        "situationCode,awayGoalie,homeGoalie\n1551,8001,8002\n1551,8001,8002\n")
    (tmp_path / "2025020002.csv").write_text(
        "situationCode,awayGoalie,homeGoalie\n1551,8003,8002\n")
    df = season_frame("2025", tmp_path).sort_values(
        ["game_id", "goalie_id"]).reset_index(drop=True)

    assert list(df.columns) == ["season", "game_id", "goalie_id", "toi_5v5_s"]
    # Merge keys must match goalie_games_<season>.csv, which reads back int64.
    assert all(str(df[c].dtype) == "int64" for c in df.columns)
    assert len(df) == 4
    assert df.loc[0].tolist() == [2025, 2025020001, 8001, 2]
    assert df.loc[3].tolist() == [2025, 2025020002, 8003, 1]


def test_season_frame_raises_on_empty_timeline_dir(tmp_path):
    # The pre-backfill state of 2021/2022. An empty CSV here would blank a
    # whole season downstream while every stage still reported success.
    with pytest.raises(RuntimeError, match="no timelines"):
        season_frame("2021", tmp_path)
