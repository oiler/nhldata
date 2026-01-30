#!/usr/bin/env python3
"""
NHL On-Ice Shifts Processor

Processes NHL shift data to create a second-by-second timeline showing
which players and goaltenders are on the ice for each team.

Usage:
    python process_shifts.py GAME_NUMBER SEASON

Example:
    python process_shifts.py 631 2025
    
This will:
- Read: ../2025/shifts/2025020631.json
- Output JSON: output/json/2025020631.json
- Output CSV: output/csv/2025020631.csv
"""

import sys
import json
import csv
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


# ============================================================================
# CONFIGURATION
# ============================================================================
GAME_TYPE = "02"  # Regular season
PERIOD_LENGTH_REGULATION = 1200  # 20 minutes in seconds
PERIOD_LENGTH_OT_REGULAR = 300   # 5 minutes in seconds
PERIOD_LENGTH_OT_PLAYOFF = 1200  # 20 minutes in seconds


# ============================================================================
# TIME CONVERSION FUNCTIONS
# ============================================================================

def time_to_seconds(time_str: str) -> int:
    """
    Convert MM:SS format to total seconds.
    
    Args:
        time_str: Time in MM:SS format (e.g., "02:30")
    
    Returns:
        Total seconds (e.g., 150)
    """
    if not time_str:
        return 0
    parts = time_str.split(":")
    minutes = int(parts[0])
    seconds = int(parts[1])
    return minutes * 60 + seconds


def calculate_game_seconds(period: int, seconds_into_period: int) -> int:
    """
    Calculate total seconds elapsed in game.
    
    Each period has 1201 data points (seconds 0-1200).
    
    Args:
        period: Period number (1, 2, 3, 4)
        seconds_into_period: Seconds elapsed in current period
    
    Returns:
        Total seconds elapsed since start of game
    """
    if period <= 3:
        # Each regulation period has 1201 data points (0-1200)
        return (period - 1) * (PERIOD_LENGTH_REGULATION + 1) + seconds_into_period
    elif period == 4:
        # 3 regulation periods + OT period
        return 3 * (PERIOD_LENGTH_REGULATION + 1) + seconds_into_period
    else:
        # Playoff OT (periods 5+)
        return (3 * (PERIOD_LENGTH_REGULATION + 1) + 
                (PERIOD_LENGTH_OT_REGULAR + 1) + 
                (period - 5) * (PERIOD_LENGTH_REGULATION + 1) + 
                seconds_into_period)


# ============================================================================
# GOALTENDER DETECTION
# ============================================================================

def identify_starting_goaltenders(shifts: List[Dict], team_ids: List[int]) -> Dict[int, int]:
    """
    Identify the starting goaltender for each team.
    
    Strategy:
    1. Find all players who start at period 1, time 00:00
    2. For each team, calculate total duration in period 1
    3. Player with duration closest to 20:00 (1200 seconds) is the goaltender
    
    Args:
        shifts: List of all shift dictionaries
        team_ids: List of team IDs in the game
    
    Returns:
        Dict mapping teamId -> playerId of starting goaltender
    """
    starting_goaltenders = {}
    
    for team_id in team_ids:
        # Find all players on this team who start at period 1, time 00:00
        period_1_starters = []
        
        for shift in shifts:
            if (shift['teamId'] == team_id and 
                shift['period'] == 1 and 
                shift['startTime'] == '00:00' and
                shift['detailCode'] == 0):
                period_1_starters.append(shift['playerId'])
        
        # Get unique players
        unique_starters = set(period_1_starters)
        
        # Calculate total duration in period 1 for each starter
        player_durations = defaultdict(int)
        
        for shift in shifts:
            if (shift['teamId'] == team_id and 
                shift['period'] == 1 and
                shift['playerId'] in unique_starters and
                shift['detailCode'] == 0):
                duration_seconds = time_to_seconds(shift['duration'])
                player_durations[shift['playerId']] += duration_seconds
        
        # Player with duration closest to 1200 seconds (20:00) is the goaltender
        if player_durations:
            goaltender_id = max(player_durations.items(), 
                                key=lambda x: x[1])[0]  # Player with most time
            starting_goaltenders[team_id] = goaltender_id
    
    return starting_goaltenders


