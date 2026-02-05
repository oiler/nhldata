#!/usr/bin/env python3
"""
NHL Game Data Downloader

Downloads game data from NHL sources for specified game ID ranges.
- Shifts data: Scraped from NHL HTML Time-on-Ice reports (home + away files)
- Other data: Fetched from NHL API endpoints (plays, meta, boxscores)

Uses uv for package management.
Requires: beautifulsoup4, lxml (install with: uv pip install beautifulsoup4 lxml)

Usage:
    python nhlgame.py START_GAME_ID END_GAME_ID
    python nhlgame.py today
    python nhlgame.py shifts START_GAME_ID END_GAME_ID

Examples:
    python nhlgame.py 3031 3032
        Downloads all data for games 2025023031 and 2025023032

    python nhlgame.py today
        Auto-detects last saved game and downloads all games up through yesterday
        (stops before today's first scheduled game)

    python nhlgame.py shifts 1 100
        Downloads ONLY shifts data (HTML) for games 2025020001 through 2025020100
        Use this to backfill shifts for games where you already have API data

Output:
    data/{SEASON}/shifts/{gameId}_home.json  - Home team shifts (HTML scraped)
    data/{SEASON}/shifts/{gameId}_away.json  - Away team shifts (HTML scraped)
    data/{SEASON}/plays/{gameId}.json        - Play-by-play data (API)
    data/{SEASON}/meta/{gameId}.json         - Game metadata (API)
    data/{SEASON}/boxscores/{gameId}.json    - Boxscore data (API)
"""

import sys
import json
import time
import re
import requests
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# ============================================================================
# CONFIGURATION - Edit these values as needed
# ============================================================================
SEASON = "2025"  # Current season year
GAME_TYPE = "02"  # 01=Preseason, 02=Regular Season, 03=Playoffs, 04=All-Star
RATE_LIMIT_SECONDS = 9  # Delay between API requests

# HTML Shifts Configuration
SHIFT_RATE_LIMIT_SECONDS = 5  # Delay between HTML shift requests
SHIFT_RETRY_ATTEMPTS = 5  # Number of retry attempts for shift fetches
SHIFT_RETRY_DELAY_SECONDS = 10  # Delay between retries

