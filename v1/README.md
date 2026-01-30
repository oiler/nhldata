# NHL Game Data Downloader

Download NHL game data from public API endpoints for analysis and archival.

## Features

- Downloads data from 4 NHL API endpoints per game:
  - Shift charts
  - Play-by-play data
  - Game landing/metadata
  - Boxscores
- Organizes data by season in separate folders
- Graceful error handling with detailed logging
- Rate limiting to respect API servers
- Always overwrites existing data with fresh downloads

## Setup

### Prerequisites

- Python 3.8 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Install uv if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install dependencies:
```bash
uv pip install -e .
```

Or install dependencies directly:
```bash
uv pip install requests
```

## Usage

### Basic Command

```bash
python nhlgame.py START_GAME_ID END_GAME_ID
```

### Examples

Download data for games 3031 and 3032:
```bash
python nhlgame.py 3031 3032
```

Download a single game (3050):
```bash
python nhlgame.py 3050 3050
```

Download a range of games (1 through 100):
```bash
python nhlgame.py 1 100
```

### What Gets Downloaded

For each game ID, the script constructs the full NHL game ID using:
- **Season**: `2025` (default, configurable in script)
- **Game Type**: `02` (regular season, configurable in script)
- **Game Number**: The number you provide (e.g., `3031`)

So `python nhlgame.py 3031 3032` downloads data for:
- `2025023031`
- `2025023032`

## Directory Structure

```
2025/                      # Season folder (auto-created)
├── shifts/               # Shift chart data
│   ├── 2025023031.json
│   └── 2025023032.json
├── plays/                # Play-by-play data
│   ├── 2025023031.json
│   └── 2025023032.json
├── meta/                 # Game metadata/landing
│   ├── 2025023031.json
│   └── 2025023032.json
└── boxscores/            # Boxscore data
    ├── 2025023031.json
    └── 2025023032.json

nogames.json              # Log of 404 errors (game not found)
errors.json               # Log of other errors (network, parsing, etc.)
```

## Configuration

Edit the top of `nhlgame.py` to change defaults:

```python
SEASON = "2025"              # Change to download different seasons
GAME_TYPE = "02"             # 01=Preseason, 02=Regular, 03=Playoffs
RATE_LIMIT_SECONDS = 10      # Delay between API requests
```

## Error Handling

The script tracks two types of errors:

### nogames.json
Games that returned 404 (not found). This usually means:
- Game hasn't been played yet
- Game ID doesn't exist
- Game was cancelled

### errors.json
Other failures such as:
- Network timeouts
- API server errors (500, 503, etc.)
- Malformed JSON responses

Each error log includes:
- Game ID
- Endpoint that failed
- Error message
- Timestamp

## Rate Limiting

The script waits **10 seconds** between each API request by default. This means:
- 40 seconds per complete game (4 endpoints × 10 seconds)
- ~90 games per hour
- Very respectful to the NHL API servers

You can adjust `RATE_LIMIT_SECONDS` in the script if needed.

## Data Overwriting

The script **always overwrites** existing JSON files. This is by design so you can:
- Re-download games to get updated data
- Fix corrupted downloads
- Update historical games if needed

If you want to preserve old data, back it up before re-running the script.

## Tips

### Downloading Multiple Seasons

To download data for the 2024 season:
1. Edit `SEASON = "2024"` in the script
2. Run your download commands
3. Data will be saved to `2024/` folder

### Regular Season Game Ranges

- Current NHL: Games 0001 to 1312 (82 games × 32 teams / 2)
- When NHL expands to 84 games: Update the range accordingly

### Finding Game Numbers

Games are numbered sequentially throughout the season:
- First game of season: `0001`
- 100th game of season: `0100`
- Last game of season: `1312`

## Troubleshooting

### "Module not found" error
Make sure you installed dependencies:
```bash
uv pip install requests
```

### All downloads failing with 404
- Check that the game IDs exist (games may not be played yet)
- Verify the season and game type are correct
- Check `nogames.json` for details

### Connection timeouts
- Check your internet connection
- The NHL API might be experiencing issues
- Check `errors.json` for details

## License

MIT License - feel free to use and modify as needed.
