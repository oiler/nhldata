# Season toggle for 2025-26 and 2026-27 — Design

**Date:** 2026-09-29
**Status:** Spec, pending oiler review
**Related:** `BACKLOG.md` items "Keep the deployed browser current during the season", "Extend the goalie pipeline to 2026-27", and "Scheduled and on-demand Edge refresh"

## Problem

The 2026-27 regular season opens on 2026-09-29, and the daily orchestrator switched to `NHL_SEASON=2026` on the same day. From 2026-09-30, `data/2026/generated/browser/league.db` grows every morning. The browser can't show it:

- `SEASONS = ["2025"]` in `v2/browser/app.py:7`, and the season filter bar is hidden (`display:none`, `app.py:84`). The `store-season` store uses `memory` storage (`app.py:61`), a workaround from when 2024-25 was hidden.
- Pages can't import `SEASONS` or `DEFAULT_SEASON` from `app.py` without a circular import, because `app.py` loads the pages. Each page hard-codes `"2025"` instead: `games.py:37`, `teams.py:65`, `team.py:181`, `skaters.py:81`, `player.py:138`, `goalies.py:42`, `elites.py:123`, `filters.py:9` and `:97`, and the `db.py` defaults.
- The skaters page loads Edge bursts once at import for 2025 only (`skaters.py:35`) and takes the Age cutoff from a 2025-only dict (`skaters.py:22`). Age depends on the Edge CSV's `birth_date` column, so a season without an Edge fetch has no ages.
- The player page looks up metadata in 2025, then 2024 (`player.py:105`), so a player whose first season is 2026-27 has no name.
- `season_date_range()` (`filters.py:9`) falls back to `(yr-1)-10-01` through `yr-06-30` when a season has no games. Seasons are keyed by start year, so the fallback for `"2026"` returns the 2025-26 window. This fallback applies to 2026 until the first daily run builds its `league.db`.

## Goal

In local dev, a user switches between 2025-26 and 2026-27 with the season filter, and every page shows the selected season's data, or says plainly that data for that season isn't available.

Success means:

- The season filter is visible, lists `2025-26` and `2026-27`, and opens on 2025-26.
- Games, teams, team, skaters, player, goalies, and elites pages all follow the selected season. No page falls back to a hard-coded `"2025"`.
- Age displays for every season whose players table carries `birthDate`, with or without Edge data.
- A season without Edge bursts shows an em dash in SB/a60 and Max MPH instead of failing.
- A season without goalie data shows a "not yet available" message on `/goalies` and on the team page's goalie section.
- Next season's rollover is a change to one file, `v2/browser/seasons.py`.

## Non-goals

- **Deploy freshness.** The deployed site stays image-baked. Keeping it current is the `BACKLOG.md` item "Keep the deployed browser current during the season".
- **Goalie data for 2026-27.** The goalie pipeline stays 2021–2025. See the `BACKLOG.md` item "Extend the goalie pipeline to 2026-27".
- **Automated Edge refresh.** Edge bursts for 2026-27 come from a manual run. See the `BACKLOG.md` item "Scheduled and on-demand Edge refresh".
- **Re-enabling 2024-25.** It stays out of `SEASONS`.
- **Automatic default switching.** oiler changes `DEFAULT_SEASON` by hand when 2026-27 has enough games.
- **`edm.db`.** No page reads it (`db.query()` has no callers). It stays as is.

## Design

### Season config: `v2/browser/seasons.py`

A new module with no imports from the app or pages, so every module can import it:

| Name | Value or behavior |
|---|---|
| `SEASONS` | `["2025", "2026"]`, oldest first; the order the filter shows |
| `DEFAULT_SEASON` | `"2025"`; oiler flips it to `"2026"` by hand |
| `season_label(season)` | `"2025"` → `"2025-26"` |
| `age_cutoff(season)` | `date(int(season), 9, 15)`, the NHL convention for age as of Sept 15 of the start year |

Values stay 4-digit start years everywhere (stores, queries, paths). Only the filter labels use `season_label()`.

### App shell: `app.py`

- `app.py` imports `SEASONS` and `DEFAULT_SEASON` from `seasons.py` and drops its own definitions.
- The filter bar loses `display:none`. The radio options use `season_label()` for labels.
- `store-season` switches back to `storage_type="session"`, as the comment at `app.py:58` directs once `SEASONS` has more than one entry. Update that comment and the one at `app.py:82` to describe the new state.

### Pages and shared modules

- Every `season or "2025"` becomes `season or DEFAULT_SEASON`, and every `season: str = "2025"` default becomes `season: str = DEFAULT_SEASON`: `games.py`, `teams.py`, `team.py`, `skaters.py`, `player.py`, `goalies.py`, `elites.py`, `filters.py`, `db.py`, and `burst_data.py`.
- `player.py` layout looks up `_META_SQL` in each season of `SEASONS`, newest first, and uses the first match. Current team and position then come from the most recent season the player appears in.
- `elites.py` keeps reading its season from the URL, defaulting to `DEFAULT_SEASON`.
- `game.py` needs no change; it derives the season from the game ID.

