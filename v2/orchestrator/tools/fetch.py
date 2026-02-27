# v2/orchestrator/tools/fetch.py
"""Wrappers around v1/nhlgame.py for fetching raw NHL data."""

import subprocess
import sys

from v2.orchestrator.config import SCRIPTS


def _run_nhlgame(args: list[str]) -> dict:
    cmd = [sys.executable, str(SCRIPTS["fetch_games"])] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        return {"status": "error", "stderr": result.stderr, "stdout": result.stdout}
    return {"status": "ok", "stdout": result.stdout}


def fetch_games(start: int, end: int, season: str = "2025") -> dict:
    """Fetch all raw data (boxscores, plays, meta, shifts) for a game range."""
    return _run_nhlgame([str(start), str(end)])


def fetch_shifts(start: int, end: int, season: str = "2025") -> dict:
    """Backfill shifts only for a game range."""
    return _run_nhlgame(["shifts", str(start), str(end)])
