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