def detect_goaltender_changes(shifts: List[Dict], team_id: int, 
                               starting_goaltender: int) -> Dict[int, int]:
    """
    Detect if/when a goaltender is replaced.
    
    Returns a mapping of period -> goaltender playerId for that period.
    
    Args:
        shifts: List of all shift dictionaries
        team_id: Team ID to analyze
        starting_goaltender: PlayerId of starting goaltender
    
    Returns:
        Dict mapping period number -> playerId of goaltender in that period
    """
    # Start with assumption that starting goaltender plays all periods
    period_goaltenders = {1: starting_goaltender, 2: starting_goaltender, 
                          3: starting_goaltender, 4: starting_goaltender}
    
    # Get all shifts for this team
    team_shifts = [s for s in shifts if s['teamId'] == team_id and s['detailCode'] == 0]
    
    # Check each period for potential goaltender changes
    for period in [2, 3, 4]:
        # Find players who start at 00:00 of this period
        period_starters = []
        for shift in team_shifts:
            if shift['period'] == period and shift['startTime'] == '00:00':
                period_starters.append({
                    'playerId': shift['playerId'],
                    'duration': time_to_seconds(shift['duration'])
                })
        
        # If we find a new player (not the starting goaltender) with a long shift (>120 seconds)
        # at the start of a period, they're likely the new goaltender
        for starter in period_starters:
            if starter['playerId'] != starting_goaltender and starter['duration'] > 120:
                period_goaltenders[period] = starter['playerId']
                # Update subsequent periods too
                for p in range(period + 1, 5):
                    period_goaltenders[p] = starter['playerId']
                break
    
    return period_goaltenders


# ============================================================================
# SHIFT PROCESSING
# ============================================================================

def build_player_timeline(shifts: List[Dict]) -> Dict[int, Dict[int, Set[int]]]:
    """
    Build a timeline of which players are on ice at each second.
    
    Special handling for second 0 of EACH period:
    - ONLY include players with startTime="00:00" (the period starters)
    - Do NOT apply regular range logic for second 0
    
    For all other seconds (1-1200 per period):
    - Players are on ice from startTime+1 through endTime (inclusive)
    - This prevents overlaps during on-the-fly changes
    - Since we use startTime+1, a shift ending at 20:00 (1200) is safe
      (would start at second 1 of next period, which is handled separately)
    
    Args:
        shifts: List of shift dictionaries (already filtered for detailCode=0)
    
    Returns:
        Dict mapping game_second -> teamId -> set of playerIds on ice
    """
    # Structure: {game_second: {teamId: {playerId, playerId, ...}}}
    timeline = defaultdict(lambda: defaultdict(set))
    
    # First pass: Add period starters at second 0 of each period
    for shift in shifts:
        team_id = shift['teamId']
        player_id = shift['playerId']
        period = shift['period']
        
        # Skip shootout (period 5)
        if period == 5:
            continue
        
        start_seconds = time_to_seconds(shift['startTime'])
        
        # Add period starters to second 0
        if start_seconds == 0:
            game_second_0 = calculate_game_seconds(period, 0)
            timeline[game_second_0][team_id].add(player_id)
    
    # Second pass: Add regular shifts (startTime+1 through endTime)
    for shift in shifts:
        team_id = shift['teamId']
        player_id = shift['playerId']
        period = shift['period']
        
        # Skip shootout (period 5)
        if period == 5:
            continue
        
        start_seconds = time_to_seconds(shift['startTime'])
        end_seconds = time_to_seconds(shift['endTime'])
        
        # Determine period max (second 1200 is the LAST second of a 20-minute period)
        if period <= 3:
            period_max = PERIOD_LENGTH_REGULATION  # 1200 (00:00 through 20:00)
        elif period == 4:
            period_max = PERIOD_LENGTH_OT_REGULAR  # 300 (00:00 through 05:00)
        else:
            period_max = PERIOD_LENGTH_REGULATION  # Default
        
        # Cap at period max
        end_seconds = min(end_seconds, period_max)
        
        # Regular handling: player on ice from startTime+1 through endTime (inclusive)
        for seconds_into_period in range(start_seconds + 1, end_seconds + 1):
            game_second = calculate_game_seconds(period, seconds_into_period)
            timeline[game_second][team_id].add(player_id)
    
    return timeline


