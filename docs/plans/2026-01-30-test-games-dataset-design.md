# Test Games Dataset Design

## Overview

Build a curated dataset of ~20 NHL games that provide comprehensive coverage of all situationCode variations. This dataset will serve as a validation test suite for future analytics projects.

## Goals

1. **Primary:** Cover as many unique situationCodes as possible with minimal games
2. **Secondary:** Prioritize games with high situationCode diversity (many codes, many transitions)
3. **Constraint:** Maximum 20 games in the final dataset

## Project Structure

**New directory:**
```
tools/
  discover_test_games.py   # Discovery/analysis script
```

**Output files:**
```
resources/
  game_analysis.csv        # Full ranked list of all games
  TEST_GAMES.md            # Manually curated final 20 games
```

## Discovery Script

`tools/discover_test_games.py` will:

1. Scan all play-by-play files in `data/2025/plays/`
2. For each game, calculate:
   - List of unique situationCodes found
   - Count of unique situationCodes
   - Count of situationCode transitions (changes from one code to another)
3. Rank games by unique codes (primary), transitions (tiebreaker)
4. Output to console: Top 40 games with their codes and counts
5. Export to CSV with columns:
   - `game_id`
   - `unique_codes` (count)
   - `transitions` (count)
   - `codes_list` (comma-separated list of codes found)

**Usage:**
```bash
python tools/discover_test_games.py
```

No arguments needed - scans the standard data directory.

## Curated Test Games File

After reviewing CSV output, manually create `resources/TEST_GAMES.md`:

```markdown
# NHL Test Games Dataset

## Selection Criteria
- Maximum 20 games
- Prioritized by situationCode diversity
- Combined coverage target: all observed situationCodes

## Coverage Summary
Total unique situationCodes covered: XX
Codes covered: 1551, 1451, 1541, 1441, 0651, ...

## Test Games

| Game ID | Unique Codes | Transitions | Codes |
|---------|--------------|-------------|-------|
| 2025020XXX | 8 | 24 | 1551, 1451, 1541, 1441, 0651, ... |
| 2025020XXX | 7 | 19 | 1551, 1351, 1531, ... |
| ... | ... | ... | ... |

## Codes Not Yet Covered
- 0340 (both goalies pulled - extremely rare)
- ...
```

## Workflow

1. **Run discovery script** - Generates ranked list and CSV
2. **Review and select** - Pick ~20 games maximizing coverage using greedy approach
3. **Document selections** - Create TEST_GAMES.md with final list and coverage notes
4. **Use in testing** - Future projects reference TEST_GAMES.md for validation

## SituationCode Reference

Format: `[Away Goalie][Away Skaters][Home Skaters][Home Goalie]`

**Realistic universe (~27-36 codes):**
- Both goalies in (1__1): 9 combinations (1331 through 1551)
- Away goalie pulled (0__1): 9 combinations (0431 through 0651)
- Home goalie pulled (1__0): 9 combinations (1340 through 1560)
- Both goalies pulled (0__0): 9 combinations (extremely rare)

## Dependencies

- Python 3
- pathlib, json (standard library)
- Existing play-by-play data in `data/2025/plays/`

## Future Enhancements

Penalty edge case coverage (Table 13 scenarios) can be added in a future iteration after the core situationCode dataset is established.
