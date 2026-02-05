# NHL Timeline Generator v2

Generates second-by-second timelines showing players on ice and situationCode for each NHL game.

## Overview

The timeline generator processes HTML-scraped shift data to create accurate, validated timelines. Each second of gameplay includes:
- Which skaters are on ice (by player ID)
- Which goalie is in net (or if pulled)
- The situationCode representing the game state

## Usage

```bash
# Single game
uv run python v2/timelines/generate_timeline.py 591 2025

# Batch mode
uv run python v2/timelines/generate_timeline.py 1 100 2025
```

## Input Files

Per game, requires:
- `data/{season}/shifts/{gameId}_home.json` - Home team shifts (HTML scraped)
- `data/{season}/shifts/{gameId}_away.json` - Away team shifts (HTML scraped)
- `data/{season}/boxscores/{gameId}.json` - Player ID mapping and goalie identification
- `data/{season}/plays/{gameId}.json` - Period count and penalty shot detection

## Output Files

Per game, generates:
- `data/{season}/generated/timelines/json/{gameId}.json`
- `data/{season}/generated/timelines/csv/{gameId}.csv`

## SituationCode vs Strength

### SituationCode

The raw 4-digit code from NHL data, always ordered **away team first**:

```
[Away Goalie][Away Skaters][Home Skaters][Home Goalie]
```

- **Goalie values**: 1 = in net, 0 = pulled
- **Skater values**: 3-6 skaters on ice

### Strength

A normalized representation of skater counts, **not team-specific**. The larger number always comes first.

- `5v4` means one team has 5 skaters, the other has 4
- Both `1451` (home PP) and `1541` (away PP) have Strength `5v4`

This separation allows filtering by game situation (e.g., "all 5v4 power plays") regardless of which team has the advantage.

### Common Codes

| Code | Strength | Meaning |
|------|----------|---------|
| 1551 | 5v5 | 5v5, both goalies in |
| 1541 | 5v4 | Away power play |
| 1451 | 5v4 | Home power play |
| 1441 | 4v4 | 4v4, both goalies |
| 1331 | 3v3 | 3v3 overtime |
| 0651 | 5v5 | Away goalie pulled, 6v5 |
| 1560 | 5v5 | Home goalie pulled, 5v6 |
| 0101 | N/A | Penalty shot: away shooter |
| 1010 | N/A | Penalty shot: home shooter |

See `resources/SITUATIONCODE_TABLE.md` for the complete reference of all 30 valid codes.

## Output Structure

### JSON Format

```json
{
  "gameId": "2025020153",
  "season": "20252026",
  "gameDate": "2025-10-28",
  "gameType": 2,
  "isPlayoff": false,
  "numPeriods": 4,
  "homeTeam": {
    "id": 13,
    "abbrev": "FLA",
    "name": "Florida Panthers"
  },
  "awayTeam": {
    "id": 24,
    "abbrev": "ANA",
    "name": "Anaheim Ducks"
  },
  "timeline": [
    {
      "period": 1,
      "secondsIntoPeriod": 0,
      "secondsElapsedGame": 0,
      "situationCode": "1551",
      "home": {
        "skaters": [8477932, 8478055, 8480185, 8482113, 8482713],
        "skaterCount": 5,
        "goalie": 8480193
      },
      "away": {
        "skaters": [8476885, 8478873, 8481754, 8482803, 8484153],
        "skaterCount": 5,
        "goalie": 8480843
      }
    }
  ]
}
```

### CSV Format

Columns ordered to match situationCode format (away team first):

```
period,secondsIntoPeriod,secondsElapsedGame,situationCode,awayGoalie,awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters
```

Player IDs are pipe-separated for SQLite compatibility:
```
1,0,0,1551,8480843,5,8476885|8478873|8481754|8482803|8484153,5,8480193,8477932|8478055|8480185|8482113|8482713
```

## Validation

The generator validates calculated TOI against the shift file's `gameTotals.toi` for every player. On mismatch, it stops and reports the discrepancy.

```
Validating TOI... ✓ 38 players match
```

## Timing Logic

### Shift Processing

A shift from `startTime` to `endTime` counts seconds `startTime` through `endTime-1` (exclusive end). This ensures:
- Correct TOI calculation (shift duration matches)
- No double-counting during line changes

Example: Player A ends at 5:30, Player B starts at 5:30
- Player A: on ice for seconds 0-329
- Player B: on ice for seconds 330+

### Period Handling

| Period | Duration | Seconds |
|--------|----------|---------|
| 1-3 | 20 minutes | 0-1199 |
| 4 (regular season OT) | 5 minutes | 0-299 |
| 4+ (playoff OT) | 20 minutes | 0-1199 |
| 5 (shootout) | Excluded | N/A |

## Data Pipeline

1. **Load shift data** - HTML-scraped shifts for home and away teams
2. **Build player mapping** - Jersey number → Player ID from boxscore
3. **Identify goalies** - From boxscore's `goalies` list
4. **Process shifts** - Build second-by-second player lookup
5. **Detect penalty shots** - From plays data (codes 0101, 1010)
6. **Generate timeline** - Calculate situationCode for each second
7. **Validate TOI** - Compare against shift file totals
8. **Write output** - JSON and CSV files

## Dependencies

- Shift data from HTML scraper (`v1/nhlgame.py shifts`)
- Boxscore data from NHL API (`v1/nhlgame.py`)
- Plays data from NHL API (`v1/nhlgame.py`)

## Known Limitations

- Penalty shots are detected from plays data but the timeline shows the shift-based players, not the 1v1 situation
- Shootouts (Period 5) are excluded as they occur after regulation/OT playing time
- Requires accurate shift data; corrupted HTML scrapes will cause validation failures

## Test Games

See `resources/TEST_GAMES.md` for a curated set of 8 games that cover all 25 situationCodes and have been validated.
