# Postponed Games Tracking Design

## Overview

Track games that were postponed and need to be re-downloaded later when they are actually played.

## Problem

Some games are postponed after being scheduled. When we download data for these games:
- The boxscore API returns `gameState: "FUT"` (future)
- The shifts HTML may not exist or be empty
- We need to come back later to get the actual game data

Example: Game 2025020828 was postponed.

## Solution

Create a `postponed_games.json` file that tracks games needing re-download.

### Detection

When downloading a game, check the boxscore response for:
- `gameState: "FUT"` - Game not yet played
- `gameState: "PPD"` - Game postponed (if this exists)

### Tracking File

Location: `data/2025/postponed_games.json`

```json
{
  "games": [
    {
      "gameId": "2025020828",
      "originalDate": "2026-01-28",
      "reason": "gameState=FUT",
      "detectedAt": "2026-01-31T10:30:00Z"
    }
  ]
}
```

### Workflow

1. During download, if `gameState` indicates game not played:
   - Log to `postponed_games.json`
   - Skip shifts download (will fail anyway)
   - Continue to next game (don't stop)

2. Periodically run a check command:
   ```bash
   python nhlgame.py check-postponed
   ```
   - Re-check each game in the postponed list
   - If now `gameState: "OFF"` (finished), re-download all data
   - Remove from postponed list

### New Command

```bash
python nhlgame.py check-postponed
```

Re-downloads any postponed games that have now been played.

## Implementation Tasks

1. Add `gameState` check after boxscore download
2. Create `log_postponed_game()` function
3. Skip shifts for postponed games
4. Add `check-postponed` command
5. Update documentation

## Notes

- Don't treat postponed games as errors
- Keep existing data (partial boxscore may have rescheduled date info)
- May need to check meta endpoint for reschedule info
