# Competition Score

Computes per-skater competition difficulty scores for a single NHL game.

## What it measures

For every skater in a game, two values are produced based on 5v5 ice time:

- **`comp_fwd`** — mean game 5v5 TOI (seconds) of opposing forwards while the player was on ice
- **`comp_def`** — mean game 5v5 TOI (seconds) of opposing defensemen while the player was on ice

Higher values mean the player faced opponents who logged more total ice time — a proxy for facing tougher competition.

## How it works

1. Load the game's second-by-second timeline CSV
2. For each skater, sum up their 5v5 seconds (situations `1551`, `0651`, `1560`)
3. For each of those seconds, compute the mean TOI of opposing forwards and opposing defensemen
4. Average those per-second values across the full game

## Inputs required

Both files must exist before running:

| File | Description |
|---|---|
| `data/{season}/generated/timelines/csv/{gameId}.csv` | Second-by-second timeline (from `generate_timeline.py`) |
| `data/{season}/plays/{gameId}.json` | Play-by-play data (from `nhlgame.py`) |

## Output

`data/{season}/generated/competition/{gameId}.csv`

| Column | Description |
|---|---|
| `gameId` | Full game ID (e.g. `2025020001`) |
| `playerId` | NHL player ID |
| `team` | Team abbreviation |
| `position` | `F` or `D` |
| `toi_seconds` | Player's 5v5 ice time this game (seconds) |
| `comp_fwd` | Mean opposing forward TOI (seconds) |
| `comp_def` | Mean opposing defenseman TOI (seconds) |

Rows are sorted by `toi_seconds` descending. Goalies are excluded.

## Usage

Run from the project root:

```bash
# Single game
uv run python v2/competition/compute_competition.py <game_number> <season>

# Range of games
uv run python v2/competition/compute_competition.py <start> <end> <season>
```

```bash
# Game 1 of the 2025-26 season
uv run python v2/competition/compute_competition.py 1 2025

# Games 1 through 900
uv run python v2/competition/compute_competition.py 1 900 2025
```

## Tests

```bash
python -m pytest v2/competition/tests/ -v
```
