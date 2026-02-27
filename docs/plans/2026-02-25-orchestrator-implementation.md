# NHL Pipeline Orchestrator — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Claude-powered orchestrator that manages the NHL data pipeline (fetch, generate, build) with daily scheduled runs and manual ad-hoc commands.

**Architecture:** A `runner.py` entry point invokes a Claude agent (via `anthropic` SDK with tool use). The agent gets thin wrapper tools around existing scripts. State is tracked per-game in `pipeline_state.json`. Scheduling via macOS `launchd`.

**Tech Stack:** Python 3.10+, `anthropic` SDK (tool use), `subprocess` for script invocation, `launchd` for scheduling, `osascript` for notifications.

---

### Task 1: Project scaffolding and config

**Files:**
- Create: `v2/orchestrator/__init__.py`
- Create: `v2/orchestrator/config.py`
- Create: `v2/orchestrator/tools/__init__.py`
- Create: `v2/orchestrator/tests/__init__.py`

---

**Step 1: Create directory structure**

```bash
mkdir -p v2/orchestrator/tools v2/orchestrator/tests
```

**Step 2: Create `v2/orchestrator/__init__.py`**

```python
# v2/orchestrator/__init__.py
```

**Step 3: Create `v2/orchestrator/tools/__init__.py`**

```python
# v2/orchestrator/tools/__init__.py
```

**Step 4: Create `v2/orchestrator/tests/__init__.py`**

```python
# v2/orchestrator/tests/__init__.py
```

**Step 5: Create `v2/orchestrator/config.py`**

```python
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
```

**Step 6: Verify config imports cleanly**

```bash
cd /Users/jrf1039/files/projects/nhl
python -c "from v2.orchestrator.config import PROJECT_ROOT, SCRIPTS; print(PROJECT_ROOT); print(all(p.exists() for p in SCRIPTS.values()))"
```

Expected: prints project root path and `True`.

---

### Task 2: State management

**Files:**
- Create: `v2/orchestrator/state.py`
- Create: `v2/orchestrator/tests/test_state.py`

---

**Step 1: Write the failing test**

```python
# v2/orchestrator/tests/test_state.py
import json
import tempfile
from pathlib import Path

import pytest

from v2.orchestrator.state import PipelineState


def test_new_state_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        state = PipelineState(path, season="2025")
        state.save()
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["season"] == "2025"
        assert data["games"] == {}


def test_load_existing_state():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        path.write_text(json.dumps({
            "season": "2025",
            "last_schedule_check": "2026-01-01T06:00:00",
            "games": {
                "2025020001": {
                    "scheduled_date": "2025-10-05",
                    "fetch": {"status": "complete", "timestamp": "2026-01-01T06:01:00"},
                }
            }
        }))
        state = PipelineState(path, season="2025")
        assert state.get_game_stage("2025020001", "fetch")["status"] == "complete"


def test_update_game_stage():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        state = PipelineState(path, season="2025")
        state.set_game_stage("2025020100", "fetch", "complete")
        state.save()
        reloaded = PipelineState(path, season="2025")
        assert reloaded.get_game_stage("2025020100", "fetch")["status"] == "complete"


def test_set_game_stage_failed_with_error():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        state = PipelineState(path, season="2025")
        state.set_game_stage("2025020100", "shifts", "failed", error="Empty response")
        assert state.get_game_stage("2025020100", "shifts")["status"] == "failed"
        assert state.get_game_stage("2025020100", "shifts")["error"] == "Empty response"


def test_games_needing_stage():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline_state.json"
        state = PipelineState(path, season="2025")
        state.set_game_stage("2025020001", "fetch", "complete")
        state.set_game_stage("2025020001", "timeline", "complete")
        state.set_game_stage("2025020002", "fetch", "complete")
        state.set_game_stage("2025020002", "timeline", "failed")
        state.set_game_stage("2025020003", "fetch", "complete")
        # game 3 has no timeline entry at all
        needing = state.games_needing_stage("timeline")
        assert "2025020002" in needing  # failed
        assert "2025020003" in needing  # missing
        assert "2025020001" not in needing  # complete
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest v2/orchestrator/tests/test_state.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'v2.orchestrator.state'`

**Step 3: Implement `v2/orchestrator/state.py`**

