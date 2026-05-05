# NHL EDGE Skater Data + Burst-per-60 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Project policy:** oiler handles all git commits manually. The "Stage" steps below stop at `git add` — do **not** run `git commit`.

**Goal:** Pull every active 2025-26 skater's NHL EDGE `skater-detail` payload, persist the raw JSON for future reuse, and compute a per-player "bursts over 20 mph per 60 minutes of all-strengths TOI" metric.

**Architecture:** A new `v2/edge/` module with two scripts. `fetch_skater_detail.py` enumerates skaters from `league.db`, hits the public NHL EDGE API once per player (with a browser User-Agent, rate limiting, retry on transient errors, resume-on-rerun), and saves each response verbatim to `data/2025/edge/skater_detail/{playerId}.json`. `compute_burst_rates.py` reads those JSONs, joins season-total `total_toi_seconds` from `league.db`, and writes a single CSV at `data/2025/generated/edge/player_bursts.csv`. Pure-function logic (player ID enumeration, JSON field extraction, per-60 math, table assembly) is unit-tested with synthetic data; the orchestration loop is validated by an end-to-end run.

**Tech Stack:** Python 3.11, `urllib` (stdlib HTTP — no new deps), `pandas`, `sqlite3` (stdlib), `pytest`. League data source: `data/2025/generated/browser/league.db`. EDGE endpoint: `https://api-web.nhle.com/v1/edge/skater-detail/{playerId}/20252026/2`.

---

## Scope

**In scope:**
- Fetch + cache full `skater-detail` payload for every distinct skater in `competition` for season 2025 (~940 players).
- Compute season-total bursts-per-60 (all-strengths TOI denominator) per player and emit a CSV.
- Unit tests for the pure-function logic.
- One end-to-end run to populate the cache and produce the CSV.

**Out of scope (explicitly deferred):**
- Team-level burst rate aggregation.
- League-relative percentile/z-score normalization.
- Browser app integration (no new pages, no `league.db` schema changes).
- Other EDGE endpoints (`skater-zone-time`, `skater-shot-speed-detail`, etc.). The raw JSON we save **does** include zone time, shot speed, distance, etc. for free, so future callers can mine those fields without a re-fetch.
- Trade-attribution math (when a player suits up for two teams). Per-player metric is season-total; team-attribution is a future concern.

---

## File Structure

**Create:**
- `v2/edge/__init__.py` — empty marker, mirrors `v2/competition/__init__.py`.
- `v2/edge/fetch_skater_detail.py` — fetcher script (entry point + helpers).
- `v2/edge/compute_burst_rates.py` — analyzer script (entry point + pure functions).
- `v2/edge/tests/__init__.py` — empty marker.
- `v2/edge/tests/test_compute_burst_rates.py` — pytest unit tests.
- `data/2025/edge/skater_detail/` — output dir for raw JSONs (created on first run).
- `data/2025/generated/edge/` — output dir for computed CSV (created on first run).

**Modify:**
- None. No changes to existing files; this is a new self-contained module.

**Responsibilities:**
- `fetch_skater_detail.py`: enumerate player IDs from `league.db`, fetch each player's EDGE payload, save to disk, retry on transient errors, log progress. No analysis logic.
- `compute_burst_rates.py`: read disk JSONs + `league.db` TOI data, compute per-60, output CSV. No network I/O.
- `test_compute_burst_rates.py`: synthetic-data tests for pure functions (player ID enumeration, JSON field extraction, per-60 math).

---

## Task 1: Module Skeleton

**Files:**
- Create: `v2/edge/__init__.py`
- Create: `v2/edge/tests/__init__.py`

- [ ] **Step 1: Create the package directories and empty init files**

```bash
mkdir -p /Users/jrf1039/files/projects/nhl/v2/edge/tests
touch /Users/jrf1039/files/projects/nhl/v2/edge/__init__.py
touch /Users/jrf1039/files/projects/nhl/v2/edge/tests/__init__.py
```

- [ ] **Step 2: Verify pytest can discover the new package**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/ -v --collect-only`
Expected: `0 tests collected` with no errors (the package is empty but discoverable).

- [ ] **Step 3: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/__init__.py v2/edge/tests/__init__.py
```

