# Flatten Boxscore Data Implementation Plan (v1.7)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Flatten NHL boxscore JSON data into a CSV with one row per game for spreadsheet analysis and database import.

**Architecture:** Single Python script reads boxscore JSON files, extracts specified fields with underscore-notation for nested objects, and outputs a single CSV containing all games. Player IDs are pipe-separated arrays.

**Tech Stack:** Python 3, json, csv (standard library only)

---

## Output Format

### CSV Columns (in order)

| Column | Source | Example |
|--------|--------|---------|
| id | boxscore.id | 2025020734 |
| gameDate | boxscore.gameDate | 2026-01-13 |
| startTimeUTC | boxscore.startTimeUTC | 2026-01-14T03:00:00Z |
| easternUTCOffset | boxscore.easternUTCOffset | -05:00 |
| venueUTCOffset | boxscore.venueUTCOffset | -08:00 |
| periodDescriptor_number | boxscore.periodDescriptor.number | 3 |
| periodDescriptor_periodType | boxscore.periodDescriptor.periodType | REG |
| periodDescriptor_maxRegulationPeriods | boxscore.periodDescriptor.maxRegulationPeriods | 3 |
| awayTeam_id | boxscore.awayTeam.id | 25 |
| awayTeam_abbrev | boxscore.awayTeam.abbrev | DAL |
| awayTeam_score | boxscore.awayTeam.score | 1 |
| awayTeam_sog | boxscore.awayTeam.sog | 25 |
| homeTeam_id | boxscore.homeTeam.id | 24 |
| homeTeam_abbrev | boxscore.homeTeam.abbrev | ANA |
| homeTeam_score | boxscore.homeTeam.score | 3 |
| homeTeam_sog | boxscore.homeTeam.sog | 25 |
| awayTeam_playerIds | all player IDs from playerByGameStats.awayTeam | 8480840\|8476889\|... |
| homeTeam_playerIds | all player IDs from playerByGameStats.homeTeam | 8481754\|8476458\|... |

### Sample Output Row

```csv
id,gameDate,startTimeUTC,easternUTCOffset,venueUTCOffset,periodDescriptor_number,periodDescriptor_periodType,periodDescriptor_maxRegulationPeriods,awayTeam_id,awayTeam_abbrev,awayTeam_score,awayTeam_sog,homeTeam_id,homeTeam_abbrev,homeTeam_score,homeTeam_sog,awayTeam_playerIds,homeTeam_playerIds
2025020734,2026-01-13,2026-01-14T03:00:00Z,-05:00,-08:00,3,REG,3,25,DAL,1,25,24,ANA,3,25,8480840|8476889|8473994|...,8481754|8476458|8473986|...
```

---

## Usage

```bash
# All games in season (outputs single file with all games)
uv run python tools/flatten_boxscore.py 2025

# Specific game range
uv run python tools/flatten_boxscore.py 1 100 2025
```

## Output Location

```
data/{season}/generated/flatboxscores/boxscores.csv
```

---

## Task 1: Create Script with Argument Parsing

**Files:**
- Create: `tools/flatten_boxscore.py`

**Step 1: Create script with argument parsing and main structure**

```python
#!/usr/bin/env python3
"""
NHL Boxscore CSV Flattener

Flattens boxscore JSON files into a single CSV for spreadsheet analysis.

Usage:
    python tools/flatten_boxscore.py <season>
    python tools/flatten_boxscore.py <start> <end> <season>

Examples:
    python tools/flatten_boxscore.py 2025
    python tools/flatten_boxscore.py 1 100 2025
"""

import sys
import json
import csv
from pathlib import Path
from typing import Dict, List, Optional


# CSV column definitions (in order)
CSV_COLUMNS = [
    'id',
    'gameDate',
    'startTimeUTC',
    'easternUTCOffset',
    'venueUTCOffset',
    'periodDescriptor_number',
    'periodDescriptor_periodType',
    'periodDescriptor_maxRegulationPeriods',
    'awayTeam_id',
    'awayTeam_abbrev',
    'awayTeam_score',
    'awayTeam_sog',
    'homeTeam_id',
    'homeTeam_abbrev',
    'homeTeam_score',
    'homeTeam_sog',
    'awayTeam_playerIds',
    'homeTeam_playerIds',
]


def main():
    """Main entry point."""
    if len(sys.argv) == 2:
        # All games mode: flatten_boxscore.py <season>
        season = sys.argv[1]
        start_game = None
        end_game = None
    elif len(sys.argv) == 4:
        # Range mode: flatten_boxscore.py <start> <end> <season>
        try:
            start_game = int(sys.argv[1])
            end_game = int(sys.argv[2])
        except ValueError:
            print("Error: start and end must be integers")
            sys.exit(1)
        season = sys.argv[3]
    else:
        print(__doc__)
        sys.exit(1)

    print(f"NHL Boxscore CSV Flattener")
    print(f"Season: {season}")
    if start_game and end_game:
        print(f"Game range: {start_game} to {end_game}")
    else:
        print(f"Processing all games")

    # TODO: Implement processing


if __name__ == "__main__":
    main()
```