def build_goaltender_timeline(shifts: List[Dict], team_ids: List[int]) -> Dict[int, Dict[int, Optional[int]]]:
    """
    Build a timeline of which goaltender is on ice for each team at each second.
    
    Special handling for second 0 of EACH period:
    - ONLY include goaltenders with startTime="00:00"
    - Do NOT apply regular range logic for second 0
    
    For all other seconds (1-1199 per period):
    - Goaltenders are on ice from startTime+1 through endTime (inclusive)
    
    Args:
        shifts: List of shift dictionaries
        team_ids: List of team IDs
    
    Returns:
        Dict mapping game_second -> teamId -> playerId (or None if no goaltender)
    """
    # Identify starting goaltenders
    starting_goaltenders = identify_starting_goaltenders(shifts, team_ids)
    
    # Detect any goaltender changes
    goaltender_by_period = {}
    for team_id in team_ids:
        if team_id in starting_goaltenders:
            goaltender_by_period[team_id] = detect_goaltender_changes(
                shifts, team_id, starting_goaltenders[team_id]
            )
    
    # Build timeline
    timeline = defaultdict(lambda: defaultdict(lambda: None))
    
    for team_id in team_ids:
        if team_id not in starting_goaltenders:
            continue
        
        # Get all shifts for goaltenders on this team
        goaltender_ids = set(goaltender_by_period[team_id].values())
        
        # First pass: Add period starters at second 0
        for shift in shifts:
            if (shift['teamId'] == team_id and 
                shift['playerId'] in goaltender_ids and
                shift['detailCode'] == 0):
                
                period = shift['period']
                if period == 5:  # Skip shootout
                    continue
                
                start_seconds = time_to_seconds(shift['startTime'])
                
                # Add goaltender to second 0 if they start the period
                if start_seconds == 0:
                    game_second_0 = calculate_game_seconds(period, 0)
                    timeline[game_second_0][team_id] = shift['playerId']
        
        # Second pass: Add regular shifts (startTime+1 through endTime)
        for shift in shifts:
            if (shift['teamId'] == team_id and 
                shift['playerId'] in goaltender_ids and
                shift['detailCode'] == 0):
                
                period = shift['period']
                if period == 5:  # Skip shootout
                    continue
                
                start_seconds = time_to_seconds(shift['startTime'])
                end_seconds = time_to_seconds(shift['endTime'])
                
                # Determine period max (second 1200 is the LAST second of a 20-minute period)
                if period <= 3:
                    period_max = PERIOD_LENGTH_REGULATION  # 1200
                elif period == 4:
                    period_max = PERIOD_LENGTH_OT_REGULAR  # 300
                else:
                    period_max = PERIOD_LENGTH_REGULATION  # Default
                
                # Cap at period max
                end_seconds = min(end_seconds, period_max)
                
                # Regular handling: goaltender on ice from startTime+1 through endTime (inclusive)
                for seconds_into_period in range(start_seconds + 1, end_seconds + 1):
                    game_second = calculate_game_seconds(period, seconds_into_period)
                    timeline[game_second][team_id] = shift['playerId']
    
    return timeline


# ============================================================================
# TIMELINE GENERATION
# ============================================================================

