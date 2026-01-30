# HTML Shifts Scraper Design

## Overview

Update `nhlgame.py` to replace API-based shifts fetching with HTML scraping from NHL's official Time-on-Ice reports. The NHL shifts API frequently returns empty data for 2024-2025+ seasons, requiring this HTML fallback approach.

## Files Affected

| Action | File | Purpose |
|--------|------|---------|
| Create | `v1/nhlgame_api_shifts.py.bak` | Preserve old API shifts code |
| Modify | `v1/nhlgame.py` | Replace shifts endpoint with HTML scraping |

## Key Behavior Changes

| Aspect | Old (API) | New (HTML) |
|--------|-----------|------------|
| Source | `api.nhle.com/stats/rest/en/shiftcharts` | `nhl.com/scores/htmlreports/.../TH*.HTM` + `TV*.HTM` |
| Requests per game | 1 | 2 (home + away) |
| Output files | `{gameId}.json` | `{gameId}_home.json` + `{gameId}_away.json` |
| Rate limit | 9 seconds | 5 seconds (between shift requests) |
| Error handling | Log and continue | Retry 5x (10s delay), then stop |

## Dependencies

- `beautifulsoup4` - HTML parsing
- `lxml` or `html5lib` - fallback parsers

---

## URL Construction

**Pattern:**
```
https://www.nhl.com/scores/htmlreports/{SEASON_ID}/{REPORT_CODE}{GAME_NUM}.HTM
```

**Report codes:**
- `TH` = Home team shifts
- `TV` = Away team shifts

**Conversion from game ID:**
```
Game ID:    2025020001
            ↓
Season ID:  20252026  (year + year+1, derived automatically)
Game Num:   020001    (last 6 digits)
```

**Example URLs:**
- Home: `https://www.nhl.com/scores/htmlreports/20252026/TH020001.HTM`
- Away: `https://www.nhl.com/scores/htmlreports/20252026/TV020001.HTM`

---

## Fetching Logic

**Fetch sequence for each game:**
```
1. Fetch TH{game_num}.HTM (home shifts)
2. Wait 5 seconds
3. Fetch TV{game_num}.HTM (away shifts)
4. Wait 5 seconds (before next endpoint)
```

**Retry logic (per request):**
```
attempt = 1
while attempt <= 5:
    response = fetch(url)
    if success:
        break
    wait 10 seconds
    attempt += 1

if still failed after 5 attempts:
    STOP script entirely
    report: game ID, URL, error details
```

**Request order within a game:**
```
1. shifts (home)     ← HTML, 5s delay
2. shifts (away)     ← HTML, 5s delay
3. plays             ← API, 9s delay
4. meta              ← API, 9s delay
5. boxscores         ← API, no delay (last)
```

---

## Output JSON Structure

Each file (`{gameId}_home.json` or `{gameId}_away.json`) contains:

```json
{
  "gameId": "2025020001",
  "teamType": "home",
  "team": {
    "abbrev": "FLA",
    "name": "Florida Panthers"
  },
  "source": {
    "url": "https://www.nhl.com/scores/htmlreports/20252026/TH020001.HTM",
    "fetchedAt": "2026-01-29T14:30:00Z"
  },
  "players": [
    {
      "number": 63,
      "name": "Brad Marchand",
      "position": "LW",
      "shifts": [
        {
          "shiftNumber": 1,
          "period": 1,
          "startTime": "00:00",
          "endTime": "00:34",
          "duration": "00:34",
          "event": null
        },
        {
          "shiftNumber": 2,
          "period": 1,
          "startTime": "03:03",
          "endTime": "04:18",
          "duration": "01:15",
          "event": null
        }
      ],
      "periodSummary": [
        {"period": 1, "shifts": 8, "avgDuration": "00:45", "toi": "06:02", "evToi": "05:12", "ppToi": "00:50", "shToi": "00:00"},
        {"period": 2, "shifts": 9, "avgDuration": "00:52", "toi": "07:48", "evToi": "06:30", "ppToi": "01:18", "shToi": "00:00"},
        {"period": 3, "shifts": 7, "avgDuration": "00:48", "toi": "05:36", "evToi": "04:45", "ppToi": "00:51", "shToi": "00:00"}
      ],
      "gameTotals": {
        "shifts": 24,
        "avgDuration": "00:48",
        "toi": "19:26",
        "evToi": "16:27",
        "ppToi": "02:59",
        "shToi": "00:00"
      }
    }
  ]
}
```