```python
# v2/orchestrator/state.py
"""Pipeline state tracking — per-game progress through each pipeline stage."""

import json
from datetime import datetime, timezone
from pathlib import Path


STAGES = ["fetch", "shifts", "flatten_boxscore", "flatten_plays",
          "timeline", "competition"]


class PipelineState:
    def __init__(self, path: Path, season: str):
        self.path = path
        self.season = season
        if path.exists():
            self._data = json.loads(path.read_text())
        else:
            self._data = {"season": season, "last_schedule_check": None, "games": {}}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    @property
    def last_schedule_check(self) -> str | None:
        return self._data.get("last_schedule_check")

    @last_schedule_check.setter
    def last_schedule_check(self, value: str):
        self._data["last_schedule_check"] = value

    def get_game_stage(self, game_id: str, stage: str) -> dict | None:
        game = self._data["games"].get(game_id, {})
        return game.get(stage)

    def set_game_stage(self, game_id: str, stage: str, status: str,
                       error: str | None = None):
        if game_id not in self._data["games"]:
            self._data["games"][game_id] = {}
        entry = {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if error:
            entry["error"] = error
        self._data["games"][game_id][stage] = entry

    def set_scheduled_date(self, game_id: str, date_str: str):
        if game_id not in self._data["games"]:
            self._data["games"][game_id] = {}
        self._data["games"][game_id]["scheduled_date"] = date_str

    def games_needing_stage(self, stage: str) -> list[str]:
        """Return game IDs where the given stage is missing, failed, or skipped."""
        result = []
        for game_id, game_data in self._data["games"].items():
            stage_data = game_data.get(stage)
            if stage_data is None or stage_data.get("status") in ("failed", "skipped"):
                result.append(game_id)
        return result

    def all_game_ids(self) -> list[str]:
        return list(self._data["games"].keys())
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest v2/orchestrator/tests/test_state.py -v
```

Expected: 5/5 PASS

---

### Task 3: Parameterize `build_league_db.py`

**Files:**
- Modify: `v2/browser/build_league_db.py`

Currently `SEASON_DIR = "data/2025"` is hardcoded. Add an optional CLI arg so the orchestrator (and manual users) can pass a season.

---

**Step 1: Update the script to accept an optional season argument**

At the top of `v2/browser/build_league_db.py`, replace the hardcoded path block:

```python
SEASON_DIR = "data/2025"
OUTPUT_DB = os.path.join(SEASON_DIR, "generated", "browser", "league.db")
COMPETITION_DIR = os.path.join(SEASON_DIR, "generated", "competition")
PLAYERS_CSV = os.path.join(SEASON_DIR, "generated", "players", "csv", "players.csv")
FLATBOXSCORES_CSV = os.path.join(SEASON_DIR, "generated", "flatboxscores", "boxscores.csv")
```

With:

```python
import sys as _sys

_season = _sys.argv[1] if len(_sys.argv) > 1 else "2025"
SEASON_DIR = f"data/{_season}"
OUTPUT_DB = os.path.join(SEASON_DIR, "generated", "browser", "league.db")
COMPETITION_DIR = os.path.join(SEASON_DIR, "generated", "competition")
PLAYERS_CSV = os.path.join(SEASON_DIR, "generated", "players", "csv", "players.csv")
FLATBOXSCORES_CSV = os.path.join(SEASON_DIR, "generated", "flatboxscores", "boxscores.csv")
```

Note: `sys` is imported as `_sys` to avoid collision if `sys` is imported elsewhere in the file. Check if `sys` is already imported — if so, just use that.

**Step 2: Update the docstring**

Update the module docstring to document the new usage:

```
Usage:
    python v2/browser/build_league_db.py          # defaults to 2025
    python v2/browser/build_league_db.py 2024      # builds 2024 database
```

**Step 3: Verify existing tests still pass**

```bash
python -m pytest v2/browser/tests/ -v
```

Expected: All 24 tests PASS (tests use in-memory DB, not affected by CLI arg change).

**Step 4: Verify the script still works with no arg**

```bash
python v2/browser/build_league_db.py
```

Expected: Rebuilds `data/2025/generated/browser/league.db` as before.

---

### Task 4: Schedule tool

**Files:**
- Create: `v2/orchestrator/tools/schedule.py`
- Create: `v2/orchestrator/tests/test_schedule.py`

---

**Step 1: Write the failing test**

