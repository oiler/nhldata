# Plan: Game Data Checker (v1.6)

## Goal
Create `tools/gamecheck.py` that scans data folders for a season and reports missing or empty game files.

## Usage
```bash
uv run python tools/gamecheck.py 2025
```

## Algorithm

1. **Determine game range**: Find highest game number in `data/{season}/boxscores/` directory (same approach as `get_last_saved_game()` in nhlgame.py)

2. **Check each data folder** for games 1 through max_game:
   - `boxscores/{gameId}.json`
   - `plays/{gameId}.json`
   - `meta/{gameId}.json`
   - `shifts/{gameId}_home.json`
   - `shifts/{gameId}_away.json`

3. **Identify issues**:
   - Missing files (file doesn't exist)
   - Empty files (0 bytes)
   - Malformed JSON (optional: try to parse)

4. **Report summary** with actionable output

## Output Format

```
NHL Game Data Check - Season 2025
==================================
Checking games 1-902 (902 total)

Boxscores:   902/902 ✓
Plays:       900/902 (2 missing)
Meta:        902/902 ✓
Shifts Home: 856/902 (46 missing)
Shifts Away: 856/902 (46 missing)

Missing Files:
  plays/2025020485.json
  plays/2025020595.json
  shifts/2025020847_home.json
  shifts/2025020847_away.json
  ... (truncated, showing first 10)

Empty Files:
  (none)

To download missing data:
  uv run python v1/nhlgame.py 485 485
  uv run python v1/nhlgame.py 595 595
  uv run python v1/nhlgame.py shifts 847 847
```

## Implementation

### File: `tools/gamecheck.py`

```python
#!/usr/bin/env python3
"""
NHL Game Data Checker

Scans data folders for missing or empty game files.

Usage:
    python tools/gamecheck.py <season>

Example:
    python tools/gamecheck.py 2025
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

GAME_TYPE = "02"  # Regular season

DATA_CHECKS = [
    ("boxscores", "{game_id}.json"),
    ("plays", "{game_id}.json"),
    ("meta", "{game_id}.json"),
    ("shifts", "{game_id}_home.json"),
    ("shifts", "{game_id}_away.json"),
]
```

### Key Functions

1. **`get_max_game_number(season: str) -> int`**
   - Scan boxscores directory for highest game number
   - Pattern: `{season}02*.json`
   - Extract game number from filename

2. **`check_file(filepath: Path) -> str`**
   - Returns: "ok", "missing", or "empty"
   - Check existence, then size > 0

3. **`scan_season(season: str) -> Dict`**
   - For each game 1 to max_game
   - Check all 5 file types
   - Return dict with missing/empty lists per type

4. **`print_report(results: Dict, season: str)`**
   - Summary counts per folder
   - List of missing/empty files
   - Suggested download commands

## Changes

| File | Change |
|------|--------|
| `tools/gamecheck.py` | New file (~120 lines) |

## Verification

```bash
# Run on 2025 season
uv run python tools/gamecheck.py 2025

# Expected: Summary showing file counts and any gaps
```

## Edge Cases

- **No boxscores exist**: Error message "No games found for season {season}"
- **Season folder doesn't exist**: Error message with instructions
- **Partial shifts**: Only home or only away missing (report separately)
