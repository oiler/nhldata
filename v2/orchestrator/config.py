# v2/orchestrator/config.py
"""Orchestrator configuration — paths, season, constants."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Active season — the only season the daily run fetches for.
SEASON = os.environ.get("NHL_SEASON", "2025")

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
SCRIPTS = {
    "fetch_games": PROJECT_ROOT / "v1" / "nhlgame.py",
    "flatten_boxscore": PROJECT_ROOT / "tools" / "flatten_boxscore.py",
    "flatten_plays": PROJECT_ROOT / "tools" / "flatten_plays.py",
    "generate_timeline": PROJECT_ROOT / "v2" / "timelines" / "generate_timeline.py",
    "compute_competition": PROJECT_ROOT / "v2" / "competition" / "compute_competition.py",
    "get_players": PROJECT_ROOT / "v2" / "players" / "get_players.py",
    "build_league_db": PROJECT_ROOT / "v2" / "browser" / "build_league_db.py",
    "gamecheck": PROJECT_ROOT / "tools" / "gamecheck.py",
}
