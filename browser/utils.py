# browser/utils.py
from datetime import date

import pandas as pd

from browser.seasons import age_cutoff


def seconds_to_mmss(seconds) -> str:
    """Convert numeric seconds to 'MM:SS'. None/NaN mean missing data, not a
    measured zero — a goalie-game with no timeline must not render as 00:00."""
    if pd.isna(seconds):
        return "—"
    m, sec = divmod(abs(int(seconds)), 60)
    return f"{m:02d}:{sec:02d}"


def age_in_season(birth_date, season: str):
    """Integer age at the season's Sept 15 cutoff, or None when the birth date is missing."""
    if birth_date is None or birth_date == "" or pd.isna(birth_date):
        return None
    birth = date.fromisoformat(birth_date)
    cutoff = age_cutoff(season)
    age = cutoff.year - birth.year
    if (cutoff.month, cutoff.day) < (birth.month, birth.day):
        age -= 1
    return age
