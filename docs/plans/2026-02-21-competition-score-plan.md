# Competition Score Per-Game Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** For a single NHL game, compute per-skater competition scores (`comp_fwd`, `comp_def`) representing the mean game 5v5 TOI (in seconds) of opposing forwards and defensemen while that player was on ice.

**Architecture:** Single script `v2/competition/compute_competition.py` that loads a game's timeline CSV and plays JSON, computes lookups from `rosterSpots`, scores every 5v5 second, aggregates per player, and writes a CSV to `data/{season}/generated/competition/{gameId}.csv`. All logic is pure functions — easy to test and later extend for batch/season processing.

**Tech Stack:** Python 3.11+, csv (stdlib), json (stdlib), pathlib (stdlib), pytest

---

## Reference

- Design doc: `docs/plans/2026-02-21-competition-score-design.md`
- Timeline format: `data/2025/generated/timelines/csv/2025020001.csv`
  - Columns: `period, secondsIntoPeriod, secondsElapsedGame, situationCode, strength, awayGoalie, awaySkaterCount, awaySkaters, homeSkaterCount, homeGoalie, homeSkaters`
  - `awaySkaters` / `homeSkaters`: pipe-delimited player IDs e.g. `8476473|8477450|8481624`
  - Goalies are in `awayGoalie`/`homeGoalie` — NOT in the skater columns
- Plays JSON: `data/2025/plays/2025020001.json`
  - `rosterSpots[].playerId`, `.positionCode` (C/L/R/D/G), `.teamId`
  - `homeTeam.abbrev`, `homeTeam.id`, `awayTeam.abbrev`, `awayTeam.id`
- Situation codes in scope: `1551`, `0651`, `1560` (all others ignored)
- Position mapping: `C`, `L`, `R` → `F`; `D` → `D`; unknown → `F`

---

## Task 1: Scaffold

**Files:**
- Create: `v2/competition/__init__.py` (empty)
- Create: `v2/competition/tests/__init__.py` (empty)

**Step 1: Create the directories and empty init files**

```bash
mkdir -p v2/competition/tests
touch v2/competition/__init__.py
touch v2/competition/tests/__init__.py
```

**Step 2: Verify structure**

```bash
ls v2/competition/
ls v2/competition/tests/
```

Expected:
```
v2/competition/    → __init__.py  tests/
v2/competition/tests/  → __init__.py
```

**Step 3: Commit**

```bash
git add v2/competition/
git commit -m "chore: scaffold competition score module"
```

---

## Task 2: build_lookups()

Builds two dicts from the plays JSON:
- `positions`: `{playerId: 'F' or 'D'}`
- `teams`: `{playerId: teamAbbrev}`

**Files:**
- Create: `v2/competition/compute_competition.py`
- Create: `v2/competition/tests/test_compute_competition.py`

**Step 1: Write the failing test**

```python
# v2/competition/tests/test_compute_competition.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from compute_competition import build_lookups


def test_build_lookups_positions():
    plays_data = {
        "homeTeam": {"id": 1, "abbrev": "EDM"},
        "awayTeam": {"id": 2, "abbrev": "CGY"},
        "rosterSpots": [
            {"playerId": 100, "positionCode": "C",  "teamId": 1},
            {"playerId": 200, "positionCode": "L",  "teamId": 1},
            {"playerId": 300, "positionCode": "R",  "teamId": 2},
            {"playerId": 400, "positionCode": "D",  "teamId": 2},
            {"playerId": 500, "positionCode": "G",  "teamId": 1},
        ],
    }
    positions, teams = build_lookups(plays_data)

    assert positions[100] == "F"  # C → F
    assert positions[200] == "F"  # L → F
    assert positions[300] == "F"  # R → F
    assert positions[400] == "D"  # D → D
    assert positions[500] == "G"  # G kept as-is (filtered elsewhere)


def test_build_lookups_teams():
    plays_data = {
        "homeTeam": {"id": 1, "abbrev": "EDM"},
        "awayTeam": {"id": 2, "abbrev": "CGY"},
        "rosterSpots": [
            {"playerId": 100, "positionCode": "C", "teamId": 1},
            {"playerId": 400, "positionCode": "D", "teamId": 2},
        ],
    }
    positions, teams = build_lookups(plays_data)

    assert teams[100] == "EDM"
    assert teams[400] == "CGY"
```

