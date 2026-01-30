# NHL On-Ice Shifts Processor

Processes NHL shift data to create a second-by-second timeline of which players (and goaltenders) are on the ice for each team.

## Overview

The NHL shift data contains information about when each player enters and exits the ice during a game. This script processes that data to create a complete timeline showing exactly who was on the ice at every second of the game.

## Input Data Format

### File Naming
```
[YYYY][TT][IIII].json
```

- `YYYY` = Season year (e.g., 2025)
- `TT` = Game type (01=Preseason, 02=Regular Season, 03=Playoffs)
- `IIII` = Game ID (e.g., 0631)

Example: `2025020631.json` = 2024-2025 Regular Season, Game 631

### Shift Data Structure

Each shift contains:
- `id` - Unique shift identifier
- `gameId` - Game identifier (matches filename)
- `detailCode` - 0 = regular shift, other values = logged events (ignore these)
- `period` - Period number (1, 2, 3 for regulation; 4 for OT; 5 for shootout)
- `duration` - Shift length in MM:SS format
- `startTime` - When shift started in MM:SS format (time elapsed in period)
- `endTime` - When shift ended in MM:SS format (time elapsed in period)
- `playerId` - NHL player ID
- `teamId` - NHL team ID
- `firstName`, `lastName` - Player name (not used in output)
- `shiftNumber` - Sequential shift number for this player

### Important Notes

- **Filter out non-regular shifts:** Skip any shift with `detailCode != 0`
- **Inclusive timing:** A shift from 00:00 to 00:36 includes seconds 0 through 36 (both inclusive)
- **Time format:** MM:SS where MM = minutes, SS = seconds
- **Period lengths:** 
  - Periods 1-3 (regulation): 20:00 each = 1200 seconds
  - Period 4 (OT, regular season): 5:00 = 300 seconds
  - Period 5 (shootout): Not timed, skip this period

## Goaltender Detection Logic

The shift data does not distinguish goaltenders from skaters. We must detect them algorithmically.

### Key Principles

1. **Each team has exactly 0 or 1 goaltender on ice at any time** (never 2)
2. **Goaltenders have much longer shifts** than skaters (~20 min/period vs <2 min typical)
3. **Starting goaltenders begin the game** at period 1, time 00:00
4. **Goaltenders always start periods** at 00:00
5. **Teams can change goaltenders** mid-game (backup replaces starter)
6. **Goaltenders can be pulled** temporarily (delayed penalty, extra attacker)

### Detection Algorithm

#### Phase 1: Identify Starting Goaltenders

Every game starts with 12 players (6 per team) at period 1, time 00:00.

For each team:
1. Find all players with `period=1` AND `startTime="00:00"`
2. Group by `teamId`
3. Calculate **total duration in period 1** for each player (sum all their shifts)
4. Player with duration closest to 20:00 (1200 seconds) = **starting goaltender**

**Rationale:** 
- Skaters typically play 30-90 seconds per shift, totaling <10 minutes/period
- Goaltenders play nearly the entire period, ~20 minutes total
- Even if pulled briefly (delayed penalty), total time is still ~19-20 minutes

**Example from sample data:**
```
Period 1 starters for team 22:
- Player 8474641: 2 shifts, total 2:30 → Skater
- Player 8477498: 3 shifts, total 3:45 → Skater  
- Player 8478971: 2 shifts, total 19:34 → GOALTENDER (pulled briefly, but ~20 min total)
- Player 8479365: 2 shifts, total 2:10 → Skater
- Player 8479368: 1 shift, total 0:36 → Skater
- Player 8480831: 2 shifts, total 1:52 → Skater
```

#### Phase 2: Detect Goaltender Changes

When a starting goaltender stops playing, check for replacement:

**Check 1: Immediate Replacement**
- If a player makes their **first appearance** at the same time the starting goaltender exits
- That player is the new goaltender
- "Same time" = within a few seconds (e.g., starter ends at 12:30, new player starts at 12:30)

