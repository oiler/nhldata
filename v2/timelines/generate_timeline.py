#!/usr/bin/env python3
"""
NHL Timeline Generator v2

Generates second-by-second timelines showing players on ice and situationCode
for each game. Primary data source is HTML-scraped shift files.

Usage:
    # Single game
    python v2/timelines/generate_timeline.py 591 2025

    # Batch mode
    python v2/timelines/generate_timeline.py 1 100 2025
"""

import json
import csv
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = Path("data")


# ============================================================================
# DATA LOADING
# ============================================================================

def load_json(filepath: Path) -> Dict:
    """Load a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def load_shifts(season: str, game_id: str, team_type: str) -> Dict:
    """Load shift data for a team (home or away)."""
    filepath = DATA_DIR / season / "shifts" / f"{game_id}_{team_type}.json"
    return load_json(filepath)


def load_boxscore(season: str, game_id: str) -> Dict:
    """Load boxscore data for a game."""
    filepath = DATA_DIR / season / "boxscores" / f"{game_id}.json"
    return load_json(filepath)


def load_plays(season: str, game_id: str) -> Dict:
    """Load play-by-play data for a game."""
    filepath = DATA_DIR / season / "plays" / f"{game_id}.json"
    return load_json(filepath)


# ============================================================================
# PLAYER MAPPING
# ============================================================================

def build_player_mapping(boxscore: Dict) -> Dict[str, Dict[int, int]]:
    """
    Build jersey number -> player ID mapping from boxscore data.

    Returns:
        {
            'home': {sweaterNumber: playerId, ...},
            'away': {sweaterNumber: playerId, ...}
        }
    """
    mapping = {'home': {}, 'away': {}}

    for team_key, team_type in [('homeTeam', 'home'), ('awayTeam', 'away')]:
        team_data = boxscore.get('playerByGameStats', {}).get(team_key, {})

        for position_group in ['forwards', 'defense', 'goalies']:
            players = team_data.get(position_group, [])
            for player in players:
                sweater = player.get('sweaterNumber')
                player_id = player.get('playerId')
                if sweater is not None and player_id is not None:
                    mapping[team_type][sweater] = player_id

    return mapping


def get_goalie_ids(boxscore: Dict) -> Dict[str, Set[int]]:
    """
    Get goalie player IDs from boxscore data.

    Returns:
        {
            'home': {playerId, ...},
            'away': {playerId, ...}
        }
    """
    goalie_ids = {'home': set(), 'away': set()}

    for team_key, team_type in [('homeTeam', 'home'), ('awayTeam', 'away')]:
        team_data = boxscore.get('playerByGameStats', {}).get(team_key, {})
        goalies = team_data.get('goalies', [])
        for goalie in goalies:
            player_id = goalie.get('playerId')
            if player_id is not None:
                goalie_ids[team_type].add(player_id)

    return goalie_ids


# ============================================================================
# TIME PARSING
# ============================================================================

def time_to_seconds(time_str: str) -> int:
    """Convert MM:SS time string to seconds."""
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])


def seconds_to_time(seconds: int) -> str:
    """Convert seconds to MM:SS time string."""
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


# ============================================================================
# SHIFT PROCESSING
# ============================================================================

def process_shifts(shifts_data: Dict, player_mapping: Dict[int, int],
                   goalie_ids: Set[int]) -> Dict[Tuple[int, int], Dict]:
    """
    Process shift data into a lookup structure.

    Args:
        shifts_data: Raw shift data from JSON file
        player_mapping: Jersey number -> player ID mapping
        goalie_ids: Set of goalie player IDs for this team

    Returns:
        Dictionary keyed by (period, second) containing:
        {
            'skaters': set of player IDs,
            'goalie': player ID or None
        }
    """
    # Build per-second lookup
    seconds_data: Dict[Tuple[int, int], Dict] = {}

    for player in shifts_data.get('players', []):
        jersey = player.get('number')
        if jersey is None:
            continue

        player_id = player_mapping.get(jersey)
        if player_id is None:
            # Player not in boxscore mapping - skip with warning
            name = player.get('name', 'Unknown')
            print(f"  Warning: No mapping for #{jersey} {name}")
            continue

        is_goalie = player_id in goalie_ids

        for shift in player.get('shifts', []):
            period = shift.get('period')
            start_time = shift.get('startTime')
            end_time = shift.get('endTime')

            if period is None or start_time is None or end_time is None:
                continue

            start_sec = time_to_seconds(start_time)
            end_sec = time_to_seconds(end_time)

            # Process each second of the shift
            # A shift from 0:00 to 5:30 (330 seconds duration) counts seconds 0-329.
            # The end second is when the player left, not when they were on ice.
            #
            # For line changes at the same timestamp:
            # - Player A ends at 5:30 (endTime=330), on ice for seconds 0-329
            # - Player B starts at 5:30 (startTime=330), on ice for seconds 330+
            # This prevents double-counting at the changeover.

            for sec in range(start_sec, end_sec):
                key = (period, sec)
                if key not in seconds_data:
                    seconds_data[key] = {'skaters': set(), 'goalie': None}

                if is_goalie:
                    seconds_data[key]['goalie'] = player_id
                else:
                    seconds_data[key]['skaters'].add(player_id)

    return seconds_data


# ============================================================================
# PENALTY SHOT DETECTION
# ============================================================================

def get_penalty_shots(plays: Dict) -> List[Dict]:
    """
    Extract penalty shot events from play-by-play data.

    Returns list of:
        {
            'period': int,
            'second': int,
            'shooter_team': 'home' or 'away'
        }
    """
    penalty_shots = []

    for play in plays.get('plays', []):
        situation_code = play.get('situationCode')

        # Penalty shot codes: 0101 (away shooter) or 1010 (home shooter)
        if situation_code in ('0101', '1010'):
            period = play.get('periodDescriptor', {}).get('number')
            time_in_period = play.get('timeInPeriod')

            # Skip shootout (period 5)
            if period == 5:
                continue

            # Skip period-end/game-end artifacts
            type_desc = play.get('typeDescKey', '')
            if type_desc in ('period-end', 'game-end'):
                continue

            if period is not None and time_in_period is not None:
                second = time_to_seconds(time_in_period)
                shooter_team = 'home' if situation_code == '1010' else 'away'
                penalty_shots.append({
                    'period': period,
                    'second': second,
                    'shooter_team': shooter_team,
                    'situation_code': situation_code
                })

    return penalty_shots


# ============================================================================
# GAME INFO
# ============================================================================

def get_game_info(boxscore: Dict, plays: Dict) -> Dict:
    """Extract game metadata."""
    # Determine number of periods from plays data
    max_period = 0
    for play in plays.get('plays', []):
        period = play.get('periodDescriptor', {}).get('number', 0)
        if period > max_period:
            max_period = period

    # Determine if playoff game (gameType == 3)
    game_type = boxscore.get('gameType', 2)
    is_playoff = game_type == 3

    return {
        'gameId': str(boxscore.get('id', '')),
        'season': str(boxscore.get('season', '')),
        'gameDate': boxscore.get('gameDate', ''),
        'gameType': game_type,
        'isPlayoff': is_playoff,
        'numPeriods': max_period,
        'homeTeam': {
            'id': boxscore.get('homeTeam', {}).get('id'),
            'abbrev': boxscore.get('homeTeam', {}).get('abbrev'),
            'name': boxscore.get('homeTeam', {}).get('name', {}).get('default', '')
        },
        'awayTeam': {
            'id': boxscore.get('awayTeam', {}).get('id'),
            'abbrev': boxscore.get('awayTeam', {}).get('abbrev'),
            'name': boxscore.get('awayTeam', {}).get('name', {}).get('default', '')
        }
    }


def get_period_length(period: int, is_playoff: bool) -> int:
    """
    Get the length of a period in seconds.

    Periods 1-3: 1200 seconds (20 minutes)
    Period 4 (regular season OT): 300 seconds (5 minutes)
    Period 4+ (playoff OT): 1200 seconds (20 minutes)
    """
    if period <= 3:
        return 1200
    elif is_playoff:
        return 1200  # Playoff OT is 20 minutes
    else:
        return 300   # Regular season OT is 5 minutes


# ============================================================================
# TIMELINE GENERATION
# ============================================================================

def build_situation_code(home_skaters: int, home_goalie: bool,
                         away_skaters: int, away_goalie: bool) -> str:
    """
    Build situationCode from player counts.

    Format: [Away Goalie][Away Skaters][Home Skaters][Home Goalie]
    """
    return f"{1 if away_goalie else 0}{away_skaters}{home_skaters}{1 if home_goalie else 0}"


def situationcode_to_strength(code: str) -> str:
    """
    Convert situationCode to normalized strength.

    Strength is team-agnostic: both 1451 (home PP) and 1541 (away PP) map to 5v4.
    When a goalie is pulled, the extra attacker is normalized out so strength
    remains consistent (e.g., 0641 with pulled goalie → 5v4).

    Args:
        code: 4-digit situationCode [awayGoalie][awaySkaters][homeSkaters][homeGoalie]

    Returns:
        Strength string like "5v5", "5v4", "4v3", or "N/A" for penalty shots
    """
    # Penalty shots
    if code in ('0101', '1010'):
        return 'N/A'

    # Parse digits: [awayGoalie][awaySkaters][homeSkaters][homeGoalie]
    away_goalie = int(code[0])
    away_skaters = int(code[1])
    home_skaters = int(code[2])
    home_goalie = int(code[3])

    # Normalize: if goalie pulled, that team has an extra attacker
    # Subtract 1 to get effective strength
    if away_goalie == 0:
        away_skaters -= 1
    if home_goalie == 0:
        home_skaters -= 1

    # Format with larger number first
    high = max(away_skaters, home_skaters)
    low = min(away_skaters, home_skaters)
    return f"{high}v{low}"


def generate_timeline(season: str, game_id: str) -> Tuple[Dict, List[Dict]]:
    """
    Generate second-by-second timeline for a game.

    Returns:
        (game_info, timeline_entries)
    """
    # Load data
    home_shifts = load_shifts(season, game_id, 'home')
    away_shifts = load_shifts(season, game_id, 'away')
    boxscore = load_boxscore(season, game_id)
    plays = load_plays(season, game_id)

    # Build mappings
    player_mapping = build_player_mapping(boxscore)
    goalie_ids = get_goalie_ids(boxscore)

    # Process shifts
    home_seconds = process_shifts(home_shifts, player_mapping['home'], goalie_ids['home'])
    away_seconds = process_shifts(away_shifts, player_mapping['away'], goalie_ids['away'])

    # Get penalty shots
    penalty_shots = get_penalty_shots(plays)
    penalty_shot_lookup = {(ps['period'], ps['second']): ps for ps in penalty_shots}

    # Get game info
    game_info = get_game_info(boxscore, plays)

    # Build timeline
    timeline = []
    total_elapsed = 0

    for period in range(1, game_info['numPeriods'] + 1):
        # Skip shootout (period 5 in regular season)
        if period == 5 and not game_info['isPlayoff']:
            continue

        period_length = get_period_length(period, game_info['isPlayoff'])

        for sec in range(period_length):  # 0 through period_length-1
            key = (period, sec)

            # Get players on ice
            home_data = home_seconds.get(key, {'skaters': set(), 'goalie': None})
            away_data = away_seconds.get(key, {'skaters': set(), 'goalie': None})

            home_skaters = sorted(home_data['skaters'])
            away_skaters = sorted(away_data['skaters'])
            home_goalie = home_data['goalie']
            away_goalie = away_data['goalie']

            # Check for penalty shot override
            if key in penalty_shot_lookup:
                situation_code = penalty_shot_lookup[key]['situation_code']
            else:
                # Calculate situationCode from shift data
                situation_code = build_situation_code(
                    len(home_skaters), home_goalie is not None,
                    len(away_skaters), away_goalie is not None
                )

            # Calculate normalized strength
            strength = situationcode_to_strength(situation_code)

            entry = {
                'period': period,
                'secondsIntoPeriod': sec,
                'secondsElapsedGame': total_elapsed,
                'situationCode': situation_code,
                'strength': strength,
                'home': {
                    'skaters': home_skaters,
                    'skaterCount': len(home_skaters),
                    'goalie': home_goalie
                },
                'away': {
                    'skaters': away_skaters,
                    'skaterCount': len(away_skaters),
                    'goalie': away_goalie
                }
            }

            timeline.append(entry)
            total_elapsed += 1

    return game_info, timeline


# ============================================================================
# VALIDATION
# ============================================================================

def parse_toi_to_seconds(toi_str: str) -> int:
    """Parse TOI string (MM:SS) to seconds."""
    if not toi_str:
        return 0
    parts = toi_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])


def validate_toi(timeline: List[Dict], home_shifts: Dict, away_shifts: Dict,
                 player_mapping: Dict, goalie_ids: Dict) -> Tuple[bool, List[str]]:
    """
    Validate calculated TOI against shift file totals.

    Returns:
        (success, list of error messages)
    """
    errors = []

    # Calculate TOI from timeline
    calculated_toi: Dict[int, int] = {}  # player_id -> seconds

    for entry in timeline:
        for player_id in entry['home']['skaters']:
            calculated_toi[player_id] = calculated_toi.get(player_id, 0) + 1
        if entry['home']['goalie']:
            calculated_toi[entry['home']['goalie']] = calculated_toi.get(entry['home']['goalie'], 0) + 1

        for player_id in entry['away']['skaters']:
            calculated_toi[player_id] = calculated_toi.get(player_id, 0) + 1
        if entry['away']['goalie']:
            calculated_toi[entry['away']['goalie']] = calculated_toi.get(entry['away']['goalie'], 0) + 1

    # Compare against expected TOI from shift files
    for team_type, shifts_data in [('home', home_shifts), ('away', away_shifts)]:
        mapping = player_mapping[team_type]

        for player in shifts_data.get('players', []):
            jersey = player.get('number')
            if jersey is None:
                continue

            player_id = mapping.get(jersey)
            if player_id is None:
                continue

            expected_toi = parse_toi_to_seconds(player.get('gameTotals', {}).get('toi', '0:00'))
            actual_toi = calculated_toi.get(player_id, 0)

            if expected_toi != actual_toi:
                name = player.get('name', 'Unknown')
                diff = actual_toi - expected_toi
                errors.append(
                    f"  {team_type.upper()} #{jersey} {name}: "
                    f"calculated {actual_toi}s, expected {expected_toi}s (diff: {diff:+d}s)"
                )

    return len(errors) == 0, errors


# ============================================================================
# OUTPUT
# ============================================================================

def write_json_output(game_info: Dict, timeline: List[Dict], output_path: Path):
    """Write timeline to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        **game_info,
        'timeline': timeline
    }

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)


