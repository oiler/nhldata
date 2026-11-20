# pipeline/orchestrator/tests/test_validate.py
import json
import tempfile
from pathlib import Path

from pipeline.orchestrator.tools.validate import validate_game


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


def _write_raw(base: Path, game_id: str):
    for sub, name in (("boxscores", f"{game_id}.json"), ("plays", f"{game_id}.json"),
                      ("meta", f"{game_id}.json"), ("shifts", f"{game_id}_home.json"),
                      ("shifts", f"{game_id}_away.json")):
        _write_json(base / sub / name, {"id": game_id})


def _write_derived(base: Path, game_id: str, skip: str | None = None):
    for sub in ("flatplays", "timelines/csv", "competition"):
        if sub == skip:
            continue
        path = base / "generated" / sub / f"{game_id}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")


def test_pending_games_separates_fetch_from_generate():
    from pipeline.orchestrator.tools.validate import pending_games

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        # 1: fully processed. 2: never fetched. 3: fetched, timeline never generated.
        _write_raw(base, "2026020001")
        _write_derived(base, "2026020001")
        _write_raw(base, "2026020003")
        _write_derived(base, "2026020003", skip="timelines/csv")

        result = pending_games([2026020001, 2026020002, 2026020003], data_dir=base)

    assert result == {"fetch": [2], "generate": [2, 3]}
