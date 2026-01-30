#!/usr/bin/env python3
"""
NHL Play-by-Play Data Flattener

Converts nested JSON play events to flat CSV format for easier analysis.

Usage:
    python flatten_plays.py GAME_ID SEASON

Example:
    python flatten_plays.py 0393 2025
    
This will read from: 2025/plays/2025020393.json
And output to: plays_2025020393.csv
"""

import sys
import json
import csv
from pathlib import Path
from typing import Dict, List, Any


def flatten_period_descriptor(period_desc: Dict) -> Dict:
    """
    Flatten periodDescriptor object.
    
    Input: {"number": 1, "periodType": "REG", "maxRegulationPeriods": 3}
    Output: {"periodNumber": 1, "periodType": "REG", "maxRegulationPeriods": 3}
    """
    return {
        "periodNumber": period_desc.get("number"),
        "periodType": period_desc.get("periodType"),
        "maxRegulationPeriods": period_desc.get("maxRegulationPeriods")
    }


def flatten_play_event(play: Dict, game_id: str) -> Dict:
    """
    Flatten a single play event from nested structure to flat dictionary.
    
    Handles:
    - periodDescriptor object -> periodNumber, periodType, maxRegulationPeriods
    - details object -> flattened into parent
    - Adds game_id as first column
    """
    flattened = {"game_id": game_id}
    
    # Add all top-level fields except nested objects
    for key, value in play.items():
        if key == "periodDescriptor":
            # Flatten period descriptor
            period_data = flatten_period_descriptor(value)
            flattened.update(period_data)
        elif key == "details":
            # Flatten details object into parent
            if isinstance(value, dict):
                flattened.update(value)
        else:
            # Add simple fields as-is
            # Convert lists/dicts to JSON strings for CSV compatibility
            if isinstance(value, (list, dict)):
                flattened[key] = json.dumps(value)
            else:
                flattened[key] = value
    
    return flattened


def load_plays_json(filepath: Path) -> List[Dict]:
    """Load the plays array from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # The plays should be in a "plays" key at the top level
    if "plays" in data:
        return data["plays"]
    else:
        raise ValueError(f"No 'plays' array found in {filepath}")


def write_plays_to_csv(plays: List[Dict], output_path: Path):
    """
    Write flattened plays to CSV file.
    
    Uses natural field order with prioritized columns.
    """
    if not plays:
        print("Warning: No plays to write")
        return
    
    # Define priority column order
    priority_order = [
        "game_id",
        "eventId",
        "periodNumber",
        "periodType",
        "maxRegulationPeriods",
        "timeInPeriod",
        "timeRemaining",
        "situationCode",
        "homeTeamDefendingSide",
        "typeCode",
        "typeDescKey",
        "sortOrder",
        # Details section - coordinates first
        "xCoord",
        "yCoord",
        "zoneCode",
    ]
    
    # Collect all columns that appear in the data
    all_columns = []
    seen = set()
    
    # First pass: collect columns in order of first appearance
    for play in plays:
        for key in play.keys():
            if key not in seen:
                all_columns.append(key)
                seen.add(key)
    
    # Build final column order: priority columns first, then remaining in appearance order
    columns = []
    for col in priority_order:
        if col in seen:
            columns.append(col)
    
    # Add remaining columns (those not in priority list)
    for col in all_columns:
        if col not in priority_order:
            columns.append(col)
    
    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(plays)
    
    print(f"✓ Wrote {len(plays)} plays to {output_path}")
    print(f"  Columns: {len(columns)}")


def construct_game_id(game_number: str, season: str) -> str:
    """Construct full game ID."""
    game_type = "02"  # Regular season
    return f"{season}{game_type}{int(game_number):04d}"


def main():
    """Main execution function."""
    # Validate arguments
    if len(sys.argv) != 3:
        print("Error: Invalid number of arguments")
        print(f"Usage: python {sys.argv[0]} GAME_NUMBER SEASON")
        print(f"Example: python {sys.argv[0]} 393 2025")
        print(f"  This reads: ../2025/plays/2025020393.json")
        print(f"  And outputs: output/plays_2025020393.csv")
        sys.exit(1)
    
    game_number = sys.argv[1]
    season = sys.argv[2]
    
    # Construct paths relative to project root
    # Script is in: nhlgamedata/plays/
    # Data is in: nhlgamedata/2025/plays/
    # Output goes to: nhlgamedata/plays/output/
    project_root = Path(__file__).parent.parent  # Go up to nhlgamedata/
    game_id = construct_game_id(game_number, season)
    input_file = project_root / season / "plays" / f"{game_id}.json"
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"plays_{game_id}.csv"
    
    print(f"\nNHL Play-by-Play Data Flattener")
    print(f"{'='*60}")
    print(f"Game ID: {game_id}")
    print(f"Input:   {input_file}")
    print(f"Output:  {output_file}")
    print(f"{'='*60}\n")
    
    # Check if input file exists
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    # Load plays from JSON
    print(f"Loading plays from {input_file}...")
    plays_raw = load_plays_json(input_file)
    print(f"✓ Loaded {len(plays_raw)} play events")
    
    # Flatten all plays
    print(f"Flattening play events...")
    plays_flattened = [flatten_play_event(play, game_id) for play in plays_raw]
    print(f"✓ Flattened {len(plays_flattened)} play events")
    
    # Write to CSV
    print(f"Writing to CSV...")
    write_plays_to_csv(plays_flattened, output_file)
    
    print(f"\n{'='*60}")
    print(f"Complete! CSV saved to: {output_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()