---

## Task 2: Player ID Enumeration (TDD)

**Files:**
- Create: `v2/edge/compute_burst_rates.py`
- Create: `v2/edge/tests/test_compute_burst_rates.py`

- [ ] **Step 1: Write the failing test**

Add to `v2/edge/tests/test_compute_burst_rates.py`:

```python
"""Tests for v2/edge/compute_burst_rates.py."""

import sqlite3
from pathlib import Path

import pytest


def _make_test_db(tmp_path: Path) -> Path:
    """Create a synthetic league.db with a competition table for tests."""
    db_path = tmp_path / "league.db"
    con = sqlite3.connect(db_path)
    con.execute(
        """
        CREATE TABLE competition (
            gameId INTEGER, playerId INTEGER, team TEXT, position TEXT,
            toi_seconds INTEGER, total_toi_seconds INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TABLE players (
            playerId INTEGER PRIMARY KEY, currentTeamAbbrev TEXT,
            firstName TEXT, lastName TEXT, position TEXT,
            heightInInches INTEGER, weightInPounds INTEGER, shootsCatches TEXT
        )
        """
    )
    rows = [
        # playerId 1: 3 games for EDM
        (2025020001, 1, "EDM", "C", 600, 1200),
        (2025020002, 1, "EDM", "C", 700, 1300),
        (2025020003, 1, "EDM", "C", 650, 1250),
        # playerId 2: 1 game for COL
        (2025020001, 2, "COL", "D", 800, 1500),
        # playerId 3: 2 games for VAN, 1 for FLA (traded)
        (2025020005, 3, "VAN", "L", 500, 900),
        (2025020006, 3, "VAN", "L", 550, 950),
        (2025020010, 3, "FLA", "L", 600, 1000),
    ]
    con.executemany(
        "INSERT INTO competition VALUES (?,?,?,?,?,?)", rows
    )
    con.executemany(
        "INSERT INTO players (playerId, firstName, lastName, position, currentTeamAbbrev) VALUES (?,?,?,?,?)",
        [
            (1, "Test", "One", "C", "EDM"),
            (2, "Test", "Two", "D", "COL"),
            (3, "Test", "Three", "L", "FLA"),
        ],
    )
    con.commit()
    con.close()
    return db_path


def test_list_skater_ids_returns_distinct_skaters(tmp_path):
    from v2.edge.compute_burst_rates import list_skater_ids

    db_path = _make_test_db(tmp_path)
    ids = list_skater_ids(db_path)
    assert sorted(ids) == [1, 2, 3]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py::test_list_skater_ids_returns_distinct_skaters -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'v2.edge.compute_burst_rates'` or similar.

- [ ] **Step 3: Write the minimal implementation**

Create `v2/edge/compute_burst_rates.py`:

```python
"""Compute per-player bursts-over-20mph per 60 minutes of all-strengths TOI.

Inputs: cached EDGE skater-detail JSONs + league.db competition table.
Output: data/2025/generated/edge/player_bursts.csv
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def list_skater_ids(db_path: Path) -> list[int]:
    """Return distinct playerIds from the competition table."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT DISTINCT playerId FROM competition ORDER BY playerId"
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py::test_list_skater_ids_returns_distinct_skaters -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/compute_burst_rates.py v2/edge/tests/test_compute_burst_rates.py
```

---

## Task 3: Player TOI Lookup (TDD)

**Files:**
- Modify: `v2/edge/compute_burst_rates.py` (append a function)
- Modify: `v2/edge/tests/test_compute_burst_rates.py` (append a test)

- [ ] **Step 1: Write the failing test**

Append to `v2/edge/tests/test_compute_burst_rates.py`:

```python
def test_get_player_season_totals_aggregates_all_games(tmp_path):
    from v2.edge.compute_burst_rates import get_player_season_totals

    db_path = _make_test_db(tmp_path)
    totals = get_player_season_totals(db_path)
    # playerId 1: 3 games, total_toi 1200+1300+1250 = 3750
    assert totals[1]["gp"] == 3
    assert totals[1]["total_toi_seconds"] == 3750
    # playerId 3: 3 games (2 VAN + 1 FLA), total_toi 900+950+1000 = 2850
    assert totals[3]["gp"] == 3
    assert totals[3]["total_toi_seconds"] == 2850
    # name + position propagated from players table
    assert totals[1]["name"] == "Test One"
    assert totals[1]["position"] == "C"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py::test_get_player_season_totals_aggregates_all_games -v`
Expected: FAIL with `ImportError: cannot import name 'get_player_season_totals'`.

- [ ] **Step 3: Write the minimal implementation**

Append to `v2/edge/compute_burst_rates.py`:

```python
def get_player_season_totals(db_path: Path) -> dict[int, dict]:
    """Return per-player season totals: GP, total_toi_seconds, name, position.

    Joins competition with players for human-readable name and roster position.
    """
    con = sqlite3.connect(db_path)
    try:
        sql = """
        SELECT c.playerId,
               COUNT(*) AS gp,
               SUM(c.total_toi_seconds) AS total_toi_seconds,
               COALESCE(p.firstName || ' ' || p.lastName, '?') AS name,
               COALESCE(p.position, '?') AS position
        FROM competition c
        LEFT JOIN players p ON p.playerId = c.playerId
        GROUP BY c.playerId
        """
        rows = con.execute(sql).fetchall()
    finally:
        con.close()
    return {
        pid: {"gp": gp, "total_toi_seconds": toi, "name": name, "position": pos}
        for pid, gp, toi, name, pos in rows
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py -v`
Expected: 2 passed.

- [ ] **Step 5: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/compute_burst_rates.py v2/edge/tests/test_compute_burst_rates.py
```

---

## Task 4: EDGE JSON Field Extraction (TDD)

**Files:**
- Modify: `v2/edge/compute_burst_rates.py`
- Modify: `v2/edge/tests/test_compute_burst_rates.py`

- [ ] **Step 1: Write the failing test**

Append to `v2/edge/tests/test_compute_burst_rates.py`:

```python
def test_extract_edge_fields_picks_burst_and_speed():
    from v2.edge.compute_burst_rates import extract_edge_fields

    payload = {
        "player": {"id": 8478402, "team": {"abbrev": "EDM"}},
        "skatingSpeed": {
            "burstsOver20": {"value": 681, "percentile": 1.0,
                             "leagueAvg": {"value": 75.2}},
            "speedMax": {"imperial": 24.6119, "metric": 39.6089},
        },
        "totalDistanceSkated": {"imperial": 330.2671},
    }
    out = extract_edge_fields(payload)
    assert out["bursts_over_20"] == 681
    assert out["speed_max_mph"] == pytest.approx(24.6119)
    assert out["distance_miles"] == pytest.approx(330.2671)
    assert out["current_team"] == "EDM"


