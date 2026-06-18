import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from metrics import carryover_per_player


def test_carryover_per_player_aggregates_line_and_joins_bursts():
    comp = pd.DataFrame({
        "playerId": [1, 1, 2],
        "line_number": [1, 3, 2],
    })
    bursts = pd.DataFrame(
        {"bursts_per_60": [4.5, 1.2], "speed_max_mph": [22.1, 20.0]},
        index=pd.Index([1, 2], name="playerId"),
    )
    out = carryover_per_player(comp, bursts)
    assert out.loc[1, "avg_line"] == 2.0          # mean(1, 3)
    assert out.loc[1, "bursts_per_60"] == 4.5
    assert out.loc[2, "speed_max_mph"] == 20.0


def test_carryover_per_player_missing_bursts_is_nan():
    comp = pd.DataFrame({"playerId": [9], "line_number": [2]})
    bursts = pd.DataFrame(columns=["bursts_per_60", "speed_max_mph"])
    bursts.index.name = "playerId"
    out = carryover_per_player(comp, bursts)
    assert out.loc[9, "avg_line"] == 2.0
    assert pd.isna(out.loc[9, "bursts_per_60"])
