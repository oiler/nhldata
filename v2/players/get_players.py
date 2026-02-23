#!/usr/bin/env python3
"""
NHL Player Data Fetcher

Downloads player landing page data from the NHL API and generates
structured player files with metadata and game appearance history.

Usage:
    python v2/players/get_players.py <season>
    python v2/players/get_players.py <team_abbrev> <season>
    python v2/players/get_players.py <player_id> <season>
    python v2/players/get_players.py backfill <season>

Examples:
    python v2/players/get_players.py 2025
        -> Downloads all active players, saves raw + generated data

    python v2/players/get_players.py EDM 2025
        -> Downloads all Edmonton Oilers players

    python v2/players/get_players.py 8478402 2025
        -> Downloads Connor McDavid's data only

    python v2/players/get_players.py backfill 2025
        -> Fetches any players found in competition data who are missing
           a raw JSON file in data/2025/players/
"""

import sys
import json
import csv
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple


# Configuration
GAME_TYPE = 2  # Regular season
RATE_LIMIT_SECONDS = 2  # Delay between API requests

# All 32 NHL team abbreviations
NHL_TEAMS = [
    "ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ",
    "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NSH",
    "NJD", "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "SEA",
    "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH",
]

# API endpoints
ROSTER_URL = "https://api-web.nhle.com/v1/roster/{team}/{season_id}"
PLAYER_LANDING_URL = "https://api-web.nhle.com/v1/player/{player_id}/landing"
PLAYER_GAMELOG_URL = "https://api-web.nhle.com/v1/player/{player_id}/game-log/{season_id}/{game_type}"

# CSV columns (in order)
CSV_COLUMNS = [
    'playerId',
    'currentTeamId',
    'currentTeamAbbrev',
    'firstName',
    'lastName',
    'sweaterNumber',
    'position',
    'heightInInches',
    'weightInPounds',
    'birthDate',
    'birthCountry',
    'shootsCatches',
    'draftYear',
    'draftTeam',
    'draftRound',
    'draftPick',
    'draftOverall',
    'gameIds',
    'teamIds',
]


def get_season_id(season: str) -> str:
    """Convert season year to NHL season ID format (e.g., 2025 -> 20252026)."""
    year = int(season)
    return f"{year}{year + 1}"


