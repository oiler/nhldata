import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from metrics import carryover_per_player
from build_league_db import count_5v5_events


def test_count_5v5_events_credits_correct_fields_and_filters_strength():
    df = pd.DataFrame([
        {"typeDescKey": "hit",          "situationCode": "1551", "details.hittingPlayerId": 10, "details.blockingPlayerId": None, "details.playerId": None},
        {"typeDescKey": "hit",          "situationCode": "1441", "details.hittingPlayerId": 10, "details.blockingPlayerId": None, "details.playerId": None},  # not 5v5
        {"typeDescKey": "blocked-shot", "situationCode": "1551", "details.hittingPlayerId": None, "details.blockingPlayerId": 20, "details.playerId": None},
        {"typeDescKey": "takeaway",     "situationCode": "1551", "details.hittingPlayerId": None, "details.blockingPlayerId": None, "details.playerId": 30},
        {"typeDescKey": "giveaway",     "situationCode": "1551", "details.hittingPlayerId": None, "details.blockingPlayerId": None, "details.playerId": 30},
    ])
    out = count_5v5_events(df, game_id=2025020001).set_index("playerId")
    assert out.loc[10, "hits"] == 1          # 1441 hit excluded
    assert out.loc[20, "blocks"] == 1
    assert out.loc[30, "takeaways"] == 1
    assert out.loc[30, "giveaways"] == 1
    assert (out["gameId"] == 2025020001).all()


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