**Step 2: Verify script runs**

Run: `uv run python tools/flatten_boxscore.py 2025`

Expected: Shows "Processing all games" message

**Step 3: Commit**

```bash
git add tools/flatten_boxscore.py
git commit -m "feat: add flatten_boxscore.py with argument parsing"
```

---

## Task 2: Add File Discovery and Loading

**Files:**
- Modify: `tools/flatten_boxscore.py`

**Step 1: Add function to find boxscore files**

Add after CSV_COLUMNS definition:

```python
def get_boxscore_files(season: str, start_game: Optional[int] = None,
                       end_game: Optional[int] = None) -> List[Path]:
    """
    Get list of boxscore JSON files to process.

    Args:
        season: Season year (e.g., "2025")
        start_game: Optional start game number
        end_game: Optional end game number

    Returns:
        Sorted list of boxscore file paths
    """
    boxscores_dir = Path("data") / season / "boxscores"

    if not boxscores_dir.exists():
        print(f"Error: Directory not found: {boxscores_dir}")
        sys.exit(1)

    # Find all boxscore files
    pattern = f"{season}02*.json"
    files = sorted(boxscores_dir.glob(pattern))

    if not files:
        print(f"Error: No boxscore files found in {boxscores_dir}")
        sys.exit(1)

    # Filter by game range if specified
    if start_game is not None and end_game is not None:
        filtered = []
        for f in files:
            # Extract game number from filename (e.g., 2025020734.json -> 734)
            game_num = int(f.stem[6:])  # Skip "202502"
            if start_game <= game_num <= end_game:
                filtered.append(f)
        files = filtered

    return files


def load_boxscore(filepath: Path) -> Dict:
    """Load a boxscore JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)
```

**Step 2: Update main() to use file discovery**

Replace the TODO comment in main() with:

```python
    # Find boxscore files
    files = get_boxscore_files(season, start_game, end_game)
    print(f"Found {len(files)} boxscore files")

    # TODO: Process files
```

**Step 3: Verify file discovery works**

Run: `uv run python tools/flatten_boxscore.py 1 10 2025`

Expected: Shows "Found 10 boxscore files"

**Step 4: Commit**

```bash
git add tools/flatten_boxscore.py
git commit -m "feat: add boxscore file discovery and loading"
```

---

## Task 3: Add Boxscore Flattening Logic

**Files:**
- Modify: `tools/flatten_boxscore.py`

**Step 1: Add function to extract player IDs**

Add after load_boxscore:

```python
def extract_player_ids(team_stats: Dict) -> str:
    """
    Extract all player IDs from a team's playerByGameStats.

    Args:
        team_stats: The awayTeam or homeTeam dict from playerByGameStats

    Returns:
        Pipe-separated string of player IDs
    """
    player_ids = []

    for position_group in ['forwards', 'defense', 'goalies']:
        players = team_stats.get(position_group, [])
        for player in players:
            player_id = player.get('playerId')
            if player_id is not None:
                player_ids.append(str(player_id))

    return '|'.join(player_ids)
```

**Step 2: Add function to flatten a boxscore**

Add after extract_player_ids:

