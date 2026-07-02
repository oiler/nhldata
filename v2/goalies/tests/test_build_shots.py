import json

from v2.goalies.build_shots import build_season
from v2.goalies.tests.test_extract import _game, _play


def test_build_season_reads_dir_and_adds_season(tmp_path):
    plays = tmp_path / "2021" / "plays"
    plays.mkdir(parents=True)
    (plays / "2021020001.json").write_text(json.dumps(_game([_play("shot-on-goal")])))
    df = build_season(plays)
    assert len(df) == 1
    assert df.iloc[0]["season"] == "2021"
    assert df.iloc[0]["goalie_id"] == 900