**Step 2: Run test to confirm failure**

```bash
cd /path/to/nhl && python -m pytest v2/competition/tests/test_compute_competition.py::test_build_lookups_positions -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'compute_competition'`

**Step 3: Create compute_competition.py with build_lookups()**

```python
#!/usr/bin/env python3
"""
NHL Competition Score Generator

Computes per-skater competition scores for a single game based on
the mean game 5v5 TOI of opposing forwards and defensemen.

Usage:
    python v2/competition/compute_competition.py <game_number> <season>

Example:
    python v2/competition/compute_competition.py 1 2025
    → writes data/2025/generated/competition/2025020001.csv
"""

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

DATA_DIR = Path("data")
SCORED_SITUATIONS = {"1551", "0651", "1560"}
GAME_TYPE = "02"

_FORWARD_CODES = {"C", "L", "R"}


def build_lookups(plays_data: dict) -> Tuple[Dict[int, str], Dict[int, str]]:
    """
    Build position and team lookups from plays JSON rosterSpots.

    Returns:
        positions: {playerId: 'F', 'D', or 'G'}
        teams:     {playerId: teamAbbrev}
    """
    team_map = {
        plays_data["homeTeam"]["id"]: plays_data["homeTeam"]["abbrev"],
        plays_data["awayTeam"]["id"]: plays_data["awayTeam"]["abbrev"],
    }

    positions: Dict[int, str] = {}
    teams: Dict[int, str] = {}

    for spot in plays_data.get("rosterSpots", []):
        pid = spot["playerId"]
        code = spot.get("positionCode", "")
        positions[pid] = "F" if code in _FORWARD_CODES else ("D" if code == "D" else "G")
        teams[pid] = team_map.get(spot["teamId"], "")

    return positions, teams
```

**Step 4: Run tests**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py::test_build_lookups_positions v2/competition/tests/test_compute_competition.py::test_build_lookups_teams -v
```

Expected: both PASS

**Step 5: Commit**

```bash
git add v2/competition/compute_competition.py v2/competition/tests/test_compute_competition.py
git commit -m "feat: add build_lookups from plays rosterSpots"
```

---

## Task 3: compute_game_toi()

Count each skater's 5v5 seconds on ice from the filtered timeline rows.

**Files:**
- Modify: `v2/competition/compute_competition.py`
- Modify: `v2/competition/tests/test_compute_competition.py`

**Step 1: Write the failing test**

Append to `test_compute_competition.py`:

```python
from compute_competition import compute_game_toi


def test_compute_game_toi_counts_seconds():
    # 3 identical rows — each player should accumulate 3 seconds
    row = {
        "situationCode": "1551",
        "awaySkaters": "1|2|3|4|5",
        "homeSkaters": "6|7|8|9|10",
    }
    rows = [row, row, row]
    toi = compute_game_toi(rows)

    for pid in range(1, 11):
        assert toi[pid] == 3, f"Player {pid} expected 3s, got {toi.get(pid)}"