def setup_directories(season: str) -> Dict[str, Path]:
    """Create directory structure for player data."""
    base = Path("data") / season
    paths = {
        "raw": base / "players",
        "json": base / "generated" / "players" / "json",
        "csv": base / "generated" / "players" / "csv",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def build_team_abbrev_to_id_map(season: str) -> Dict[str, int]:
    """
    Build a mapping of team abbreviation -> team ID from flat boxscore data.

    Args:
        season: Season year (e.g., "2025")

    Returns:
        Dict mapping team abbreviation to team ID (e.g., {"EDM": 22, "TOR": 10})
    """
    mapping = {}
    boxscore_csv = Path("data") / season / "generated" / "flatboxscores" / "boxscores.csv"

    if not boxscore_csv.exists():
        print(f"\nWARNING: {boxscore_csv} not found!")
        print(f"Team ID mapping will be incomplete. Run this first:")
        print(f"  python tools/flatten_boxscore.py {season}")
        print(f"Continuing anyway...\n")
        return mapping

    with open(boxscore_csv, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            away_abbrev = row.get('awayTeam_abbrev')
            away_id = row.get('awayTeam_id')
            home_abbrev = row.get('homeTeam_abbrev')
            home_id = row.get('homeTeam_id')

            if away_abbrev and away_id:
                mapping[away_abbrev] = int(away_id)
            if home_abbrev and home_id:
                mapping[home_abbrev] = int(home_id)

    print(f"Loaded team mapping: {len(mapping)} teams from boxscore data")
    return mapping


def fetch_json(url: str, retries: int = 3) -> Optional[Dict]:
    """Fetch JSON from a URL with retry. Returns None on failure."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            print(f"  HTTP {response.status_code}: {url}")
            if response.status_code >= 500 and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return None
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"  Error (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return None


def get_roster_player_ids(team: str, season_id: str) -> List[int]:
    """Fetch player IDs from a team's roster."""
    url = ROSTER_URL.format(team=team, season_id=season_id)
    data = fetch_json(url)
    if not data:
        return []

    player_ids = []
    for group in ['forwards', 'defensemen', 'goalies']:
        for player in data.get(group, []):
            pid = player.get('id')
            if pid:
                player_ids.append(pid)
    return player_ids


def fetch_player_landing(player_id: int) -> Optional[Dict]:
    """Fetch the full player landing page from the API."""
    url = PLAYER_LANDING_URL.format(player_id=player_id)
    return fetch_json(url)


def fetch_player_gamelog(player_id: int, season_id: str) -> Optional[Dict]:
    """Fetch the player's game log for a specific season."""
    url = PLAYER_GAMELOG_URL.format(
        player_id=player_id, season_id=season_id, game_type=GAME_TYPE
    )
    return fetch_json(url)


def extract_player_meta(landing: Dict) -> Dict:
    """
    Extract metadata fields from a player landing page response.

    Handles both string and {default: "..."} formats for name fields.
    """
    def get_name(val):
        if isinstance(val, dict):
            return val.get('default', '')
        return val or ''

    draft = landing.get('draftDetails', {}) or {}

    # draftDetails.teamAbbrev may also be a {default: "..."} object
    draft_team_raw = draft.get('teamAbbrev', '')
    draft_team = get_name(draft_team_raw) if isinstance(draft_team_raw, dict) else (draft_team_raw or '')

    current_abbrev_raw = landing.get('currentTeamAbbrev', '')
    current_abbrev = get_name(current_abbrev_raw) if isinstance(current_abbrev_raw, dict) else (current_abbrev_raw or '')

    return {
        'playerId': landing.get('playerId'),
        'currentTeamId': landing.get('currentTeamId'),
        'currentTeamAbbrev': current_abbrev,
        'firstName': get_name(landing.get('firstName', '')),
        'lastName': get_name(landing.get('lastName', '')),
        'sweaterNumber': landing.get('sweaterNumber'),
        'position': landing.get('position', ''),
        'heightInInches': landing.get('heightInInches'),
        'weightInPounds': landing.get('weightInPounds'),
        'birthDate': landing.get('birthDate', ''),
        'birthCountry': landing.get('birthCountry', ''),
        'shootsCatches': landing.get('shootsCatches', ''),
        'draftYear': draft.get('year'),
        'draftTeam': draft_team,
        'draftRound': draft.get('round'),
        'draftPick': draft.get('pickInRound'),
        'draftOverall': draft.get('overallPick'),
    }


def extract_gamelog_entries(gamelog_data: Dict) -> List[Dict]:
    """
    Extract game appearances from a game log response.

    Returns:
        List of {"gameId": int, "teamAbbrev": str} dicts
    """
    entries = []
    for game in gamelog_data.get('gameLog', []):
        game_id = game.get('gameId')
        team_abbrev_raw = game.get('teamAbbrev', '')
        team_abbrev = team_abbrev_raw.get('default', '') if isinstance(team_abbrev_raw, dict) else (team_abbrev_raw or '')

        if game_id:
            entries.append({
                'gameId': game_id,
                'teamAbbrev': team_abbrev,
            })
    return entries


def process_player(player_id: int, season: str, season_id: str,
                   paths: Dict[str, Path],
                   team_map: Dict[str, int]) -> Optional[Dict]:
    """
    Fetch and process a single player's data.

    1. Fetches and saves raw landing page to data/{season}/players/
    2. Fetches game log for the season
    3. Returns processed player dict with meta + game appearances

    Returns:
        Processed player dict, or None if fetch failed
    """
    # Fetch landing page
    landing = fetch_player_landing(player_id)
    if not landing:
        print(f"  Failed to fetch landing for player {player_id}")
        return None

    # Save raw landing data
    raw_path = paths["raw"] / f"{player_id}.json"
    with open(raw_path, 'w') as f:
        json.dump(landing, f, indent=2)

    time.sleep(RATE_LIMIT_SECONDS)

    # Fetch game log
    gamelog_data = fetch_player_gamelog(player_id, season_id)
    gamelog_entries = []
    if gamelog_data:
        gamelog_entries = extract_gamelog_entries(gamelog_data)

    time.sleep(RATE_LIMIT_SECONDS)

    # Build processed player record
    meta = extract_player_meta(landing)

    # Derive unique team IDs from game log using our abbrev->id mapping
    team_abbrevs_seen = list(dict.fromkeys(
        entry['teamAbbrev'] for entry in gamelog_entries if entry['teamAbbrev']
    ))
    team_ids_seen = []
    for abbrev in team_abbrevs_seen:
        tid = team_map.get(abbrev)
        if tid and tid not in team_ids_seen:
            team_ids_seen.append(tid)

    meta['teamIds'] = team_ids_seen
    meta['teamAbbrevs'] = team_abbrevs_seen
    meta['gameLog'] = gamelog_entries

    return meta


def build_csv_row(player: Dict) -> Dict:
    """Convert a processed player dict to a CSV row dict."""
    row = {}
    for col in CSV_COLUMNS:
        if col == 'gameIds':
            row[col] = '|'.join(str(g['gameId']) for g in player.get('gameLog', []))
        elif col == 'teamIds':
            row[col] = '|'.join(str(tid) for tid in player.get('teamIds', []))
        else:
            val = player.get(col, '')
            row[col] = '' if val is None else val
    return row


def write_csv(players: List[Dict], output_path: Path):
    """Write player data to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [build_csv_row(p) for p in players]
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_json(players: List[Dict], season: str, season_id: str, output_path: Path):
    """Write player data to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "season": season_id,
        "seasonYear": season,
        "generatedAt": datetime.now().isoformat(),
        "playerCount": len(players),
        "players": players,
    }
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)


