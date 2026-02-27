# v2/orchestrator/tests/test_state.py
import json
import tempfile
from pathlib import Path

import pytest

from v2.orchestrator.state import PipelineState


def test_new_state_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        state = PipelineState(path, season="2025")
        state.save()
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["season"] == "2025"
        assert data["games"] == {}


def test_load_existing_state():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        path.write_text(json.dumps({
            "season": "2025",
            "last_schedule_check": "2026-01-01T06:00:00",
            "games": {
                "2025020001": {
                    "scheduled_date": "2025-10-05",
                    "fetch": {"status": "complete", "timestamp": "2026-01-01T06:01:00"},
                }
            }
        }))
        state = PipelineState(path, season="2025")
        assert state.get_game_stage("2025020001", "fetch")["status"] == "complete"


def test_update_game_stage():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        state = PipelineState(path, season="2025")
        state.set_game_stage("2025020100", "fetch", "complete")
        state.save()
        reloaded = PipelineState(path, season="2025")
        assert reloaded.get_game_stage("2025020100", "fetch")["status"] == "complete"


def test_set_game_stage_failed_with_error():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        state = PipelineState(path, season="2025")
        state.set_game_stage("2025020100", "shifts", "failed", error="Empty response")
        assert state.get_game_stage("2025020100", "shifts")["status"] == "failed"
        assert state.get_game_stage("2025020100", "shifts")["error"] == "Empty response"


def test_games_needing_stage():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        state = PipelineState(path, season="2025")
        state.set_game_stage("2025020001", "fetch", "complete")
        state.set_game_stage("2025020001", "timeline", "complete")
        state.set_game_stage("2025020002", "fetch", "complete")
        state.set_game_stage("2025020002", "timeline", "failed")
        state.set_game_stage("2025020003", "fetch", "complete")
        # game 3 has no timeline entry at all
        needing = state.games_needing_stage("timeline")
        assert "2025020002" in needing  # failed
        assert "2025020003" in needing  # missing
        assert "2025020001" not in needing  # complete
