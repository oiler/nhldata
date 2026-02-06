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
from pathlib import Path
from typing import Dict, List, Tuple

GAME_TYPE = "02"  # Regular season

DATA_CHECKS = [
    ("boxscores", "{game_id}.json"),
    ("plays", "{game_id}.json"),
    ("meta", "{game_id}.json"),
    ("shifts", "{game_id}_home.json"),
    ("shifts", "{game_id}_away.json"),
]


def get_max_game_number(data_dir: Path, season: str) -> int:
    """Find highest game number in boxscores directory."""
    boxscores_dir = data_dir / season / "boxscores"
    if not boxscores_dir.exists():
        return 0

    max_game = 0
    prefix = f"{season}{GAME_TYPE}"
    for f in boxscores_dir.glob(f"{prefix}*.json"):
        # Extract game number from filename like 2025020001.json
        try:
            game_id = f.stem  # e.g., "2025020001"
            if game_id.startswith(prefix):
                game_num = int(game_id[len(prefix):])
                max_game = max(max_game, game_num)
        except ValueError:
            continue

    return max_game


def check_file(filepath: Path) -> str:
    """Check if file exists and is not empty."""
    if not filepath.exists():
        return "missing"
    if filepath.stat().st_size == 0:
        return "empty"
    return "ok"


def scan_season(data_dir: Path, season: str, max_game: int) -> Dict:
    """Scan all data folders for missing or empty files."""
    results = {
        "boxscores": {"ok": [], "missing": [], "empty": []},
        "plays": {"ok": [], "missing": [], "empty": []},
        "meta": {"ok": [], "missing": [], "empty": []},
        "shifts_home": {"ok": [], "missing": [], "empty": []},
        "shifts_away": {"ok": [], "missing": [], "empty": []},
    }

    for game_num in range(1, max_game + 1):
        game_id = f"{season}{GAME_TYPE}{game_num:04d}"

        for folder, pattern in DATA_CHECKS:
            filename = pattern.format(game_id=game_id)
            filepath = data_dir / season / folder / filename

            # Determine result key
            if folder == "shifts":
                if "_home" in pattern:
                    key = "shifts_home"
                else:
                    key = "shifts_away"
            else:
                key = folder

            status = check_file(filepath)
            results[key][status].append((game_num, filepath.name))

    return results


def print_report(results: Dict, season: str, max_game: int):
    """Print formatted report of scan results."""
    print(f"\nNHL Game Data Check - Season {season}")
    print("=" * 40)
    print(f"Checking games 1-{max_game} ({max_game} total)\n")

    # Summary counts
    labels = [
        ("Boxscores", "boxscores"),
        ("Plays", "plays"),
        ("Meta", "meta"),
        ("Shifts Home", "shifts_home"),
        ("Shifts Away", "shifts_away"),
    ]

    for label, key in labels:
        ok_count = len(results[key]["ok"])
        missing_count = len(results[key]["missing"])
        empty_count = len(results[key]["empty"])
        total = ok_count + missing_count + empty_count

        if missing_count == 0 and empty_count == 0:
            print(f"{label + ':':14} {ok_count}/{total} ✓")
        else:
            issues = []
            if missing_count > 0:
                issues.append(f"{missing_count} missing")
            if empty_count > 0:
                issues.append(f"{empty_count} empty")
            print(f"{label + ':':14} {ok_count}/{total} ({', '.join(issues)})")

    # Missing files detail
    all_missing: List[Tuple[int, str, str]] = []
    for label, key in labels:
        for game_num, filename in results[key]["missing"]:
            folder = "shifts" if "shifts" in key else key
            all_missing.append((game_num, folder, filename))

    if all_missing:
        print(f"\nMissing Files:")
        # Sort by game number, show first 10
        all_missing.sort(key=lambda x: x[0])
        for game_num, folder, filename in all_missing[:10]:
            print(f"  {folder}/{filename}")
        if len(all_missing) > 10:
            print(f"  ... ({len(all_missing) - 10} more)")

    # Empty files detail
    all_empty: List[Tuple[int, str, str]] = []
    for label, key in labels:
        for game_num, filename in results[key]["empty"]:
            folder = "shifts" if "shifts" in key else key
            all_empty.append((game_num, folder, filename))

    if all_empty:
        print(f"\nEmpty Files:")
        all_empty.sort(key=lambda x: x[0])
        for game_num, folder, filename in all_empty[:10]:
            print(f"  {folder}/{filename}")
        if len(all_empty) > 10:
            print(f"  ... ({len(all_empty) - 10} more)")

    if not all_missing and not all_empty:
        print(f"\nAll files present and non-empty.")
    else:
        # Suggested download commands
        print(f"\nTo download missing data:")

        # Group missing by type
        missing_plays = set()
        missing_shifts = set()
        for game_num, folder, filename in all_missing:
            if folder in ("boxscores", "plays", "meta"):
                missing_plays.add(game_num)
            elif folder == "shifts":
                missing_shifts.add(game_num)

        if missing_plays:
            sorted_plays = sorted(missing_plays)
            for gn in sorted_plays[:3]:
                print(f"  uv run python v1/nhlgame.py {gn} {gn}")
            if len(sorted_plays) > 3:
                print(f"  ... ({len(sorted_plays) - 3} more games)")

        if missing_shifts:
            sorted_shifts = sorted(missing_shifts)
            for gn in sorted_shifts[:3]:
                print(f"  uv run python v1/nhlgame.py shifts {gn} {gn}")
            if len(sorted_shifts) > 3:
                print(f"  ... ({len(sorted_shifts) - 3} more games)")


def main():
    if len(sys.argv) != 2:
        print("Usage: python tools/gamecheck.py <season>")
        print("Example: python tools/gamecheck.py 2025")
        sys.exit(1)

    season = sys.argv[1]
    data_dir = Path(__file__).parent.parent / "data"

    # Check season directory exists
    season_dir = data_dir / season
    if not season_dir.exists():
        print(f"Error: Season directory not found: {season_dir}")
        print(f"Create it with: mkdir -p {season_dir}/boxscores")
        sys.exit(1)

    # Find max game number
    max_game = get_max_game_number(data_dir, season)
    if max_game == 0:
        print(f"Error: No games found for season {season}")
        print(f"Check that boxscores exist in: {data_dir}/{season}/boxscores/")
        sys.exit(1)

    # Scan and report
    results = scan_season(data_dir, season, max_game)
    print_report(results, season, max_game)


if __name__ == "__main__":
    main()
