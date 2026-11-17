"""Seasons the browser offers, keyed by 4-digit start year.

Kept free of app and page imports so every module can use it: pages can't
import from app.py, because app.py loads the pages.
"""

from datetime import date

SEASONS = ["2025", "2026"]
DEFAULT_SEASON = "2025"


def normalize_season(value) -> str:
    """Return `value` if it's an offered season, else DEFAULT_SEASON.

    Season values arrive from the client (store, radio, query string) and end
    up in file paths and int() calls, so unknown values never pass through.
    """
    return value if value in SEASONS else DEFAULT_SEASON


def season_label(season: str) -> str:
    y = int(season)
    return f"{y}-{(y + 1) % 100:02d}"


def age_cutoff(season: str) -> date:
    """NHL convention: age as of Sept 15 of the season's start year."""
    return date(int(season), 9, 15)
