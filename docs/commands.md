# NHL Project Commands

## Data Download

### nhlgame.py - Download game data from NHL API
```bash
# Download boxscores, plays, meta for game range
uv run python v1/nhlgame.py 1 100

# Download shift data for game range
uv run python v1/nhlgame.py shifts 1 100

# Download a single game
uv run python v1/nhlgame.py 828 828

# Download today's games
uv run python v1/nhlgame.py today
```

## Tools

### gamecheck.py - Check for missing/empty data files
```bash
uv run python tools/gamecheck.py 2025
```

### flatten_plays.py - Flatten play-by-play data to CSV
```bash
# Single game
uv run python tools/flatten_plays.py 153 2025

# Range of games
uv run python tools/flatten_plays.py 1 100 2025
```

### discover_test_games.py - Find games with specific scenarios for testing
```bash
uv run python tools/discover_test_games.py
```

## Timeline Generation

### generate_timeline.py - Generate second-by-second situation timelines
```bash
# Single game
uv run python v2/timelines/generate_timeline.py 591 2025

# Batch mode
uv run python v2/timelines/generate_timeline.py 1 100 2025
```

