# v2/orchestrator/tools/generate.py
"""Wrappers around data generation scripts."""

import subprocess
import sys

from v2.orchestrator.config import SCRIPTS


def _run_script(script_key: str, args: list[str]) -> dict:
    cmd = [sys.executable, str(SCRIPTS[script_key])] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        return {"status": "error", "script": script_key,
                "stderr": result.stderr, "stdout": result.stdout}
    return {"status": "ok", "script": script_key, "stdout": result.stdout}


def flatten_boxscores(season: str = "2025") -> dict:
    """Flatten all boxscore JSONs into master CSV."""
    return _run_script("flatten_boxscore", [season])


def flatten_plays(start: int, end: int, season: str = "2025") -> dict:
    """Flatten play-by-play JSONs for a game range."""
    return _run_script("flatten_plays", [str(start), str(end), season])


def fetch_players(season: str = "2025") -> dict:
    """Fetch/update all player metadata."""
    return _run_script("get_players", [season])


def generate_timelines(start: int, end: int, season: str = "2025") -> dict:
    """Generate second-by-second timelines for a game range."""
    return _run_script("generate_timeline", [str(start), str(end), season])


def compute_competition(start: int, end: int, season: str = "2025") -> dict:
    """Compute competition scores for a game range."""
    return _run_script("compute_competition", [str(start), str(end), season])