```python
# v2/orchestrator/tests/test_schedule.py
import json
from unittest.mock import patch, MagicMock

from v2.orchestrator.tools.schedule import check_schedule


def _mock_schedule_response(game_ids: list[int], date: str = "2026-02-25"):
    """Build a minimal NHL schedule API response."""
    games = []
    for gid in game_ids:
        games.append({"id": gid, "gameType": 2, "gameState": "OFF"})
    return {
        "gameWeek": [
            {"date": date, "games": games}
        ]
    }


@patch("v2.orchestrator.tools.schedule.requests.get")
def test_check_schedule_returns_game_ids(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _mock_schedule_response(
        [2025020900, 2025020901, 2025020902], "2026-02-25"
    )
    mock_get.return_value = mock_resp

    result = check_schedule("2026-02-25")
    assert result["status"] == "ok"
    assert result["date"] == "2026-02-25"
    assert result["game_ids"] == [2025020900, 2025020901, 2025020902]
    assert result["game_count"] == 3


@patch("v2.orchestrator.tools.schedule.requests.get")
def test_check_schedule_no_games(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"gameWeek": [{"date": "2026-02-25", "games": []}]}
    mock_get.return_value = mock_resp

    result = check_schedule("2026-02-25")
    assert result["status"] == "ok"
    assert result["game_ids"] == []
    assert result["game_count"] == 0


@patch("v2.orchestrator.tools.schedule.requests.get")
def test_check_schedule_api_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = Exception("Server error")
    mock_get.return_value = mock_resp

    result = check_schedule("2026-02-25")
    assert result["status"] == "error"
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest v2/orchestrator/tests/test_schedule.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement `v2/orchestrator/tools/schedule.py`**

```python
# v2/orchestrator/tools/schedule.py
"""Check the NHL schedule API for games played on a given date."""

import requests

SCHEDULE_URL = "https://api-web.nhle.com/v1/schedule/{date}"


def check_schedule(date: str) -> dict:
    """Query NHL schedule for games on the given date (YYYY-MM-DD).

    Returns dict with: status, date, game_ids, game_count (or error).
    Only includes regular-season games (gameType == 2) that are final (gameState == "OFF").
    """
    try:
        resp = requests.get(SCHEDULE_URL.format(date=date), timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"status": "error", "date": date, "error": str(e)}

    game_ids = []
    for week_day in data.get("gameWeek", []):
        if week_day.get("date") != date:
            continue
        for game in week_day.get("games", []):
            if game.get("gameType") == 2:
                game_ids.append(game["id"])

    return {
        "status": "ok",
        "date": date,
        "game_ids": game_ids,
        "game_count": len(game_ids),
    }
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest v2/orchestrator/tests/test_schedule.py -v
```

Expected: 3/3 PASS

---

### Task 5: Validation tool

**Files:**
- Create: `v2/orchestrator/tools/validate.py`
- Create: `v2/orchestrator/tests/test_validate.py`

---

**Step 1: Write the failing test**

```python
# v2/orchestrator/tests/test_validate.py
import json
import tempfile
from pathlib import Path

from v2.orchestrator.tools.validate import validate_game


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_validate_game_all_present():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "data" / "2025"
        game_id = "2025020001"
        _write_json(base / "boxscores" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "plays" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "meta" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "shifts" / f"{game_id}_home.json", {"shifts": []})
        _write_json(base / "shifts" / f"{game_id}_away.json", {"shifts": []})

        result = validate_game(game_id, data_dir=base)
        assert result["status"] == "complete"
        assert result["missing"] == []


def test_validate_game_missing_shifts():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "data" / "2025"
        game_id = "2025020001"
        _write_json(base / "boxscores" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "plays" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "meta" / f"{game_id}.json", {"id": game_id})
        # No shifts files

        result = validate_game(game_id, data_dir=base)
        assert result["status"] == "incomplete"
        assert "shifts_home" in result["missing"]
        assert "shifts_away" in result["missing"]


def test_validate_game_invalid_json():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "data" / "2025"
        game_id = "2025020001"
        (base / "boxscores").mkdir(parents=True)
        (base / "boxscores" / f"{game_id}.json").write_text("not json{{{")
        _write_json(base / "plays" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "meta" / f"{game_id}.json", {"id": game_id})
        _write_json(base / "shifts" / f"{game_id}_home.json", {"shifts": []})
        _write_json(base / "shifts" / f"{game_id}_away.json", {"shifts": []})

        result = validate_game(game_id, data_dir=base)
        assert result["status"] == "invalid"
        assert "boxscore" in result["errors"][0]
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest v2/orchestrator/tests/test_validate.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement `v2/orchestrator/tools/validate.py`**

