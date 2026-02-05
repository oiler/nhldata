#!/usr/bin/env python3
"""
NHL Test Games Discovery Script

Analyzes all play-by-play files to find games with high situationCode diversity.
Use this to identify candidate games for the test dataset.

Usage:
    python tools/discover_test_games.py

Output:
    - Console: Top 40 games ranked by situationCode diversity
    - CSV: resources/game_analysis.csv with full ranked list
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Set


# ============================================================================
# CONFIGURATION
# ============================================================================
SEASON = "2025"
PLAYS_DIR = Path("data") / SEASON / "plays"
OUTPUT_CSV = Path("resources") / "game_analysis.csv"
TOP_N_CONSOLE = 40


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def analyze_game(plays_file: Path) -> Dict:
    """
    Analyze a single game's play-by-play data for situationCode diversity.

    Args:
        plays_file: Path to the play-by-play JSON file

    Returns:
        Dictionary with analysis results
    """
    with open(plays_file, 'r') as f:
        data = json.load(f)

    game_id = str(data.get('id', plays_file.stem))
    plays = data.get('plays', [])

    # Extract situationCodes from plays
    # Exclusions:
    #   - Period 5 (shootout) - occurs after playing time, different format
    #   - period-end/game-end events - have artificial situationCodes not representing gameplay
    # Included:
    #   - Penalty shot codes (0101, 1010) - happen during live gameplay
    situation_codes: List[str] = []
    for play in plays:
        # Skip shootout period (Period 5) - occurs after playing time
        period = play.get('periodDescriptor', {}).get('number', 0)
        if period == 5:
            continue

        # Skip period-end and game-end events - they have artificial situationCodes
        type_desc_key = play.get('typeDescKey', '')
        if type_desc_key in ('period-end', 'game-end'):
            continue

        code = play.get('situationCode')
        if code:
            situation_codes.append(code)

    # Calculate unique codes
    unique_codes: Set[str] = set(situation_codes)

    # Calculate transitions (changes from one code to another)
    transitions = 0
    prev_code = None
    for code in situation_codes:
        if prev_code is not None and code != prev_code:
            transitions += 1
        prev_code = code

    return {
        'game_id': game_id,
        'unique_codes_count': len(unique_codes),
        'transitions': transitions,
        'codes_list': sorted(unique_codes),
        'total_plays_with_code': len(situation_codes)
    }


def discover_all_games() -> List[Dict]:
    """
    Scan all play-by-play files and analyze each game.

    Returns:
        List of analysis results, sorted by unique codes (desc), then transitions (desc)
    """
    if not PLAYS_DIR.exists():
        print(f"Error: Plays directory not found: {PLAYS_DIR}")
        return []

    plays_files = sorted(PLAYS_DIR.glob("*.json"))

    if not plays_files:
        print(f"Error: No play-by-play files found in {PLAYS_DIR}")
        return []

    print(f"Analyzing {len(plays_files)} games...")

    results = []
    for i, plays_file in enumerate(plays_files):
        try:
            result = analyze_game(plays_file)
            results.append(result)
        except Exception as e:
            print(f"  Warning: Failed to analyze {plays_file.name}: {e}")

        # Progress indicator
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(plays_files)} games...")

    # Sort by unique codes (desc), then transitions (desc)
    results.sort(key=lambda x: (x['unique_codes_count'], x['transitions']), reverse=True)

    return results


def calculate_coverage(results: List[Dict]) -> Dict:
    """
    Calculate overall situationCode coverage across all games.

    Returns:
        Dictionary with coverage statistics
    """
    all_codes: Set[str] = set()
    for result in results:
        all_codes.update(result['codes_list'])

    return {
        'total_unique_codes': len(all_codes),
        'all_codes': sorted(all_codes)
    }


def export_csv(results: List[Dict], output_path: Path):
    """
    Export analysis results to CSV file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['game_id', 'unique_codes', 'transitions', 'codes_list'])

        for result in results:
            writer.writerow([
                result['game_id'],
                result['unique_codes_count'],
                result['transitions'],
                ','.join(result['codes_list'])
            ])


