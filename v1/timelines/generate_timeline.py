#!/usr/bin/env python3
"""
NHL Situation Timeline Generator

Creates a timeline of situationCode changes for a game by:
1. Processing play-by-play events
2. Tracking penalties and their expirations
3. Calculating situationCode changes based on active penalties
4. Inserting synthetic penalty expiration events

Usage:
    python generate_timeline.py GAME_ID SEASON

Example:
    python generate_timeline.py 591 2025
    
This will:
- Read: ../2025/plays/2025020591.json
- Output: timelines/timeline_2025020591.json
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================
GAME_TYPE = "02"  # Regular season


# ============================================================================
# TIME CONVERSION FUNCTIONS
# ============================================================================

def time_to_seconds(time_str: str) -> int:
    """Convert MM:SS format to total seconds."""
    if not time_str or time_str == "00:00":
        return 0
    parts = time_str.split(":")
    minutes = int(parts[0])
    seconds = int(parts[1])
    return minutes * 60 + seconds


def seconds_to_time(seconds: int) -> str:
    """Convert total seconds to MM:SS format."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def calculate_game_seconds(period: int, seconds_into_period: int) -> int:
    """Calculate total seconds elapsed in game."""
    # Each regulation period is 1200 seconds (20 minutes)
    return (period - 1) * 1200 + seconds_into_period