def test_compute_game_toi_ignores_non_5v5():
    rows = [
        {"situationCode": "1441", "awaySkaters": "1|2|3|4",   "homeSkaters": "6|7|8|9"},
        {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|8|9|10"},
    ]
    toi = compute_game_toi(rows)

    # Player 5 and 10 only appear in the 1551 row → 1 second each
    assert toi.get(5) == 1
    assert toi.get(10) == 1
    # Players 1-4 and 6-9 appear in both rows → 2 seconds each
    assert toi.get(1) == 2
```

**Step 2: Run test to confirm failure**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py::test_compute_game_toi_counts_seconds -v
```

Expected: FAIL — `ImportError: cannot import name 'compute_game_toi'`

**Step 3: Add compute_game_toi() to compute_competition.py**

```python
def compute_game_toi(rows: List[dict]) -> Dict[int, int]:
    """
    Count 5v5 seconds on ice per skater.

    Args:
        rows: list of timeline row dicts (all rows, not pre-filtered)

    Returns:
        {playerId: seconds}
    """
    toi: Dict[int, int] = {}
    for row in rows:
        if row["situationCode"] not in SCORED_SITUATIONS:
            continue
        for col in ("awaySkaters", "homeSkaters"):
            raw = row.get(col, "")
            if not raw:
                continue
            for pid_str in raw.split("|"):
                pid = int(pid_str)
                toi[pid] = toi.get(pid, 0) + 1
    return toi
```

**Step 4: Run tests**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py::test_compute_game_toi_counts_seconds v2/competition/tests/test_compute_competition.py::test_compute_game_toi_ignores_non_5v5 -v
```

Expected: both PASS

**Step 5: Commit**

```bash
git add v2/competition/compute_competition.py v2/competition/tests/test_compute_competition.py
git commit -m "feat: add compute_game_toi"
```

---

## Task 4: score_game()

Core algorithm. For each 5v5 second, accumulate the mean opposing F and D TOI for every skater on ice.

**Files:**
- Modify: `v2/competition/compute_competition.py`
- Modify: `v2/competition/tests/test_compute_competition.py`

**Step 1: Work out the expected values by hand**

Given 1 row at `1551`:
- Away: `1(F,10s)`, `2(F,8s)`, `3(F,6s)`, `4(D,12s)`, `5(D,9s)`
- Home: `6(F,20s)`, `7(F,15s)`, `8(F,5s)`, `9(D,18s)`, `10(D,14s)`

For away player 1 (F), opposing home team:
- opp forwards: 6→20, 7→15, 8→5 → mean = (20+15+5)/3 = **13.333...**
- opp defense: 9→18, 10→14 → mean = (18+14)/2 = **16.0**

For home player 6 (F), opposing away team:
- opp forwards: 1→10, 2→8, 3→6 → mean = (10+8+6)/3 = **8.0**
- opp defense: 4→12, 5→9 → mean = (12+9)/2 = **10.5**

Since there is only 1 row, the per-second value IS the final mean for each player.

**Step 2: Write the failing test**

Append to `test_compute_competition.py`:

```python
from compute_competition import score_game


def test_score_game_single_row():
    rows = [{
        "situationCode": "1551",
        "awaySkaters": "1|2|3|4|5",
        "homeSkaters": "6|7|8|9|10",
    }]
    toi = {1: 10, 2: 8, 3: 6, 4: 12, 5: 9,
           6: 20, 7: 15, 8: 5, 9: 18, 10: 14}
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 8: "F", 9: "D", 10: "D"}

    result = score_game(rows, toi, positions)

    # Away player 1: opp fwd mean=(20+15+5)/3, opp def mean=(18+14)/2
    assert abs(result[1]["comp_fwd"] - 40/3) < 0.001
    assert abs(result[1]["comp_def"] - 16.0) < 0.001

    # Home player 6: opp fwd mean=(10+8+6)/3, opp def mean=(12+9)/2
    assert abs(result[6]["comp_fwd"] - 8.0) < 0.001
    assert abs(result[6]["comp_def"] - 10.5) < 0.001


def test_score_game_skips_non_5v5():
    rows = [
        {"situationCode": "1441", "awaySkaters": "1|2|3|4",   "homeSkaters": "6|7|8|9"},
        {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|8|9|10"},
    ]
    toi = {i: 10 for i in range(1, 11)}
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 8: "F", 9: "D", 10: "D"}

    result = score_game(rows, toi, positions)

    # Player 5 only appears in the 1551 row (1 second), so result should exist
    assert 5 in result
    # Player 1 appears in both rows but only the 1551 row is scored
    assert 1 in result
    # The score should only reflect 1 second (the 1551 row)
    assert abs(result[5]["comp_fwd"] - (10 + 10 + 10) / 3) < 0.001
