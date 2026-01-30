# NHL Situation Timeline Generator

Generates clean situationCode timelines from play-by-play data for accurate time-on-ice calculations by game strength.

## Quick Start

```bash
cd timelines
python generate_timeline.py GAME_NUMBER SEASON
```

**Example:**
```bash
python generate_timeline.py 591 2025
```

This will:
- Read: `../2025/plays/2025020591.json`
- Output: `output/2025/timeline_2025020591.json`

## What It Does

Creates a clean timeline of situationCode changes containing only:
1. **period-start** - Beginning of each period
2. **period-end** - End of each period  
3. **faceoff** - Every faceoff (shows current situationCode)
4. **delayed-penalty** - When delayed penalty is called
5. **penalty-expired** - Synthetic events when penalties expire (even during play)

## Key Features

✅ **Smart coincidental penalty cancellation** - Groups penalties by type (roughing, fighting, etc.) and cancels matching counts between teams

✅ **Accurate penalty tracking** - Only tracks net penalties after coincidental cancellation

✅ **Synthetic expiration events** - Inserts penalty expirations at exact times, even during play

✅ **Delayed penalty cleanup** - Logs only the start, actual penalty, and resumption faceoff

✅ **No duplicates** - Prevents processing the same penalties multiple times

## Output Format

JSON file with this structure:

```json
{
  "gameId": 2025020591,
  "season": 20252026,
  "gameType": 2,
  "homeTeam": {"id": 13, "abbrev": "FLA"},
  "awayTeam": {"id": 14, "abbrev": "TBL"},
  "situationTimeline": [
    {
      "eventId": 54,
      "eventType": "period-start",
      "periodNumber": 1,
      "periodType": "REG",
      "maxRegulationPeriods": 3,
      "timeInPeriod": "00:00",
      "timeRemaining": "20:00",
      "secondsIntoPeriod": 0,
      "secondsElapsedGame": 0,
      "situationCode_before": null,
      "situationCode_after": "1551",
      "isSynthetic": false,
      "isDelayedPenalty": false,
      "penaltyExpiration": null
    },
    {
      "eventId": null,
      "eventType": "penalty-expired",
      "periodNumber": 1,
      "periodType": "REG",
      "maxRegulationPeriods": 3,
      "timeInPeriod": "05:25",
      "timeRemaining": "14:35",
      "secondsIntoPeriod": 325,
      "secondsElapsedGame": 325,
      "situationCode_before": "1451",
      "situationCode_after": "1551",
      "isSynthetic": true,
      "isDelayedPenalty": false,
      "penaltyExpiration": {
        "originalEventId": 106,
        "penaltyDesc": "cross-checking",
        "penaltyDuration": 2,
        "teamId": 14
      }
    }
  ]
}
```

## SituationCode Format

**Format:** `[Away Goalie][Away Skaters][Home Skaters][Home Goalie]`

**Common Codes:**
- `1551` = 5v5 even strength
- `1451` = Home power play (away has 4, home has 5)
- `1541` = Away power play (home has 4, away has 5)
- `1441` = 4v4 (both teams penalized)

See `SITUATIONCODE_REFERENCE.md` for complete reference.

## Use Cases

### Time-on-Ice by Strength
Query the timeline to find the situationCode at any moment, then calculate time-on-ice for shifts:

```python
# Example: Player shift from 300s to 420s
for entry in timeline:
    if entry['secondsElapsedGame'] <= 300:
        situation_at_start = entry['situationCode_after']
    if entry['secondsElapsedGame'] <= 420:
        situation_at_end = entry['situationCode_after']

# Calculate time at each strength between 300s and 420s
```

### Power Play Analysis
Filter for entries where situationCode indicates power play (e.g., `1451` or `1541`).

### Penalty Kill Tracking
Find when teams are shorthanded and track defensive performance.

## Directory Structure

```
timelines/
├── generate_timeline.py      # Main script
├── README.md                  # This file
└── output/                    # Generated timeline files
    ├── 2025/
    │   ├── timeline_2025020591.json
    │   └── ...
    ├── 2024/
    │   └── ...
    └── 2023/
        └── ...
```

## Technical Details

### Penalty Tracking Logic

1. **Collect all penalties at same timestamp**
2. **Group by penalty type (descKey)** - e.g., "roughing", "fighting", "cross-checking"
3. **Cancel coincidentals by type** - If HOME has 2 roughing and AWAY has 2 roughing, they cancel
4. **Track only net penalties** - Remaining penalties after cancellation
5. **Combine consecutive penalties** - Same player with multiple penalties serves them consecutively

### Example: 5 Penalties at 03:25

```
HOME: Player A - 2x roughing
AWAY: Player B - 2x roughing  
AWAY: Player C - 1x cross-checking

Cancellation:
  Roughing: HOME 2, AWAY 2 → Cancel 2 from each = 0 net
  Cross-checking: HOME 0, AWAY 1 → 1 net AWAY penalty

Result: Track only 1 penalty (Player C cross-checking)
```

### Synthetic Expiration Events

When penalties expire during play (not at a stoppage), synthetic events are inserted:

- Calculated expiration time: `penalty_start + duration_minutes * 60`
- Inserted at exact second
- Recalculates situationCode based on remaining active penalties
- No coincidental cancellation at expiration (only applies when penalties are assessed)

### Goal During Power Play

When a goal is scored during a power play:
- The earliest-expiring **minor** penalty on the shorthanded team is removed
- Major penalties are NOT affected by goals
- SituationCode is recalculated

## Requirements

- Python 3.7+
- Input: Play-by-play JSON files from NHL API (via `nhlgame.py`)
- No external dependencies

## Related Files

- `../plays/flatten_plays.py` - Converts play-by-play to CSV
- `SITUATIONCODE_REFERENCE.md` - Complete situationCode documentation
- `../nhlgame.py` - Downloads raw game data from NHL API
