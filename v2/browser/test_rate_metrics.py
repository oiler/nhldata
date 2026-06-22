import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from metrics import carryover_per_player, events_per60, corsi_per60
from build_league_db import count_5v5_events, corsi_for_game


_CORSI_COLS = {
    "typeDescKey": None, "situationCode": None, "timeInPeriod": None,
    "periodDescriptor.number": None, "details.shootingPlayerId": None,
    "details.scoringPlayerId": None,
}


def _ev(**kw):
    row = dict(_CORSI_COLS)
    row.update(kw)
    return row


def test_corsi_for_game_credits_shooter_side_from_timeline():
    # Home shooter 100 vs away on-ice {200,201,202,203,204}; home {100,101,102,103,104}
    timeline = [{
        "period": "1", "secondsIntoPeriod": "22", "situationCode": "1551",
        "awaySkaters": "200|201|202|203|204",
        "homeSkaters": "100|101|102|103|104",
    }]
    flat = pd.DataFrame([
        # a blocked shot BY home player 100 (blocker is away 200) -> still CF for home
        _ev(typeDescKey="blocked-shot", situationCode="1551", timeInPeriod="00:22",
            **{"periodDescriptor.number": 1, "details.shootingPlayerId": 100}),
    ])
    out = corsi_for_game(flat, timeline, game_id=99).set_index("playerId")
    assert out.loc[100, "cf"] == 1 and out.loc[100, "ca"] == 0   # shooter side = home
    assert out.loc[200, "ca"] == 1 and out.loc[200, "cf"] == 0   # away side against
    assert out["cf"].sum() == 5   # exactly the 5 home skaters credited CF
    assert out["ca"].sum() == 5   # exactly the 5 away skaters credited CA


def test_corsi_for_game_empty_timeline_returns_empty():
    flat = pd.DataFrame([
        _ev(typeDescKey="shot-on-goal", situationCode="1551", timeInPeriod="00:10",
            **{"periodDescriptor.number": 1, "details.shootingPlayerId": 100}),
    ])
    assert corsi_for_game(flat, [], game_id=99).empty


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


def test_events_per60_uses_full_toi_denominator():
    events = pd.DataFrame([
        {"gameId": 1, "playerId": 7, "hits": 3, "blocks": 1, "takeaways": 0, "giveaways": 2, "ishots": 4},
    ])
    # player 7 played two games at 5v5: 1200s total -> 3 hits over 1200s = 9.0/60min
    toi = pd.DataFrame([
        {"gameId": 1, "playerId": 7, "toi_seconds": 600},
        {"gameId": 2, "playerId": 7, "toi_seconds": 600},
    ])
    out = events_per60(events, toi)
    assert round(out.loc[7, "hits_per60"], 2) == 9.0       # 3 * 3600 / 1200
    assert round(out.loc[7, "gv_per60"], 2) == 6.0         # 2 * 3600 / 1200
    assert out.loc[7, "blocks_per60"] > 0
    assert round(out.loc[7, "ishots_per60"], 2) == 12.0    # 4 * 3600 / 1200


def test_corsi_per60_restricts_denominator_to_covered_games():
    onice = pd.DataFrame([
        {"gameId": 1, "playerId": 5, "cf": 10, "ca": 5},
    ])
    # game 2 has no onice row (missing timeline) -> its TOI must NOT dilute the rate
    toi = pd.DataFrame([
        {"gameId": 1, "playerId": 5, "toi_seconds": 600},
        {"gameId": 2, "playerId": 5, "toi_seconds": 600},
    ])
    out = corsi_per60(onice, toi)
    assert round(out.loc[5, "cf_per60"], 1) == 60.0   # 10 * 3600 / 600 (game 1 only)
    assert round(out.loc[5, "ca_per60"], 1) == 30.0   # 5  * 3600 / 600
    assert round(out.loc[5, "cf_pct"], 3) == 0.667    # 10 / 15


def test_count_5v5_events_counts_individual_shot_attempts():
    df = pd.DataFrame([
        {"typeDescKey": "shot-on-goal", "situationCode": "1551", "details.shootingPlayerId": 50, "details.scoringPlayerId": None, "details.blockingPlayerId": None},
        {"typeDescKey": "missed-shot",  "situationCode": "1551", "details.shootingPlayerId": 50, "details.scoringPlayerId": None, "details.blockingPlayerId": None},
        {"typeDescKey": "blocked-shot", "situationCode": "1551", "details.shootingPlayerId": 50, "details.scoringPlayerId": None, "details.blockingPlayerId": 60},
        {"typeDescKey": "goal",         "situationCode": "1551", "details.shootingPlayerId": None, "details.scoringPlayerId": 50, "details.blockingPlayerId": None},
        {"typeDescKey": "shot-on-goal", "situationCode": "1441", "details.shootingPlayerId": 50, "details.scoringPlayerId": None, "details.blockingPlayerId": None},  # not 5v5
    ])
    out = count_5v5_events(df, game_id=2025020001).set_index("playerId")
    assert out.loc[50, "ishots"] == 4         # SOG + missed + blocked(as shooter) + goal; 1441 excluded
    assert out.loc[60, "blocks"] == 1         # blocker still credited a block
    assert out.loc[60, "ishots"] == 0         # blocker did not attempt the shot


def test_points_per100_shots_ratio_and_floor():
    from metrics import points_per100_shots

    points = pd.DataFrame([
        {"gameId": 1, "playerId": 1, "points": 10},
        {"gameId": 1, "playerId": 2, "points": 3},
        {"gameId": 1, "playerId": 3, "points": 2},
    ])
    ishots = pd.DataFrame([
        {"gameId": 1, "playerId": 1, "ishots": 50},
        {"gameId": 1, "playerId": 2, "ishots": 20},
        {"gameId": 1, "playerId": 3, "ishots": 0},
    ])
    out = points_per100_shots(points, ishots, min_attempts=50)
    assert round(out.loc[1, "p_per100"], 1) == 20.0          # 10 * 100 / 50
    assert out.loc[1, "p_per100_ranked"] == 20.0             # 50 >= floor -> ranked
    assert round(out.loc[2, "p_per100"], 1) == 15.0          # 3 * 100 / 20
    assert pd.isna(out.loc[2, "p_per100_ranked"])            # 20 < 50 -> unranked
    assert pd.isna(out.loc[3, "p_per100"])                   # 0 attempts -> NaN value