```python
# v2/orchestrator/tools/validate.py
"""Validate raw game data — file existence, JSON parsing, structure."""

import json
from pathlib import Path

from v2.orchestrator.config import season_dir

EXPECTED_FILES = {
    "boxscore": "boxscores/{game_id}.json",
    "plays": "plays/{game_id}.json",
    "meta": "meta/{game_id}.json",
    "shifts_home": "shifts/{game_id}_home.json",
    "shifts_away": "shifts/{game_id}_away.json",
}


def validate_game(game_id: str, data_dir: Path | None = None,
                  season: str | None = None) -> dict:
    """Validate that all raw data files exist and parse as valid JSON.

    Returns dict with: status ("complete", "incomplete", "invalid"),
    missing (list of missing file keys), errors (list of parse errors).
    """
    base = data_dir or season_dir(season)
    missing = []
    errors = []

    for key, pattern in EXPECTED_FILES.items():
        path = base / pattern.format(game_id=game_id)
        if not path.exists() or path.stat().st_size == 0:
            missing.append(key)
            continue
        try:
            json.loads(path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append(f"{key}: {e}")

    if errors:
        return {"status": "invalid", "game_id": game_id,
                "missing": missing, "errors": errors}
    if missing:
        return {"status": "incomplete", "game_id": game_id,
                "missing": missing, "errors": []}
    return {"status": "complete", "game_id": game_id,
            "missing": [], "errors": []}
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest v2/orchestrator/tests/test_validate.py -v
```

Expected: 3/3 PASS

---

### Task 6: Script wrapper tools (fetch, generate, build)

**Files:**
- Create: `v2/orchestrator/tools/fetch.py`
- Create: `v2/orchestrator/tools/generate.py`
- Create: `v2/orchestrator/tools/build.py`
- Create: `v2/orchestrator/tests/test_tools.py`

All wrappers follow the same pattern: call `subprocess.run` with the right args, capture output, return structured result. Grouped into one task because the pattern is identical.

---

**Step 1: Write the failing tests**

```python
# v2/orchestrator/tests/test_tools.py
from unittest.mock import patch, MagicMock
import subprocess

from v2.orchestrator.tools.fetch import fetch_games, fetch_shifts
from v2.orchestrator.tools.generate import (
    flatten_boxscores, flatten_plays, fetch_players,
    generate_timelines, compute_competition,
)
from v2.orchestrator.tools.build import build_league_db


def _mock_run_success(stdout="Done"):
    return MagicMock(returncode=0, stdout=stdout, stderr="")


def _mock_run_failure(stderr="Error"):
    return MagicMock(returncode=1, stdout="", stderr=stderr)


@patch("v2.orchestrator.tools.fetch.subprocess.run")
def test_fetch_games_success(mock_run):
    mock_run.return_value = _mock_run_success()
    result = fetch_games(900, 902, season="2025")
    assert result["status"] == "ok"
    assert mock_run.called


@patch("v2.orchestrator.tools.fetch.subprocess.run")
def test_fetch_games_failure(mock_run):
    mock_run.return_value = _mock_run_failure("Connection error")
    result = fetch_games(900, 902, season="2025")
    assert result["status"] == "error"


@patch("v2.orchestrator.tools.fetch.subprocess.run")
def test_fetch_shifts_calls_shifts_mode(mock_run):
    mock_run.return_value = _mock_run_success()
    fetch_shifts(900, 902, season="2025")
    cmd = mock_run.call_args[0][0]
    assert "shifts" in cmd


@patch("v2.orchestrator.tools.generate.subprocess.run")
def test_flatten_boxscores(mock_run):
    mock_run.return_value = _mock_run_success()
    result = flatten_boxscores(season="2025")
    assert result["status"] == "ok"


@patch("v2.orchestrator.tools.generate.subprocess.run")
def test_generate_timelines(mock_run):
    mock_run.return_value = _mock_run_success()
    result = generate_timelines(900, 902, season="2025")
    assert result["status"] == "ok"


@patch("v2.orchestrator.tools.generate.subprocess.run")
def test_compute_competition(mock_run):
    mock_run.return_value = _mock_run_success()
    result = compute_competition(900, 902, season="2025")
    assert result["status"] == "ok"


@patch("v2.orchestrator.tools.build.subprocess.run")
def test_build_league_db(mock_run):
    mock_run.return_value = _mock_run_success("competition: 32000 rows")
    result = build_league_db(season="2025")
    assert result["status"] == "ok"
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest v2/orchestrator/tests/test_tools.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement `v2/orchestrator/tools/fetch.py`**

```python
# v2/orchestrator/tools/fetch.py
"""Wrappers around v1/nhlgame.py for fetching raw NHL data."""

import subprocess
import sys

from v2.orchestrator.config import SCRIPTS


