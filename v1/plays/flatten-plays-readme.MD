# NHL Play-by-Play Data Flattener

Convert nested JSON play-by-play data into flat CSV format for easier analysis in spreadsheets, databases, or data tools.

## Purpose

This script takes the complex nested JSON structure from NHL play-by-play endpoints and flattens it into a simple CSV where each row is one play event.

## What It Does

### Flattening Rules:

1. **Adds game_id as first column** - Every row gets the full game ID (e.g., `2025020393`)

2. **Flattens periodDescriptor** - Nested object becomes flat columns:
   ```json
   "periodDescriptor": {
     "number": 1,
     "periodType": "REG",
     "maxRegulationPeriods": 3
   }
   ```
   Becomes:
   ```
   periodNumber, periodType, maxRegulationPeriods
   1, REG, 3
   ```

3. **Flattens details object** - All fields moved to parent level:
   ```json
   "details": {
     "xCoord": -45,
     "yCoord": -4,
     "shotType": "wrist"
   }
   ```
   Becomes:
   ```
   xCoord, yCoord, shotType
   -45, -4, wrist
   ```

4. **Preserves all other fields** - Any remaining nested arrays/objects are converted to JSON strings

## Usage

### Basic Command:
```bash
python flatten_plays.py GAME_NUMBER SEASON
```

### Examples:

Flatten game 393 from 2025 season:
```bash
python flatten_plays.py 393 2025
```
- Reads: `2025/plays/2025020393.json`
- Outputs: `plays_2025020393.csv`

Flatten game 1 from 2024 season:
```bash
python flatten_plays.py 1 2024
```
- Reads: `2024/plays/2024020001.json`
- Outputs: `plays_2024020001.csv`

## Input File Location

The script expects your JSON files to be organized as:
```
SEASON/
  plays/
    GAMEIDS.json
```

For example:
```
2025/
  plays/
    2025020393.json
    2025020394.json
2024/
  plays/
    2024020001.json
```

## Output Format

The CSV will have:
- **First column:** `game_id`
- **Remaining columns:** All flattened fields from the play events
- **One row per play event**

Example output columns:
```
game_id, eventId, periodNumber, periodType, timeInPeriod, timeRemaining, 
situationCode, typeDescKey, xCoord, yCoord, shotType, shootingPlayerId, ...
```

## Column Handling

- Columns are automatically detected from your data
- All plays may not have all columns (some events have different fields)
- Missing values appear as empty cells in CSV
- Nested arrays/objects (if any remain) are stored as JSON strings

## Use Cases

1. **Quick exploration** - Open CSV in Excel/Google Sheets to browse plays
2. **Filtering** - Find specific event types or situations
3. **Importing to databases** - Easy to load into PostgreSQL, SQLite, etc.
4. **Data analysis** - Work with plays in pandas, R, or other tools

## Tips

### Working with Multiple Games

Create a batch script to process multiple games:
```bash
#!/bin/bash
for i in {1..50}; do
  python flatten_plays.py $i 2025
done
```

### Combining Multiple CSVs

After creating multiple CSVs, combine them:
```bash
# Keep header from first file, then append all data
head -n 1 plays_2025020001.csv > all_plays_2025.csv
tail -n +2 -q plays_202502*.csv >> all_plays_2025.csv
```

### Opening in Excel

If you have special characters or the CSV doesn't open correctly:
1. Open Excel
2. Use "Data" → "From Text/CSV"
3. Select UTF-8 encoding
4. Import

## Next Steps

Once you have CSV files:
- Analyze in spreadsheets for quick exploration
- Load into Snowflake for SQL analysis
- Use for data validation before building full pipeline
- Understand the schema before designing your database tables

## Notes

- Script only processes the "plays" array from the JSON
- Assumes regular season games (game type "02")
- Output files are created in the current directory
- Each run creates a new CSV (overwrites if file exists)