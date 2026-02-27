# v2/orchestrator/tests/test_validate.py
import json
import tempfile
from pathlib import Path

from v2.orchestrator.tools.validate import validate_game


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_validate_game_all_present():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "data" / "2025"
        game_id = "2025020001"
        _write_json(base / "boxscores" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "plays" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "meta" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "shifts" / f"{game_id}_home.json", {"shifts": []})
        _write_json(base / "shifts" / f"{game_id}_away.json", {"shifts": []})

        result = validate_game(game_id, data_dir=base)
        assert result["status"] == "complete"
        assert result["missing"] == []


def test_validate_game_missing_shifts():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "data" / "2025"
        game_id = "2025020001"
        _write_json(base / "boxscores" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "plays" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "meta" / f"{game_id}.json", {"id": game_id})
        # No shifts files

        result = validate_game(game_id, data_dir=base)
        assert result["status"] == "incomplete"
        assert "shifts_home" in result["missing"]
        assert "shifts_away" in result["missing"]


def test_validate_game_invalid_json():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "data" / "2025"
        game_id = "2025020001"
        (base / "boxscores").mkdir(parents=True)
        (base / "boxscores" / f"{game_id}.json").write_text("not json{{{")
        _write_json(base / "plays" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "meta" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "shifts" / f"{game_id}_home.json", {"shifts": []})
        _write_json(base / "shifts" / f"{game_id}_away.json", {"shifts": []})

        result = validate_game(game_id, data_dir=base)
        assert result["status"] == "invalid"
        assert "boxscore" in result["errors"][0]
