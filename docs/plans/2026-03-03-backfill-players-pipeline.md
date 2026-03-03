# Backfill Players Pipeline Step

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `backfill_players` step to the orchestrator pipeline so missing player data is automatically fetched after competition data is generated, before the league DB is rebuilt.

**Architecture:** Add a thin wrapper tool in `generate.py` that calls the existing `get_players.py backfill <season>` script. Wire it into the agent's tool list and update the system prompt pipeline order. Place it after `compute_competition` (which creates the competition CSVs that the backfill scans) and before `build_league_db` (which reads players.csv).

**Tech Stack:** subprocess wrapper, existing `get_players.py backfill` mode.

---

### Task 1: Add backfill_players tool function

**Files:**
- Modify: `v2/orchestrator/tools/generate.py`
- Test: `v2/orchestrator/tests/test_tools.py`

---

**Step 1: Add test for backfill_players**

Add to the end of `v2/orchestrator/tests/test_tools.py`:

```python
from v2.orchestrator.tools.generate import backfill_players

@patch("v2.orchestrator.tools.generate.subprocess.run")
def test_backfill_players(mock_run):
    mock_run.return_value = _mock_run_success("Players backfilled: 3")
    result = backfill_players(season="2025")
    assert result["status"] == "ok"
    cmd = mock_run.call_args[0][0]
    assert "backfill" in cmd
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/orchestrator/tests/test_tools.py::test_backfill_players -v
```

Expected: FAIL — `ImportError: cannot import name 'backfill_players'`

**Step 3: Add backfill_players function**

Add to `v2/orchestrator/tools/generate.py` after the `compute_competition` function:

```python
def backfill_players(season: str = "2025") -> dict:
    """Fetch any players in competition data missing from players.csv."""
    return _run_script("get_players", ["backfill", season])
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/orchestrator/tests/test_tools.py::test_backfill_players -v
```

Expected: PASS

**Step 5: Run full test suite**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v
```

Expected: All 69 tests pass (68 existing + 1 new).

---

### Task 2: Wire backfill_players into the agent

**Files:**
- Modify: `v2/orchestrator/agent.py`

---

**Step 1: Add import**

Update the import from `generate` (line 10-13) to include `backfill_players`:

```python
from v2.orchestrator.tools.generate import (
    flatten_boxscores, flatten_plays, fetch_players,
    generate_timelines, compute_competition, backfill_players,
)
```

**Step 2: Add tool definition**

Add to the `TOOLS` list, after the `compute_competition` entry and before `build_league_db`:

```python
    {
        "name": "backfill_players",
        "description": "Fetch any players found in competition data who are missing a raw data file. Run after compute_competition to catch call-ups and recent additions.",
        "input_schema": {
            "type": "object",
            "properties": {"season": {"type": "string"}},
            "required": ["season"]
        }
    },
```

**Step 3: Add handler**

Add to the `TOOL_HANDLERS` dict, after `compute_competition`:

```python
    "backfill_players": lambda args: backfill_players(
        season=args["season"]),
```

**Step 4: Update SYSTEM_PROMPT pipeline order**

Update the pipeline order in SYSTEM_PROMPT to insert step 10:

```
1. check_schedule → learn which games were played
2. fetch_games → download raw data for those games
3. validate_game → confirm files exist, JSON is valid
4. If shifts missing → fetch_shifts to retry, then validate again
5. flatten_boxscores → flatten all boxscores to master CSV (run for full season)
6. flatten_plays → flatten play-by-play for new games
7. fetch_players → update player metadata (catches new player IDs)
8. generate_timelines → build second-by-second timelines (requires shifts)
9. compute_competition → calculate competition scores (requires timelines)
10. backfill_players → fetch any players in competition data missing from players.csv
11. build_league_db → rebuild league.db from all generated data
12. notify → send summary notification
```

**Step 5: Run full test suite**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v
```

Expected: All 69 tests pass.

---

### Task 3: Run backfill for current missing players

Fix the 3 LAK players missing from last night's game:

```bash
cd /Users/jrf1039/files/projects/nhl && python v2/players/get_players.py backfill 2025
python v2/browser/build_league_db.py
```

Verify names resolved:

```bash
sqlite3 data/2025/generated/browser/league.db "
SELECT playerId, firstName || ' ' || lastName AS name
FROM players WHERE playerId IN (8483699, 8483675, 8483756)
"
```

Expected: Angus Booth, Kenny Connors, Jared Wright.