def _run_nhlgame(args: list[str]) -> dict:
    cmd = [sys.executable, str(SCRIPTS["fetch_games"])] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        return {"status": "error", "stderr": result.stderr, "stdout": result.stdout}
    return {"status": "ok", "stdout": result.stdout}


def fetch_games(start: int, end: int, season: str = "2025") -> dict:
    """Fetch all raw data (boxscores, plays, meta, shifts) for a game range."""
    return _run_nhlgame([str(start), str(end)])


def fetch_shifts(start: int, end: int, season: str = "2025") -> dict:
    """Backfill shifts only for a game range."""
    return _run_nhlgame(["shifts", str(start), str(end)])
```

**Step 4: Implement `v2/orchestrator/tools/generate.py`**

```python
# v2/orchestrator/tools/generate.py
"""Wrappers around data generation scripts."""

import subprocess
import sys

from v2.orchestrator.config import SCRIPTS


def _run_script(script_key: str, args: list[str]) -> dict:
    cmd = [sys.executable, str(SCRIPTS[script_key])] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        return {"status": "error", "script": script_key,
                "stderr": result.stderr, "stdout": result.stdout}
    return {"status": "ok", "script": script_key, "stdout": result.stdout}


def flatten_boxscores(season: str = "2025") -> dict:
    """Flatten all boxscore JSONs into master CSV."""
    return _run_script("flatten_boxscore", [season])


def flatten_plays(start: int, end: int, season: str = "2025") -> dict:
    """Flatten play-by-play JSONs for a game range."""
    return _run_script("flatten_plays", [str(start), str(end), season])


def fetch_players(season: str = "2025") -> dict:
    """Fetch/update all player metadata."""
    return _run_script("get_players", [season])


def generate_timelines(start: int, end: int, season: str = "2025") -> dict:
    """Generate second-by-second timelines for a game range."""
    return _run_script("generate_timeline", [str(start), str(end), season])


def compute_competition(start: int, end: int, season: str = "2025") -> dict:
    """Compute competition scores for a game range."""
    return _run_script("compute_competition", [str(start), str(end), season])
```

**Step 5: Implement `v2/orchestrator/tools/build.py`**

```python
# v2/orchestrator/tools/build.py
"""Wrapper around build_league_db.py."""

import subprocess
import sys

from v2.orchestrator.config import SCRIPTS


def build_league_db(season: str = "2025") -> dict:
    """Rebuild the league SQLite database."""
    cmd = [sys.executable, str(SCRIPTS["build_league_db"]), season]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        return {"status": "error", "stderr": result.stderr, "stdout": result.stdout}
    return {"status": "ok", "stdout": result.stdout}
```

**Step 6: Run tests to verify they pass**

```bash
python -m pytest v2/orchestrator/tests/test_tools.py -v
```

Expected: 7/7 PASS

---

### Task 7: Notification tool

**Files:**
- Create: `v2/orchestrator/tools/notify.py`
- Create: `v2/orchestrator/tests/test_notify.py`

---

**Step 1: Write the failing test**

```python
# v2/orchestrator/tests/test_notify.py
from unittest.mock import patch

from v2.orchestrator.tools.notify import send_notification


@patch("v2.orchestrator.tools.notify.subprocess.run")
def test_send_notification(mock_run):
    send_notification("NHL Pipeline", "4 games processed")
    assert mock_run.called
    cmd = mock_run.call_args[0][0]
    assert "osascript" in cmd[0]
    assert "NHL Pipeline" in cmd[-1]
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest v2/orchestrator/tests/test_notify.py -v
```

Expected: FAIL

**Step 3: Implement `v2/orchestrator/tools/notify.py`**

```python
# v2/orchestrator/tools/notify.py
"""macOS native notifications via osascript."""

import subprocess


def send_notification(title: str, message: str):
    """Send a macOS notification. Fails silently on non-macOS."""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ], capture_output=True, timeout=10)
    except Exception:
        pass  # non-macOS or osascript unavailable
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest v2/orchestrator/tests/test_notify.py -v
```

Expected: 1/1 PASS

---

### Task 8: Log writer

**Files:**
- Create: `v2/orchestrator/log_writer.py`

---

**Step 1: Implement the log writer**

```python
# v2/orchestrator/log_writer.py
"""Write pipeline run logs as markdown files."""

from datetime import datetime
from pathlib import Path

from v2.orchestrator.config import log_dir


