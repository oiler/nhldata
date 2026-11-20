"""Where the project's data/ tree lives.

The one place pipeline and research code find data/. Scripts used to
resolve "data" against the working directory, so they worked only when
started from the repository root.

data_dir() returns $NHL_DATA_DIR when it's set, so data/ can live outside
the repository. Otherwise it returns <repo>/data.

The browser doesn't use this module: browser/runtime_paths.py keeps its own
lookup, because the Docker image ships the browser alone (D57).
"""

import os
from pathlib import Path


def repo_root() -> Path:
    """The repository root: the folder that holds pyproject.toml."""
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    override = os.environ.get("NHL_DATA_DIR")
    return Path(override) if override else repo_root() / "data"


def season_dir(season: str) -> Path:
    return data_dir() / season