**Notes:**
- `event` field captures goal (G), penalty (P), etc. from NHL data; `null` if none
- `source` block provides traceability back to the HTML report
- Times kept as strings (MM:SS) matching NHL's format

---

## HTML Parsing Approach

**Parser strategy:**
BeautifulSoup with fallback parsers (NHL's HTML can be inconsistent):

```python
parsers = ['lxml', 'html.parser', 'html5lib']
for parser in parsers:
    try:
        soup = BeautifulSoup(html, parser)
        if soup.find_all('table'):
            break
    except:
        continue
```

**Parsing steps:**
1. Fetch HTML page
2. Find all player sections (identified by player name/number headers)
3. For each player:
   - Extract player info (number, name, position)
   - Parse shifts table (shift #, period, start, end, duration, event)
   - Parse period summary table
   - Parse game totals row
4. Assemble into JSON structure

**Validation checks during parsing:**
- Confirm we found at least 1 player (empty page = error)
- Confirm shifts have required fields (period, start, end)
- Log warnings for unexpected formats but continue if data is usable

**Team info extraction:**
The HTML header contains team name and abbreviation - extract from page rather than hardcoding.

---

## Error Handling

**Error scenarios and responses:**

| Scenario | Response |
|----------|----------|
| HTTP 404 (page not found) | Retry 5x, then STOP |
| HTTP timeout | Retry 5x, then STOP |
| HTTP other error (500, etc.) | Retry 5x, then STOP |
| HTML parses but no players found | STOP immediately (malformed data) |
| HTML parses but missing fields | STOP immediately (data integrity) |

**Stop behavior:**
When stopping, script outputs:
```
ERROR: Failed to fetch shifts data
  Game ID: 2025020001
  URL: https://www.nhl.com/scores/htmlreports/20252026/TH020001.HTM
  Attempts: 5
  Last error: HTTP 503 Service Unavailable

Script stopped. Fix the issue and resume from game 0001.
```

---

## Full Script Flow

**Per game:**
```
┌─ Game 2025020001 ─────────────────────────────┐
│  1. Fetch shifts (home) ← HTML               │
│     └─ retry up to 5x if failed              │
│     └─ save 2025020001_home.json             │
│  2. Wait 5s                                   │
│  3. Fetch shifts (away) ← HTML               │
│     └─ retry up to 5x if failed              │
│     └─ save 2025020001_away.json             │
│  4. Wait 5s                                   │
│  5. Fetch plays ← API                        │
│  6. Wait 9s                                   │
│  7. Fetch meta ← API                         │
│  8. Wait 9s                                   │
│  9. Fetch boxscores ← API                    │
└───────────────────────────────────────────────┘
Wait 9s → Next game
```

---

## Configuration

Existing config values in `nhlgame.py` remain, with additions:

```python
# Existing
SEASON = "2025"
GAME_TYPE = "02"
RATE_LIMIT_SECONDS = 9

# New
SHIFT_RATE_LIMIT_SECONDS = 5
SHIFT_RETRY_ATTEMPTS = 5
SHIFT_RETRY_DELAY_SECONDS = 10
```

---

## Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Output format | Player-centric JSON | Matches how NHL presents data |
| Files per game | 2 (home + away) | Mirrors NHL's source structure |
| File naming | `{gameId}_home.json` / `{gameId}_away.json` | Flat structure, easy to find |
| Season derivation | Automatic (year → year+1) | Simpler than config/lookup |
| Error handling | Stop on failure | Data integrity is critical |
| Old code preservation | Separate `.bak` file | Easy to restore if API improves |
