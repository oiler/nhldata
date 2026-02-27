# v2/orchestrator/tools/schedule.py
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
