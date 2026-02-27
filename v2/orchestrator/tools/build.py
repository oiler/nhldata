# v2/orchestrator/tools/build.py
"""Wrapper around build_league_db.py."""

import subprocess
import sys

from v2.orchestrator.config import SCRIPTS


def build_league_db(season: str = "2025") -> dict:
    """Rebuild the league SQLite database."""
    cmd = [sys.executable, str(SCRIPTS["build_league_db"]), season]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        return {"status": "error", "stderr": result.stderr, "stdout": result.stdout}
    return {"status": "ok", "stdout": result.stdout}
