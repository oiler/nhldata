# Get Player Info Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a script that fetches NHL player data from the API and generates structured player files with metadata and game appearance history, supporting queries by all active players, by team, or by individual player ID.

**Architecture:** The script fetches raw player landing pages from `api-web.nhle.com` and saves them as-is. It then fetches game logs per player to build a processed dataset combining player metadata with season game appearances. To discover all active players, it iterates all 32 team rosters. A team abbreviation-to-ID mapping is derived from our existing flat boxscore data.

**Tech Stack:** Python 3.10+, requests, json, csv, pathlib (same dependencies as existing scripts)

---

## API Endpoints Used

- **Team Roster:** `https://api-web.nhle.com/v1/roster/{teamAbbrev}/20252026`
  - Returns `forwards`, `defensemen`, `goalies` arrays with player `id` fields
- **Player Landing:** `https://api-web.nhle.com/v1/player/{playerId}/landing`
  - Returns full player profile with meta, draft details, current team info
- **Player Game Log:** `https://api-web.nhle.com/v1/player/{playerId}/game-log/20252026/2`
  - Returns `gameLog` array with `gameId`, `teamAbbrev` per game played

## Directory Structure

```
data/2025/
├── players/                           # Raw API responses (new)
│   └── {playerId}.json                # Full landing page JSON per player
└── generated/
    └── players/                       # Processed output (new)
        ├── json/
        │   └── players.json           # All players in one structured file
        └── csv/
            └── players.csv            # All players in one CSV
```

## Output Formats

**CSV columns:**
```
playerId,currentTeamId,currentTeamAbbrev,firstName,lastName,sweaterNumber,position,heightInInches,weightInPounds,birthDate,birthCountry,shootsCatches,draftYear,draftTeam,draftRound,draftPick,draftOverall,gameIds,teamIds
```
- `gameIds`: pipe-delimited list of game IDs played this season (e.g., `2025020001|2025020015|...`)
- `teamIds`: pipe-delimited list of unique team IDs played for this season (e.g., `22` or `22|25` for a traded player)

**JSON structure:**
```json
{
  "season": "20252026",
  "seasonYear": "2025",
  "generatedAt": "2026-02-09T...",
  "playerCount": 850,
  "players": [
    {
      "playerId": 8478402,
      "currentTeamId": 22,
      "currentTeamAbbrev": "EDM",
      "firstName": "Connor",
      "lastName": "McDavid",
      "sweaterNumber": 97,
      "position": "C",
      "heightInInches": 73,
      "weightInPounds": 194,
      "birthDate": "1997-01-13",
      "birthCountry": "CAN",
      "shootsCatches": "L",
      "draftYear": 2015,
      "draftTeam": "EDM",
      "draftRound": 1,
      "draftPick": 1,
      "draftOverall": 1,
      "teamIds": [22],
      "teamAbbrevs": ["EDM"],
      "gameLog": [
        {"gameId": 2025020001, "teamAbbrev": "EDM"},
        {"gameId": 2025020015, "teamAbbrev": "EDM"}
      ]
    }
  ]
}
```

## Script Usage

```
v2/players/get_players.py 2025                    # All active players (all 32 rosters)
v2/players/get_players.py EDM 2025                # All players on one team
v2/players/get_players.py 8478402 2025            # Single player by ID
```

---

### Task 1: Create the script skeleton with argument parsing

**Files:**
- Create: `v2/players/get_players.py`

**Step 1: Write the script with imports, constants, arg parsing, and stub functions**

```python
#!/usr/bin/env python3
"""
NHL Player Data Fetcher

Downloads player landing page data from the NHL API and generates
structured player files with metadata and game appearance history.

Usage:
    python v2/players/get_players.py <season>
    python v2/players/get_players.py <team_abbrev> <season>
    python v2/players/get_players.py <player_id> <season>

Examples:
    python v2/players/get_players.py 2025
        -> Downloads all active players, saves raw + generated data

    python v2/players/get_players.py EDM 2025
        -> Downloads all Edmonton Oilers players

    python v2/players/get_players.py 8478402 2025
        -> Downloads Connor McDavid's data only
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
SEASON_ID_FORMAT = "{year}{next_year}"  # e.g., 20252026
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
        print(f"Warning: {boxscore_csv} not found, team ID mapping will be incomplete")
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


def fetch_json(url: str) -> Optional[Dict]:
    """Fetch JSON from a URL. Returns None on failure."""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
        print(f"  HTTP {response.status_code}: {url}")
        return None
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"  Error: {e}")
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
            row[col] = player.get(col, '')
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


def main():
    """Main entry point."""
    if len(sys.argv) == 2:
        # All active players mode
        season = sys.argv[1]
        mode = "all"
    elif len(sys.argv) == 3:
        # Team or player mode
        first_arg = sys.argv[1]
        season = sys.argv[2]
        mode = "targeted"
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

    write_csv(players, csv_path)
    write_json(players, season, season_id, json_path)

    print(f"\nComplete!")
    print(f"  Raw data: data/{season}/players/ ({len(players)} files)")
    print(f"  CSV: {csv_path}")
    print(f"  JSON: {json_path}")
    print(f"  Players processed: {len(players)}")


if __name__ == "__main__":
    main()
```

