# NHL Data Browser - Web Interface Design

**Date:** 2026-02-12
**Status:** Prototyping with Datasette (EDM only) before building final static site

## Problem

Make NHL timeline and player data publicly browsable via a web interface. Key use cases:
- Team-specific dashboards showing player ice time by strength (5v5, 5v4, etc.)
- League-wide rankings (e.g., players by height/weight scaled by ice time)
- Team and player comparisons

## Phase 1: Datasette Prototype (EDM Only)

Before committing to a full frontend design, build a SQLite database with all Oilers 2025 data and explore it with Datasette to discover what views and aggregations matter.

### Why Datasette

- Instant web UI for browsing, filtering, sorting, and querying SQLite
- No frontend code required — focus entirely on the data
- Supports arbitrary SQL queries for ad-hoc exploration
- Helps answer: what tables, columns, and aggregations does the final site need?

### Data Scope

- **Team:** Edmonton Oilers (EDM, teamId=22)
- **Season:** 2025 (58 games)
- **Sources:** flat boxscores, flat plays, raw boxscore JSONs, shift JSONs, timeline CSVs, players CSV

### SQLite Schema

#### `games` — 58 rows
From flat boxscores CSV + meta JSONs.
```
gameId, gameDate, opponent, homeAway,
edmGoals, oppGoals, result, periodCount
```

#### `players` — ~34 rows
From players CSV, filtered to currentTeamAbbrev=EDM.
```
playerId, firstName, lastName, sweaterNumber, position,
heightInInches, weightInPounds, birthDate, birthCountry, shootsCatches
```

#### `player_game_stats` — ~2,300 rows (EDM players only)
From raw boxscore JSONs (the flat boxscores lack per-player stats).
```
playerId, gameId, position, goals, assists, points, plusMinus,
pim, hits, sog, faceoffWinningPctg, toi, blockedShots,
shifts, giveaways, takeaways, powerPlayGoals
```

#### `plays` — ~20,000 rows (both teams)
From flat plays CSVs, all 48 columns, filtered to 58 EDM games.
```
(all columns from flat plays files)
```

#### `shifts` — ~29,000 rows (both teams)
From shift JSONs (home + away per game).
```
gameId, playerName, sweaterNumber, teamType,
shiftNumber, period, startTime, endTime, duration
```

#### `timelines` — ~209,000 rows (both teams)
From generated timeline CSVs.
```
gameId, period, secondsIntoPeriod, secondsElapsedGame,
situationCode, strength, awayGoalie, awaySkaterCount,
awaySkaters, homeSkaterCount, homeGoalie, homeSkaters
```

**Total:** ~260,000 rows across 6 tables.

### Build Script

Python script (`v2/browser/build_edm_db.py`) that:
1. Reads flat boxscores CSV → filters to 58 EDM games → `games` table
2. Reads players CSV → filters to EDM → `players` table
3. Parses 58 raw boxscore JSONs → extracts EDM player stats → `player_game_stats` table
4. Reads 58 flat play CSVs → `plays` table
5. Parses 116 shift JSONs (home + away per game) → `shifts` table
6. Reads 58 timeline CSVs → `timelines` table

Output: `data/2025/generated/browser/edm.db`

### Usage

```bash
pip install datasette
datasette data/2025/generated/browser/edm.db
```

### What We're Exploring

- What aggregations are useful? (per-player season totals vs. per-game breakdowns)
- What derived metrics matter? (5v5 TOI per game, size scaled by ice time)
- How should timeline data be pre-aggregated for the final site?
- What views/pages should the final static site have?

## Phase 2: Final Static Site (All 32 Teams)

Decisions from Phase 1 will inform the final design. Preliminary decisions:

### Architecture: Static site with pre-rendered HTML + CSV data files

Inspired by [thescoop.org/umdwbb-data](https://thescoop.org/umdwbb-data/) — a zero-dependency static site (vanilla HTML/CSS/JS) that loads CSV files client-side.

- **No database** — Python build step generates aggregated CSVs, JS fetches and renders them
- **No backend server** — hosted on GitHub Pages for free
- **Python stays central** — all data processing and HTML generation in Python (Jinja2 templates)
- **Daily batch updates** — regenerate CSVs, push to repo, site updates automatically

### URL Routing: Clean paths + query params for filters

```
/teams/EDM/               → Oilers dashboard
/teams/EDM/?strength=5v5  → filtered to 5v5
/rankings/                → league-wide rankings
/rankings/?sort=toi_5v5   → sorted by 5v5 ice time
/compare/?teams=EDM,CGY   → side-by-side comparison
```

- GitHub Pages serves `/teams/EDM/` → `/teams/EDM/index.html` natively
- JS reads `URLSearchParams` for filter state
- `history.replaceState()` keeps URL bar in sync
- All views are bookmarkable and shareable

### Site Structure (pre-rendered)

```
site/
├── index.html                    → season/league landing
├── teams/
│   ├── index.html                → all teams list
│   ├── EDM/
│   │   └── index.html            → team dashboard
│   └── ... (32 teams)
├── rankings/
│   └── index.html                → league-wide rankings
├── compare/
│   └── index.html                → comparison tool
└── data/
    ├── teams/
    │   ├── EDM.csv
    │   └── ...
    └── rankings.csv
```

### Tech Stack

- **Data processing:** Python (pandas, existing pipeline)
- **HTML generation:** Python + Jinja2 templates
- **Frontend:** Vanilla HTML/CSS/JavaScript (no frameworks)
- **Hosting:** GitHub Pages (free, `.nojekyll`)
- **Data format:** CSV files fetched client-side via `fetch()`

## Approaches Considered and Rejected

### SQLite + FastAPI + HTMX
- Server-rendered approach with real query flexibility
- Rejected because: adds infrastructure overhead, data volume doesn't require a database, static approach is simpler and free

### Pre-computed static JSON + lightweight API
- Hybrid static + dynamic approach
- Rejected because: splits hosting, most complex to maintain

## Source Data Available (Full Season)

- **901 timeline files** — second-by-second situationCode + playerIds on ice
- **774 players** — height, weight, position, team, draft info, game logs
- **909 boxscores** — per-game TOI, goals, assists, etc.
- **908 flat play files** — 48-column play-by-play events
- **1,817 shift files** — per-player shift-by-shift data
- All linked by consistent 8-digit `playerId`
