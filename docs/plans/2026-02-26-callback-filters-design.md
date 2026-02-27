# Callback Filters — Design Document

## Problem

All browser pages use static `layout()` functions that query the database once at page load. There's no way to filter data by date range or home/away. Adding interactive filters requires refactoring pages to use Dash callbacks.

## Solution

Refactor 4 pages (games, skaters, team, player) from static layouts to callback-driven pages with server-side filtering. Each page gets a filter bar with date range pickers and (on 3 pages) a home/away toggle. Filters re-query the database and recalculate aggregated stats.

## Pages Affected

| Page | Date Range | Home/Away | Aggregation |
|---|---|---|---|
| Games (`/games`) | Yes | No | None — just filter rows |
| Skaters (`/skaters`) | Yes | Yes | Reaggregate TOI, competition, wPPI |
| Team (`/team/<abbrev>`) | Yes | Yes | Reaggregate player stats + filter game log |
| Player (`/player/<player_id>`) | Yes | Yes | Filter per-game rows (summary stats later) |
| Game detail (`/game/<game_id>`) | No | No | Untouched |

## Refactoring Pattern

Current:
```
layout() → query DB → build HTML → return static page
```

New:
```
layout() → return title + filter bar + empty container
callback(date_start, date_end, home_away) → query DB with filters → build HTML → update container
```

Each page defines its own callback since each has different SQL, URL parameters, and output structure.

## Filter Bar

Consistent layout across all filtered pages, built by a shared utility:

```
[Start Date: [____]]  [End Date: [____]]  [All] [Home] [Away]
```

- **Date pickers**: `dcc.DatePickerSingle` for start and end. Default to the season's first and last game dates (full season on initial load).
- **H/A toggle**: Three inline `html.Button` elements styled as a button group. "All" active by default. Only on skaters, team, and player pages.
- Shared utility `v2/browser/filters.py` provides `make_filter_bar(page_id, include_home_away=True)` for consistent UI.

## SQL Changes

### Games page

Straightforward row filtering:

```sql
WHERE awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
```

### Skaters page

Join games table to access `gameDate`, add date and H/A filtering:

```sql
JOIN games g ON c.gameId = g.gameId
WHERE g.gameDate BETWEEN ? AND ?
  AND (? = 'all' OR (? = 'home' AND c.team = g.homeTeam_abbrev)
                  OR (? = 'away' AND c.team = g.awayTeam_abbrev))
```

Aggregation (TOI/GP, vs Top Fwd %, etc.) recalculates from the filtered rows. PPI/PPI+ pulled from `player_metrics` (fixed). wPPI/wPPI+/avg_toi_share computed in Python from filtered data.

### Team page

Same pattern for the player stats query. Game log query also filtered:

```sql
WHERE gameDate BETWEEN ? AND ?
  AND (? = 'all' OR (? = 'home' AND homeTeam_abbrev = ?)
                  OR (? = 'away' AND awayTeam_abbrev = ?))
```

### Player page

Already joins games. Add date and H/A clauses to the existing query.

## Metric Recalculation

**Fixed (full season, from player_metrics table):**
- PPI — physical attribute (height/weight)
- PPI+ — percentile of PPI

**Recalculated from filtered data in Python:**
- wPPI — PPI * (player_avg_toi / league_avg_toi) for filtered window
- wPPI+ — percentile of wPPI for filtered window
- avg_toi_share — 5 * player_toi / team_total_toi per game, averaged
- TOI/GP, vs Top Fwd %, vs Top Def %, OPP F TOI, OPP D TOI

The wPPI calculation logic already exists in `build_league_db.py`. The callback replicates it in a few lines of pandas over the filtered competition data.

## Shared Utility

`v2/browser/filters.py` provides:

- `make_filter_bar(page_id, include_home_away=True)` — returns filter controls HTML with unique component IDs namespaced by `page_id`
- `season_date_range(season)` — returns (min_date, max_date) from the games table for default date picker values

## What Doesn't Change

- Game detail page — untouched
- Database schema — no changes to league.db
- `build_league_db.py` — player_metrics still pre-computed for full season
- Orchestrator — untouched
- `db.py` — league_query stays the same

## Player Page — Future Summary Stats

The player page callback will be structured to support season summary stats in a future update. The callback will already have the filtered game data in a dataframe, so computing and displaying summary stats is a matter of adding a section above the game log table when ready.