```python
def flatten_boxscore(boxscore: Dict) -> Dict:
    """
    Flatten a boxscore into a single row dict.

    Args:
        boxscore: Raw boxscore JSON data

    Returns:
        Dict with flattened column names and values
    """
    # Get playerByGameStats
    player_stats = boxscore.get('playerByGameStats', {})
    away_stats = player_stats.get('awayTeam', {})
    home_stats = player_stats.get('homeTeam', {})

    return {
        'id': boxscore.get('id'),
        'gameDate': boxscore.get('gameDate'),
        'startTimeUTC': boxscore.get('startTimeUTC'),
        'easternUTCOffset': boxscore.get('easternUTCOffset'),
        'venueUTCOffset': boxscore.get('venueUTCOffset'),
        'periodDescriptor_number': boxscore.get('periodDescriptor', {}).get('number'),
        'periodDescriptor_periodType': boxscore.get('periodDescriptor', {}).get('periodType'),
        'periodDescriptor_maxRegulationPeriods': boxscore.get('periodDescriptor', {}).get('maxRegulationPeriods'),
        'awayTeam_id': boxscore.get('awayTeam', {}).get('id'),
        'awayTeam_abbrev': boxscore.get('awayTeam', {}).get('abbrev'),
        'awayTeam_score': boxscore.get('awayTeam', {}).get('score'),
        'awayTeam_sog': boxscore.get('awayTeam', {}).get('sog'),
        'homeTeam_id': boxscore.get('homeTeam', {}).get('id'),
        'homeTeam_abbrev': boxscore.get('homeTeam', {}).get('abbrev'),
        'homeTeam_score': boxscore.get('homeTeam', {}).get('score'),
        'homeTeam_sog': boxscore.get('homeTeam', {}).get('sog'),
        'awayTeam_playerIds': extract_player_ids(away_stats),
        'homeTeam_playerIds': extract_player_ids(home_stats),
    }
```

**Step 3: Test flattening on a single file**

Run: `uv run python -c "
from tools.flatten_boxscore import load_boxscore, flatten_boxscore
from pathlib import Path
bs = load_boxscore(Path('data/2025/boxscores/2025020734.json'))
row = flatten_boxscore(bs)
print(f'id: {row[\"id\"]}')
print(f'awayTeam_abbrev: {row[\"awayTeam_abbrev\"]}')
print(f'awayTeam_playerIds (first 50 chars): {row[\"awayTeam_playerIds\"][:50]}...')
"`

Expected: Shows game ID 2025020734, DAL, and pipe-separated player IDs

**Step 4: Commit**

```bash
git add tools/flatten_boxscore.py
git commit -m "feat: add boxscore flattening logic"
```

---

## Task 4: Add CSV Output

**Files:**
- Modify: `tools/flatten_boxscore.py`

**Step 1: Add CSV writing function**

Add after flatten_boxscore:

```python
def write_csv(rows: List[Dict], output_path: Path):
    """
    Write flattened boxscores to CSV.

    Args:
        rows: List of flattened boxscore dicts
        output_path: Path to output CSV file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
```

**Step 2: Update main() to process files and write CSV**

Replace the TODO comment in main() with:

```python
    # Process each boxscore
    rows = []
    for filepath in files:
        boxscore = load_boxscore(filepath)
        row = flatten_boxscore(boxscore)
        rows.append(row)

    # Write output
    output_path = Path("data") / season / "generated" / "flatboxscores" / "boxscores.csv"
    write_csv(rows, output_path)

    print(f"Wrote {len(rows)} games to {output_path}")
```

**Step 3: Run on small range and verify output**

Run: `uv run python tools/flatten_boxscore.py 1 5 2025`

Expected: Creates CSV with 5 rows + header

Verify: `head -2 data/2025/generated/flatboxscores/boxscores.csv`

**Step 4: Commit**

```bash
git add tools/flatten_boxscore.py
git commit -m "feat: add CSV output for flattened boxscores"
```

---

## Task 5: Final Testing and Documentation

**Files:**
- Modify: `tools/flatten_boxscore.py`

**Step 1: Run on full season**

Run: `uv run python tools/flatten_boxscore.py 2025`

Expected: Processes all games, creates boxscores.csv

**Step 2: Verify CSV integrity**

Run: `wc -l data/2025/generated/flatboxscores/boxscores.csv`

Expected: Line count = number of games + 1 (header)

Run: `head -1 data/2025/generated/flatboxscores/boxscores.csv`

Expected: Shows all 18 column headers

**Step 3: Spot check data accuracy**

Run: `grep "2025020734" data/2025/generated/flatboxscores/boxscores.csv`

Expected: Row contains DAL vs ANA, score 1-3

**Step 4: Commit**

```bash
git add data/2025/generated/flatboxscores/boxscores.csv
git commit -m "feat: generate flattened boxscores CSV for 2025 season"
```

---

## Changes Summary

| File | Change |
|------|--------|
| `tools/flatten_boxscore.py` | New file (~120 lines) |
| `data/2025/generated/flatboxscores/boxscores.csv` | Generated output |

## Verification Checklist

- [ ] Script runs with `uv run python tools/flatten_boxscore.py 2025`
- [ ] CSV has correct 18 columns in expected order
- [ ] Player IDs are pipe-separated
- [ ] Nested fields use underscore separator (e.g., awayTeam_id)
- [ ] All games in season are included when running without range
- [ ] Game range filtering works correctly