def write_csv_output(game_info: Dict, timeline: List[Dict], output_path: Path):
    """Write timeline to CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)

        # Header - away team first to match situationCode format
        # situationCode: [Away Goalie][Away Skaters][Home Skaters][Home Goalie]
        writer.writerow([
            'period', 'secondsIntoPeriod', 'secondsElapsedGame', 'situationCode', 'strength',
            'awayGoalie', 'awaySkaterCount', 'awaySkaters',
            'homeSkaterCount', 'homeGoalie', 'homeSkaters'
        ])

        # Data rows
        for entry in timeline:
            writer.writerow([
                entry['period'],
                entry['secondsIntoPeriod'],
                entry['secondsElapsedGame'],
                entry['situationCode'],
                entry['strength'],
                entry['away']['goalie'] or '',
                entry['away']['skaterCount'],
                '|'.join(str(p) for p in entry['away']['skaters']),
                entry['home']['skaterCount'],
                entry['home']['goalie'] or '',
                '|'.join(str(p) for p in entry['home']['skaters'])
            ])


# ============================================================================
# MAIN
# ============================================================================

def process_game(game_num: int, season: str, validate: bool = True) -> bool:
    """
    Process a single game.

    Returns True if successful, False otherwise.
    """
    game_id = f"{season}02{game_num:04d}"

    print(f"\nNHL Timeline Generator v2")
    print("=" * 80)
    print(f"Game ID: {game_id}")
    print(f"Input:   data/{season}/shifts/{game_id}_home.json")
    print(f"         data/{season}/shifts/{game_id}_away.json")
    print(f"         data/{season}/plays/{game_id}.json")

    json_output = DATA_DIR / season / "generated" / "timelines" / "json" / f"{game_id}.json"
    csv_output = DATA_DIR / season / "generated" / "timelines" / "csv" / f"{game_id}.csv"

    print(f"Output:  {json_output}")
    print(f"         {csv_output}")
    print("=" * 80)

    try:
        # Generate timeline
        print("\nProcessing shifts...", end=" ", flush=True)
        game_info, timeline = generate_timeline(season, game_id)
        print(f"✓ {len(timeline)} seconds generated")

        # Validate
        if validate:
            print("Validating TOI...", end=" ", flush=True)
            home_shifts = load_shifts(season, game_id, 'home')
            away_shifts = load_shifts(season, game_id, 'away')
            boxscore = load_boxscore(season, game_id)
            player_mapping = build_player_mapping(boxscore)
            goalie_ids = get_goalie_ids(boxscore)

            success, errors = validate_toi(timeline, home_shifts, away_shifts,
                                           player_mapping, goalie_ids)

            if success:
                # Count unique players
                all_players = set()
                for entry in timeline:
                    all_players.update(entry['home']['skaters'])
                    all_players.update(entry['away']['skaters'])
                    if entry['home']['goalie']:
                        all_players.add(entry['home']['goalie'])
                    if entry['away']['goalie']:
                        all_players.add(entry['away']['goalie'])

                print(f"✓ {len(all_players)} players match")
            else:
                print(f"✗ MISMATCH")
                print("\nTOI Validation Errors:")
                for error in errors:
                    print(error)
                return False

        # Write output
        print("Writing output...", end=" ", flush=True)
        write_json_output(game_info, timeline, json_output)
        write_csv_output(game_info, timeline, csv_output)
        print("✓")

        print("\nComplete!")
        return True

    except FileNotFoundError as e:
        print(f"\n✗ File not found: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python v2/timelines/generate_timeline.py <game_num> <season>")
        print("  python v2/timelines/generate_timeline.py <start> <end> <season>")
        print("\nExamples:")
        print("  python v2/timelines/generate_timeline.py 591 2025")
        print("  python v2/timelines/generate_timeline.py 1 100 2025")
        sys.exit(1)

    if len(sys.argv) == 3:
        # Single game mode
        game_num = int(sys.argv[1])
        season = sys.argv[2]
        success = process_game(game_num, season)
        sys.exit(0 if success else 1)
    else:
        # Batch mode
        start = int(sys.argv[1])
        end = int(sys.argv[2])
        season = sys.argv[3]

        succeeded = 0
        failed = 0

        for game_num in range(start, end + 1):
            try:
                if process_game(game_num, season):
                    succeeded += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"Error processing game {game_num}: {e}")
                failed += 1

        print("\n" + "=" * 80)
        print(f"Batch complete: {succeeded} succeeded, {failed} failed")
        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
