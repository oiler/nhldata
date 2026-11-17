"""Single source of truth for runtime data file locations.

Two modes:

1. Production (DATA_DIR set): a flat layout under DATA_DIR with one folder
   per season — `<DATA_DIR>/<season>/league.db`, etc. This is what the
   Docker image ships.

2. Local dev (DATA_DIR unset): the legacy pipeline layout under
   `<repo>/data/<season>/generated/...` so existing workflows keep working
   without env vars or symlinks.

Only files the deployed app actually reads belong here. Pipeline-only
inputs (raw boxscores, flatplays, shifts, etc.) stay out.
"""

import os
from pathlib import Path


def _runtime_mode() -> bool:
    return "DATA_DIR" in os.environ


def is_runtime_mode() -> bool:
    """Public alias for _runtime_mode().

    True in the deployed image (DATA_DIR set), False in local dev. Used to
    decide whether a missing data file is a fatal deploy error or a tolerable
    local-dev gap.
    """
    return _runtime_mode()


def data_root() -> Path:
    if _runtime_mode():
        return Path(os.environ["DATA_DIR"])
    # parents[2] is only safe when the file is deep inside the repo; in the
    # Docker image it sits at /app/runtime_paths.py with only two parents,
    # which is why this lookup is gated behind the runtime-mode branch.
    return Path(__file__).resolve().parents[2] / "data"


def league_db(season: str) -> Path:
    if _runtime_mode():
        return data_root() / season / "league.db"
    return data_root() / season / "generated" / "browser" / "league.db"


def edm_db(season: str) -> Path:
    if _runtime_mode():
        return data_root() / season / "edm.db"
    return data_root() / season / "generated" / "browser" / "edm.db"


def player_bursts_csv(season: str) -> Path:
    if _runtime_mode():
        return data_root() / season / "player_bursts.csv"
    return data_root() / season / "generated" / "edge" / "player_bursts.csv"


def goalies_db() -> Path:
    """Cross-season goalie DB (single file, all seasons — not per-season)."""
    if _runtime_mode():
        return data_root() / "goalies.db"
    return data_root() / "generated" / "browser" / "goalies.db"


def season_ready(season: str) -> bool:
    """True when the season has data to show.

    Production: tools/sync-runtime-data.sh ships a non-default season only
    after its files pass every check, so both files being present means the
    season is verified. Local dev needs only league.db; burst columns show
    em dashes without the Edge CSV.
    """
    if _runtime_mode():
        return league_db(season).exists() and player_bursts_csv(season).exists()
    return league_db(season).exists()
