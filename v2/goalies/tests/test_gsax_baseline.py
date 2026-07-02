import pytest

from v2.goalies.gsax_baseline import gsax_table
from v2.goalies.tests.test_difficulty import _synthetic_shots


def test_gsax_identifies_the_weaker_goalie():
    df = _synthetic_shots(3000)
    table = gsax_table(df).set_index("goalie_id")
    # goalie 901 allows +0.8 logits more than the blind model expects
    assert table.loc[901, "gsax"] < table.loc[900, "gsax"]
    assert table.loc[900, "shots"] == 3000
    # xGA sums to total expected goals: with symmetric goalies, total xga ~ total ga
    total = table["xga"].sum() / table["ga"].sum()
    assert total == pytest.approx(1.0, abs=0.05)
    assert table.loc[900, "gsax_per100"] == pytest.approx(
        100 * table.loc[900, "gsax"] / 3000)
