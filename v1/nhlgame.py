#!/usr/bin/env python3
"""
NHL Game Data Downloader

Downloads game data from NHL API endpoints for specified game ID ranges.
Uses uv for package management.

Usage:
    python nhlgame.py START_GAME_ID END_GAME_ID

Example:
    python nhlgame.py 3031 3032
    
This will download data for games 2025023031 and 2025023032
"""

import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# ============================================================================
# CONFIGURATION - Edit these values as needed
# ============================================================================
SEASON = "2025"  # Current season year
GAME_TYPE = "02"  # 01=Preseason, 02=Regular Season, 03=Playoffs, 04=All-Star
RATE_LIMIT_SECONDS = 9  # Delay between API requests

# API Endpoints
ENDPOINTS = {
    "shifts": "https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={game_id}",
    "plays": "https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play",
    "meta": "https://api-web.nhle.com/v1/gamecenter/{game_id}/landing",
    "boxscores": "https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore"
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def construct_game_id(game_number: int) -> str:
    """Construct full game ID from game number."""
    return f"{SEASON}{GAME_TYPE}{game_number:04d}"


def setup_directories(season: str) -> Dict[str, Path]:
    """Create directory structure for the season."""
    base_path = Path(season)
    paths = {}
    
    for endpoint_name in ENDPOINTS.keys():
        path = base_path / endpoint_name
        path.mkdir(parents=True, exist_ok=True)
        paths[endpoint_name] = path
    
    return paths


def load_error_log(filename: str) -> List[Dict]:
    """Load error log file or return empty list."""
    filepath = Path(filename)
    if filepath.exists():
        with open(filepath, 'r') as f:
            return json.load(f)
    return []


def save_error_log(filename: str, errors: List[Dict]):
    """Save error log to file."""
    filepath = Path(filename)
    with open(filepath, 'w') as f:
        json.dump(errors, indent=2, fp=f)


def log_error(error_type: str, game_id: str, endpoint_name: str, error_message: str):
    """Log an error to the appropriate error file."""
    filename = "nogames.json" if error_type == "404" else "errors.json"
    errors = load_error_log(filename)
    
    error_entry = {
        "game_id": game_id,
        "endpoint": endpoint_name,
        "error": error_message,
        "timestamp": datetime.now().isoformat()
    }
    
    errors.append(error_entry)
    save_error_log(filename, errors)


def fetch_endpoint(url: str, game_id: str, endpoint_name: str) -> Tuple[bool, Dict]:
    """
    Fetch data from an API endpoint.
    
    Returns:
        Tuple of (success: bool, data: dict or None)
    """
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 404:
            log_error("404", game_id, endpoint_name, "Game not found")
            return False, None
        
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            log_error("error", game_id, endpoint_name, error_msg)
            return False, None
        
        data = response.json()
        return True, data
        
    except requests.exceptions.Timeout:
        log_error("error", game_id, endpoint_name, "Request timeout")
        return False, None
    except requests.exceptions.RequestException as e:
        log_error("error", game_id, endpoint_name, f"Request error: {str(e)}")
        return False, None
    except json.JSONDecodeError as e:
        log_error("error", game_id, endpoint_name, f"JSON decode error: {str(e)}")
        return False, None


def save_game_data(data: Dict, filepath: Path):
    """Save game data to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def download_game(game_id: str, paths: Dict[str, Path]) -> Tuple[int, int]:
    """
    Download all endpoint data for a single game.
    
    Returns:
        Tuple of (successful_downloads, failed_downloads)
    """
    print(f"\n{'='*60}")
    print(f"Processing Game ID: {game_id}")
    print(f"{'='*60}")
    
    successful = 0
    failed = 0
    
    for endpoint_name, url_template in ENDPOINTS.items():
        url = url_template.format(game_id=game_id)
        print(f"  Fetching {endpoint_name}... ", end="", flush=True)
        
        success, data = fetch_endpoint(url, game_id, endpoint_name)
        
        if success:
            filepath = paths[endpoint_name] / f"{game_id}.json"
            save_game_data(data, filepath)
            print(f"✓ Saved to {filepath}")
            successful += 1
        else:
            print("✗ Failed")
            failed += 1
        
        # Rate limiting between requests
        if endpoint_name != list(ENDPOINTS.keys())[-1]:  # Don't sleep after last endpoint
            time.sleep(RATE_LIMIT_SECONDS)
    
    return successful, failed


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main execution function."""
    # Validate command line arguments
    if len(sys.argv) != 3:
        print("Error: Invalid number of arguments")
        print(f"Usage: python {sys.argv[0]} START_GAME_ID END_GAME_ID")
        print(f"Example: python {sys.argv[0]} 3031 3032")
        sys.exit(1)
    
    try:
        start_game = int(sys.argv[1])
        end_game = int(sys.argv[2])
    except ValueError:
        print("Error: Game IDs must be integers")
        sys.exit(1)
    
    if start_game > end_game:
        print("Error: Start game ID must be less than or equal to end game ID")
        sys.exit(1)
    
    # Setup
    print(f"\nNHL Game Data Downloader")
    print(f"Season: {SEASON}")
    print(f"Game Type: {GAME_TYPE}")
    print(f"Game Range: {start_game:04d} to {end_game:04d}")
    print(f"Rate Limit: {RATE_LIMIT_SECONDS} seconds between requests")
    
    paths = setup_directories(SEASON)
    print(f"\nData will be saved to: {SEASON}/")
    
    # Download games
    total_games = end_game - start_game + 1
    total_successful = 0
    total_failed = 0
    
    for game_num in range(start_game, end_game + 1):
        game_id = construct_game_id(game_num)
        successful, failed = download_game(game_id, paths)
        total_successful += successful
        total_failed += failed
        
        # Rate limiting between games (after all endpoints for one game)
        if game_num < end_game:
            print(f"\nWaiting {RATE_LIMIT_SECONDS} seconds before next game...")
            time.sleep(RATE_LIMIT_SECONDS)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"Total games processed: {total_games}")
    print(f"Total successful downloads: {total_successful}")
    print(f"Total failed downloads: {total_failed}")
    print(f"\nError logs:")
    print(f"  - nogames.json (404 errors)")
    print(f"  - errors.json (other errors)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
