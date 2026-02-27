# v2/orchestrator/tests/test_schedule.py
import json
from unittest.mock import patch, MagicMock

from v2.orchestrator.tools.schedule import check_schedule


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


@patch("v2.orchestrator.tools.schedule.requests.get")
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


@patch("v2.orchestrator.tools.schedule.requests.get")
def test_check_schedule_no_games(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"gameWeek": [{"date": "2026-02-25", "games": []}]}
    mock_get.return_value = mock_resp

    result = check_schedule("2026-02-25")
    assert result["status"] == "ok"
    assert result["game_ids"] == []
    assert result["game_count"] == 0


@patch("v2.orchestrator.tools.schedule.requests.get")
def test_check_schedule_api_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = Exception("Server error")
    mock_get.return_value = mock_resp

    result = check_schedule("2026-02-25")
    assert result["status"] == "error"