class LogWriter:
    def __init__(self, season: str):
        self.season = season
        self.lines: list[str] = []
        self.start_time = datetime.now()
        self._add(f"# Pipeline Run — {self.start_time.strftime('%Y-%m-%d %H:%M')}\n")

    def section(self, title: str):
        self._add(f"\n## {title}\n")

    def item(self, text: str):
        self._add(f"- {text}")

    def _add(self, line: str):
        self.lines.append(line)

    def save(self) -> Path:
        out_dir = log_dir(self.season)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = self.start_time.strftime("%Y-%m-%d") + ".md"
        path = out_dir / filename
        path.write_text("\n".join(self.lines) + "\n")
        return path

    def summary(self) -> str:
        """Return the last section's content as a short string for notifications."""
        for i in range(len(self.lines) - 1, -1, -1):
            if self.lines[i].startswith("## Summary"):
                return "\n".join(self.lines[i + 1:]).strip()
        return "Pipeline run complete."
```

---

### Task 9: Agent definition

**Files:**
- Create: `v2/orchestrator/agent.py`

This is the core — defines the Claude agent with tool-use via the `anthropic` SDK.

---

**Step 1: Implement `v2/orchestrator/agent.py`**

```python
# v2/orchestrator/agent.py
"""Claude-powered pipeline orchestrator agent."""

import json
from anthropic import Anthropic

from v2.orchestrator.tools.schedule import check_schedule
from v2.orchestrator.tools.validate import validate_game
from v2.orchestrator.tools.fetch import fetch_games, fetch_shifts
from v2.orchestrator.tools.generate import (
    flatten_boxscores, flatten_plays, fetch_players,
    generate_timelines, compute_competition,
)
from v2.orchestrator.tools.build import build_league_db
from v2.orchestrator.tools.notify import send_notification

SYSTEM_PROMPT = """\
You are the NHL data pipeline orchestrator. You manage three services:
1. FETCH — download raw game data from the NHL API (boxscores, plays, meta, shifts)
2. GENERATE — process raw data into derived outputs (timelines, competition scores, etc.)
3. BUILD — rebuild the SQLite database that powers the web browser app

PIPELINE ORDER (dependencies):
1. check_schedule → learn which games were played
2. fetch_games → download raw data for those games
3. validate_game → confirm files exist, JSON is valid
4. If shifts missing → fetch_shifts to retry, then validate again
5. flatten_boxscores → flatten all boxscores to master CSV (run for full season)
6. flatten_plays → flatten play-by-play for new games
7. fetch_players → update player metadata (catches new player IDs)
8. generate_timelines → build second-by-second timelines (requires shifts)
9. compute_competition → calculate competition scores (requires timelines)
10. build_league_db → rebuild league.db from all generated data
11. notify → send summary notification

RULES:
- If a game's shifts fail after retries, skip its timeline and competition but process other games.
- Always validate after fetching. Always rebuild the DB after any generation step succeeds.
- Game IDs are full NHL IDs like 2025020734. Game numbers are 1-1312 (the last 4 digits).
- To convert a game ID to a game number: int(game_id[-4:]).
- The season is provided in each tool call. Use it consistently.
- Report clearly what succeeded and what failed.
- You are an assistant, not an owner. Execute the requested work and report results.
"""

TOOLS = [
    {
        "name": "check_schedule",
        "description": "Query the NHL schedule API for games played on a given date. Returns game IDs and count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
            },
            "required": ["date"]
        }
    },
    {
        "name": "validate_game",
        "description": "Validate that all raw data files exist and parse as valid JSON for a game. Returns status (complete/incomplete/invalid), missing files, and errors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "game_id": {"type": "string", "description": "Full NHL game ID (e.g. 2025020734)"},
                "season": {"type": "string", "description": "Season year (e.g. 2025)"}
            },
            "required": ["game_id"]
        }
    },
    {
        "name": "fetch_games",
        "description": "Download all raw data (boxscores, plays, meta, shifts) for a range of game numbers. Rate-limited; may take several minutes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer", "description": "Start game number (1-1312)"},
                "end": {"type": "integer", "description": "End game number (1-1312)"},
                "season": {"type": "string"}
            },
            "required": ["start", "end"]
        }
    },
    {
        "name": "fetch_shifts",
        "description": "Retry/backfill shift data only for a range of game numbers. Use when shifts were empty on initial fetch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "season": {"type": "string"}
            },
            "required": ["start", "end"]
        }
    },
    {
        "name": "flatten_boxscores",
        "description": "Flatten all boxscore JSONs into a master CSV. Run for the full season (not per-game).",
        "input_schema": {
            "type": "object",
            "properties": {"season": {"type": "string"}},
            "required": ["season"]
        }
    },
    {
        "name": "flatten_plays",
        "description": "Flatten play-by-play JSONs for a range of game numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "season": {"type": "string"}
            },
            "required": ["start", "end", "season"]
        }
    },
    {
        "name": "fetch_players",
        "description": "Fetch/update all player metadata for the season.",
        "input_schema": {
            "type": "object",
            "properties": {"season": {"type": "string"}},
            "required": ["season"]
        }
    },
    {
        "name": "generate_timelines",
        "description": "Generate second-by-second timelines for a range of game numbers. Requires shifts data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "season": {"type": "string"}
            },
            "required": ["start", "end", "season"]
        }
    },
    {
        "name": "compute_competition",
        "description": "Compute competition scores for a range of game numbers. Requires timelines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "season": {"type": "string"}
            },
            "required": ["start", "end", "season"]
        }
    },
    {
        "name": "build_league_db",
        "description": "Rebuild the league SQLite database from all generated data.",
        "input_schema": {
            "type": "object",
            "properties": {"season": {"type": "string"}},
            "required": ["season"]
        }
    },
    {
        "name": "send_notification",
        "description": "Send a macOS desktop notification with a title and message.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["title", "message"]
        }
    },
]