**Step 2: Verify the file was created**

Run: `python v2/players/get_players.py`
Expected: Prints the docstring usage help and exits with code 1

**Step 3: Commit**

```bash
git add v2/players/get_players.py
git commit -m "feat: add get_players.py script skeleton with arg parsing"
```

---

### Task 2: Test with a single player

**Files:**
- None to modify (testing existing code)

**Step 1: Run the script for a single player (Connor McDavid)**

Run: `python v2/players/get_players.py 8478402 2025`

Expected:
- Creates `data/2025/players/8478402.json` (raw API response)
- Creates `data/2025/generated/players/json/players.json` (processed)
- Creates `data/2025/generated/players/csv/players.csv` (processed)
- Console output shows player name and game count

**Step 2: Verify raw data was saved correctly**

Run: `python -c "import json; d=json.load(open('data/2025/players/8478402.json')); print(d.get('playerId'), d.get('firstName'), d.get('lastName'))"`

Expected: `8478402 Connor McDavid` (or `8478402 {'default': 'Connor'} {'default': 'McDavid'}` if name fields are dicts)

**Step 3: Verify CSV output**

Run: `head -2 data/2025/generated/players/csv/players.csv`

Expected: Header row with all CSV_COLUMNS, followed by one data row for McDavid with pipe-delimited gameIds and teamIds

**Step 4: Verify JSON output**

Run: `python -c "import json; d=json.load(open('data/2025/generated/players/json/players.json')); p=d['players'][0]; print(p['firstName'], p['lastName'], len(p['gameLog']), 'games', p['teamAbbrevs'])"`

Expected: `Connor McDavid <N> games ['EDM']`

**Step 5: Fix any issues found during testing**

If field name formats differ from expected (e.g., `firstName` is `{'default': 'Connor'}` instead of `"Connor"`), adjust `extract_player_meta()` accordingly.

**Step 6: Commit**

```bash
git add v2/players/get_players.py
git commit -m "fix: adjust field extraction based on API response testing"
```

---

### Task 3: Test with a single team

**Files:**
- None to modify (testing existing code)

**Step 1: Run the script for one team**

Run: `python v2/players/get_players.py EDM 2025`

Expected:
- Fetches EDM roster (~20 players)
- Downloads landing page + game log for each
- Saves raw files to `data/2025/players/`
- Generates CSV and JSON with all EDM players
- Console shows progress with player names and game counts

**Step 2: Verify player count**

Run: `python -c "import json; d=json.load(open('data/2025/generated/players/json/players.json')); print(d['playerCount'], 'players')"`

Expected: ~20 players

**Step 3: Spot-check a traded player (if any visible)**

Look for players whose `teamAbbrevs` list contains more than one team. If found, verify the `teamIds` list is also correct.

**Step 4: Commit if fixes were needed**

```bash
git add v2/players/get_players.py
git commit -m "fix: adjust player processing based on team-level testing"
```

---

### Task 4: Test with all active players

**Files:**
- None to modify (testing existing code)

**Step 1: Run the script for all teams**

Run: `python v2/players/get_players.py 2025`

Expected:
- Iterates all 32 team rosters
- Deduplicates player IDs across teams
- Downloads ~800-900 unique players
- This will take a while due to rate limiting (~2s per request, 2 requests per player)
- Total time estimate: ~1-2 hours for ~850 players

**Step 2: Verify output completeness**

Run: `python -c "import json; d=json.load(open('data/2025/generated/players/json/players.json')); print(d['playerCount'], 'players'); traded=[p for p in d['players'] if len(p['teamAbbrevs'])>1]; print(len(traded), 'traded players')"`

Expected: ~800-900 players total, with some traded players identified

**Step 3: Verify CSV row count matches JSON player count**

Run: `wc -l data/2025/generated/players/csv/players.csv`

Expected: playerCount + 1 (header row)

**Step 4: Commit**

```bash
git add v2/players/get_players.py
git commit -m "feat: verified all-players mode working correctly"
```

---

## Notes

### Rate Limiting
The script makes 2 API calls per player (landing + game log) plus 1 per team roster. For all 32 teams with ~850 unique players, that's roughly 1,732 API calls. At 2 seconds between calls, expect ~60 minutes for a full run.

### Incremental Updates
This first version always fetches fresh data. A future enhancement could skip players whose raw data already exists (pass a `--refresh` flag to force re-download).

### Data Freshness
Player data changes throughout the season (trades, call-ups, injuries). Running this script periodically will capture those changes. The `generatedAt` timestamp in the JSON output tracks when the data was last pulled.

### Team ID Mapping
Team IDs are derived from the flat boxscore CSV (`data/2025/generated/flatboxscores/boxscores.csv`). This file must exist before running the player script. If it doesn't exist, the script will warn but continue -- team IDs in the output will just be empty.

### Undrafted Players
Players without draft details will have `None`/empty values for all draft fields. This is expected behavior.
