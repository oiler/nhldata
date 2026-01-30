# v2 Timeline Generator Design

## Overview

Generate second-by-second timelines showing players on ice and situationCode for each game. Primary data source is HTML-scraped shift files.

## Dependencies

Must be built after:
1. `2026-01-30-nhlgame-today-param-design.md` - Auto-fetch game data
2. `2026-01-29-html-shifts-scraper-design.md` - HTML shift data source
3. `2026-01-30-test-games-dataset-design.md` - Validation test suite

## Input Files (per game)

- `data/2025/shifts/2025020001_home.json` - home team shifts (HTML scraped)
- `data/2025/shifts/2025020001_away.json` - away team shifts (HTML scraped)
- `data/2025/plays/2025020001.json` - game metadata

## Output Files (per game)

- `data/2025/generated/timelines/json/2025020001.json`
- `data/2025/generated/timelines/csv/2025020001.csv`

## Script Location

```
v2/
  timelines/
    generate_timeline.py
    README.md
```

## Output Structure

### JSON Format

```json
{
  "gameId": "2025020001",
  "season": "20252026",
  "gameDate": "2025-10-07",
  "homeTeam": {
    "id": 13,
    "abbrev": "FLA",
    "name": "Florida Panthers"
  },
  "awayTeam": {
    "id": 16,
    "abbrev": "CHI",
    "name": "Chicago Blackhawks"
  },
  "timeline": [
    {
      "period": 1,
      "secondsIntoPeriod": 0,
      "secondsElapsedGame": 0,
      "situationCode": "1551",
      "home": {
        "skaters": [8477180, 8478402, 8479318, 8480039, 8481234],
        "skaterCount": 5,
        "goalie": 8478048
      },
      "away": {
        "skaters": [8476453, 8477474, 8478550, 8479339, 8480801],
        "skaterCount": 5,
        "goalie": 8477180
      }
    }
  ]
}
```

### CSV Format

Columns:
```
period,secondsIntoPeriod,secondsElapsedGame,situationCode,homeSkaters,homeSkaterCount,homeGoalie,awaySkaters,awaySkaterCount,awayGoalie
```

Example row:
```
1,0,0,1551,8477180|8478402|8479318|8480039|8481234,5,8478048,8476453|8477474|8478550|8479339|8480801,5,8477180
```

Player IDs are pipe-separated for SQLite compatibility.

## SituationCode Calculation

**Format:** `[Away Goalie][Away Skaters][Home Skaters][Home Goalie]`

**Calculation per second:**
1. Count home skaters on ice (from home shifts file)
2. Count away skaters on ice (from away shifts file)
3. Determine home goalie status (on ice = 1, pulled = 0)
4. Determine away goalie status (on ice = 1, pulled = 0)
5. Build code: `f"{awayGoalie}{awaySkaterCount}{homeSkaterCount}{homeGoalie}"`

**Goaltender identification:**
- HTML shift files include `position` field - goaltenders are explicitly identified

**Edge cases:**
- Pulled goalie: goalie not on ice = 0 in code, skater count may be 6
- Minimum 3 skaters per team (stacked penalties)
- Maximum 6 skaters (5 + extra attacker with pulled goalie)

## Timing Logic

**Baseline approach (from v1):**

For second 0 of each period:
- Only include players with `startTime="00:00"` (period starters)

For seconds 1-1200 (regulation) or 1-300 (OT):
- Players on ice from `startTime + 1` through `endTime` (inclusive)
- This prevents double-counting during on-the-fly line changes

**Period handling:**
- Periods 1-3: 1201 data points each (seconds 0-1200)
- Period 4 (regular season OT): 301 data points (seconds 0-300)
- Periods 5+ (playoff OT): 1201 data points each

**Why startTime + 1:**
When player A's shift ends at 05:30 and player B's shift starts at 05:30:
- Second 330: Player A on ice (their shift includes endTime)
- Second 331: Player B on ice (their shift starts at startTime + 1)

This logic will be validated against the test games dataset and refined if issues are discovered.

## Validation

**Primary validation: TOI comparison**

After building the timeline, sum each player's seconds on ice and compare against the shift file's `gameTotals.toi` field.

```
Player 8477180: Calculated 1166s, Expected 1166s ✓
Player 8478402: Calculated 1042s, Expected 1042s ✓
Player 8479318: Calculated 892s, Expected 890s ✗ MISMATCH
```

**On mismatch:**
- STOP immediately
- Print detailed error showing player ID, calculated vs expected, discrepancy
- Exit with error code

**Console output (success):**
```
Validation: 42 players checked
  Home (FLA): 21 players ✓
  Away (CHI): 21 players ✓
All TOI totals match.
```

## Script Interface

**Usage:**
```bash
# Single game
python v2/timelines/generate_timeline.py 591 2025

# Batch mode
python v2/timelines/generate_timeline.py 1 100 2025
```

**Console output:**
```
NHL Timeline Generator v2
================================================================================
Game ID: 2025020591
Input:   data/2025/shifts/2025020591_home.json
         data/2025/shifts/2025020591_away.json
         data/2025/plays/2025020591.json
Output:  data/2025/generated/timelines/json/2025020591.json
         data/2025/generated/timelines/csv/2025020591.csv
================================================================================

Processing shifts... ✓ 3603 seconds generated
Validating TOI... ✓ 42 players match
Writing output... ✓

Complete!
```

## Directory Structure

```
data/
  2025/
    shifts/                    # NHL source (HTML scraped)
      2025020001_home.json
      2025020001_away.json
    plays/                     # NHL source (API)
    meta/                      # NHL source (API)
    boxscores/                 # NHL source (API)
    generated/
      timelines/
        json/
          2025020001.json
        csv/
          2025020001.csv

v2/
  timelines/
    generate_timeline.py
    README.md
```

## Implementation Order

1. **nhlgame.py "today" parameter**
   - Auto-detect last saved game
   - Fetch games up through yesterday
   - File: `2026-01-30-nhlgame-today-param-design.md`

2. **HTML Shifts Scraper**
   - Fetches shift data from NHL HTML reports
   - Outputs `{gameId}_home.json` and `{gameId}_away.json`
   - File: `2026-01-29-html-shifts-scraper-design.md`

3. **Test Games Dataset**
   - Discovery script to find high-diversity games
   - Curated list of ~20 games covering all situationCodes
   - File: `2026-01-30-test-games-dataset-design.md`

4. **v2 Timeline Generator** (this design)
   - Reads HTML shift files + plays metadata
   - Generates second-by-second timeline with situationCode
   - Validates against TOI totals
   - Outputs JSON and CSV

## Testing Approach

- Build v2 timeline generator
- Run against test games dataset
- Validate TOI matches for all games
- Verify situationCode coverage across all expected codes
- Refine timing logic if any edge cases fail
