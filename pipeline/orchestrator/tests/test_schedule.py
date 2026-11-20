# pipeline/orchestrator/tests/test_schedule.py
import json
from unittest.mock import patch, MagicMock

from pipeline.orchestrator.tools.schedule import check_schedule


def _mock_schedule_response(game_ids: list[int], date: str = "2026-02-25"):
    """Build a minimal NHL schedule API response."""
    games = []
    for gid in game_ids:
        games.append({"id": gid, "gameType": 2, "gameState": "OFF"})
    return {
        "gameWeek": [
            {"date": date, "games": games}
        ]
    }


@patch("pipeline.orchestrator.tools.schedule.requests.get")
def test_check_schedule_returns_game_ids(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _mock_schedule_response(
        [2025020900, 2025020901, 2025020902], "2026-02-25"
    )
    mock_get.return_value = mock_resp

    result = check_schedule("2026-02-25")
    assert result["status"] == "ok"
    assert result["date"] == "2026-02-25"
    assert result["game_ids"] == [2025020900, 2025020901, 2025020902]
    assert result["game_count"] == 3


@patch("pipeline.orchestrator.tools.schedule.requests.get")
def test_check_schedule_no_games(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"gameWeek": [{"date": "2026-02-25", "games": []}]}
    mock_get.return_value = mock_resp

    result = check_schedule("2026-02-25")
    assert result["status"] == "ok"
    assert result["game_ids"] == []
    assert result["game_count"] == 0


@patch("pipeline.orchestrator.tools.schedule.requests.get")
def test_check_schedule_api_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = Exception("Server error")
    mock_get.return_value = mock_resp

    result = check_schedule("2026-02-25")
    assert result["status"] == "error"


def _week(start_date, next_start, days):
    """One schedule API response: days maps date -> list of (id, gameType, gameState)."""
    return {
        "regularSeasonStartDate": "2026-10-01",
        "nextStartDate": next_start,
        "gameWeek": [
            {"date": d, "games": [{"id": i, "gameType": t, "gameState": s} for i, t, s in games]}
            for d, games in days.items()
        ],
    }


@patch("pipeline.orchestrator.tools.schedule.requests.get")
def test_played_game_ids_walks_the_season_and_keeps_only_finished_games(mock_get):
    weeks = {
        "2026-10-01": _week("2026-10-01", "2026-10-08", {
            "2026-10-01": [(2026020002, 2, "OFF"), (2026020001, 2, "FINAL"),
                           (2026010099, 1, "OFF")],          # preseason game
            "2026-10-03": [(2026020003, 2, "PPD")],           # postponed, never played
        }),
        "2026-10-08": _week("2026-10-08", "2026-10-15", {
            "2026-10-08": [(2026020004, 2, "OFF"), (2025020005, 2, "OFF")],  # other season
            "2026-10-09": [(2026020006, 2, "OFF")],           # after through_date
        }),
    }

    def fake_get(url, timeout):
        resp = MagicMock()
        resp.json.return_value = weeks[url.rsplit("/", 1)[1]]
        return resp

    mock_get.side_effect = fake_get

    from pipeline.orchestrator.tools.schedule import played_game_ids
    assert played_game_ids("2026-10-08", "2026") == [2026020001, 2026020002, 2026020004]
