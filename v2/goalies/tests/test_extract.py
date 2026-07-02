from v2.goalies.extract import extract_goalie_shots

HOME, AWAY = 10, 20
HOME_GOALIE, AWAY_GOALIE = 900, 901


def _play(type_desc, time="05:00", code="1551", x=-70, y=-20, shooter=1,
          goalie=HOME_GOALIE, owner=AWAY, shot_type="wrist", period=1,
          period_type="REG", defending="right"):
    details = {"xCoord": x, "yCoord": y, "zoneCode": "O", "eventOwnerTeamId": owner}
    if type_desc == "goal":
        details.update(scoringPlayerId=shooter, shotType=shot_type,
                       goalieInNetId=goalie, awayScore=1, homeScore=0)
    elif type_desc in ("shot-on-goal", "missed-shot"):
        details.update(shootingPlayerId=shooter, shotType=shot_type, goalieInNetId=goalie)
    return {
        "typeDescKey": type_desc,
        "situationCode": code,
        "homeTeamDefendingSide": defending,
        "periodDescriptor": {"number": period, "periodType": period_type},
        "timeInPeriod": time,
        "details": details,
    }


def _game(plays):
    return {
        "id": 2021020001,
        "gameDate": "2021-10-12",
        "homeTeam": {"id": HOME, "abbrev": "EDM"},
        "awayTeam": {"id": AWAY, "abbrev": "CGY"},
        "rosterSpots": [
            {"playerId": 1, "positionCode": "C", "teamId": AWAY},
            {"playerId": 2, "positionCode": "D", "teamId": AWAY},
            {"playerId": HOME_GOALIE, "positionCode": "G", "teamId": HOME},
            {"playerId": AWAY_GOALIE, "positionCode": "G", "teamId": AWAY},
        ],
        "plays": plays,
    }


def test_basic_save_row():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal"),
        _play("stoppage", time="05:01", owner=None, goalie=None),
    ]))
    assert len(rows) == 1
    r = rows[0]
    assert r["goalie_id"] == HOME_GOALIE and r["goalie_is_home"] is True
    assert r["is_goal"] is False and r["on_net"] is True
    assert r["strength"] == "EV"
    # away shooter, home defends right -> away attacks +x -> no flip
    assert (r["x_norm"], r["y_norm"]) == (-70, -20)
    assert r["froze"] is True and r["rebound_generated"] is False


def test_home_shot_flips_coordinates():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal", owner=HOME, goalie=AWAY_GOALIE, x=-70, y=-20),
    ]))
    # home defends right -> home attacks -x -> flip=-1
    assert (rows[0]["x_norm"], rows[0]["y_norm"]) == (70, 20)
    assert rows[0]["goalie_is_home"] is False


def test_rebound_and_no_freeze():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal", time="05:00"),
        _play("missed-shot", time="05:02"),
    ]))
    assert rows[0]["rebound_generated"] is True and rows[0]["froze"] is False


def test_goal_updates_score_diff_and_skips_windows():
    rows = extract_goalie_shots(_game([
        _play("goal", time="05:00"),
        _play("shot-on-goal", time="10:00"),
    ]))
    goal, save = rows
    assert goal["is_goal"] is True and goal["froze"] is None
    assert goal["score_diff"] == 0          # tied when the shot was taken
    assert save["score_diff"] == -1         # home goalie's team now trails
    assert save["dt_prev"] == 300 and save["prev_type"] == "goal"
    # prior-event coords carry the same flip as the shot (away shooter, no flip)
    assert (save["prev_x_norm"], save["prev_y_norm"]) == (-70, -20)


def test_exclusions():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal", goalie=None),                    # empty net
        _play("shot-on-goal", code="0101"),                    # penalty shot
        _play("shot-on-goal", period_type="SO", period=5),     # shootout
        _play("shot-on-goal", x=None),                         # missing coords
        _play("blocked-shot"),                                 # blocked
    ]))
    assert rows == []


def test_shooter_position_and_pk_strength():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal", shooter=2, code="1451"),  # away D shoots while away is SH
    ]))
    assert rows[0]["shooter_position"] == "D"
    assert rows[0]["strength"] == "PP"  # home goalie's team has 5 v 4
