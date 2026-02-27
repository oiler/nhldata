# v2/orchestrator/tools/validate.py
"""Validate raw game data — file existence, JSON parsing, structure."""

import json
from pathlib import Path

from v2.orchestrator.config import season_dir

EXPECTED_FILES = {
    "boxscore": "boxscores/{game_id}.json",
    "plays": "plays/{game_id}.json",
    "meta": "meta/{game_id}.json",
    "shifts_home": "shifts/{game_id}_home.json",
    "shifts_away": "shifts/{game_id}_away.json",
}


def validate_game(game_id: str, data_dir: Path | None = None,
                  season: str | None = None) -> dict:
    """Validate that all raw data files exist and parse as valid JSON.

    Returns dict with: status ("complete", "incomplete", "invalid"),
    missing (list of missing file keys), errors (list of parse errors).
    """
    base = data_dir or season_dir(season)
    missing = []
    errors = []

    for key, pattern in EXPECTED_FILES.items():
        path = base / pattern.format(game_id=game_id)
        if not path.exists() or path.stat().st_size == 0:
            missing.append(key)
            continue
        try:
            json.loads(path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append(f"{key}: {e}")

    if errors:
        return {"status": "invalid", "game_id": game_id,
                "missing": missing, "errors": errors}
    if missing:
        return {"status": "incomplete", "game_id": game_id,
                "missing": missing, "errors": []}
    return {"status": "complete", "game_id": game_id,
            "missing": [], "errors": []}
