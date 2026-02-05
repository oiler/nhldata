# Play-by-Play CSV Flattener Design

## Purpose

Flatten NHL play-by-play JSON data into a browsable CSV for spreadsheet analysis.

## Input

- `data/{season}/plays/{gameId}.json` - Play-by-play JSON file

## Output

- `data/{season}/generated/flatplays/{gameId}.csv` - One row per play, all nested fields flattened to columns

## Script Location

```
tools/
  flatten_plays.py
```

## Usage

```bash
# Single game
uv run python tools/flatten_plays.py 153 2025

# Range of games
uv run python tools/flatten_plays.py 1 100 2025
```

## Flattening Strategy

Nested objects become dot-notation columns:

```json
{
  "periodDescriptor": {"number": 1, "periodType": "REG"},
  "details": {"xCoord": 25, "yCoord": -10}
}
```

Becomes columns: `periodDescriptor.number`, `periodDescriptor.periodType`, `details.xCoord`, `details.yCoord`

## Implementation Steps

1. Load JSON, extract `plays` array
2. First pass: scan all plays to discover all possible column paths
3. Second pass: build rows with values (blank if missing)
4. Write CSV with sorted column headers

## Column Ordering

1. Core fields first: `eventId`, `situationCode`, `typeDescKey`, `timeInPeriod`, `timeRemaining`
2. Period fields: `periodDescriptor.*`
3. Details fields: `details.*` (alphabetical)
4. Remaining fields (alphabetical)
