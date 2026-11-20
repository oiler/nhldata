# pipeline/orchestrator/tools/schedule.py
"""Check the NHL schedule API for games played on a given date."""

import requests

SCHEDULE_URL = "https://api-web.nhle.com/v1/schedule/{date}"


def check_schedule(date: str) -> dict:
    """Query NHL schedule for games on the given date (YYYY-MM-DD).

    Returns dict with: status, date, game_ids, game_count (or error).
    Only includes regular-season games (gameType == 2).
    """
    try:
        resp = requests.get(SCHEDULE_URL.format(date=date), timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"status": "error", "date": date, "error": str(e)}

    game_ids = []
    for week_day in data.get("gameWeek", []):
        if week_day.get("date") != date:
            continue
        for game in week_day.get("games", []):
            if game.get("gameType") == 2:
                game_ids.append(game["id"])

    return {
        "status": "ok",
        "date": date,
        "game_ids": game_ids,
        "game_count": len(game_ids),
    }


FINISHED_STATES = {"OFF", "FINAL"}


def played_game_ids(through_date: str, season: str) -> list[int]:
    """Regular-season games of `season` that finished on or before through_date.

    Walks the schedule a week at a time from the season's first day, so the
    result does not depend on which earlier daily runs succeeded. Raises on an
    API failure: a partial list would look like games that need no work.
    """
    def week(start: str) -> dict:
        resp = requests.get(SCHEDULE_URL.format(date=start), timeout=30)
        resp.raise_for_status()
        return resp.json()

    game_ids = []
    start = week(through_date)["regularSeasonStartDate"]
    while start and start <= through_date:
        data = week(start)
        for week_day in data.get("gameWeek", []):
            if week_day["date"] > through_date:
                continue
            for game in week_day.get("games", []):
                if (game.get("gameType") == 2
                        and game.get("gameState") in FINISHED_STATES
                        and str(game["id"]).startswith(season)):
                    game_ids.append(game["id"])
        start = data.get("nextStartDate")

    return sorted(game_ids)