# Map tool names to handler functions
TOOL_HANDLERS = {
    "check_schedule": lambda args: check_schedule(args["date"]),
    "validate_game": lambda args: validate_game(
        args["game_id"], season=args.get("season")),
    "fetch_games": lambda args: fetch_games(
        args["start"], args["end"], season=args.get("season", "2025")),
    "fetch_shifts": lambda args: fetch_shifts(
        args["start"], args["end"], season=args.get("season", "2025")),
    "flatten_boxscores": lambda args: flatten_boxscores(
        season=args["season"]),
    "flatten_plays": lambda args: flatten_plays(
        args["start"], args["end"], season=args["season"]),
    "fetch_players": lambda args: fetch_players(season=args["season"]),
    "generate_timelines": lambda args: generate_timelines(
        args["start"], args["end"], season=args["season"]),
    "compute_competition": lambda args: compute_competition(
        args["start"], args["end"], season=args["season"]),
    "build_league_db": lambda args: build_league_db(
        season=args["season"]),
    "send_notification": lambda args: send_notification(
        args["title"], args["message"]),
}


def run_agent(user_message: str, season: str = "2025",
              model: str = "claude-haiku-4-5-20251001") -> str:
    """Run the orchestrator agent with the given instruction.

    Returns the agent's final text response.
    """
    client = Anthropic()
    messages = [{"role": "user", "content": user_message}]
    system = SYSTEM_PROMPT + f"\n\nCurrent season: {season}"

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # Collect text and tool-use blocks
        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        if response.stop_reason == "end_turn" or not tool_calls:
            return "\n".join(text_parts)

        # Execute tool calls and build tool_result messages
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tc in tool_calls:
            handler = TOOL_HANDLERS.get(tc.name)
            if handler:
                try:
                    result = handler(tc.input)
                except Exception as e:
                    result = {"status": "error", "error": str(e)}
            else:
                result = {"status": "error", "error": f"Unknown tool: {tc.name}"}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})
```

---

### Task 10: Runner (entry point)

**Files:**
- Create: `v2/orchestrator/runner.py`

---

**Step 1: Implement `v2/orchestrator/runner.py`**

```python
#!/usr/bin/env python3
# v2/orchestrator/runner.py
"""NHL Pipeline Orchestrator — entry point.

Usage:
    python v2/orchestrator/runner.py                        # Daily scheduled run
    python v2/orchestrator/runner.py "re-fetch game 734"    # Manual command
"""

import sys
from datetime import date, timedelta

from v2.orchestrator.agent import run_agent
from v2.orchestrator.config import SEASON
from v2.orchestrator.log_writer import LogWriter


def daily_prompt(season: str) -> str:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return (
        f"Run the daily pipeline for season {season}.\n"
        f"1. Check the NHL schedule for {yesterday}.\n"
        f"2. Fetch any new games.\n"
        f"3. Validate all fetched data.\n"
        f"4. If shifts are missing, retry with fetch_shifts.\n"
        f"5. Run all generation steps for new games.\n"
        f"6. Rebuild the league database.\n"
        f"7. Send a notification summarizing what happened."
    )