def print_top_games(results: List[Dict], n: int):
    """
    Print top N games to console.
    """
    print(f"\n{'='*80}")
    print(f"TOP {n} GAMES BY SITUATIONCODE DIVERSITY")
    print(f"{'='*80}")
    print(f"{'Rank':<6} {'Game ID':<12} {'Unique':<8} {'Trans':<8} {'Codes'}")
    print(f"{'-'*80}")

    for i, result in enumerate(results[:n]):
        codes_str = ', '.join(result['codes_list'][:8])
        if len(result['codes_list']) > 8:
            codes_str += f", ... (+{len(result['codes_list']) - 8} more)"

        print(f"{i+1:<6} {result['game_id']:<12} {result['unique_codes_count']:<8} {result['transitions']:<8} {codes_str}")


def print_coverage_summary(coverage: Dict):
    """
    Print coverage summary to console.
    """
    print(f"\n{'='*80}")
    print(f"SITUATIONCODE COVERAGE SUMMARY")
    print(f"{'='*80}")
    print(f"Total unique codes found across all games: {coverage['total_unique_codes']}")
    print(f"\nAll codes: {', '.join(coverage['all_codes'])}")


def suggest_greedy_selection(results: List[Dict], max_games: int = 20) -> List[Dict]:
    """
    Suggest a greedy selection of games to maximize code coverage.

    Strategy: Start with the game with most unique codes, then iteratively
    add the game that contributes the most new codes.
    """
    if not results:
        return []

    selected = []
    covered_codes: Set[str] = set()

    while len(selected) < max_games and results:
        # Find game that adds most new codes
        best_game = None
        best_new_codes = 0
        best_idx = -1

        for i, result in enumerate(results):
            new_codes = len(set(result['codes_list']) - covered_codes)
            if new_codes > best_new_codes:
                best_new_codes = new_codes
                best_game = result
                best_idx = i

        if best_game is None or best_new_codes == 0:
            break

        selected.append(best_game)
        covered_codes.update(best_game['codes_list'])
        results.pop(best_idx)

    return selected


def print_greedy_suggestion(selected: List[Dict], all_codes: Set[str]):
    """
    Print the greedy selection suggestion.
    """
    covered_codes: Set[str] = set()
    for game in selected:
        covered_codes.update(game['codes_list'])

    missing_codes = all_codes - covered_codes

    print(f"\n{'='*80}")
    print(f"SUGGESTED SELECTION (Greedy Algorithm - {len(selected)} games)")
    print(f"{'='*80}")
    print(f"{'#':<4} {'Game ID':<12} {'New Codes':<10} {'Total Coverage'}")
    print(f"{'-'*80}")

    running_coverage: Set[str] = set()
    for i, game in enumerate(selected):
        new_codes = set(game['codes_list']) - running_coverage
        running_coverage.update(game['codes_list'])
        print(f"{i+1:<4} {game['game_id']:<12} +{len(new_codes):<9} {len(running_coverage)}/{len(all_codes)}")

    print(f"\n{'='*80}")
    print(f"Coverage: {len(covered_codes)}/{len(all_codes)} codes ({100*len(covered_codes)/len(all_codes):.1f}%)")

    if missing_codes:
        print(f"\nMissing codes: {', '.join(sorted(missing_codes))}")
    else:
        print(f"\nFull coverage achieved!")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print(f"\nNHL Test Games Discovery Script")
    print(f"{'='*80}")
    print(f"Scanning: {PLAYS_DIR}")

    # Analyze all games
    results = discover_all_games()

    if not results:
        return

    print(f"\nAnalyzed {len(results)} games successfully.")

    # Calculate coverage
    coverage = calculate_coverage(results)

    # Print coverage summary
    print_coverage_summary(coverage)

    # Print top games
    print_top_games(results, TOP_N_CONSOLE)

    # Export to CSV
    export_csv(results, OUTPUT_CSV)
    print(f"\n✓ Full results exported to: {OUTPUT_CSV}")

    # Suggest greedy selection
    results_copy = [r.copy() for r in results]  # Don't modify original
    selected = suggest_greedy_selection(results_copy, max_games=20)
    print_greedy_suggestion(selected, set(coverage['all_codes']))

    print(f"\n{'='*80}")
    print(f"Next steps:")
    print(f"  1. Review the suggested selection above")
    print(f"  2. Check {OUTPUT_CSV} for full game list")
    print(f"  3. Create resources/TEST_GAMES.md with your final selection")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