**Check 2: Period Start**
- If a player who hasn't played yet starts at `00:00` of a new period
- AND has a long shift (>2 minutes)
- That player is the new goaltender

**Check 3: Game-Wide Analysis (Fallback)**
When starter + backup patterns aren't obvious:

For all players on the team:
1. Calculate **total time on ice** for entire game
2. Calculate **total number of shifts** for entire game
3. Player who meets ALL criteria:
   - Total time ≈ (remaining game time after starter left)
   - Total shifts < 5 (goaltenders rarely rotate more than 2-3 times)
   - Starter total + Backup total ≈ 59-60 minutes

**Multiple Changes:**
- Rare, but possible
- Apply same logic recursively
- Track current goaltender as game progresses

#### Phase 3: Track Goaltender Throughout Game

For each second of the game:
- **If goaltender is on ice:** Include their `playerId` in output
- **If goaltender is pulled:** Set `goaltender: null`
- **Never have 2 goaltenders on ice simultaneously**

**Common Pull Scenarios:**
1. **Delayed penalty:** Temporarily off for extra attacker (10-30 seconds)
2. **Extra attacker:** End of game, trailing team pulls goalie (30-120 seconds)
3. **Performance/injury:** Permanent replacement (rest of game)

## Shift Timing Logic

### The Core Challenge

NHL shift data has overlapping timestamps when players change on-the-fly:
- **Departing player:** startTime="00:00", endTime="00:32", duration="00:32"
- **Incoming player:** startTime="00:32", endTime="01:21", duration="00:49"

Both players are marked as "on ice" at second 32, which would incorrectly show too many players.

### The Solution: Period-by-Period Processing

Instead of creating one continuous timeline, we process each period independently. This approach:
- Eliminates period boundary issues
- Naturally handles overtime periods of varying lengths
- Ensures accurate time-on-ice calculations

**Each period has seconds 0-1200 (1201 data points representing a 20-minute period):**
- Second 0 = special case (period starters only)
- Seconds 1-1200 = regular play

**1. Second 0 of Each Period (Special Case)**
- At the start of each period (seconds_into_period = 0), ONLY include players with startTime="00:00"
- This captures the period starters cleanly
- Applies to all periods (1, 2, 3, and OT)

**2. Regular Seconds (1-1200)**
- Players are on ice from `startTime + 1` through `endTime` (inclusive)
- This gives the **departing player priority** - they remain on ice through their endTime
- The incoming player starts the NEXT second
- Example: Player A ends at 0:32 (on ice at second 32), Player B starts at 0:32 (on ice starting second 33)

**3. Period Boundary Handling**
- At the end of each period, ALL players come off the ice (period clock stops)
- Valid seconds_into_period range: 0-1200 for regulation (20 minutes), 0-300 for OT (5 minutes)
- Each period is processed independently, so no overlap between periods
- The next period starts fresh with only the period starters at second 0

**4. Goal Verification**
- Players must be on ice at their endTime (e.g., goal scored at 19:19 means player is on ice at second 1159)
- This confirms departing players have priority at transition moments

### Timeline Structure

**Regulation game:**
- Period 1: seconds_into_period 0-1200 (seconds_elapsed_game 0-1200)
- Period 2: seconds_into_period 0-1200 (seconds_elapsed_game 1201-2401)
- Period 3: seconds_into_period 0-1200 (seconds_elapsed_game 2402-3602)
- **Total: 3603 seconds**

**With overtime:**
- Period 4: seconds_into_period 0-300 for regular season (seconds_elapsed_game 3603-3903)
- Period 4+: seconds_into_period 0-1200 for playoff overtime (20-minute periods)

### JSON Structure

```json
[
  {
    "period": 1,
    "seconds_into_period": 0,
    "seconds_elapsed_game": 0,
    "skaters": {
      "6": {
        "onIce": [8478550, 8479325, 8480012, 8476923, 8477956],
        "count": 5,
        "goaltender": 8477507
      },
      "22": {
        "onIce": [8474641, 8477498, 8479365, 8479368, 8480831],
        "count": 5,
        "goaltender": 8478971
      }
    }
  }
]
```

