# v2/orchestrator/state.py
"""Pipeline state tracking — per-game progress through each pipeline stage."""

import json
from datetime import datetime, timezone
from pathlib import Path


STAGES = ["fetch", "shifts", "flatten_boxscore", "flatten_plays",
          "timeline", "competition"]


class PipelineState:
    def __init__(self, path: Path, season: str):
        self.path = path
        self.season = season
        if path.exists():
            self._data = json.loads(path.read_text())
        else:
            self._data = {"season": season, "last_schedule_check": None, "games": {}}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    @property
    def last_schedule_check(self) -> str | None:
        return self._data.get("last_schedule_check")

    @last_schedule_check.setter
    def last_schedule_check(self, value: str):
        self._data["last_schedule_check"] = value

    def get_game_stage(self, game_id: str, stage: str) -> dict | None:
        game = self._data["games"].get(game_id, {})
        return game.get(stage)

    def set_game_stage(self, game_id: str, stage: str, status: str,
                       error: str | None = None):
        if game_id not in self._data["games"]:
            self._data["games"][game_id] = {}
        entry = {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if error:
            entry["error"] = error
        self._data["games"][game_id][stage] = entry

    def set_scheduled_date(self, game_id: str, date_str: str):
        if game_id not in self._data["games"]:
            self._data["games"][game_id] = {}
        self._data["games"][game_id]["scheduled_date"] = date_str

    def games_needing_stage(self, stage: str) -> list[str]:
        """Return game IDs where the given stage is missing, failed, or skipped."""
        result = []
        for game_id, game_data in self._data["games"].items():
            stage_data = game_data.get(stage)
            if stage_data is None or stage_data.get("status") in ("failed", "skipped"):
                result.append(game_id)
        return result

    def all_game_ids(self) -> list[str]:
        return list(self._data["games"].keys())
