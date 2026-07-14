from v2.goalies.toi import extract_goalie_games, parse_toi


def _box():
    return {
        "id": 2023020100,
        "gameDate": "2023-10-28",
        "homeTeam": {"abbrev": "EDM", "score": 3},
        "awayTeam": {"abbrev": "CGY", "score": 4},
        "playerByGameStats": {
            "homeTeam": {"goalies": [
                {"playerId": 900, "toi": "58:31", "starter": True,
                 "shotsAgainst": 30, "goalsAgainst": 4, "saves": 26},
                {"playerId": 901, "toi": "00:00", "starter": False,
                 "shotsAgainst": 0, "goalsAgainst": 0, "saves": 0},
            ]},
            "awayTeam": {"goalies": [
                {"playerId": 902, "toi": "60:00", "starter": True,
                 "shotsAgainst": 28, "goalsAgainst": 3, "saves": 25},
            ]},
        },
    }


def test_parse_toi():
    assert parse_toi("58:31") == 3511
    assert parse_toi("61:23") == 3683
    assert parse_toi("00:00") == 0


def test_extract_goalie_games_skips_unused_backup():
    rows = extract_goalie_games(_box())
    assert [r["goalie_id"] for r in rows] == [900, 902]
    home = rows[0]
    assert home["team_abbrev"] == "EDM" and home["opp_abbrev"] == "CGY"
    assert home["is_home"] is True and home["starter"] is True
    assert home["toi_s"] == 3511 and home["shots_against"] == 30
    assert home["goals_against"] == 4 and home["box_saves"] == 26
    assert home["game_date"] == "2023-10-28" and home["game_id"] == 2023020100
    assert rows[1]["is_home"] is False and rows[1]["team_abbrev"] == "CGY"