### CSV Structure

Each row represents one second of the game:

```csv
period,seconds_into_period,seconds_elapsed_game,teamA,teamB,teamAskaters,teamAcount,teamAgoaltender,teamBskaters,teamBcount,teamBgoaltender
1,0,0,6,22,"[8477507,8478042,8478401,8479325,8479999]",5,8480280,"[8474641,8477498,8479365,8479368,8480831]",5,8478971
1,1,1,6,22,"[8477507,8478042,8478401,8479325,8479999]",5,8480280,"[8474641,8477498,8479365,8479368,8480831]",5,8478971
```

**CSV Column Descriptions:**
- `period` - Period number (1, 2, 3, or 4)
- `seconds_into_period` - Seconds elapsed in current period (0-1199)
- `seconds_elapsed_game` - Total seconds elapsed in game
- `teamA` - Team ID of first team (lower teamId)
- `teamB` - Team ID of second team (higher teamId)
- `teamAskaters` - Array of playerIds on ice for teamA (formatted as `[id,id,id]`)
- `teamAcount` - Number of skaters on ice for teamA
- `teamAgoaltender` - PlayerId of goaltender on ice for teamA (empty if pulled)
- `teamBskaters` - Array of playerIds on ice for teamB (formatted as `[id,id,id]`)
- `teamBcount` - Number of skaters on ice for teamB
- `teamBgoaltender` - PlayerId of goaltender on ice for teamB (empty if pulled)

### Team Ordering

- Teams are identified by `teamId` (numerical)
- Ordered numerically (lower teamId first)
- No home/away designation (not available in shift data)

### Game Length

- **Regulation:** 3 periods × 1200 seconds = 3600 seconds
- **Regular season OT:** Period 4, 300 seconds (5 minutes)
- **Playoff OT:** Period 4+, 1200 seconds each (20 minutes), continues until goal
- **Shootout:** Period 5, skip (not timed)

## Usage

### Single Game

```bash
cd onice
python process_shifts.py GAME_NUMBER SEASON
```

**Example:**
```bash
python process_shifts.py 631 2025
```

**Input:** `../2025/shifts/2025020631.json`  
**Outputs:** 
- JSON: `output/json/2025020631.json`
- CSV: `output/csv/2025020631.csv`

### Batch Processing

Process multiple games in sequence:

```bash
cd onice
python process_shifts.py START_GAME END_GAME SEASON
```

**Example:**
```bash
python process_shifts.py 600 631 2025
```

This will process games 600 through 631 (inclusive) for the 2025 season.

**Note:** 
- If output files already exist, they will be replaced with new data
- If an input file is missing, it will be skipped with a warning

## Edge Cases & Validation

### Multiple Shifts Per Player
- Players can have multiple shifts per period
- Sum durations across all shifts in a period to detect goaltenders

### Goaltender Pulled Multiple Times
- Track each pull/return
- Set `goaltender: null` only when actually off ice

### No Goaltender On Ice
- Valid scenario (extra attacker situations)
- Both teams can simultaneously have no goaltender

### Data Quality Issues
- Some shifts may have timing inconsistencies
- `duration` should equal `endTime - startTime`
- If mismatch, use `startTime` and `endTime` as source of truth

### Maximum Players On Ice
- NHL rules: Maximum 6 players per team (including goaltender)
- If data shows >6, this indicates a data quality issue
- Log warning but process anyway

## Algorithm Performance

- Game length: ~3600 seconds (regulation)
- Typical shifts per game: 600-800
- Processing complexity: O(n × m) where n = shifts, m = game seconds
- Expected runtime: <1 second per game

## Future Enhancements

1. ~~CSV output format~~ ✅ **COMPLETED**
2. Batch processing (multiple games)
3. Validation reports (data quality checks)
4. Integration with situationCode timeline for power play analysis
5. Playoff overtime handling (20-minute OT periods)
