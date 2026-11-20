# pipeline/orchestrator/tests/test_smoke.py
"""Smoke tests — verify all modules import and agent can be constructed."""


def test_config_imports():
    from pipeline.orchestrator.config import PROJECT_ROOT, SCRIPTS, SEASON
    assert PROJECT_ROOT.exists()
    assert len(SCRIPTS) > 0


def test_state_imports():
    from pipeline.orchestrator.state import PipelineState
    assert PipelineState is not None


def test_all_tools_import():
    from pipeline.orchestrator.tools.schedule import check_schedule
    from pipeline.orchestrator.tools.validate import validate_game
    from pipeline.orchestrator.tools.fetch import fetch_games, fetch_shifts
    from pipeline.orchestrator.tools.generate import (
        flatten_boxscores, flatten_plays, fetch_players,
        generate_timelines, compute_competition, backfill_players,
    )
    from pipeline.orchestrator.tools.build import build_league_db
    from pipeline.orchestrator.tools.notify import send_notification


def test_agent_imports():
    from pipeline.orchestrator.agent import TOOLS, TOOL_HANDLERS, SYSTEM_PROMPT
    assert len(TOOLS) == 12
    assert len(TOOL_HANDLERS) == 12


def test_runner_imports():
    from pipeline.orchestrator.runner import daily_prompt
    prompt = daily_prompt("2025", "2026-02-25", {"fetch": [900], "generate": [900]})
    assert "2025" in prompt