```

**Step 3: Run test to confirm failure**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py::test_score_game_single_row -v
```

Expected: FAIL — `ImportError: cannot import name 'score_game'`

**Step 4: Add score_game() to compute_competition.py**

```python
def score_game(
    rows: List[dict],
    toi: Dict[int, int],
    positions: Dict[int, str],
) -> Dict[int, dict]:
    """
    For every skater in every 5v5 second, accumulate the mean opposing
    forward and defense TOI.

    Returns:
        {playerId: {"side": "home"|"away", "comp_fwd": float, "comp_def": float}}
    """
    # accum[playerId] = {"side": str, "fwd_vals": [...], "def_vals": [...]}
    accum: Dict[int, dict] = {}

    for row in rows:
        if row["situationCode"] not in SCORED_SITUATIONS:
            continue

        away = [int(p) for p in row["awaySkaters"].split("|")] if row.get("awaySkaters") else []
        home = [int(p) for p in row["homeSkaters"].split("|")] if row.get("homeSkaters") else []

        for player_id, opponents, side in (
            [(p, home, "away") for p in away] +
            [(p, away, "home") for p in home]
        ):
            if player_id not in accum:
                accum[player_id] = {"side": side, "fwd_vals": [], "def_vals": []}

            opp_fwd = [toi.get(p, 0) for p in opponents if positions.get(p, "F") == "F"]
            opp_def = [toi.get(p, 0) for p in opponents if positions.get(p, "F") == "D"]

            if opp_fwd:
                accum[player_id]["fwd_vals"].append(sum(opp_fwd) / len(opp_fwd))
            if opp_def:
                accum[player_id]["def_vals"].append(sum(opp_def) / len(opp_def))

    # Compute means and flatten
    result: Dict[int, dict] = {}
    for pid, data in accum.items():
        fwd_vals = data["fwd_vals"]
        def_vals = data["def_vals"]
        result[pid] = {
            "side": data["side"],
            "comp_fwd": sum(fwd_vals) / len(fwd_vals) if fwd_vals else 0.0,
            "comp_def": sum(def_vals) / len(def_vals) if def_vals else 0.0,
        }

    return result
```

**Step 5: Run all tests so far**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py -v
```

Expected: all tests PASS

**Step 6: Commit**

```bash
git add v2/competition/compute_competition.py v2/competition/tests/test_compute_competition.py
git commit -m "feat: add score_game with per-second competition scoring"
```

---

## Task 5: Full pipeline — load, run, write output

Wire everything together: load files, run the pipeline, write the output CSV.

**Files:**
- Modify: `v2/competition/compute_competition.py`

**Step 1: Write the integration test**

Append to `test_compute_competition.py`:

```python
import os
from compute_competition import run_game


def test_run_game_produces_output():
    """Integration test using real 2025 game data."""
    game_number = 1
    season = "2025"
    output_path = Path("data/2025/generated/competition/2025020001.csv")

    # Clean up before test
    if output_path.exists():
        output_path.unlink()

    run_game(game_number, season)

    assert output_path.exists(), "Output CSV was not created"

    with open(output_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) > 0, "Output CSV is empty"

    # Check required columns
    required = {"gameId", "playerId", "team", "position", "toi_seconds", "comp_fwd", "comp_def"}
    assert required.issubset(set(rows[0].keys())), f"Missing columns: {required - set(rows[0].keys())}"

    # comp_fwd and comp_def should be positive numbers
    for row in rows:
        assert float(row["comp_fwd"]) > 0, f"Player {row['playerId']} has zero comp_fwd"
        assert float(row["comp_def"]) > 0, f"Player {row['playerId']} has zero comp_def"
```

**Step 2: Run test to confirm failure**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py::test_run_game_produces_output -v
```

Expected: FAIL — `ImportError: cannot import name 'run_game'`

**Step 3: Add load helpers and run_game() to compute_competition.py**

