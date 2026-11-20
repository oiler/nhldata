"""Loads the speed-burst dataset behind the skaters leaderboard's SB/a60 and
Max MPH columns. (Age comes from the players table, not this file.)

The CSV is baked into the deployed image by browser/sync-runtime-data.sh, so a
missing or empty file for a season the image ships is a deploy mistake, not
missing upstream data. In production the skaters page loads every ready
season at import, so a bad file fails boot and the deploy fails loudly. On
this single-machine app that means production is down until you roll back
(see the deploy runbook), which is why the sync script and the Dockerfile
guard check these files first. Local dev (DATA_DIR unset) degrades
gracefully so the app still runs without the edge pipeline output.
"""

import functools
import logging
from pathlib import Path

import pandas as pd

from runtime_paths import is_runtime_mode, player_bursts_csv, season_ready
from seasons import DEFAULT_SEASON

logger = logging.getLogger(__name__)

BURST_COLUMNS = ["playerId", "bursts_per_60", "speed_max_mph", "birth_date"]


def load_bursts(season: str = DEFAULT_SEASON, csv_path=None) -> pd.DataFrame:
    """Return the burst dataset for `season` with columns BURST_COLUMNS.

    Raises RuntimeError in production when the CSV is missing or has no data
    rows; returns an empty frame (and logs a warning) in local dev.
    """
    path = Path(csv_path) if csv_path is not None else player_bursts_csv(season)

    if path.exists():
        df = pd.read_csv(path)[BURST_COLUMNS]
        if not df.empty:
            return df
        reason = f"player_bursts CSV has no data rows: {path}"
    else:
        reason = f"player_bursts CSV not found: {path}"

    detail = f"{reason} — skater SB/a60 and Max MPH depend on it."
    if is_runtime_mode():
        raise RuntimeError(f"{detail} Run browser/sync-runtime-data.sh and redeploy.")
    logger.warning("%s Columns will be blank in local dev.", detail)
    return pd.DataFrame(columns=BURST_COLUMNS)


@functools.lru_cache(maxsize=None)
def bursts_for(season: str) -> pd.DataFrame:
    """load_bursts(season) indexed by playerId, cached for the process lifetime.

    Burst CSVs change only on a manual Edge run; restart the app after one.
    """
    return load_bursts(season).set_index("playerId")


def preload_ready_seasons(seasons) -> None:
    """Production only: load each ready season's bursts now, so a present-but-empty
    CSV fails boot rather than a request. Seasons left out of the image are logged
    and skipped; the browser shows them as not available."""
    if not is_runtime_mode():
        return
    for season in seasons:
        if season_ready(season):
            bursts_for(season)
        else:
            logger.warning("season %s not in image; the browser shows it as not available", season)