def generate_timeline(shifts_data: Dict) -> Tuple[List[Dict], List[int]]:
    """
    Generate the complete second-by-second timeline.
    
    Processes each period separately to avoid boundary issues.
    Each period has seconds 0-1200 (regulation) or 0-300 (OT).
    
    Args:
        shifts_data: Raw shift data from JSON file
    
    Returns:
        Tuple of (timeline list, sorted team_ids list)
    """
    # Filter shifts to only regular shifts (detailCode = 0)
    shifts = [s for s in shifts_data['data'] if s.get('detailCode') == 0]
    
    # Get unique team IDs and sort them
    team_ids = sorted(set(s['teamId'] for s in shifts))
    
    # Build player timeline (skaters)
    player_timeline = build_player_timeline(shifts)
    
    # Build goaltender timeline
    goaltender_timeline = build_goaltender_timeline(shifts, team_ids)
    
    # Determine which periods were played
    max_period = max(s['period'] for s in shifts if s['period'] < 5)  # Exclude shootout
    periods_to_process = list(range(1, max_period + 1))
    
    # Build the timeline period-by-period
    timeline = []
    seconds_elapsed_game = 0
    
    for period in periods_to_process:
        # Determine period length
        if period <= 3:
            period_length = PERIOD_LENGTH_REGULATION  # 1200 seconds (20 minutes)
        elif period == 4:
            period_length = PERIOD_LENGTH_OT_REGULAR  # 300 seconds (5 minutes)
        else:
            # Playoff OT (periods 5+) - 20 minutes each
            period_length = PERIOD_LENGTH_REGULATION
        
        # Generate seconds 0 through period_length for this period
        for seconds_into_period in range(0, period_length + 1):
            # Build skaters data for this second
            skaters_data = {}
            
            game_second = calculate_game_seconds(period, seconds_into_period)
            
            for team_id in team_ids:
                # Get players on ice (excluding goaltenders)
                players_on_ice = list(player_timeline[game_second][team_id])
                
                # Get goaltender
                goaltender_id = goaltender_timeline[game_second][team_id]
                
                # Remove goaltender from skaters list if present
                if goaltender_id and goaltender_id in players_on_ice:
                    players_on_ice.remove(goaltender_id)
                
                skaters_data[str(team_id)] = {
                    'onIce': sorted(players_on_ice),
                    'count': len(players_on_ice),
                    'goaltender': goaltender_id
                }
            
            # Add entry to timeline
            entry = {
                'period': period,
                'seconds_into_period': seconds_into_period,
                'seconds_elapsed_game': seconds_elapsed_game,
                'skaters': skaters_data
            }
            
            timeline.append(entry)
            seconds_elapsed_game += 1
        
        # Period complete - ice is cleared automatically when next period starts
    
    return timeline, team_ids


def write_csv_output(timeline: List[Dict], team_ids: List[int], output_file: Path):
    """
    Write timeline to CSV format.
    
    Args:
        timeline: List of timeline entries
        team_ids: Sorted list of team IDs [teamA, teamB]
        output_file: Path to output CSV file
    """
    team_a = str(team_ids[0])
    team_b = str(team_ids[1])
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow([
            'period',
            'seconds_into_period',
            'seconds_elapsed_game',
            'teamA',
            'teamB',
            'teamAskaters',
            'teamAcount',
            'teamAgoaltender',
            'teamBskaters',
            'teamBcount',
            'teamBgoaltender'
        ])
        
        # Write data rows
        for entry in timeline:
            team_a_data = entry['skaters'][team_a]
            team_b_data = entry['skaters'][team_b]
            
            # Format skater lists as comma-separated playerIds in brackets
            team_a_skaters = '[' + ','.join(str(p) for p in team_a_data['onIce']) + ']'
            team_b_skaters = '[' + ','.join(str(p) for p in team_b_data['onIce']) + ']'
            
            writer.writerow([
                entry['period'],
                entry['seconds_into_period'],
                entry['seconds_elapsed_game'],
                team_a,
                team_b,
                team_a_skaters,
                team_a_data['count'],
                team_a_data['goaltender'] if team_a_data['goaltender'] else '',
                team_b_skaters,
                team_b_data['count'],
                team_b_data['goaltender'] if team_b_data['goaltender'] else ''
            ])



