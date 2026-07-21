"""Extract every unblocked shot faced by a goalie, all strength states.

Raw-first: reads a single game's play-by-play dict, returns flat rows.
Freeze/rebound outcomes are computed only for saves (on-net non-goals).
"""

from v2.goalies.geometry import (attack_flip, normalize, parse_time,
                                 shot_angle, shot_distance)
from v2.goalies.situations import PENALTY_SHOT_CODES, strength_for_goalie
from v2.goalies.windows import detect_freeze, detect_rebound

SHOT_EVENTS = {"goal", "shot-on-goal", "missed-shot"}


def _event_stream(plays):
    """(time_s, typeDescKey, ownerTeamId, period) for every play with a timestamp."""
    out = []
    for p in plays:
        if "timeInPeriod" not in p:
            continue
        d = p.get("details", {})
        out.append((parse_time(p["timeInPeriod"]), p["typeDescKey"],
                    d.get("eventOwnerTeamId"), p["periodDescriptor"]["number"]))
    return out


def extract_goalie_shots(game: dict) -> list[dict]:
    """Extract every unblocked shot faced by a goalie in one game.

    Prior-event fields (`dt_prev`, `prev_type`, `prev_same_team`,
    `prev_x_norm`/`prev_y_norm`) reference the nearest preceding
    COORDINATE-BEARING play in the same period -- events without
    coordinates (e.g. most stoppages) are skipped when looking back.
    """
    home_id = game["homeTeam"]["id"]
    positions = {rs["playerId"]: rs["positionCode"] for rs in game["rosterSpots"]}
    stream = _event_stream(game["plays"])
    rows = []
    away_score = home_score = 0
    prev_event = None  # (time_s, type, owner, period, x, y)
    stream_idx = 0

    for play in game["plays"]:
        d = play.get("details", {})
        period = play["periodDescriptor"]["number"]
        t = parse_time(play["timeInPeriod"]) if "timeInPeriod" in play else None
        if t is not None:
            stream_idx += 1  # stream position of THIS play (events after = stream[stream_idx:])

        code = play.get("situationCode")
        is_shot = (
            play["typeDescKey"] in SHOT_EVENTS
            and play["periodDescriptor"]["periodType"] in ("REG", "OT")
            and code is not None and code not in PENALTY_SHOT_CODES
            and d.get("goalieInNetId") is not None
            and d.get("xCoord") is not None and d.get("yCoord") is not None
        )
        if is_shot:
            goalie_id = d["goalieInNetId"]
            shooter_team = d["eventOwnerTeamId"]
            goalie_is_home = shooter_team != home_id
            shooter = d.get("shootingPlayerId") or d.get("scoringPlayerId")
            pos = positions.get(shooter)
            if pos is not None and pos != "G":
                flip = attack_flip(play["homeTeamDefendingSide"], not goalie_is_home)
                xn, yn = normalize(d["xCoord"], d["yCoord"], flip)
                is_goal = play["typeDescKey"] == "goal"
                on_net = play["typeDescKey"] in ("goal", "shot-on-goal")
                own = home_score if goalie_is_home else away_score
                opp = away_score if goalie_is_home else home_score
                froze = rebound = None
                if on_net and not is_goal:
                    after = stream[stream_idx:]
                    froze = detect_freeze(after, t, period)
                    rebound = detect_rebound(after, t, period, shooter_team)
                row = {
                    "game_id": game["id"],
                    "game_date": game.get("gameDate"),
                    "home_abbrev": game["homeTeam"]["abbrev"],
                    "goalie_id": goalie_id,
                    "goalie_is_home": goalie_is_home,
                    "shooter_id": shooter,
                    "shooter_position": "D" if pos == "D" else "F",
                    "event": play["typeDescKey"],
                    "is_goal": is_goal,
                    "on_net": on_net,
                    "strength": strength_for_goalie(code, goalie_is_home),
                    "situation_code": code,
                    "score_diff": own - opp,
                    "period": period,
                    "time_s": t,
                    "x_norm": xn,
                    "y_norm": yn,
                    "distance": shot_distance(xn, yn),
                    "angle": shot_angle(xn, yn),
                    "shot_type": d.get("shotType"),
                    "zone": d.get("zoneCode"),
                    "dt_prev": t - prev_event[0] if prev_event and prev_event[3] == period else None,
                    "prev_type": prev_event[1] if prev_event and prev_event[3] == period else None,
                    "prev_same_team": (prev_event[2] == shooter_team)
                                      if prev_event and prev_event[3] == period else None,
                    "prev_x_norm": flip * prev_event[4] if prev_event and prev_event[3] == period else None,
                    "prev_y_norm": flip * prev_event[5] if prev_event and prev_event[3] == period else None,
                    "froze": froze,
                    "rebound_generated": rebound,
                }
                rows.append(row)

        if play["typeDescKey"] == "goal" and "awayScore" in d:
            away_score, home_score = d["awayScore"], d["homeScore"]
        if t is not None and d.get("xCoord") is not None and d.get("yCoord") is not None:
            prev_event = (t, play["typeDescKey"], d.get("eventOwnerTeamId"), period,
                          d["xCoord"], d["yCoord"])

    return rows