def test_extract_edge_fields_returns_none_for_missing_fields():
    from v2.edge.compute_burst_rates import extract_edge_fields

    # Player with no EDGE data — minimal payload
    payload = {"player": {"id": 1, "team": {"abbrev": "XXX"}}}
    out = extract_edge_fields(payload)
    assert out["bursts_over_20"] is None
    assert out["speed_max_mph"] is None
    assert out["distance_miles"] is None
    assert out["current_team"] == "XXX"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py -v -k extract_edge_fields`
Expected: 2 failures with `ImportError: cannot import name 'extract_edge_fields'`.

- [ ] **Step 3: Write the minimal implementation**

Append to `v2/edge/compute_burst_rates.py`:

```python
def extract_edge_fields(payload: dict) -> dict:
    """Pull the fields we care about out of a skater-detail JSON payload.

    Returns None for any field that's missing — the EDGE endpoint occasionally
    omits sub-blocks for players with very little ice time.
    """
    skating = payload.get("skatingSpeed") or {}
    bursts = skating.get("burstsOver20") or {}
    speed_max = skating.get("speedMax") or {}
    distance = payload.get("totalDistanceSkated") or {}
    team = (payload.get("player") or {}).get("team") or {}

    return {
        "bursts_over_20":   bursts.get("value"),
        "speed_max_mph":    speed_max.get("imperial"),
        "distance_miles":   distance.get("imperial"),
        "current_team":     team.get("abbrev"),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py -v`
Expected: 4 passed.

- [ ] **Step 5: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/compute_burst_rates.py v2/edge/tests/test_compute_burst_rates.py
```

---

## Task 5: Per-60 Math (TDD)

**Files:**
- Modify: `v2/edge/compute_burst_rates.py`
- Modify: `v2/edge/tests/test_compute_burst_rates.py`

- [ ] **Step 1: Write the failing test**

Append to `v2/edge/tests/test_compute_burst_rates.py`:

```python
def test_bursts_per_60_basic():
    from v2.edge.compute_burst_rates import bursts_per_60

    # 681 bursts over 113088 seconds = 21.6810 per 60 min
    assert bursts_per_60(681, 113088) == pytest.approx(21.6810, abs=1e-3)


def test_bursts_per_60_returns_none_when_inputs_missing():
    from v2.edge.compute_burst_rates import bursts_per_60

    assert bursts_per_60(None, 1000) is None
    assert bursts_per_60(50, None) is None
    assert bursts_per_60(50, 0) is None  # avoid div-by-zero
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py -v -k bursts_per_60`
Expected: 2 failures with `ImportError: cannot import name 'bursts_per_60'`.

- [ ] **Step 3: Write the minimal implementation**

Append to `v2/edge/compute_burst_rates.py`:

```python
def bursts_per_60(bursts: int | None, total_toi_seconds: int | None) -> float | None:
    """Convert season bursts + season TOI into a per-60-minute rate."""
    if bursts is None or total_toi_seconds is None or total_toi_seconds == 0:
        return None
    return bursts * 3600.0 / total_toi_seconds
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py -v`
Expected: 6 passed.

- [ ] **Step 5: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/compute_burst_rates.py v2/edge/tests/test_compute_burst_rates.py
```

---

## Task 6: Build the Final DataFrame (TDD)

**Files:**
- Modify: `v2/edge/compute_burst_rates.py`
- Modify: `v2/edge/tests/test_compute_burst_rates.py`

- [ ] **Step 1: Write the failing test**

Append to `v2/edge/tests/test_compute_burst_rates.py`:

```python
import json


def _write_edge_json(dir_path: Path, player_id: int, bursts: int | None,
                    speed: float | None, team: str = "EDM") -> None:
    payload = {
        "player": {"id": player_id, "team": {"abbrev": team}},
        "skatingSpeed": {},
        "totalDistanceSkated": {},
    }
    if bursts is not None:
        payload["skatingSpeed"]["burstsOver20"] = {"value": bursts}
    if speed is not None:
        payload["skatingSpeed"]["speedMax"] = {"imperial": speed}
    (dir_path / f"{player_id}.json").write_text(json.dumps(payload))


def test_build_burst_table_joins_edge_and_toi(tmp_path):
    from v2.edge.compute_burst_rates import build_burst_table

    db_path = _make_test_db(tmp_path)
    edge_dir = tmp_path / "edge"
    edge_dir.mkdir()
    _write_edge_json(edge_dir, 1, bursts=100, speed=23.5, team="EDM")
    _write_edge_json(edge_dir, 2, bursts=20, speed=21.0, team="COL")
    # playerId 3 has no EDGE file — should still appear in output with Nones

    df = build_burst_table(db_path, edge_dir)

    # All three players present
    assert sorted(df["playerId"].tolist()) == [1, 2, 3]

    p1 = df.set_index("playerId").loc[1]
    # 100 bursts, total_toi 3750s → 100 * 3600 / 3750 = 96.0
    assert p1["bursts_per_60"] == pytest.approx(96.0)
    assert p1["total_toi_seconds"] == 3750
    assert p1["name"] == "Test One"

    p3 = df.set_index("playerId").loc[3]
    assert p3["bursts_per_60"] is None or pd.isna(p3["bursts_per_60"])
```

Add the pandas import at the top of the test file if not already present:

```python
import pandas as pd
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py -v -k build_burst_table`
Expected: FAIL with `ImportError: cannot import name 'build_burst_table'`.

- [ ] **Step 3: Write the minimal implementation**

Append to `v2/edge/compute_burst_rates.py`:

```python
import json

import pandas as pd


def build_burst_table(db_path: Path, edge_dir: Path) -> pd.DataFrame:
    """Join cached EDGE payloads with league.db season totals into one table.

    Players present in league.db but missing an EDGE JSON file are included
    with None for EDGE-derived fields. This makes coverage gaps visible.
    """
    totals = get_player_season_totals(db_path)
    rows = []
    for pid, totals_row in totals.items():
        edge_path = edge_dir / f"{pid}.json"
        if edge_path.exists():
            payload = json.loads(edge_path.read_text())
            edge_fields = extract_edge_fields(payload)
        else:
            edge_fields = {
                "bursts_over_20": None, "speed_max_mph": None,
                "distance_miles": None, "current_team": None,
            }
        rows.append({
            "playerId":          pid,
            "name":              totals_row["name"],
            "position":          totals_row["position"],
            "current_team":      edge_fields["current_team"],
            "gp":                totals_row["gp"],
            "total_toi_seconds": totals_row["total_toi_seconds"],
            "bursts_over_20":    edge_fields["bursts_over_20"],
            "speed_max_mph":     edge_fields["speed_max_mph"],
            "distance_miles":    edge_fields["distance_miles"],
            "bursts_per_60":     bursts_per_60(
                                    edge_fields["bursts_over_20"],
                                    totals_row["total_toi_seconds"],
                                 ),
        })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_compute_burst_rates.py -v`
Expected: 7 passed.

- [ ] **Step 5: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/compute_burst_rates.py v2/edge/tests/test_compute_burst_rates.py
```

---

## Task 7: CSV Writer + CLI Entry Point

**Files:**
- Modify: `v2/edge/compute_burst_rates.py`

- [ ] **Step 1: Append the CLI entry point**

Append to `v2/edge/compute_burst_rates.py`:

```python
DB_PATH        = Path("data/2025/generated/browser/league.db")
EDGE_DIR       = Path("data/2025/edge/skater_detail")
OUTPUT_DIR     = Path("data/2025/generated/edge")
OUTPUT_CSV     = OUTPUT_DIR / "player_bursts.csv"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"league.db not found at {DB_PATH}")
    if not EDGE_DIR.exists():
        raise SystemExit(
            f"EDGE cache dir not found at {EDGE_DIR}. "
            f"Run v2/edge/fetch_skater_detail.py first."
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = build_burst_table(DB_PATH, EDGE_DIR)
    df = df.sort_values("bursts_per_60", ascending=False, na_position="last")
    df.to_csv(OUTPUT_CSV, index=False)

    n = len(df)
    n_with_edge = df["bursts_over_20"].notna().sum()
    print(f"Wrote {n} players to {OUTPUT_CSV} ({n_with_edge} with EDGE data).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Confirm the file still parses and tests pass**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/ -v`
Expected: 7 passed.

- [ ] **Step 3: Confirm the script is importable and `main` is defined**

Run: `cd /Users/jrf1039/files/projects/nhl && python -c "from v2.edge.compute_burst_rates import main; print(main.__name__)"`
Expected output: `main`

- [ ] **Step 4: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/compute_burst_rates.py
```

---

## Task 8: EDGE Fetcher Helpers (lightweight unit tests)

**Files:**
- Create: `v2/edge/fetch_skater_detail.py`
- Create: `v2/edge/tests/test_fetch_skater_detail.py`

- [ ] **Step 1: Write the failing tests**

Create `v2/edge/tests/test_fetch_skater_detail.py`:

```python
"""Tests for v2/edge/fetch_skater_detail.py — pure-function helpers only.

Network-touching code (fetch_one) is exercised by the end-to-end run, not unit tests.
"""

from pathlib import Path


def test_build_url_uses_documented_pattern():
    from v2.edge.fetch_skater_detail import build_url

    url = build_url(player_id=8478402, season="20252026", game_type=2)
    assert url == (
        "https://api-web.nhle.com/v1/edge/skater-detail/8478402/20252026/2"
    )


def test_target_path_lives_under_player_id(tmp_path):
    from v2.edge.fetch_skater_detail import target_path

    p = target_path(tmp_path, player_id=8478402)
    assert p == tmp_path / "8478402.json"


def test_already_fetched_true_when_file_exists(tmp_path):
    from v2.edge.fetch_skater_detail import already_fetched

    f = tmp_path / "1.json"
    assert already_fetched(f) is False
    f.write_text("{}")
    assert already_fetched(f) is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_fetch_skater_detail.py -v`
Expected: 3 failures with `ModuleNotFoundError: No module named 'v2.edge.fetch_skater_detail'`.

- [ ] **Step 3: Write the minimal implementation**

Create `v2/edge/fetch_skater_detail.py`:

```python
"""Fetch and cache NHL EDGE skater-detail JSON for every active 2025-26 skater.

Reads player IDs from data/2025/generated/browser/league.db (competition table).
Writes one JSON per player to data/2025/edge/skater_detail/{playerId}.json.

Re-runs are safe: existing files are skipped (resume-on-rerun).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from v2.edge.compute_burst_rates import list_skater_ids

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
SEASON      = "20252026"
GAME_TYPE   = 2
SLEEP_SEC   = 0.3       # ~3.3 req/s — empirically clean
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 5
HTTP_TIMEOUT_SEC  = 15

DB_PATH    = Path("data/2025/generated/browser/league.db")
OUTPUT_DIR = Path("data/2025/edge/skater_detail")


def build_url(player_id: int, season: str = SEASON, game_type: int = GAME_TYPE) -> str:
    return (
        f"https://api-web.nhle.com/v1/edge/skater-detail/"
        f"{player_id}/{season}/{game_type}"
    )


def target_path(output_dir: Path, player_id: int) -> Path:
    return output_dir / f"{player_id}.json"


def already_fetched(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/test_fetch_skater_detail.py -v`
Expected: 3 passed.

- [ ] **Step 5: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/fetch_skater_detail.py v2/edge/tests/test_fetch_skater_detail.py
```

---

## Task 9: Single-Player Fetch Function with Retries

**Files:**
- Modify: `v2/edge/fetch_skater_detail.py`

- [ ] **Step 1: Append the fetch helper**

Append to `v2/edge/fetch_skater_detail.py`:

```python
class FetchError(Exception):
    """Raised when a player can't be fetched after all retries."""


def fetch_one(player_id: int) -> dict | None:
    """Fetch one player's EDGE payload. Returns None on 404 (no EDGE data).

    Retries transient errors (5xx, timeouts) up to MAX_RETRIES with linear backoff.
    Raises FetchError on persistent failure.
    """
    url = build_url(player_id)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # no EDGE data for this player — expected for some
            if 500 <= e.code < 600 and attempt < MAX_RETRIES:
                last_err = e
                time.sleep(RETRY_BACKOFF_SEC * attempt)
                continue
            raise FetchError(f"HTTP {e.code} for player {player_id}: {e}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                last_err = e
                time.sleep(RETRY_BACKOFF_SEC * attempt)
                continue
            raise FetchError(f"network error for player {player_id}: {e}") from e

    raise FetchError(f"exhausted retries for player {player_id}: {last_err}")
```

- [ ] **Step 2: Confirm tests still pass**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/edge/tests/ -v`
Expected: 10 passed (7 from compute_burst_rates + 3 from fetch_skater_detail).

- [ ] **Step 3: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/fetch_skater_detail.py
```

---

## Task 10: Fetcher Main Loop

**Files:**
- Modify: `v2/edge/fetch_skater_detail.py`

- [ ] **Step 1: Append the main loop**

Append to `v2/edge/fetch_skater_detail.py`:

```python
def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"league.db not found at {DB_PATH}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    player_ids = list_skater_ids(DB_PATH)
    print(f"Found {len(player_ids)} skaters in league.db. "
          f"Output dir: {OUTPUT_DIR}")

    n_skipped = n_fetched = n_no_data = n_errors = 0

    for i, pid in enumerate(player_ids, start=1):
        path = target_path(OUTPUT_DIR, pid)
        if already_fetched(path):
            n_skipped += 1
            continue

        try:
            payload = fetch_one(pid)
        except FetchError as e:
            n_errors += 1
            print(f"  [{i}/{len(player_ids)}] {pid}: ERROR — {e}",
                  file=sys.stderr)
            time.sleep(SLEEP_SEC)
            continue

        if payload is None:
            # 404 — write an empty marker so we don't re-fetch on next run
            path.write_text("{}")
            n_no_data += 1
        else:
            path.write_text(json.dumps(payload))
            n_fetched += 1

        if i % 50 == 0 or i == len(player_ids):
            print(f"  [{i}/{len(player_ids)}] "
                  f"fetched={n_fetched} skipped={n_skipped} "
                  f"no_data={n_no_data} errors={n_errors}")

        time.sleep(SLEEP_SEC)

    print(
        f"\nDone. fetched={n_fetched} skipped={n_skipped} "
        f"no_data={n_no_data} errors={n_errors}"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify file still parses**

Run: `cd /Users/jrf1039/files/projects/nhl && python -c "from v2.edge.fetch_skater_detail import main; print(main.__name__)"`
Expected output: `main`

- [ ] **Step 3: Run all tests one more time**

Run: `cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v`
Expected: All previously-existing tests still pass + the 10 new edge tests pass. Total should be **92 passed** (82 existing + 10 new).

- [ ] **Step 4: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/fetch_skater_detail.py
```

---

## Task 11: End-to-End Run

This task runs both scripts against the live NHL API and real `league.db` to populate the cache and produce the CSV. ~5 minutes total.

**Files:**
- Creates: `data/2025/edge/skater_detail/*.json` (~940 files)
- Creates: `data/2025/generated/edge/player_bursts.csv`

- [ ] **Step 1: Confirm preconditions**

Run:
```bash
cd /Users/jrf1039/files/projects/nhl
ls -la data/2025/generated/browser/league.db
.venv/bin/python -c "
import sqlite3
con = sqlite3.connect('data/2025/generated/browser/league.db')
print('skaters:', con.execute('SELECT COUNT(DISTINCT playerId) FROM competition').fetchone()[0])
"
```
Expected: `league.db` exists with non-zero size, ~940 skaters.

- [ ] **Step 2: Run the fetcher**

Run: `cd /Users/jrf1039/files/projects/nhl && .venv/bin/python -m v2.edge.fetch_skater_detail`
Expected: Progress lines every 50 players. Final line like `Done. fetched=~940 skipped=0 no_data=<small> errors=0`. Runtime ~5 min (940 × 0.3s + occasional retries).

- [ ] **Step 3: Spot-check a sample of the cached JSONs**

Run:
```bash
cd /Users/jrf1039/files/projects/nhl
ls data/2025/edge/skater_detail/ | wc -l
.venv/bin/python -c "
import json
from pathlib import Path
p = Path('data/2025/edge/skater_detail/8478402.json')  # McDavid
d = json.loads(p.read_text())
print('McDavid burstsOver20:', d['skatingSpeed']['burstsOver20']['value'])
print('Expected: 681 (per earlier verification)')
"
```
Expected: file count matches skater count, McDavid's burst value is 681.

- [ ] **Step 4: Run the analyzer**

Run: `cd /Users/jrf1039/files/projects/nhl && .venv/bin/python -m v2.edge.compute_burst_rates`
Expected: One line like `Wrote 940 players to data/2025/generated/edge/player_bursts.csv (~930 with EDGE data).`

- [ ] **Step 5: Spot-check the output CSV**

Run:
```bash
cd /Users/jrf1039/files/projects/nhl
head -1 data/2025/generated/edge/player_bursts.csv
echo "---top 5 by per-60---"
head -6 data/2025/generated/edge/player_bursts.csv | column -t -s,
echo "---McDavid row---"
grep '^8478402,' data/2025/generated/edge/player_bursts.csv
```
Expected:
- Header row: `playerId,name,position,current_team,gp,total_toi_seconds,bursts_over_20,speed_max_mph,distance_miles,bursts_per_60`
- Top 5 dominated by very-low-TOI call-ups (small-sample noise) — same pattern we saw with EDM.
- McDavid row with `bursts_over_20=681` and `bursts_per_60≈21.68`.

- [ ] **Step 6: Stage outputs (raw JSONs and CSV are intentionally not in `.gitignore`)**

Run:
```bash
cd /Users/jrf1039/files/projects/nhl
git status v2/edge/ data/2025/edge/ data/2025/generated/edge/
```

oiler will decide what to commit and stage manually.

---

## Task 12: Module README

**Files:**
- Create: `v2/edge/README.md`

- [ ] **Step 1: Write a brief README**

Create `v2/edge/README.md`:

```markdown
# v2/edge — NHL EDGE skater data

## Scripts

- `fetch_skater_detail.py` — fetch + cache the EDGE `skater-detail` payload for
  every skater in `league.db`. Writes to `data/2025/edge/skater_detail/{pid}.json`.
  Re-runs are resume-safe (existing files are skipped). Treats HTTP 404 as
  "no EDGE data" and writes a `{}` marker so the player isn't retried.
- `compute_burst_rates.py` — read the cached JSONs + `total_toi_seconds` from
  `competition` and emit `data/2025/generated/edge/player_bursts.csv` with
  per-player season-total `bursts_per_60` (all-strengths TOI denominator).

## Run

```bash
.venv/bin/python -m v2.edge.fetch_skater_detail
.venv/bin/python -m v2.edge.compute_burst_rates
```

## Tests

```bash
python -m pytest v2/edge/ -v
```

## Notes

- The EDGE `skater-detail` payload includes more than bursts: max speed, total
  distance, zone time (with an `Ev` even-strength variant for zone time only),
  shot speed/location, and shots-on-goal summary. The raw JSON is kept on disk
  so future analyzers can mine those fields without re-fetching.
- The NHL-provided `burstsOver20.percentile` ranks **raw counts**, not rates,
  so it conflates ice time with skating speed. Use `bursts_per_60` for
  rate-based comparisons.
- Burst counts are **not strength-sliced**. A player's burst rate reflects all
  game situations (5v5, PP, PK, OT). For our team-level analysis this is a
  caveat to document; per-player attribute comparisons are still meaningful.
```

- [ ] **Step 2: Stage**

```bash
cd /Users/jrf1039/files/projects/nhl
git add v2/edge/README.md
```

---

## Validation Summary

After running this plan end-to-end:

1. **Tests:** `python -m pytest v2/ -v` reports 92 passed (82 existing + 10 new).
2. **Cache:** `data/2025/edge/skater_detail/` contains ~940 JSON files, one per skater.
3. **Output:** `data/2025/generated/edge/player_bursts.csv` has ~940 rows with `bursts_per_60` populated for ~930 of them (a handful of players with no EDGE data will have nulls).
4. **Sanity:** McDavid's row has `bursts_over_20=681` and `bursts_per_60≈21.68`, matching the manual verification done during planning.

## Rollback

This plan only adds files — no existing files are modified. To roll back:

```bash
cd /Users/jrf1039/files/projects/nhl
git restore --staged v2/edge/ data/2025/edge/ data/2025/generated/edge/
rm -rf v2/edge/ data/2025/edge/ data/2025/generated/edge/
```

## Open Questions / Future Work

- Should the burst data be loaded into a `league.db` table for browser queries? Out of scope for this plan; revisit when designing the player-page integration.
- Trade-attribution math (per-team bursts for traded players) is unaddressed. Per-player season-total is sufficient for player-level views; team-level rollups will need to decide proration.
- Should the fetcher be added to the daily orchestrator pipeline (sync_season etc.)? End-of-season data is the most useful snapshot, so for 2025-26 a one-shot run is fine. Daily fetching is a 2026-27 question.