# API Endpoints (shifts now handled via HTML scraping)
ENDPOINTS = {
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
    base_path = Path("data") / season
    paths = {}

    # Create shifts directory (for HTML-scraped data)
    shifts_path = base_path / "shifts"
    shifts_path.mkdir(parents=True, exist_ok=True)
    paths["shifts"] = shifts_path

    # Create API endpoint directories
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


def download_game(game_id: str, paths: Dict[str, Path]) -> Tuple[int, int, bool]:
    """
    Download all endpoint data for a single game.

    Returns:
        Tuple of (successful_downloads, failed_downloads, should_stop)
        should_stop is True if a critical error occurred (shifts failed)
    """
    print(f"\n{'='*60}")
    print(f"Processing Game ID: {game_id}")
    print(f"{'='*60}")

    successful = 0
    failed = 0

    # First, download shifts via HTML scraping (critical - stops on failure)
    home_success, away_success = download_shifts(game_id, paths["shifts"])

    if not home_success or not away_success:
        # Critical failure - return immediately with stop signal
        return successful, failed + 2, True

    successful += 2  # Count both home and away shifts

    # Wait before starting API requests
    time.sleep(SHIFT_RATE_LIMIT_SECONDS)

    # Then download API endpoints
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

    return successful, failed, False


# ============================================================================
# HTML SHIFTS SCRAPING FUNCTIONS
# ============================================================================

def construct_season_id() -> str:
    """Convert SEASON to NHL season ID format (e.g., 2025 -> 20252026)."""
    year = int(SEASON)
    return f"{year}{year + 1}"


def construct_shifts_url(game_id: str, team_type: str) -> str:
    """
    Construct URL for NHL HTML shifts report.

    Args:
        game_id: Full game ID (e.g., 2025020001)
        team_type: "home" or "away"

    Returns:
        URL to the HTML shifts report
    """
    season_id = construct_season_id()
    # Report code: TH = home, TV = away (visitor)
    report_code = "TH" if team_type == "home" else "TV"
    # Game number is the last 6 digits of game_id
    game_num = game_id[4:]  # e.g., 020001 from 2025020001
    return f"https://www.nhl.com/scores/htmlreports/{season_id}/{report_code}{game_num}.HTM"


def fetch_html_with_retry(url: str, game_id: str) -> Tuple[bool, Optional[str]]:
    """
    Fetch HTML content with retry logic.

    Args:
        url: URL to fetch
        game_id: Game ID for error reporting

    Returns:
        Tuple of (success, html_content or None)
    """
    last_error = None

    for attempt in range(1, SHIFT_RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                return True, response.text

            last_error = f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            last_error = "Request timeout"
        except requests.exceptions.RequestException as e:
            last_error = f"Request error: {str(e)}"

        if attempt < SHIFT_RETRY_ATTEMPTS:
            print(f" (retry {attempt}/{SHIFT_RETRY_ATTEMPTS})...", end="", flush=True)
            time.sleep(SHIFT_RETRY_DELAY_SECONDS)

    return False, last_error


def parse_player_heading(heading_text: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Parse player number and name from heading text.

    Args:
        heading_text: Text like "2 PETRY, JEFF"

    Returns:
        Tuple of (number, name) or (None, None) if parsing fails
    """
    # Pattern: number followed by name
    match = re.match(r'(\d+)\s+(.+)', heading_text.strip())
    if match:
        return int(match.group(1)), match.group(2).strip()
    return None, None


def parse_time_value(time_str: str) -> str:
    """
    Parse time value, handling various formats.

    Args:
        time_str: Time string like "0:34 / 19:26" or "00:28"

    Returns:
        Cleaned time string in MM:SS format
    """
    if not time_str:
        return "00:00"

    # If it contains " / ", take the first part (elapsed time)
    if " / " in time_str:
        time_str = time_str.split(" / ")[0]

    time_str = time_str.strip()

    # Ensure MM:SS format
    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) == 2:
            mins = int(parts[0])
            secs = int(parts[1])
            return f"{mins:02d}:{secs:02d}"

    return time_str


def parse_period_value(period_str: str) -> int:
    """
    Parse period value, handling OT and numeric values.

    Args:
        period_str: Period string like "1", "2", "3", "OT", "2OT", etc.

    Returns:
        Period number (4 for OT, 5 for 2OT, etc.)
    """
    period_str = period_str.strip().upper()

    if period_str.isdigit():
        return int(period_str)

    if period_str == "OT":
        return 4

    # Handle 2OT, 3OT, etc.
    if period_str.endswith("OT"):
        ot_num = period_str[:-2]
        if ot_num.isdigit():
            return 3 + int(ot_num)  # 2OT = 5, 3OT = 6, etc.

    # Default to 4 for any unrecognized OT format
    if "OT" in period_str:
        return 4

    return 0  # Unknown


def parse_shifts_html(html: str, game_id: str, team_type: str, url: str) -> Optional[Dict]:
    """
    Parse HTML shifts report into structured JSON.

    Args:
        html: HTML content
        game_id: Game ID
        team_type: "home" or "away"
        url: Source URL for traceability

    Returns:
        Parsed data dictionary, or None if parsing fails
    """
    if not BS4_AVAILABLE:
        print("\nError: beautifulsoup4 is required for HTML parsing")
        print("Install with: uv pip install beautifulsoup4 lxml")
        return None

    # Try different parsers
    soup = None
    for parser in ['lxml', 'html.parser', 'html5lib']:
        try:
            soup = BeautifulSoup(html, parser)
            if soup.find_all('table'):
                break
        except Exception:
            continue

    if soup is None:
        return None

    # Extract team name from page
    team_name = ""
    team_abbrev = ""

    # Look for team heading
    team_heading = soup.find('td', class_=lambda c: c and 'teamHeading' in c)
    if team_heading:
        team_name = team_heading.get_text(strip=True)

    # Try to extract abbreviation from logo image
    logo_imgs = soup.find_all('img', alt=True)
    for img in logo_imgs:
        alt = img.get('alt', '')
        if alt and alt.upper() == team_name.upper():
            src = img.get('src', '')
            # Extract from URL like logocfla.gif
            match = re.search(r'logoc(\w+)\.gif', src)
            if match:
                team_abbrev = match.group(1).upper()
                break

    # Find all player sections
    player_headings = soup.find_all('td', class_=lambda c: c and 'playerHeading' in c)

    if not player_headings:
        return None

    players = []

    # All players are in the same table, so we need to find rows between playerHeadings
    # Get the parent table (contains all players)
    if not player_headings:
        return None

    parent_table = player_headings[0].find_parent('table')
    if not parent_table:
        return None

    all_rows = parent_table.find_all('tr')

    # Build index: find which row each playerHeading is in
    heading_row_indices = []
    for i, row in enumerate(all_rows):
        heading_cell = row.find('td', class_=lambda c: c and 'playerHeading' in c)
        if heading_cell:
            heading_row_indices.append(i)

    # Process each player section
    for idx, heading_idx in enumerate(heading_row_indices):
        # Get rows from this heading to the next (or end)
        if idx + 1 < len(heading_row_indices):
            next_heading_idx = heading_row_indices[idx + 1]
        else:
            next_heading_idx = len(all_rows)

        player_rows = all_rows[heading_idx:next_heading_idx]

        # Extract player name from first row
        heading_row = player_rows[0]
        heading_cell = heading_row.find('td', class_=lambda c: c and 'playerHeading' in c)
        if not heading_cell:
            continue

        heading_text = heading_cell.get_text(strip=True)
        number, name = parse_player_heading(heading_text)

        if number is None:
            continue

        player_data = {
            "number": number,
            "name": name,
            "shifts": [],
            "periodSummary": [],
            "gameTotals": {}
        }

        # Parse shift rows (have oddColor or evenColor class)
        # Skip rows that are inside deeply nested tables (those are period summary rows)
        # The player table is already nested 1 level deep in the layout table,
        # so shift rows have 2 parent tables, but period summary rows have 3+
        for row in player_rows:
            parent_tables = row.find_parents('table')
            if len(parent_tables) > 2:
                # This row is inside a nested table (period summary), skip it
                continue

            row_class = row.get('class', [])
            if isinstance(row_class, list):
                row_class = ' '.join(row_class)

            if 'oddColor' in row_class or 'evenColor' in row_class:
                cells = row.find_all('td')
                # Shift rows have exactly 6 cells; period summary rows have 7
                if len(cells) == 6:
                    # Check if this is a shift row (first cell is a number)
                    first_cell = cells[0].get_text(strip=True)
                    if first_cell.isdigit():
                        shift = {
                            "shiftNumber": int(first_cell),
                            "period": parse_period_value(cells[1].get_text(strip=True)),
                            "startTime": parse_time_value(cells[2].get_text(strip=True)),
                            "endTime": parse_time_value(cells[3].get_text(strip=True)),
                            "duration": parse_time_value(cells[4].get_text(strip=True)),
                            "event": cells[5].get_text(strip=True) if cells[5].get_text(strip=True) else None
                        }
                        player_data["shifts"].append(shift)

        # Find period summary table (nested table with Per, SHF, AVG, TOI headers)
        # Look for nested tables within this player's rows
        for row in player_rows:
            nested_tables = row.find_all('table')
            for nested in nested_tables:
                headers = nested.find_all('td', class_=lambda c: c and 'heading' in str(c))
                header_text = ' '.join([h.get_text(strip=True) for h in headers])

                if 'Per' in header_text and 'SHF' in header_text and 'TOI' in header_text:
                    # This is the period summary table
                    summary_rows = nested.find_all('tr')
                    for srow in summary_rows:
                        srow_class = srow.get('class', [])
                        if isinstance(srow_class, list):
                            srow_class = ' '.join(srow_class)

                        if 'oddColor' in srow_class or 'evenColor' in srow_class:
                            scells = srow.find_all('td')
                            if len(scells) >= 7:
                                per_text = scells[0].get_text(strip=True)

                                if per_text == 'TOT':
                                    # Game totals row
                                    player_data["gameTotals"] = {
                                        "shifts": int(scells[1].get_text(strip=True)),
                                        "avgDuration": scells[2].get_text(strip=True),
                                        "toi": scells[3].get_text(strip=True),
                                        "evToi": scells[4].get_text(strip=True),
                                        "ppToi": scells[5].get_text(strip=True),
                                        "shToi": scells[6].get_text(strip=True)
                                    }
                                elif per_text.isdigit() or 'OT' in per_text.upper():
                                    # Period summary row (including OT, 2OT, etc.)
                                    period_summary = {
                                        "period": parse_period_value(per_text),
                                        "shifts": int(scells[1].get_text(strip=True)),
                                        "avgDuration": scells[2].get_text(strip=True),
                                        "toi": scells[3].get_text(strip=True),
                                        "evToi": scells[4].get_text(strip=True),
                                        "ppToi": scells[5].get_text(strip=True),
                                        "shToi": scells[6].get_text(strip=True)
                                    }
                                    player_data["periodSummary"].append(period_summary)

        players.append(player_data)

    if not players:
        return None

    return {
        "gameId": game_id,
        "teamType": team_type,
        "team": {
            "abbrev": team_abbrev,
            "name": team_name
        },
        "source": {
            "url": url,
            "fetchedAt": datetime.now().isoformat()
        },
        "players": players
    }


def download_shifts(game_id: str, shifts_path: Path) -> Tuple[bool, bool]:
    """
    Download shifts data for both home and away teams via HTML scraping.

    Args:
        game_id: Full game ID
        shifts_path: Path to save shifts files

    Returns:
        Tuple of (home_success, away_success)
    """
    if not BS4_AVAILABLE:
        print("\n  Error: beautifulsoup4 required. Install with: uv pip install beautifulsoup4 lxml")
        return False, False

    results = []

    for team_type in ["home", "away"]:
        url = construct_shifts_url(game_id, team_type)
        print(f"  Fetching shifts ({team_type})... ", end="", flush=True)

        success, result = fetch_html_with_retry(url, game_id)

        if not success:
            print(f"✗ Failed after {SHIFT_RETRY_ATTEMPTS} attempts: {result}")
            print(f"\nERROR: Failed to fetch shifts data")
            print(f"  Game ID: {game_id}")
            print(f"  URL: {url}")
            print(f"  Last error: {result}")
            print(f"\nScript stopped. Fix the issue and resume from game {game_id[6:]}.")
            return (False, False) if team_type == "home" else (True, False)

        # Parse HTML
        parsed_data = parse_shifts_html(result, game_id, team_type, url)

        if parsed_data is None or not parsed_data.get("players"):
            print("✗ Failed to parse HTML (no players found)")
            print(f"\nERROR: Failed to parse shifts data")
            print(f"  Game ID: {game_id}")
            print(f"  URL: {url}")
            print(f"\nScript stopped. Fix the issue and resume from game {game_id[6:]}.")
            return (False, False) if team_type == "home" else (True, False)

        # Save to file
        filepath = shifts_path / f"{game_id}_{team_type}.json"
        save_game_data(parsed_data, filepath)
        print(f"✓ Saved to {filepath} ({len(parsed_data['players'])} players)")

        results.append(True)

        # Rate limit between home and away requests
        if team_type == "home":
            time.sleep(SHIFT_RATE_LIMIT_SECONDS)

    return tuple(results) if len(results) == 2 else (results[0] if results else False, False)


# ============================================================================
# TODAY MODE FUNCTIONS
# ============================================================================

def get_last_saved_game() -> Optional[int]:
    """
    Find the highest game number in the saved boxscores directory.

    Returns:
        The highest game number found, or None if no games exist.
    """
    boxscores_dir = Path("data") / SEASON / "boxscores"

    if not boxscores_dir.exists():
        return None

    # Pattern: 2025020XXX.json where XXX is the game number
    pattern = f"{SEASON}{GAME_TYPE}*.json"
    game_files = list(boxscores_dir.glob(pattern))

    if not game_files:
        return None

    # Extract game numbers from filenames
    game_numbers = []
    for filepath in game_files:
        # Filename is like 2025020724.json
        filename = filepath.stem  # 2025020724
        # Extract the game number (last 4 digits after season+gametype)
        prefix = f"{SEASON}{GAME_TYPE}"
        if filename.startswith(prefix):
            game_num_str = filename[len(prefix):]
            try:
                game_numbers.append(int(game_num_str))
            except ValueError:
                continue

    if not game_numbers:
        return None

    return max(game_numbers)


def get_todays_first_game() -> Optional[int]:
    """
    Fetch today's schedule and return the first game ID for the current season/game type.

    Returns:
        The lowest game number scheduled for today, or None if no games today.
    """
    today = date.today().isoformat()  # YYYY-MM-DD format
    schedule_url = f"https://api-web.nhle.com/v1/schedule/{today}"

    try:
        response = requests.get(schedule_url, timeout=30)

        if response.status_code != 200:
            print(f"Warning: Could not fetch schedule (HTTP {response.status_code})")
            return None

        data = response.json()

        # Extract game IDs from the schedule
        # The schedule response has gameWeek array with dates containing games
        game_numbers = []
        prefix = f"{SEASON}{GAME_TYPE}"

        for game_week in data.get("gameWeek", []):
            for game in game_week.get("games", []):
                game_id = str(game.get("id", ""))
                if game_id.startswith(prefix):
                    game_num_str = game_id[len(prefix):]
                    try:
                        game_numbers.append(int(game_num_str))
                    except ValueError:
                        continue

        if not game_numbers:
            return None

        return min(game_numbers)

    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not fetch schedule: {e}")
        return None
    except json.JSONDecodeError:
        print("Warning: Could not parse schedule response")
        return None


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def download_shifts_only(start_game: int, end_game: int):
    """Download only shifts data for a range of games."""
    print(f"\nNHL Shifts Data Downloader (HTML)")
    print(f"Season: {SEASON}")
    print(f"Game Type: {GAME_TYPE}")
    print(f"Game Range: {start_game:04d} to {end_game:04d}")
    print(f"Rate Limit: {SHIFT_RATE_LIMIT_SECONDS} seconds between requests")

    # Setup shifts directory
    shifts_path = Path("data") / SEASON / "shifts"
    shifts_path.mkdir(parents=True, exist_ok=True)
    print(f"\nData will be saved to: data/{SEASON}/shifts/")

    total_games = end_game - start_game + 1
    games_processed = 0
    total_successful = 0
    total_failed = 0

    for game_num in range(start_game, end_game + 1):
        game_id = construct_game_id(game_num)

        print(f"\n{'='*60}")
        print(f"Processing Game ID: {game_id}")
        print(f"{'='*60}")

        home_success, away_success = download_shifts(game_id, shifts_path)
        games_processed += 1

        if home_success:
            total_successful += 1
        else:
            total_failed += 1

        if away_success:
            total_successful += 1
        else:
            total_failed += 1

        if not home_success or not away_success:
            # Critical error - stop
            print(f"\n{'='*60}")
            print(f"DOWNLOAD STOPPED DUE TO CRITICAL ERROR")
            print(f"{'='*60}")
            print(f"Games processed before error: {games_processed}")
            print(f"Total successful downloads: {total_successful}")
            print(f"Total failed downloads: {total_failed}")
            print(f"{'='*60}\n")
            sys.exit(1)

        # Rate limiting between games
        if game_num < end_game:
            print(f"\nWaiting {SHIFT_RATE_LIMIT_SECONDS} seconds before next game...")
            time.sleep(SHIFT_RATE_LIMIT_SECONDS)

    # Summary
    print(f"\n{'='*60}")
    print(f"SHIFTS DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"Total games processed: {total_games}")
    print(f"Total successful downloads: {total_successful}")
    print(f"Total failed downloads: {total_failed}")
    print(f"{'='*60}\n")


def main():
    """Main execution function."""
    # Check for "shifts" mode (shifts-only download)
    if len(sys.argv) == 4 and sys.argv[1].lower() == "shifts":
        try:
            start_game = int(sys.argv[2])
            end_game = int(sys.argv[3])
        except ValueError:
            print("Error: Game IDs must be integers")
            sys.exit(1)

        if start_game > end_game:
            print("Error: Start game ID must be less than or equal to end game ID")
            sys.exit(1)

        download_shifts_only(start_game, end_game)
        return

    # Check for "today" mode
    if len(sys.argv) == 2 and sys.argv[1].lower() == "today":
        # Today mode: auto-determine game range
        today_str = date.today().isoformat()

        # Get last saved game
        last_saved = get_last_saved_game()
        if last_saved is None:
            print(f"Error: No saved games found in data/{SEASON}/boxscores/")
            print(f"Run with explicit game IDs first: python {sys.argv[0]} START END")
            sys.exit(1)

        # Get today's first game
        first_today = get_todays_first_game()
        if first_today is None:
            print(f"No games scheduled for today ({today_str}).")
            print(f"Most recent saved game: {SEASON}{GAME_TYPE}{last_saved:04d}")
            sys.exit(0)

        # Calculate range
        start_game = last_saved + 1
        end_game = first_today - 1

        # Check if already caught up
        if start_game > end_game:
            print(f"Already caught up!")
            print(f"Last saved: {SEASON}{GAME_TYPE}{last_saved:04d}")
            print(f"Next game (today): {SEASON}{GAME_TYPE}{first_today:04d}")
            sys.exit(0)

    elif len(sys.argv) == 3:
        # Explicit range mode
        try:
            start_game = int(sys.argv[1])
            end_game = int(sys.argv[2])
        except ValueError:
            print("Error: Game IDs must be integers")
            sys.exit(1)

        if start_game > end_game:
            print("Error: Start game ID must be less than or equal to end game ID")
            sys.exit(1)

    else:
        print("Error: Invalid arguments")
        print(f"Usage: python {sys.argv[0]} START_GAME_ID END_GAME_ID")
        print(f"       python {sys.argv[0]} today")
        print(f"       python {sys.argv[0]} shifts START_GAME_ID END_GAME_ID")
        print(f"Examples:")
        print(f"  python {sys.argv[0]} 1 100        # Download all data for games 1-100")
        print(f"  python {sys.argv[0]} today        # Download games through yesterday")
        print(f"  python {sys.argv[0]} shifts 1 100 # Download only shifts for games 1-100")
        sys.exit(1)
    
    # Setup
    print(f"\nNHL Game Data Downloader")
    print(f"Season: {SEASON}")
    print(f"Game Type: {GAME_TYPE}")
    print(f"Game Range: {start_game:04d} to {end_game:04d}")
    print(f"Rate Limit: {RATE_LIMIT_SECONDS} seconds between requests")
    
    paths = setup_directories(SEASON)
    print(f"\nData will be saved to: data/{SEASON}/")
    
    # Download games
    total_games = end_game - start_game + 1
    games_processed = 0
    total_successful = 0
    total_failed = 0

    for game_num in range(start_game, end_game + 1):
        game_id = construct_game_id(game_num)
        successful, failed, should_stop = download_game(game_id, paths)
        total_successful += successful
        total_failed += failed
        games_processed += 1

        if should_stop:
            # Critical error occurred - stop processing
            print(f"\n{'='*60}")
            print(f"DOWNLOAD STOPPED DUE TO CRITICAL ERROR")
            print(f"{'='*60}")
            print(f"Games processed before error: {games_processed}")
            print(f"Total successful downloads: {total_successful}")
            print(f"Total failed downloads: {total_failed}")
            print(f"{'='*60}\n")
            sys.exit(1)

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
