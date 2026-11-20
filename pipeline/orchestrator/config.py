# pipeline/orchestrator/config.py
"""Orchestrator configuration — paths, season, constants."""

import os
from pathlib import Path

from pipeline.paths import data_dir, repo_root

PROJECT_ROOT = repo_root()
DATA_DIR = data_dir()

# Active season — the only season the daily run fetches for.
SEASON = os.environ.get("NHL_SEASON", "2026")

# Game type: 02 = Regular Season
GAME_TYPE = "02"

# NHL Schedule API
SCHEDULE_API = "https://api-web.nhle.com/v1/schedule/{date}"

# Paths derived from season
def season_dir(season: str | None = None) -> Path:
    return DATA_DIR / (season or SEASON)

def generated_dir(season: str | None = None) -> Path:
    return season_dir(season) / "generated"

def league_db_path(season: str | None = None) -> Path:
    return generated_dir(season) / "browser" / "league.db"

def state_file_path(season: str | None = None) -> Path:
    return season_dir(season) / "pipeline_state.json"

def log_dir(season: str | None = None) -> Path:
    return season_dir(season) / "logs"

# Script paths
PIPELINE = PROJECT_ROOT / "pipeline"
SCRIPTS = {
    "fetch_games": PIPELINE / "nhlgame.py",
    "flatten_boxscore": PIPELINE / "flatten_boxscore.py",
    "flatten_plays": PIPELINE / "flatten_plays.py",
    "generate_timeline": PIPELINE / "timelines" / "generate_timeline.py",
    "compute_competition": PIPELINE / "competition" / "compute_competition.py",
    "get_players": PIPELINE / "players" / "get_players.py",
    "build_league_db": PIPELINE / "build_dbs" / "build_league_db.py",
    "gamecheck": PIPELINE / "gamecheck.py",
}