```python
def load_timeline(season: str, game_id: str) -> List[dict]:
    """Load timeline CSV, return list of row dicts."""
    path = DATA_DIR / season / "generated" / "timelines" / "csv" / f"{game_id}.csv"
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_plays(season: str, game_id: str) -> dict:
    """Load plays JSON for a game."""
    path = DATA_DIR / season / "plays" / f"{game_id}.json"
    with open(path) as f:
        return json.load(f)


def write_output(game_id: str, season: str, scores: Dict[int, dict],
                 toi: Dict[int, int], positions: Dict[int, str],
                 teams: Dict[int, str]) -> Path:
    """Write per-player competition scores to CSV."""
    out_dir = DATA_DIR / season / "generated" / "competition"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{game_id}.csv"

    rows = []
    for pid, data in scores.items():
        rows.append({
            "gameId":      game_id,
            "playerId":    pid,
            "team":        teams.get(pid, ""),
            "position":    positions.get(pid, "F"),
            "toi_seconds": toi.get(pid, 0),
            "comp_fwd":    round(data["comp_fwd"], 2),
            "comp_def":    round(data["comp_def"], 2),
        })

    rows.sort(key=lambda r: r["toi_seconds"], reverse=True)

    fieldnames = ["gameId", "playerId", "team", "position", "toi_seconds", "comp_fwd", "comp_def"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return out_path


def run_game(game_number: int, season: str) -> Path:
    """Full pipeline for a single game. Returns path to output CSV."""
    game_id = f"{season}{GAME_TYPE}{game_number:04d}"

    plays_data = load_plays(season, game_id)
    positions, teams = build_lookups(plays_data)

    timeline_rows = load_timeline(season, game_id)
    toi = compute_game_toi(timeline_rows)
    scores = score_game(timeline_rows, toi, positions)

    return write_output(game_id, season, scores, toi, positions, teams)
```

**Step 4: Add main() and CLI**

```python
def main():
    if len(sys.argv) != 3:
        print("Usage: python v2/competition/compute_competition.py <game_number> <season>")
        print("Example: python v2/competition/compute_competition.py 1 2025")
        sys.exit(1)

    try:
        game_number = int(sys.argv[1])
        season = sys.argv[2]
    except ValueError:
        print("Error: game_number must be an integer")
        sys.exit(1)

    out_path = run_game(game_number, season)
    print(f"Written: {out_path}")


if __name__ == "__main__":
    main()
```

**Step 5: Run all tests**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py -v
```

Expected: all tests PASS

**Step 6: Spot-check the output manually**

```bash
python v2/competition/compute_competition.py 1 2025
head -5 data/2025/generated/competition/2025020001.csv
```

Expected: CSV with header row + player rows sorted by `toi_seconds` descending. Top rows should be recognizable top-line forwards with 1000–1200 seconds.

**Step 7: Commit**

```bash
git add v2/competition/compute_competition.py v2/competition/tests/test_compute_competition.py
git commit -m "feat: add run_game pipeline and CLI for competition score"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `python -m pytest v2/competition/tests/ -v` — all green
- [ ] `python v2/competition/compute_competition.py 1 2025` — produces `data/2025/generated/competition/2025020001.csv`
- [ ] Output has correct columns: `gameId, playerId, team, position, toi_seconds, comp_fwd, comp_def`
- [ ] All players have `comp_fwd > 0` and `comp_def > 0`
- [ ] Rows sorted by `toi_seconds` descending
- [ ] Top players' `comp_fwd` and `comp_def` values are in seconds (roughly 600–1200 range for top opponents)

---

## Notes for Next Phase (Season Aggregation)

Not in scope here. When ready:
1. Loop `run_game()` over all games for a season → one CSV per game in `data/{season}/generated/competition/`
2. Load all per-game CSVs, weighted-average `comp_fwd`/`comp_def` by `toi_seconds` per player
3. Normalize: `(player_avg / league_avg) × 100` — computed separately for F and D populations
