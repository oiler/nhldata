# v2/orchestrator/tests/test_tools.py
from unittest.mock import patch, MagicMock
import subprocess

from v2.orchestrator.tools.fetch import fetch_games, fetch_shifts
from v2.orchestrator.tools.generate import (
    flatten_boxscores, flatten_plays, fetch_players,
    generate_timelines, compute_competition,
)
from v2.orchestrator.tools.build import build_league_db


def _mock_run_success(stdout="Done"):
    return MagicMock(returncode=0, stdout=stdout, stderr="")


def _mock_run_failure(stderr="Error"):
    return MagicMock(returncode=1, stdout="", stderr=stderr)


@patch("v2.orchestrator.tools.fetch.subprocess.run")
def test_fetch_games_success(mock_run):
    mock_run.return_value = _mock_run_success()
    result = fetch_games(900, 902, season="2025")
    assert result["status"] == "ok"
    assert mock_run.called


@patch("v2.orchestrator.tools.fetch.subprocess.run")
def test_fetch_games_failure(mock_run):
    mock_run.return_value = _mock_run_failure("Connection error")
    result = fetch_games(900, 902, season="2025")
    assert result["status"] == "error"


@patch("v2.orchestrator.tools.fetch.subprocess.run")
def test_fetch_shifts_calls_shifts_mode(mock_run):
    mock_run.return_value = _mock_run_success()
    fetch_shifts(900, 902, season="2025")
    cmd = mock_run.call_args[0][0]
    assert "shifts" in cmd


@patch("v2.orchestrator.tools.generate.subprocess.run")
def test_flatten_boxscores(mock_run):
    mock_run.return_value = _mock_run_success()
    result = flatten_boxscores(season="2025")
    assert result["status"] == "ok"


@patch("v2.orchestrator.tools.generate.subprocess.run")
def test_generate_timelines(mock_run):
    mock_run.return_value = _mock_run_success()
    result = generate_timelines(900, 902, season="2025")
    assert result["status"] == "ok"


@patch("v2.orchestrator.tools.generate.subprocess.run")
def test_compute_competition(mock_run):
    mock_run.return_value = _mock_run_success()
    result = compute_competition(900, 902, season="2025")
    assert result["status"] == "ok"


@patch("v2.orchestrator.tools.build.subprocess.run")
def test_build_league_db(mock_run):
    mock_run.return_value = _mock_run_success("competition: 32000 rows")
    result = build_league_db(season="2025")
    assert result["status"] == "ok"