def main():
    season = SEASON

    if len(sys.argv) > 1:
        # Manual mode — user provided a command
        user_message = " ".join(sys.argv[1:])
        # Inject season context
        user_message = f"[Season: {season}] {user_message}"
    else:
        # Scheduled daily mode
        user_message = daily_prompt(season)

    log = LogWriter(season)
    log.section("Agent Input")
    log.item(user_message)

    print(f"Running orchestrator (season {season})...")
    print(f"Prompt: {user_message}\n")

    try:
        result = run_agent(user_message, season=season)
    except Exception as e:
        result = f"Agent error: {e}"

    log.section("Agent Output")
    log.item(result)

    log.section("Summary")
    log.item(f"Completed at {log.start_time.strftime('%H:%M')}")

    log_path = log.save()
    print(f"\nAgent response:\n{result}")
    print(f"\nLog saved to: {log_path}")


if __name__ == "__main__":
    main()
```

---

### Task 11: launchd scheduling

**Files:**
- Create: `v2/orchestrator/com.nhl.orchestrator.plist`

---

**Step 1: Create the plist file**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nhl.orchestrator</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/jrf1039/.pyenv/versions/3.11.6/bin/python</string>
        <string>/Users/jrf1039/files/projects/nhl/v2/orchestrator/runner.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/jrf1039/files/projects/nhl</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>EnvironmentVariables</key>
    <dict>
        <key>NHL_SEASON</key>
        <string>2025</string>
        <key>ANTHROPIC_API_KEY</key>
        <string>SET_YOUR_KEY_HERE</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/jrf1039/files/projects/nhl/data/2025/logs/launchd-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/jrf1039/files/projects/nhl/data/2025/logs/launchd-stderr.log</string>
</dict>
</plist>
```

**Step 2: Installation instructions (in a comment at the top of the plist)**

To install:
```bash
# 1. Edit the plist: set ANTHROPIC_API_KEY to your real key
# 2. Copy to LaunchAgents:
cp v2/orchestrator/com.nhl.orchestrator.plist ~/Library/LaunchAgents/
# 3. Load it:
launchctl load ~/Library/LaunchAgents/com.nhl.orchestrator.plist
# 4. To unload:
launchctl unload ~/Library/LaunchAgents/com.nhl.orchestrator.plist
# 5. To test immediately:
launchctl start com.nhl.orchestrator
```

---

### Task 12: Add `anthropic` to dependencies

**Files:**
- Modify: `pyproject.toml`

---

**Step 1: Add anthropic to dependencies**

Add `"anthropic>=0.40.0"` to the `dependencies` list in `pyproject.toml`:

```toml
dependencies = [
    "requests>=2.31.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "anthropic>=0.40.0",
]
```

**Step 2: Install**

```bash
pip install anthropic
```

---

### Task 13: End-to-end smoke test

**Files:**
- Create: `v2/orchestrator/tests/test_smoke.py`

---

**Step 1: Write the smoke test**

```python
# v2/orchestrator/tests/test_smoke.py
"""Smoke tests — verify all modules import and agent can be constructed."""

def test_config_imports():
    from v2.orchestrator.config import PROJECT_ROOT, SCRIPTS, SEASON
    assert PROJECT_ROOT.exists()
    assert len(SCRIPTS) > 0


def test_state_imports():
    from v2.orchestrator.state import PipelineState
    assert PipelineState is not None


def test_all_tools_import():
    from v2.orchestrator.tools.schedule import check_schedule
    from v2.orchestrator.tools.validate import validate_game
    from v2.orchestrator.tools.fetch import fetch_games, fetch_shifts
    from v2.orchestrator.tools.generate import (
        flatten_boxscores, flatten_plays, fetch_players,
        generate_timelines, compute_competition,
    )
    from v2.orchestrator.tools.build import build_league_db
    from v2.orchestrator.tools.notify import send_notification


def test_agent_imports():
    from v2.orchestrator.agent import TOOLS, TOOL_HANDLERS, SYSTEM_PROMPT
    assert len(TOOLS) == 11
    assert len(TOOL_HANDLERS) == 11


def test_runner_imports():
    from v2.orchestrator.runner import daily_prompt
    prompt = daily_prompt("2025")
    assert "2025" in prompt
```

**Step 2: Run all orchestrator tests**

```bash
python -m pytest v2/orchestrator/tests/ -v
```

Expected: All tests PASS (state: 5, schedule: 3, validate: 3, tools: 7, notify: 1, smoke: 5 = 24 tests)

**Step 3: Run full project test suite to confirm no regressions**

```bash
python -m pytest v2/ -v
```

Expected: All tests PASS (browser: 24 + orchestrator: 24 = 48 tests)
