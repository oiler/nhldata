# Plan: Add Strength Column to Timeline Output

## Goal
Add a `strength` column to timeline output (both JSON and CSV) that normalizes situationCode to a team-agnostic skater representation.

## Why This Matters

**Strength is team-agnostic.** Both `1451` (home PP) and `1541` (away PP) map to strength `5v4`.

When a goalie is pulled for a delayed penalty, the situationCode changes (e.g., 1541 → 0641) but the effective strength remains the same (5v4). The strength column enables:
- Filtering by game situation regardless of which team has advantage
- Grouping equivalent situations (all 5v4 power plays together)
- Analysis that ignores home/away distinction

## Algorithm

```python
def situationcode_to_strength(code: str) -> str:
    """Convert situationCode to normalized strength."""
    # Penalty shots
    if code in ('0101', '1010'):
        return 'N/A'

    # Parse digits: [awayGoalie][awaySkaters][homeSkaters][homeGoalie]
    away_goalie = int(code[0])
    away_skaters = int(code[1])
    home_skaters = int(code[2])
    home_goalie = int(code[3])

    # Normalize: if goalie pulled, that team has an extra attacker
    # Subtract 1 to get effective strength
    if away_goalie == 0:
        away_skaters -= 1
    if home_goalie == 0:
        home_skaters -= 1

    # Format with larger number first
    high = max(away_skaters, home_skaters)
    low = min(away_skaters, home_skaters)
    return f"{high}v{low}"
```

## Changes to `v2/timelines/generate_timeline.py`

1. **Add `situationcode_to_strength()` function** (lines ~311-348)

2. **Update `generate_timeline()` function** (~line 409)
   - After calculating `situation_code`, also calculate `strength`
   - Add `'strength': strength` to entry dict

3. **Update `write_csv_output()` function** (~line 525-538)
   - Add `'strength'` column to header after `situationCode`
   - Add strength value to data rows

4. **Update JSON output structure** (no code change needed - just add strength to entry)

## Output Changes

### CSV Header (new column after situationCode)
```
period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,...
```

### JSON Entry (new field)
```json
{
  "period": 2,
  "secondsIntoPeriod": 1339,
  "situationCode": "0641",
  "strength": "5v4",
  ...
}
```

## Verification

Run on game 620 to verify various situations:
```bash
uv run python v2/timelines/generate_timeline.py 620 2025
```

Verified combinations from game 620:
- `1551` → `5v5` (normal play)
- `1541` → `5v4` (away PP)
- `1451` → `5v4` (home PP - same as away PP, team-agnostic)
- `1441` → `4v4` (coincidental penalties)
- `1331` → `3v3` (OT)
- `0431` → `3v3` (pulled goalie normalized: 4-1=3)
- `1431` → `4v3`

## Status

**Completed** - 2026-02-05

Changes made:
- Added `situationcode_to_strength()` function
- Updated `generate_timeline()` to include strength in entries
- Updated `write_csv_output()` to include strength column
- Updated `v2/timelines/README.md` with new field in output examples
