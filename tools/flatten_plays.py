#!/usr/bin/env python3
"""
NHL Play-by-Play CSV Flattener

Flattens play-by-play JSON data into a browsable CSV for spreadsheet analysis.

Usage:
    # Single game
    python tools/flatten_plays.py 153 2025

    # Range of games
    python tools/flatten_plays.py 1 100 2025

Output:
    data/{season}/generated/flatplays/{gameId}.csv
"""

import json
import csv
import sys
from pathlib import Path
from typing import Dict, List, Set, Any


# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = Path("data")
GAME_TYPE = "02"  # Regular season

# Core fields to appear first in column order
CORE_FIELDS = [
    'eventId',
    'sortOrder',
    'timeInPeriod',
    'timeRemaining',
    'situationCode',
    'typeCode',
    'typeDescKey',
]


# ============================================================================
# FLATTENING FUNCTIONS
# ============================================================================

def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """
    Flatten a nested dictionary into dot-notation keys.

    Example:
        {"a": {"b": 1, "c": 2}} -> {"a.b": 1, "a.c": 2}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        elif isinstance(v, list):
            # Convert lists to JSON string for CSV compatibility
            items.append((new_key, json.dumps(v) if v else ''))
        else:
            items.append((new_key, v))
    return dict(items)


def discover_columns(plays: List[Dict]) -> List[str]:
    """
    Scan all plays to discover all possible column names.
    Returns columns in sorted order with core fields first.
    """
    all_columns: Set[str] = set()

    for play in plays:
        flat = flatten_dict(play)
        all_columns.update(flat.keys())

    # Sort columns: core fields first, then period, then details, then rest
    core = [c for c in CORE_FIELDS if c in all_columns]
    period = sorted([c for c in all_columns if c.startswith('periodDescriptor.')])
    details = sorted([c for c in all_columns if c.startswith('details.')])
    rest = sorted([c for c in all_columns
                   if c not in core
                   and not c.startswith('periodDescriptor.')
                   and not c.startswith('details.')])

    return core + period + details + rest


def flatten_plays(plays: List[Dict], columns: List[str]) -> List[Dict[str, Any]]:
    """
    Flatten all plays into rows with consistent columns.
    """
    rows = []
    for play in plays:
        flat = flatten_dict(play)
        row = {col: flat.get(col, '') for col in columns}
        rows.append(row)
    return rows


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def load_plays(season: str, game_id: str) -> List[Dict]:
    """Load play-by-play data for a game."""
    filepath = DATA_DIR / season / "plays" / f"{game_id}.json"
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data.get('plays', [])


def write_csv(rows: List[Dict], columns: List[str], output_path: Path):
    """Write flattened plays to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


# ============================================================================
# MAIN
# ============================================================================

def process_game(game_num: int, season: str) -> bool:
    """
    Process a single game.

    Returns True if successful, False otherwise.
    """
    game_id = f"{season}{GAME_TYPE}{game_num:04d}"
    output_path = DATA_DIR / season / "generated" / "flatplays" / f"{game_id}.csv"

    try:
        # Load plays
        plays = load_plays(season, game_id)

        if not plays:
            print(f"  {game_id}: No plays found, skipping")
            return False

        # Discover columns and flatten
        columns = discover_columns(plays)
        rows = flatten_plays(plays, columns)

        # Write output
        write_csv(rows, columns, output_path)

        print(f"  {game_id}: {len(rows)} plays, {len(columns)} columns -> {output_path}")
        return True

    except FileNotFoundError:
        print(f"  {game_id}: Play-by-play file not found, skipping")
        return False
    except Exception as e:
        print(f"  {game_id}: Error - {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python tools/flatten_plays.py <game_num> <season>")
        print("  python tools/flatten_plays.py <start> <end> <season>")
        print()
        print("Examples:")
        print("  python tools/flatten_plays.py 153 2025")
        print("  python tools/flatten_plays.py 1 100 2025")
        sys.exit(1)

    if len(sys.argv) == 3:
        # Single game mode
        game_num = int(sys.argv[1])
        season = sys.argv[2]

        print(f"Flattening play-by-play for game {game_num}, season {season}")
        success = process_game(game_num, season)
        sys.exit(0 if success else 1)
    else:
        # Batch mode
        start = int(sys.argv[1])
        end = int(sys.argv[2])
        season = sys.argv[3]

        print(f"Flattening play-by-play for games {start}-{end}, season {season}")
        print()

        succeeded = 0
        failed = 0

        for game_num in range(start, end + 1):
            if process_game(game_num, season):
                succeeded += 1
            else:
                failed += 1

        print()
        print(f"Complete: {succeeded} succeeded, {failed} failed")
        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