def resolve_player_ids(arg: str, season_id: str) -> Tuple[List[int], str]:
    """
    Resolve the first argument to a list of player IDs and a description.

    - If arg is a team abbreviation (3 uppercase letters in NHL_TEAMS): fetch that roster
    - If arg is numeric (7-8 digits): treat as a single player ID
    - Otherwise: error

    Returns:
        Tuple of (player_id_list, description_string)
    """
    upper = arg.upper()
    if upper in NHL_TEAMS:
        print(f"Fetching roster for {upper}...")
        ids = get_roster_player_ids(upper, season_id)
        print(f"  Found {len(ids)} players on {upper}")
        return ids, f"team {upper}"

    if arg.isdigit() and len(arg) >= 7:
        return [int(arg)], f"player {arg}"

    print(f"Error: '{arg}' is not a valid team abbreviation or player ID")
    sys.exit(1)


def find_missing_player_ids(season: str) -> List[int]:
    """
    Scan competition CSVs to find player IDs with no raw JSON file.

    Returns a sorted list of player IDs that appear in
    data/{season}/generated/competition/ but have no corresponding
    data/{season}/players/{pid}.json.
    """
    import glob
    comp_dir = Path("data") / season / "generated" / "competition"
    players_dir = Path("data") / season / "players"

    seen: Set[int] = set()
    for path in glob.glob(str(comp_dir / "*.csv")):
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                pid = row.get("playerId")
                if pid:
                    seen.add(int(pid))

    missing = sorted(pid for pid in seen if not (players_dir / f"{pid}.json").exists())
    return missing


def main():
    """Main entry point."""
    if len(sys.argv) == 2:
        # All active players mode
        season = sys.argv[1]
        mode = "all"
    elif len(sys.argv) == 3:
        first_arg = sys.argv[1]
        season = sys.argv[2]
        mode = "backfill" if first_arg.lower() == "backfill" else "targeted"
    else:
        print(__doc__)
        sys.exit(1)

    season_id = get_season_id(season)
    paths = setup_directories(season)
    team_map = build_team_abbrev_to_id_map(season)

    # Resolve player IDs
    if mode == "all":
        print(f"\nNHL Player Data Fetcher")
        print(f"Season: {season} ({season_id})")
        print(f"Mode: All active players (32 teams)")
        print(f"Rate limit: {RATE_LIMIT_SECONDS}s between requests\n")

        all_ids: Set[int] = set()
        for team in NHL_TEAMS:
            print(f"  Fetching {team} roster...", end=" ", flush=True)
            ids = get_roster_player_ids(team, season_id)
            print(f"{len(ids)} players")
            all_ids.update(ids)
            time.sleep(RATE_LIMIT_SECONDS)

        player_ids = sorted(all_ids)
        desc = "all active players"
        print(f"\nTotal unique players: {len(player_ids)}")
    elif mode == "backfill":
        print(f"\nNHL Player Data Fetcher — Backfill Mode")
        print(f"Season: {season} ({season_id})")
        print(f"Scanning competition data for missing player files...\n")

        player_ids = find_missing_player_ids(season)
        if not player_ids:
            print("All players already have data files. Nothing to fetch.")
            sys.exit(0)

        print(f"Found {len(player_ids)} players missing a data file.")
        desc = "missing players (backfill)"
    else:
        print(f"\nNHL Player Data Fetcher")
        print(f"Season: {season} ({season_id})")
        print(f"Rate limit: {RATE_LIMIT_SECONDS}s between requests\n")

        player_ids, desc = resolve_player_ids(first_arg, season_id)

    # Process each player
    print(f"\nProcessing {len(player_ids)} players ({desc})...\n")
    players = []
    for i, pid in enumerate(player_ids, 1):
        print(f"  [{i}/{len(player_ids)}] Player {pid}...", end=" ", flush=True)
        result = process_player(pid, season, season_id, paths, team_map)
        if result:
            name = f"{result['firstName']} {result['lastName']}"
            games = len(result.get('gameLog', []))
            print(f"{name} ({games} games)")
            players.append(result)
        else:
            print("FAILED")

    if not players:
        print("\nError: No players were processed successfully")
        sys.exit(1)

    # Write generated output
    csv_path = paths["csv"] / "players.csv"
    json_path = paths["json"] / "players.json"

    try:
        write_csv(players, csv_path)
        write_json(players, season, season_id, json_path)
    except IOError as e:
        print(f"\nError: Failed to write output files: {e}")
        sys.exit(1)

    print(f"\nComplete!")
    print(f"  Raw data: data/{season}/players/ ({len(players)} files)")
    print(f"  CSV: {csv_path}")
    print(f"  JSON: {json_path}")
    print(f"  Players processed: {len(players)}")


if __name__ == "__main__":
    main()
