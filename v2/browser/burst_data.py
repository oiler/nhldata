"""Loads the speed-burst dataset behind the skaters leaderboard's Age, SB/a60
and Max MPH columns.

The CSV is baked into the deployed image by tools/sync-runtime-data.sh, so a
missing or empty file in production is a deploy mistake, not missing upstream
data. Failing loudly there turns a silent "blank columns" regression into a
boot failure that Fly's deploy health check catches before the bad image takes
traffic. Local dev (DATA_DIR unset) degrades gracefully so the app still runs
without the edge pipeline output.
"""

import logging
from pathlib import Path

import pandas as pd

from runtime_paths import is_runtime_mode, player_bursts_csv

logger = logging.getLogger(__name__)

BURST_COLUMNS = ["playerId", "bursts_per_60", "speed_max_mph", "birth_date"]


def load_bursts(season: str = "2025", csv_path=None) -> pd.DataFrame:
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

    detail = f"{reason} — skater Age, SB/a60 and Max MPH depend on it."
    if is_runtime_mode():
        raise RuntimeError(f"{detail} Run tools/sync-runtime-data.sh and redeploy.")
    logger.warning("%s Columns will be blank in local dev.", detail)
    return pd.DataFrame(columns=BURST_COLUMNS)
