# v2/browser/utils.py
import pandas as pd


def seconds_to_mmss(seconds) -> str:
    """Convert numeric seconds to 'MM:SS'. None/NaN mean missing data, not a
    measured zero — a goalie-game with no timeline must not render as 00:00."""
    if pd.isna(seconds):
        return "—"
    m, sec = divmod(abs(int(seconds)), 60)
    return f"{m:02d}:{sec:02d}"
