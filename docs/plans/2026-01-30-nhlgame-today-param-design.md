# nhlgame.py "today" Parameter Design

## Overview

Add a `today` parameter to `nhlgame.py` that automatically determines the game range to download based on saved data and today's schedule.

## Command Interface

**Existing mode (unchanged):**
```bash
python nhlgame.py 720 725
```
Downloads games 2025020720 through 2025020725.

**New mode:**
```bash
python nhlgame.py today
```
Automatically determines start (last saved + 1) and end (today's first game - 1).

## New Functions

### `get_last_saved_game() -> int | None`

1. Look in `data/2025/boxscores/` directory
2. List all `.json` files matching pattern `2025020*.json`
3. Extract game numbers from filenames (e.g., `2025020724.json` → `724`)
4. Return the highest game number found
5. Return `None` if directory is empty or doesn't exist

### `get_todays_first_game() -> int | None`

1. Get today's date in `YYYY-MM-DD` format
2. Call `https://api-web.nhle.com/v1/schedule/{date}`
3. Parse the JSON response to extract game IDs
4. Filter for regular season games matching current season/game type (`2025020*`)
5. Return the lowest game ID number found
6. Return `None` if no games scheduled today

## Exit Scenarios

### Scenario A: No saved games found
```
Error: No saved games found in data/2025/boxscores/
Run with explicit game IDs first: python nhlgame.py START END
```
Exit code 1.

### Scenario B: No games scheduled today
```
No games scheduled for today (2026-01-30).
Most recent saved game: 2025020724
```
Exit code 0 (informational, not an error).

### Scenario C: Already caught up
```
Already caught up!
Last saved: 2025020857
Next game (today): 2025020858
```
Exit code 0.

### Scenario D: Games to download
```
NHL Game Data Downloader
Season: 2025
Game Type: 02
Game Range: 0725 to 0857
Rate Limit: 9 seconds between requests
...
```
Proceeds with normal download flow.

## Implementation Flow

The `main()` function logic:

```
1. Check arguments
   - If arg[1] == "today": enter today-mode
   - Else: use existing two-argument mode (unchanged)

2. Today-mode flow:
   a. Call get_last_saved_game()
      - If None → error, exit 1
      - Else → start_game = last_saved + 1

   b. Call get_todays_first_game()
      - If None → print "no games today" status, exit 0
      - Else → end_game = first_today - 1

   c. Compare start_game vs end_game
      - If start_game > end_game → print "caught up" status, exit 0
      - Else → proceed with download loop (existing code)
```

## Files Modified

- `v1/nhlgame.py` - Add two new functions and modify `main()` argument handling

## Dependencies

- Uses existing `requests` library for API calls
- Uses `datetime` module for today's date (already imported)
- Uses `pathlib.Path` for directory scanning (already imported)

## Notes

- No changes to `download_game()`, `fetch_endpoint()`, or other helper functions
- Existing download logic remains untouched
- Data directory path: `data/2025/boxscores/`
- Schedule API endpoint: `https://api-web.nhle.com/v1/schedule/{YYYY-MM-DD}`
