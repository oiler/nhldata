#!/usr/bin/env python3
"""
NHL Boxscore CSV Flattener

Flattens boxscore JSON data into CSV format for spreadsheet analysis.

Usage:
    python tools/flatten_boxscore.py <season>
    python tools/flatten_boxscore.py <start> <end> <season>

Examples:
    python tools/flatten_boxscore.py 2025
        -> Outputs: data/2025/generated/flatboxscores/boxscores.csv (all games in one file)

    python tools/flatten_boxscore.py 734 734 2025
        -> Outputs: data/2025/generated/flatboxscores/2025020734.csv

    python tools/flatten_boxscore.py 1 100 2025
        -> Outputs: data/2025/generated/flatboxscores/{gameId}.csv (one file per game)
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


def main():
    """Main entry point."""
    if len(sys.argv) == 2:
        # All games mode: flatten_boxscore.py <season>
        season = sys.argv[1]
        start_game = None
        end_game = None
        range_mode = False
    elif len(sys.argv) == 4:
        # Range mode: flatten_boxscore.py <start> <end> <season>
        try:
            start_game = int(sys.argv[1])
            end_game = int(sys.argv[2])
        except ValueError:
            print("Error: start and end must be integers")
            sys.exit(1)
        season = sys.argv[3]
        range_mode = True
    else:
        print(__doc__)
        sys.exit(1)

    print(f"NHL Boxscore CSV Flattener")
    print(f"Season: {season}")
    if range_mode:
        print(f"Game range: {start_game} to {end_game}")
    else:
        print(f"Processing all games")

    # Find boxscore files
    files = get_boxscore_files(season, start_game, end_game)
    print(f"Found {len(files)} boxscore files")

    if range_mode:
        # Range mode: write individual files per game
        output_dir = Path("data") / season / "generated" / "flatboxscores"
        output_dir.mkdir(parents=True, exist_ok=True)

        success_count = 0
        for filepath in files:
            try:
                boxscore = load_boxscore(filepath)
                row = flatten_boxscore(boxscore)
                game_id = boxscore.get('id')
                output_path = output_dir / f"{game_id}.csv"
                write_csv([row], output_path)
                success_count += 1
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Skipping {filepath.name} - {e}")

        if success_count == 0:
            print("Error: No games were processed successfully")
            sys.exit(1)

        print(f"Wrote {success_count} game files to {output_dir}/")
    else:
        # Full season mode: write single file with all games
        rows = []
        for filepath in files:
            try:
                boxscore = load_boxscore(filepath)
                row = flatten_boxscore(boxscore)
                rows.append(row)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Skipping {filepath.name} - {e}")

        if not rows:
            print("Error: No games were processed successfully")
            sys.exit(1)

        output_path = Path("data") / season / "generated" / "flatboxscores" / "boxscores.csv"
        write_csv(rows, output_path)

        print(f"Wrote {len(rows)} games to {output_path}")


if __name__ == "__main__":
    main()