### Date-range fallback: `filters.py`

`season_date_range()` falls back to `f"{yr}-10-01"` through `f"{yr + 1}-06-30"`, where `yr = int(season)`. The query path doesn't change.

### Age from player data

- `build_league_db.py`'s `build_players_table()` adds a `birthDate` column (ISO `YYYY-MM-DD` text) from each player JSON's `birthDate` field.
- The skaters page's `_COMP_SQL` selects `p.birthDate`. Age is `_age_on(birthDate, age_cutoff(season))`. `_AGE_CUTOFFS` goes away, and Age no longer reads `birth_date` from the burst CSV.
- Existing databases need a rebuild to gain the column. The implementation ends by running `python v2/browser/build_league_db.py 2025` and, once `data/2026` has games, `python v2/browser/build_league_db.py 2026`. The daily orchestrator run keeps the 2026 database current after that. The skaters page doesn't guard against a missing column; a database without it is a build that hasn't been rerun.
- A player with a null `birthDate` shows an em dash for Age.

### Edge bursts per season

- `skaters.py` drops the import-time `_BURSTS_DF`. A module-level `functools.lru_cache` wrapper, `_bursts_for(season)`, calls `load_bursts(season)` and returns the frame indexed by `playerId`. The skaters callback joins `_bursts_for(season)`.
- The cache lasts for the process lifetime. Burst CSVs change only on a manual Edge run, and in local dev you restart the app after one.
- `load_bursts()` keeps its current contract: an empty frame and a logged warning in local dev, and a `RuntimeError` in production. That error now fires on the first request for the season instead of at import. The sync guard in the "Deploy guard" section keeps production from reaching it.
- A season without a CSV shows an em dash in SB/a60 and Max MPH, using the same rendering as missing TOI (commit `53c2290`).
- `player.py`'s `_load_bursts()` is already per-season and tolerates a missing file. No change.

### Goalie sections for seasons without goalie data

- `/goalies` already renders "No goalie data for this season." for an empty result. Change the text to `"{season_label(season)} goalie data isn't available yet."`.
- `team.py`'s `_goalie_environment_section()` renders the same message when `team_environment` has no rows for the season, instead of an empty section.

### Deploy guard

Deploy freshness is out of scope, but the code in this design can still be deployed. Without guard changes, a deploy would ship a `2026-27` option with no data behind it. Extend both guards to 2026:

- `tools/sync-runtime-data.sh` copies `data/2026/generated/browser/league.db` and `data/2026/generated/edge/player_bursts.csv` into `runtime_data/2026/`, adds them to its non-empty check, and runs `verify_runtime_data.py` for 2026 as well as 2025.
- The Dockerfile `RUN` guard lists `runtime_data/2026/league.db` and `runtime_data/2026/player_bursts.csv`.

The result: a deploy refuses to proceed until 2026-27 has a `league.db` and an Edge burst CSV covering at least 80% of its skaters (`DEFAULT_MIN_OVERLAP` in `verify_runtime_data.py`). A stale 2026 burst CSV fails that check as the season adds skaters, which signals that an Edge refresh is due.

## Testing

Each test goes red before the change that makes it pass, and uses synthetic data (the pattern in `test_player_metrics.py` and `test_deployment_metrics.py`).

| Test | Proves | Fails before the change because |
|---|---|---|
| `season_date_range("2026")` against a missing or empty DB returns `("2026-10-01", "2027-06-30")` | The fallback maps start year to season | It returns `("2025-10-01", "2026-06-30")` |
| `age_cutoff("2026") == date(2026, 9, 15)`; `season_label("2026") == "2026-27"` | The config helpers | `seasons.py` doesn't exist |
| Age for a player born on 2000-09-16 is 25 for season 2026, and 26 for one born on 2000-09-15 | Cutoff boundary through `birthDate` | Age comes from the 2025-only dict |
| `build_players_table()` on synthetic player JSONs writes a `birthDate` column | The DB build carries birth dates | The column doesn't exist |
| Player metadata lookup returns the newest season's row when a player is in both seasons, and the 2026 row when the player is only in 2026 | Lookup order across `SEASONS` | Lookup is hard-wired to 2025, then 2024 |
| `_bursts_for("2026")` with no CSV returns an empty frame in local dev, and `_bursts_for` loads each season's own CSV | Per-season burst loading | Bursts load once, for 2025, at import |

`load_bursts()`'s production-raise behavior already has tests in `test_burst_data.py`, which stay as is. The deploy guard changes are shell and Dockerfile edits; verify them by running `./tools/sync-runtime-data.sh` once with the 2026 files present and once with the 2026 burst CSV missing. The second run must exit non-zero.

Before finishing, run `python -m pytest v2/ -v`, then start the app locally and switch seasons on each page.

## Rollover next season

1. Add the new start year to `SEASONS` in `v2/browser/seasons.py`.
2. Add the season's `league.db` and burst CSV to `tools/sync-runtime-data.sh` and the Dockerfile guard.
3. When the new season has enough games, set `DEFAULT_SEASON` to it.
