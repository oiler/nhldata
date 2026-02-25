# 2024 Season Support — Status & Blockers

## Current Behavior

When clicking the "2024" radio button in the season selector:
1. The `dcc.Store` updates to "2024"
2. Nothing else happens — all pages keep showing 2025 data

## Blockers

### 1. No generated data for 2024

Raw API data exists in `data/2024/`:
- `boxscores/` — 1,314 JSON files
- `meta/` — 1,314 JSON files
- `plays/` — 1,314 JSON files
- `shifts/` — 3,938 files

But `data/2024/generated/` does not exist. The processing pipeline has not been run to create:
- `competition/*.csv`
- `flatboxscores/boxscores.csv`
- `players/csv/players.csv`
- `browser/league.db`

### 2. `build_league_db.py` hardcoded to 2025

```python
SEASON_DIR = "data/2025"  # hardcoded, no CLI arg or function parameter
```

Same issue in `build_edm_db.py`.

### 3. `db.py` missing 2024 in `_LEAGUE_DB_PATHS`

The league query path mapping only has 2025:

```python
_LEAGUE_DB_PATHS = {
    "2025": _PROJECT_ROOT / "data" / "2025" / "generated" / "browser" / "league.db",
}
```

The older `_DB_PATHS` (for edm.db) does have a 2024 entry, but the league-wide mapping does not.

### 4. Pages don't read the season from the store

Every page calls `league_query()` without passing a `season=` parameter:

- `skaters.py`: `league_query(_SQL)` — defaults to 2025
- `games.py`: `league_query(_SQL)` — defaults to 2025
- `player.py`: `league_query(_META_SQL, params=(pid,))` — defaults to 2025
- `team.py`: `league_query(_PLAYER_SQL, params=(abbrev,))` — defaults to 2025
- `game.py`: three `league_query()` calls — all default to 2025

The season radio buttons sync to `dcc.Store("store-season")`, but no page layout reads from that store.

## What Full 2024 Support Requires

1. **Run the data pipeline** on 2024 raw API data to generate `data/2024/generated/` (competition CSVs, flatboxscores, players CSV)
2. **Parameterize `build_league_db.py`** (and `build_edm_db.py`) to accept a season argument
3. **Add 2024 to `_LEAGUE_DB_PATHS`** in `db.py`
4. **Convert pages to callback-driven layouts** that read from `store-season` and pass `season=` to all `league_query()` calls
5. **Build `data/2024/generated/browser/league.db`**

## Notes

- PPI/PPI+ are physical attributes (height/weight) — they won't differ between seasons unless a player's listed measurements change
- wPPI, wPPI+, and avg_toi_share would differ because deployment patterns change season to season
- The `test_smoke.py` test at line 39 also hardcodes the 2025 DB path
