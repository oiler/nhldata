# v2/orchestrator/tests/test_smoke.py
"""Smoke tests — verify all modules import and agent can be constructed."""


def test_config_imports():
    from v2.orchestrator.config import PROJECT_ROOT, SCRIPTS, SEASON
    assert PROJECT_ROOT.exists()
    assert len(SCRIPTS) > 0


def test_state_imports():
    from v2.orchestrator.state import PipelineState
    assert PipelineState is not None


def test_all_tools_import():
    from v2.orchestrator.tools.schedule import check_schedule
    from v2.orchestrator.tools.validate import validate_game
    from v2.orchestrator.tools.fetch import fetch_games, fetch_shifts
    from v2.orchestrator.tools.generate import (
        flatten_boxscores, flatten_plays, fetch_players,
        generate_timelines, compute_competition,
    )
    from v2.orchestrator.tools.build import build_league_db
    from v2.orchestrator.tools.notify import send_notification


def test_agent_imports():
    from v2.orchestrator.agent import TOOLS, TOOL_HANDLERS, SYSTEM_PROMPT
    assert len(TOOLS) == 11
    assert len(TOOL_HANDLERS) == 11


def test_runner_imports():
    from v2.orchestrator.runner import daily_prompt
    prompt = daily_prompt("2025")
    assert "2025" in prompt
