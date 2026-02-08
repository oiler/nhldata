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