# ============================================================================
# MAIN FUNCTION
# ============================================================================

def process_single_game(game_number: str, season: str, script_dir: Path, project_root: Path) -> bool:
    """
    Process a single game.
    
    Returns:
        True if successful, False if file not found or error occurred
    """
    # Construct paths
    game_id = f"{season}{GAME_TYPE}{int(game_number):04d}"
    
    # Input from season folder at project root
    input_file = project_root / season / "shifts" / f"{game_id}.json"
    
    # Output to onice/output/json/ and onice/output/csv/
    json_output_dir = script_dir / "output" / "json"
    csv_output_dir = script_dir / "output" / "csv"
    json_output_dir.mkdir(parents=True, exist_ok=True)
    csv_output_dir.mkdir(parents=True, exist_ok=True)
    
    json_output_file = json_output_dir / f"{game_id}.json"
    csv_output_file = csv_output_dir / f"{game_id}.csv"
    
    # Check if input file exists
    if not input_file.exists():
        print(f"⚠ Skipping game {game_number}: Input file not found: {input_file}")
        return False
    
    try:
        # Load shift data
        with open(input_file, 'r') as f:
            shifts_data = json.load(f)
        
        # Filter to regular shifts only
        regular_shifts = [s for s in shifts_data['data'] if s.get('detailCode') == 0]
        
        # Generate timeline
        timeline, team_ids = generate_timeline(shifts_data)
        
        # Write JSON output
        with open(json_output_file, 'w') as f:
            json.dump(timeline, f, indent=2)
        
        # Write CSV output
        write_csv_output(timeline, team_ids, csv_output_file)
        
        print(f"✓ Game {game_number}: Processed {len(timeline)} seconds, Teams {team_ids[0]} vs {team_ids[1]}")
        return True
        
    except Exception as e:
        print(f"✗ Game {game_number}: Error - {str(e)}")
        return False


def main():
    """Main execution function."""
    # Validate arguments
    if len(sys.argv) not in [3, 4]:
        print("Error: Invalid number of arguments")
        print(f"Usage for single game: python {sys.argv[0]} GAME_NUMBER SEASON")
        print(f"Usage for batch: python {sys.argv[0]} START_GAME END_GAME SEASON")
        print(f"Example: python {sys.argv[0]} 631 2025")
        print(f"Example: python {sys.argv[0]} 600 631 2025")
        sys.exit(1)
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Determine if single game or batch processing
    if len(sys.argv) == 3:
        # Single game mode
        game_number = sys.argv[1]
        season = sys.argv[2]
        
        print(f"\nNHL On-Ice Shifts Processor")
        print(f"{'='*80}")
        print(f"Mode: Single Game")
        print(f"Game: {game_number}, Season: {season}")
        print(f"{'='*80}\n")
        
        success = process_single_game(game_number, season, script_dir, project_root)
        
        if success:
            print(f"\n{'='*80}")
            print(f"Complete!")
            print(f"{'='*80}\n")
        else:
            sys.exit(1)
    
    else:
        # Batch mode
        start_game = int(sys.argv[1])
        end_game = int(sys.argv[2])
        season = sys.argv[3]
        
        print(f"\nNHL On-Ice Shifts Processor")
        print(f"{'='*80}")
        print(f"Mode: Batch Processing")
        print(f"Games: {start_game} to {end_game} (inclusive), Season: {season}")
        print(f"{'='*80}\n")
        
        successful = 0
        skipped = 0
        errors = 0
        
        for game_num in range(start_game, end_game + 1):
            result = process_single_game(str(game_num), season, script_dir, project_root)
            if result:
                successful += 1
            else:
                if Path(project_root / season / "shifts" / f"{season}{GAME_TYPE}{game_num:04d}.json").exists():
                    errors += 1
                else:
                    skipped += 1
        
        print(f"\n{'='*80}")
        print(f"Batch Complete!")
        print(f"  Successful: {successful}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")
        print(f"  Total: {end_game - start_game + 1}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