def game_seconds_to_period_time(game_seconds: int) -> Tuple[int, int]:
    """Convert game seconds back to period number and seconds into period."""
    period = (game_seconds // 1200) + 1
    seconds_into_period = game_seconds % 1200
    return period, seconds_into_period


# ============================================================================
# SITUATION CODE CALCULATION
# ============================================================================

def calculate_situation_code(home_penalties: int, away_penalties: int,
                              home_goalie: bool = True, away_goalie: bool = True) -> str:
    """
    Calculate situationCode based on active penalties.
    
    Format: [Away Goalie][Away Skaters][Home Skaters][Home Goalie]
    
    CRITICAL: AWAY COMES FIRST IN THE FORMAT!
    - 1541 = AWAY has power play (away=5, home=4)
    - 1451 = HOME has power play (away=4, home=5)
    
    Args:
        home_penalties: Number of penalties against home team
        away_penalties: Number of penalties against away team  
        home_goalie: Whether home goalie is in net
        away_goalie: Whether away goalie is in net
    
    Returns:
        Four-digit situationCode string (e.g., "1551", "1451")
    """
    # Team with MORE penalties = FEWER skaters
    home_skaters = 5 - home_penalties
    away_skaters = 5 - away_penalties
    
    # Minimum 3 skaters on ice
    home_skaters = max(3, home_skaters)
    away_skaters = max(3, away_skaters)
    
    # Goalie status (1 = in net, 0 = pulled)
    h_goalie = 1 if home_goalie else 0
    a_goalie = 1 if away_goalie else 0
    
    # FORMAT: [Away Goalie][Away Skaters][Home Skaters][Home Goalie]
    return f"{a_goalie}{away_skaters}{home_skaters}{h_goalie}"
    
    # Goalie status (1 = in net, 0 = pulled)
    h_goalie = 1 if home_goalie else 0
    a_goalie = 1 if away_goalie else 0
    
    return f"{h_goalie}{home_skaters}{away_skaters}{a_goalie}"


# ============================================================================
# PENALTY TRACKING
# ============================================================================

class PenaltyTracker:
    """Tracks active penalties and calculates situationCode."""
    
    def __init__(self, home_team_id: int, away_team_id: int):
        self.home_team_id = home_team_id
        self.away_team_id = away_team_id
        self.active_penalties = []
        
    def add_penalty(self, event_id: int, team_id: int, player_id: int,
                    start_time: int, duration: int, desc: str, severity: str):
        """Add a penalty to tracking."""
        # Skip misconducts - they don't affect on-ice strength
        if severity == "MIS":
            return
        
        # Convert duration from minutes to seconds
        duration_seconds = duration * 60
        
        # Calculate expiration time
        expires_at = start_time + duration_seconds
        
        penalty = {
            'eventId': event_id,
            'teamId': team_id,
            'playerId': player_id,
            'startTime': start_time,
            'expiresAt': expires_at,
            'duration': duration,  # Store in minutes for output
            'durationSeconds': duration_seconds,
            'desc': desc,
            'severity': severity,
            'active': True
        }
        
        self.active_penalties.append(penalty)
    
    def remove_penalty_on_goal(self, scoring_team_id: int, goal_time: int):
        """
        Remove a penalty when a goal is scored during power play.
        Only removes minor penalties, not majors.
        Removes the penalty that would expire soonest.
        """
        # Find which team is shorthanded (the team that DIDN'T score)
        if scoring_team_id == self.home_team_id:
            # Home team scored, remove an away team penalty
            shorthanded_team = self.away_team_id
        else:
            # Away team scored, remove a home team penalty
            shorthanded_team = self.home_team_id
        
        # Find active minor penalties for the shorthanded team
        eligible_penalties = [
            p for p in self.active_penalties
            if p['active'] 
            and p['teamId'] == shorthanded_team
            and p['severity'] == 'MIN'
            and p['expiresAt'] > goal_time
        ]
        
        if eligible_penalties:
            # Remove the one that would expire soonest
            earliest = min(eligible_penalties, key=lambda p: p['expiresAt'])
            earliest['active'] = False
    
    def expire_penalties(self, current_time: int) -> List[Dict]:
        """
        Check for penalties that have expired and return them.
        Marks them as inactive and ensures each penalty only expires once.
        """
        expired = []
        for penalty in self.active_penalties:
            if penalty['active'] and penalty['expiresAt'] <= current_time:
                penalty['active'] = False
                # Only add to expired list if not already added
                if not penalty.get('expiration_logged', False):
                    penalty['expiration_logged'] = True
                    expired.append(penalty)
        return expired
    
    def get_active_penalty_counts(self) -> Tuple[int, int]:
        """
        Get count of active penalties for each team.
        
        Since coincidentals are already filtered out when penalties are added,
        we just count the active penalties for each team.
        
        Returns:
            (home_penalties, away_penalties)
        """
        home_count = sum(1 for p in self.active_penalties 
                        if p['active'] and p['teamId'] == self.home_team_id)
        away_count = sum(1 for p in self.active_penalties 
                        if p['active'] and p['teamId'] == self.away_team_id)
        
        return home_count, away_count
    
    def get_current_situation_code(self) -> str:
        """Calculate current situationCode based on active penalties."""
        home_penalties, away_penalties = self.get_active_penalty_counts()
        return calculate_situation_code(home_penalties, away_penalties)


# ============================================================================
# TIMELINE GENERATION
# ============================================================================

def process_penalties_at_time(plays: List[Dict], index: int, tracker: PenaltyTracker,
                               current_time: int, home_team_id: int, away_team_id: int) -> List[Dict]:
    """
    Process all penalties that occur at the same time as the current event.
    
    Applies NHL Rules 19.1 and 19.5 for coincidental penalties:
    - Rule 19.1: When exactly 1 minor vs 1 minor (no other penalties), both are served (4v4)
    - Rule 19.5: Otherwise, cancel majors first, then minors
    
    Returns list of net penalties added after coincidental cancellation.
    """
    current_event = plays[index]
    current_time_str = current_event.get('timeInPeriod')
    
    # Collect all penalties at this time, including misconducts
    all_penalties = []
    for i in range(index, len(plays)):
        event = plays[i]
        
        # Stop if we've moved past this time
        if event.get('timeInPeriod') != current_time_str:
            break
        
        if event.get('typeDescKey') == 'penalty':
            details = event.get('details', {})
            
            penalty_info = {
                'eventId': event.get('eventId'),
                'teamId': details.get('eventOwnerTeamId'),
                'playerId': details.get('committedByPlayerId'),
                'duration': details.get('duration', 0),
                'desc': details.get('descKey', ''),
                'typeCode': details.get('typeCode', '')
            }
            all_penalties.append(penalty_info)
    
    if not all_penalties:
        return []
    
    # Separate penalties by team and type
    home_minors = []
    home_majors = []
    home_misconducts = []
    
    away_minors = []
    away_majors = []
    away_misconducts = []
    
    for penalty in all_penalties:
        is_home = penalty['teamId'] == home_team_id
        
        if penalty['typeCode'] == 'MIN':
            if is_home:
                home_minors.append(penalty)
            else:
                away_minors.append(penalty)
        elif penalty['typeCode'] == 'MAJ':
            if is_home:
                home_majors.append(penalty)
            else:
                away_majors.append(penalty)
        elif penalty['typeCode'] == 'MIS':
            # Misconducts don't affect on-ice strength but must be tracked
            if is_home:
                home_misconducts.append(penalty)
            else:
                away_misconducts.append(penalty)
    
    # Check Rule 19.1: Exactly 1 minor vs 1 minor (no majors, no other penalties on clock)
    # TODO: We'd need to check if there are other penalties on the clock
    # For now, we'll apply this when 1 minor vs 1 minor and no majors
    if (len(home_minors) == 1 and len(away_minors) == 1 and 
        len(home_majors) == 0 and len(away_majors) == 0):
        # Rule 19.1: Both minors are served (4v4)
        # Don't cancel, track both
        penalties_to_track = home_minors + away_minors
    else:
        # Rule 19.5: Normal coincidental cancellation
        
        # Cancel majors first
        major_coincidental = min(len(home_majors), len(away_majors))
        net_home_majors = home_majors[major_coincidental:]
        net_away_majors = away_majors[major_coincidental:]
        
        # Cancel minors second
        minor_coincidental = min(len(home_minors), len(away_minors))
        net_home_minors = home_minors[minor_coincidental:]
        net_away_minors = away_minors[minor_coincidental:]
        
        # Track remaining penalties after cancellation
        penalties_to_track = net_home_majors + net_away_majors + net_home_minors + net_away_minors
    
    # Always track misconducts (but they don't affect on-ice strength)
    # We'll need to flag these somehow when adding to tracker
    penalties_to_track.extend(home_misconducts + away_misconducts)
    
    # Group by player and combine consecutive penalties on same player
    from collections import defaultdict
    penalties_by_player = defaultdict(lambda: {'eventId': None, 'teamId': None, 'playerId': None, 
                                                'totalDuration': 0, 'penalties': []})
    
    for penalty in penalties_to_track:
        player_id = penalty['playerId']
        if penalties_by_player[player_id]['eventId'] is None:
            penalties_by_player[player_id]['eventId'] = penalty['eventId']
            penalties_by_player[player_id]['teamId'] = penalty['teamId']
            penalties_by_player[player_id]['playerId'] = player_id
        
        penalties_by_player[player_id]['totalDuration'] += penalty['duration']
        penalties_by_player[player_id]['penalties'].append(penalty)
    
    # Add to tracker
    net_penalties = []
    for player_id, combined in penalties_by_player.items():
        if combined['eventId'] is None:
            continue
            
        # Build description
        first_penalty = combined['penalties'][0]
        desc = first_penalty['desc']
        if len(combined['penalties']) > 1:
            desc = f"{len(combined['penalties'])}x {desc}"
        
        # Add to tracker
        tracker.add_penalty(
            combined['eventId'],
            combined['teamId'],
            player_id,
            current_time,
            combined['totalDuration'],
            desc,
            first_penalty['typeCode']
        )
        
        net_penalties.append({
            'eventId': combined['eventId'],
            'teamId': combined['teamId'],
            'desc': desc,
            'duration': combined['totalDuration']
        })
    
    return net_penalties


def generate_timeline(plays_data: Dict) -> Dict:
    """
    Generate situation timeline from play-by-play data.
    
    Args:
        plays_data: Full play-by-play JSON data
    
    Returns:
        Timeline data structure
    """
    # Extract game info
    game_id = plays_data['id']
    season = plays_data['season']
    game_type = plays_data['gameType']
    home_team = {
        'id': plays_data['homeTeam']['id'],
        'abbrev': plays_data['homeTeam']['abbrev']
    }
    away_team = {
        'id': plays_data['awayTeam']['id'],
        'abbrev': plays_data['awayTeam']['abbrev']
    }
    
    # Initialize penalty tracker
    tracker = PenaltyTracker(home_team['id'], away_team['id'])
    
    # Process plays
    plays = plays_data['plays']
    timeline = []
    previous_situation = None
    
    # Track delayed penalty sequence
    in_delayed_penalty_sequence = False
    delayed_penalty_logged = False
    
    # Track which timestamps we've already processed penalties for
    processed_penalty_timestamps = set()
    
    i = 0
    while i < len(plays):
        event = plays[i]
        
        # Extract event details
        event_id = event.get('eventId')
        event_type = event.get('typeDescKey', '')
        period_desc = event['periodDescriptor']
        period_number = period_desc['number']
        period_type = period_desc['periodType']
        max_reg_periods = period_desc['maxRegulationPeriods']
        time_in_period = event.get('timeInPeriod', '00:00')
        time_remaining = event.get('timeRemaining', '20:00')
        current_situation = event.get('situationCode')
        
        # Calculate time values
        seconds_into_period = time_to_seconds(time_in_period)
        seconds_elapsed_game = calculate_game_seconds(period_number, seconds_into_period)
        
        # Handle delayed penalty sequences
        if event_type == 'delayed-penalty':
            in_delayed_penalty_sequence = True
            delayed_penalty_logged = False
        
        # During delayed penalty sequence, skip intermediate events
        if in_delayed_penalty_sequence:
            # Log the delayed penalty itself
            if event_type == 'delayed-penalty' and not delayed_penalty_logged:
                timeline_event = {
                    'eventId': event_id,
                    'eventType': event_type,
                    'periodNumber': period_number,
                    'periodType': period_type,
                    'maxRegulationPeriods': max_reg_periods,
                    'timeInPeriod': time_in_period,
                    'timeRemaining': time_remaining,
                    'secondsIntoPeriod': seconds_into_period,
                    'secondsElapsedGame': seconds_elapsed_game,
                    'situationCode_before': previous_situation,
                    'situationCode_after': current_situation,
                    'isSynthetic': False,
                    'isDelayedPenalty': True,
                    'penaltyExpiration': None
                }
                timeline.append(timeline_event)
                delayed_penalty_logged = True
                i += 1
                continue
            
            # Log the penalty that was called
            elif event_type == 'penalty':
                # Process penalties (only if we haven't already processed this timestamp)
                timestamp_key = f"{period_number}_{time_in_period}"
                if timestamp_key not in processed_penalty_timestamps:
                    processed_penalty_timestamps.add(timestamp_key)
                    penalties = process_penalties_at_time(plays, i, tracker, seconds_elapsed_game, 
                                                           home_team['id'], away_team['id'])
                
                # Note: We don't log penalty events themselves, only the resulting faceoff
                i += 1
                continue
            
            # Skip stoppage after penalty
            elif event_type == 'stoppage':
                i += 1
                continue
            
            # Log the faceoff and end sequence
            elif event_type == 'faceoff':
                timeline_event = {
                    'eventId': event_id,
                    'eventType': event_type,
                    'periodNumber': period_number,
                    'periodType': period_type,
                    'maxRegulationPeriods': max_reg_periods,
                    'timeInPeriod': time_in_period,
                    'timeRemaining': time_remaining,
                    'secondsIntoPeriod': seconds_into_period,
                    'secondsElapsedGame': seconds_elapsed_game,
                    'situationCode_before': previous_situation,
                    'situationCode_after': current_situation,
                    'isSynthetic': False,
                    'isDelayedPenalty': False,
                    'penaltyExpiration': None
                }
                timeline.append(timeline_event)
                previous_situation = current_situation
                
                in_delayed_penalty_sequence = False
                i += 1
                continue
            
            # Skip all other events during delayed penalty sequence
            else:
                i += 1
                continue
        
        # Regular event processing (not in delayed penalty sequence)
        # Check for expired penalties BEFORE processing this event
        expired_penalties = tracker.expire_penalties(seconds_elapsed_game)
        
        # Insert synthetic expiration events
        for penalty in expired_penalties:
            exp_period, exp_seconds = game_seconds_to_period_time(penalty['expiresAt'])
            exp_time_in_period = seconds_to_time(exp_seconds)
            exp_time_remaining = seconds_to_time(1200 - exp_seconds)
            
            # Calculate what situation should be after this penalty expires
            situation_after_expiration = tracker.get_current_situation_code()
            
            # Always log penalty expirations (even if situationCode doesn't change due to multiple penalties)
            timeline_event = {
                'eventId': None,
                'eventType': 'penalty-expired',
                'periodNumber': exp_period,
                'periodType': period_type,
                'maxRegulationPeriods': max_reg_periods,
                'timeInPeriod': exp_time_in_period,
                'timeRemaining': exp_time_remaining,
                'secondsIntoPeriod': exp_seconds,
                'secondsElapsedGame': penalty['expiresAt'],
                'situationCode_before': previous_situation,
                'situationCode_after': situation_after_expiration,
                'isSynthetic': True,
                'isDelayedPenalty': False,
                'penaltyExpiration': {
                    'originalEventId': penalty['eventId'],
                    'penaltyDesc': penalty['desc'],
                    'penaltyDuration': penalty['duration'],
                    'teamId': penalty['teamId']
                }
            }
            timeline.append(timeline_event)
            previous_situation = situation_after_expiration
        
        # Process current event
        
        # Handle penalties (for tracking purposes, even if not logged)
        if event_type == 'penalty':
            timestamp_key = f"{period_number}_{time_in_period}"
            if timestamp_key not in processed_penalty_timestamps:
                processed_penalty_timestamps.add(timestamp_key)
                penalties = process_penalties_at_time(plays, i, tracker, seconds_elapsed_game, 
                                                       home_team['id'], away_team['id'])
        
        # Handle goals during power play (for penalty tracking)
        if event_type == 'goal':
            details = event.get('details', {})
            scoring_team_id = details.get('eventOwnerTeamId')
            tracker.remove_penalty_on_goal(scoring_team_id, seconds_elapsed_game)
        
        # Only log specific event types
        loggable_events = ['period-start', 'period-end', 'faceoff']
        
        if event_type in loggable_events:
            timeline_event = {
                'eventId': event_id,
                'eventType': event_type,
                'periodNumber': period_number,
                'periodType': period_type,
                'maxRegulationPeriods': max_reg_periods,
                'timeInPeriod': time_in_period,
                'timeRemaining': time_remaining,
                'secondsIntoPeriod': seconds_into_period,
                'secondsElapsedGame': seconds_elapsed_game,
                'situationCode_before': previous_situation,
                'situationCode_after': current_situation,
                'isSynthetic': False,
                'isDelayedPenalty': False,
                'penaltyExpiration': None
            }
            timeline.append(timeline_event)
            previous_situation = current_situation
        
        i += 1
    
    # Build final output
    return {
        'gameId': game_id,
        'season': season,
        'gameType': game_type,
        'homeTeam': home_team,
        'awayTeam': away_team,
        'situationTimeline': timeline
    }


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main execution function."""
    # Validate arguments
    if len(sys.argv) != 3:
        print("Error: Invalid number of arguments")
        print(f"Usage: python {sys.argv[0]} GAME_NUMBER SEASON")
        print(f"Example: python {sys.argv[0]} 591 2025")
        sys.exit(1)
    
    game_number = sys.argv[1]
    season = sys.argv[2]
    
    # Construct paths
    game_id = f"{season}{GAME_TYPE}{int(game_number):04d}"
    
    # Script is in timelines/ folder, parent is project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Input from season folder at project root
    input_file = project_root / season / "plays" / f"{game_id}.json"
    
    # Output to timelines/output/SEASON/ subdirectory
    output_dir = script_dir / "output" / season
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"timeline_{game_id}.json"
    
    print(f"\nNHL Situation Timeline Generator")
    print(f"{'='*80}")
    print(f"Game ID: {game_id}")
    print(f"Input:   {input_file}")
    print(f"Output:  {output_file}")
    print(f"{'='*80}\n")
    
    # Check if input file exists
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    # Load play-by-play data
    print(f"Loading play-by-play data...")
    with open(input_file, 'r') as f:
        plays_data = json.load(f)
    print(f"✓ Loaded {len(plays_data['plays'])} play events")
    
    # Generate timeline
    print(f"Generating situation timeline...")
    timeline_data = generate_timeline(plays_data)
    print(f"✓ Generated timeline with {len(timeline_data['situationTimeline'])} entries")
    
    # Count synthetic events
    synthetic_count = sum(1 for e in timeline_data['situationTimeline'] if e['isSynthetic'])
    print(f"  - {synthetic_count} synthetic penalty expiration events")
    print(f"  - {len(timeline_data['situationTimeline']) - synthetic_count} real events")
    
    # Write output
    print(f"Writing timeline to file...")
    with open(output_file, 'w') as f:
        json.dump(timeline_data, f, indent=2)
    print(f"✓ Timeline saved to {output_file}")
    
    print(f"\n{'='*80}")
    print(f"Complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
