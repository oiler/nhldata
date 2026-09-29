# Season toggle for 2025-26 and 2026-27 — Design

**Date:** 2026-09-29
**Status:** Approved by oiler on 2026-09-29
**Related:** `BACKLOG.md` items "Keep the deployed browser current during the season", "Extend the goalie pipeline to 2026-27", and "Scheduled and on-demand Edge refresh"

## Problem

The 2026-27 regular season opens on 2026-09-29, and the daily orchestrator switched to `NHL_SEASON=2026` on the same day. From 2026-09-30, `data/2026/generated/browser/league.db` is rebuilt every morning. The browser can't show it:

- `SEASONS = ["2025"]` in `v2/browser/app.py:7`, and the season filter bar is hidden (`style={"display": "none"}`, `app.py:99`). The `store-season` store uses `memory` storage (`app.py:61`), a workaround from when 2024-25 was hidden.
- Pages can't import `SEASONS` or `DEFAULT_SEASON` from `app.py` without a circular import, because `app.py` loads the pages. Each page hard-codes `"2025"` instead: `games.py:37`, `teams.py:65`, `team.py:181`, `skaters.py:81`, `player.py:138`, `goalies.py:42`, `elites.py:123`, `filters.py:9`, `:16` (the integer `else 2025`), and `:97`, `burst_data.py:24`, and the `db.py` defaults.
- The skaters page loads Edge bursts once at import for 2025 only (`skaters.py:35`) and joins them onto every season (`skaters.py:160`), so selecting 2026-27 would show 2025-26 burst values beside 2026-27 stats. The Age cutoff comes from a 2025-only dict (`skaters.py:22`), and Age depends on the burst CSV's `birth_date` column.
- The player page looks up metadata in 2025, then 2024 (`player.py:105`), so a player whose first season is 2026-27 has no name.
- `season_date_range()` (`filters.py:9`) falls back to `(yr-1)-10-01` through `yr-06-30` when a season has no scored games. Seasons are keyed by start year, so the fallback for `"2026"` returns the 2025-26 window.
- Early in a season, `build_league_db.py` fails. When no skater has at least 5 games, `build_player_metrics_table()` returns without creating `player_metrics` (`build_league_db.py:156-158`), and `build_constants_table()` then reads that table unconditionally (`build_league_db.py:825`) and raises `no such table`. The daily run's 2026 build fails this way for roughly the first two weeks of the season, leaving a partial `league.db`.
- Table links in the browser are DataTable markdown anchors (`markdown_options={"link_target": "_self"}`), which reload the page. The season radio has no persistence, so any season other than the default would reset to `DEFAULT_SEASON` on every table link click.

## Goal

In local dev, a user switches between 2025-26 and 2026-27 with the season filter, and every season-aware page shows the selected season's data, or says plainly that data for that season isn't available.

Success means:

- The season filter lists `2025-26` and `2026-27`, opens on 2025-26, and matches DESIGN.md.
- The season filter shows only on season-aware pages: games, teams, team, skaters, player, and goalies. Each of those follows the selected season, and none falls back to a hard-coded `"2025"`.
- A selected season survives full page loads in the same tab, including table link clicks.
- When a season isn't ready, season-aware pages say `"2026-27 data isn't available yet."` instead of a date-range message. The "Season not ready" section defines ready.
- A deploy never waits on 2026-27. The default season's files must pass every check, or the deploy is refused. Any other season ships only when its files pass the same checks, and is otherwise left out of the image and shows as not available.
- `build_league_db.py` completes for a season where no skater has 5 games.
- Age displays for every skater with a `birthDate`, with or without Edge data.
- A season without Edge bursts shows an em dash in SB/a60 and Max MPH, never another season's values.
- A season without goalie data shows a "not yet available" message on `/goalies` and on the team page's goalie section.
- Next season's browser rollover is a one-line change to `SEASONS` in `v2/browser/seasons.py`. The deploy guards (`tools/sync-runtime-data.sh`, `Dockerfile`, `.gitignore`) name each season's files explicitly, so each rollover edits them too, as listed in the "Rollover next season" section.

## Non-goals

- **Deploy freshness.** The deployed site stays image-baked. Keeping it current is the `BACKLOG.md` item "Keep the deployed browser current during the season".
- **Goalie data for 2026-27.** The goalie pipeline stays 2021–2025. See the `BACKLOG.md` item "Extend the goalie pipeline to 2026-27".
- **Automated Edge refresh.** Edge bursts for 2026-27 come from a manual run. See the `BACKLOG.md` item "Scheduled and on-demand Edge refresh".
- **Re-enabling 2024-25.** It stays out of `SEASONS`. The player metadata lookup drops its 2024 fallback, so a 2024-only player shows as `Player {id}`. No season-aware page links to one, because `/elites?season=2024` now normalizes to `DEFAULT_SEASON`. `runtime_data/2024/league.db` keeps shipping; removing it is separate cleanup.
- **`/elites` following the filter.** `/elites` is unlinked and hidden from the nav. It keeps reading `?season=` from the URL.
- **Automatic default switching.** oiler changes `DEFAULT_SEASON` by hand when 2026-27 has enough games.
- **`edm.db`.** No page reads it: `db.query()` is called only by `available_teams()`, which has no callers. It stays as is.

## Design

### Season config: `v2/browser/seasons.py`

A new module that imports only `datetime.date`, so every module can import it:

| Name | Value or behavior |
|---|---|
| `SEASONS` | `["2025", "2026"]`, oldest first; the order the filter shows |
| `DEFAULT_SEASON` | `"2025"`; oiler flips it to `"2026"` by hand |
| `normalize_season(value)` | Returns `value` if it's in `SEASONS`, otherwise `DEFAULT_SEASON` |
| `season_label(season)` | `f"{y}-{(y + 1) % 100:02d}"` where `y = int(season)`; `"2025"` → `"2025-26"` |
| `age_cutoff(season)` | `date(int(season), 9, 15)`, the NHL convention for age as of Sept 15 of the start year |

Values stay 4-digit start years everywhere (stores, queries, paths). Only user-facing text (filter labels and "not available" messages) uses `season_label()`.

`normalize_season()` guards every place a season value enters from the client (the store, the radio, and the `/elites` query string). A season string is joined into a file path by `runtime_paths.league_db()` and passed to `int()` by `goalies.py:44` and `team.py:81`, so an unknown value must never reach them.

### App shell: `app.py`

- `app.py` imports `SEASONS`, `DEFAULT_SEASON`, and `season_label` from `seasons.py` and drops its own definitions.
- The filter bar gets an `id` (`season-bar`) and loses its hard-coded `display:none`. A `toggle_season_bar` callback on `url.pathname`, modeled on `toggle_goalie_situation_bar` (`app.py:314-318`), shows it only on `/games`, `/teams`, `/team/*`, `/skaters`, `/player/*`, and `/goalies`.
- The radio options use `season_label()` for labels.
- `filter-season` gets `persistence=True, persistence_type="session"`, so the selection survives full page loads in the same tab. `store-season` stays `memory` and keeps following the radio through `sync_season`. Rewrite the comments at `app.py:58-60` and `app.py:82-85` to describe this.
- `sync_season` passes the radio value through `normalize_season()`.
- Style the radio to DESIGN.md. Replace the inline `labelStyle` and `inputStyle` with a `season-options` class. In `assets/style.css`, set option labels to `color: var(--text)`, `text-transform: none`, and `letter-spacing: 0`; set `accent-color: var(--navy)` on the inputs; and give rows a `40px` height under the `640px` breakpoint. Scope the eyebrow `.filter-bar label` rule to the group label, for example with a class on `html.Label("Season")`.
- The Max MPH glossary entry (`app.py:162-163`) drops "2025-26" and its season-specific figures (league average and leader) and describes "the selected season's regular-season ice time". The Age example (`app.py:143`) and the goalie coverage line (`app.py:207`) stay accurate as written.

### Pages and shared modules

- Every `season or "2025"` becomes `normalize_season(season)`, and every `season: str = "2025"` default becomes `season: str = DEFAULT_SEASON`: `games.py`, `teams.py`, `team.py`, `skaters.py`, `player.py`, `goalies.py`, `elites.py`, `filters.py`, `db.py`, and `burst_data.py`.
- A new `db.player_meta(pid, seasons=SEASONS)` looks up `_META_SQL` in each season, newest first, and returns the first match or `None`. `player.py`'s layout calls it. Current team and position come from the most recent season the player appears in.
- `elites.py` passes its `season` query argument through `normalize_season()`.
- `game.py` needs no change; it derives the season from the game ID.
- `build_league_db.py`'s CLI default (`:39`) keeps `"2025"`. It isn't a page, and the orchestrator always passes the season.

### Season not ready

A new `runtime_paths.season_ready(season)` decides whether a season has data to show:

| Mode | Ready when |
|---|---|
| Production (`DATA_DIR` set) | Both `league_db(season)` and `player_bursts_csv(season)` exist. The sync script copies a non-default season into the image only when its files pass every check, so presence means verified. |
| Local dev | `league_db(season)` exists. Burst columns show em dashes when the CSV is missing. |

When a season isn't ready, games, teams, team, skaters, and player return `html.P(f"{season_label(season)} data isn't available yet.")` before running their queries. When it's ready, the existing date-range messages stay. `2026-27` stays in the filter either way.

### Early-season database: `build_league_db.py`

The two build bullets in this section shipped on 2026-09-29, ahead of the rest of this spec, so the daily run builds 2026 during the opening weeks. Tests: `test_player_metrics_empty_table_when_no_one_eligible` and `test_constants_empty_table_when_no_one_eligible`. The page bullet remains open.

- When nothing is eligible, `build_player_metrics_table()` writes an empty `player_metrics` table with its full schema (`playerId, ppi, ppi_plus, wppi, wppi_plus, avg_toi_share`) instead of returning without one.
- `build_constants_table()` writes an empty `constants` table (its key/value schema) when `player_metrics` is empty.
- Every other table builder must also complete on a season's first games. The test in the "Testing" section runs the full build to prove it; a builder that fails gets the same empty-table treatment.
- Pages treat an empty `player_metrics` or `constants` as missing values: an em dash for PPI+ and wPPI+ cells, and no wPPI+ where it needs the league mean. They don't raise.

### Date-range fallback: `filters.py`

`season_date_range()` falls back to `f"{yr}-09-01"` through `f"{yr + 1}-06-30"`, where `yr = int(normalize_season(season))`. September 1 covers a late-September opener, as in 2026-27. The query path doesn't change.

### Age from player data

- `build_players_table()` adds `"birthDate"` to its `keep` list. `players.csv` already carries it as ISO `YYYY-MM-DD` text for every season.
- `_recover_missing_players()` adds `"birthDate": d.get("birthDate")` to each recovered row. This matters: 198 of 940 skaters in the 2025 `players` table enter only through this JSON recovery path, and all of them show an Age today through the burst CSV.
- A new `utils.age_in_season(birth_date, season)` returns the integer age at `age_cutoff(season)`, or `None` for a missing birth date. It replaces `skaters.py`'s `_age_on()` and `_AGE_CUTOFFS`.
- The skaters page's `_COMP_SQL` selects `p.birthDate`, the `update_skaters` groupby carries it with `birthDate=("birthDate", "first")`, and Age is `age_in_season(birthDate, season)`.
- The skaters page doesn't guard against a missing `birthDate` column. The deploy guard catches a stale database in production, and locally a database without the column is a build that hasn't been rerun.

### Edge bursts per season

- A new `burst_data.bursts_for(season)` wraps `load_bursts(season)` in `functools.lru_cache` and returns the frame indexed by `playerId`. It lives in `burst_data.py`, which has no Dash import.
- `skaters.py` drops the import-time `_BURSTS_DF` and joins only `bursts_per_60` and `speed_max_mph` from `bursts_for(season)`. `BURST_COLUMNS` keeps `birth_date` as part of the Edge CSV contract; the browser ignores it.
- In runtime mode (`is_runtime_mode()`), `skaters.py` calls `bursts_for(s)` at import for each season in `SEASONS` where `season_ready(s)` is true, so a present-but-empty CSV in production still fails boot, as `burst_data.py` intends. A season left out of the image is skipped. Local dev loads lazily.
- `load_bursts()` keeps its contract: an empty frame and a logged warning in local dev, and a `RuntimeError` in production.
- Missing SB/a60, Max MPH, and Age values stay NaN. Their column formats add `.nully("—")`, for example `Format(precision=2, scheme=Scheme.fixed).nully("—")` for the burst columns and `Format().nully("—")` for Age. The columns stay numeric, so native sort and filter keep working.
- `player.py`'s `_load_bursts()` is already per-season and tolerates a missing file. No change.

### Goalie sections for seasons without goalie data

- `/goalies` already renders "No goalie data for this season." for an empty result. Change the text to `f"{season_label(season)} goalie data isn't available yet."`.
- `team.py`'s `_goalie_environment_section()` shows the heading and the same message only when `goalies.db` has no rows for the season at all (`SELECT 1 FROM team_environment WHERE season = ? LIMIT 1` returns nothing). When the season exists but the team's row doesn't, it keeps omitting the section, as it does today.

### Text and contract updates

Update prose that the design makes wrong:

- `burst_data.py`: the module docstring and the error text at `:40`. Age no longer depends on the burst CSV, and in production a missing CSV fails at import through the preload in `skaters.py`.
- `Dockerfile:37-41`: the comment that the skaters page raises at import (still true in runtime mode, now through the preload for ready seasons). Also update its list of gitignored season directories, and note that optional seasons may be absent.
- `verify_runtime_data.py:6`: "blank Age/SB-a60/Max-MPH" becomes "blank SB/a60 and Max MPH".

### Deploy guard

Deploy freshness is out of scope, but the code in this design can still be deployed. The guard treats seasons in two tiers, named explicitly in `tools/sync-runtime-data.sh`:

| Tier | Seasons | Check fails or files missing |
|---|---|---|
| Required | 2025 (the default season) | The sync exits non-zero, as today, and the deploy is refused |
| Optional | 2026 | The sync removes `runtime_data/2026/`, prints a `WARNING` line naming the failed check, and exits 0. The deploy proceeds, and 2026-27 shows as not available |

- For an optional season, the sync script stages `league.db` and `player_bursts.csv` in a temporary directory, runs every check there, and moves them into `runtime_data/<season>/` only when all checks pass. A previously synced copy is removed on failure, so a stale season never ships beside a failed one.
- The checks are the same for both tiers: non-empty files, `verify_runtime_data.py` burst coverage of at least 80% (`DEFAULT_MIN_OVERLAP`), and a new `birthDate` check.
- `verify_runtime_data.py` gains the `birthDate` check: `players` has a `birthDate` column (`PRAGMA table_info(players)`), and at least 95% of distinct F/D `playerId`s in `competition` have a non-null `birthDate`. That catches a database built before this change and a recovery path that drops birth dates.
- The Dockerfile `RUN` guard keeps listing only required files (2024, 2025, `edm.db`, and `goalies.db`). It doesn't list 2026 files, because their absence is a valid state.
- `.gitignore` adds `v2/browser/runtime_data/2026/`.

The result: a 2025-only fix always deploys. 2026-27 appears in production once a sync finds a complete `league.db` and an Edge burst CSV covering at least 80% of its skaters. If a later 2026 Edge CSV slips under 80%, the next deploy drops 2026-27 back to not available, and the sync's `WARNING` line says why. Rerunning the Edge fetch fixes it.

### Rollout order

The orchestrator runs `build_league_db.py` from the main checkout, and `data/` is gitignored, so a branch has no data tree of its own. Until this change is merged to master, every 08:00 run rebuilds the 2026 database with the old code: no `birthDate`, and a failed build while the season is under 5 games per skater. After merging, run `python v2/browser/build_league_db.py 2025` and `python v2/browser/build_league_db.py 2026` from the main checkout. The daily run keeps 2026 current from then on.

## Testing

Each test goes red before the change that makes it pass, and uses synthetic data (the pattern in `test_player_metrics.py` and `test_deployment_metrics.py`).

| Test | Unit | Fails before the change because |
|---|---|---|
| A full build on synthetic competition rows where every skater has fewer than 5 games completes, and `player_metrics` and `constants` exist with 0 rows | `build_league_db` builders, run in `main()` order | `build_constants_table` raises `no such table: player_metrics` |
| `season_date_range("2026")` returns `("2026-09-01", "2027-06-30")` for a missing DB, and for a DB whose `games` table has no scored games | `filters.season_date_range` | It returns `("2025-10-01", "2026-06-30")` |
| `season_label("2026") == "2026-27"`; `age_cutoff("2026") == date(2026, 9, 15)`; `normalize_season` returns `DEFAULT_SEASON` for `"2024"`, `"../x"`, and `None` | `seasons.py` | The module doesn't exist |
| `age_in_season("2000-09-16", "2026") == 25`, `age_in_season("2000-09-15", "2026") == 26`, and `age_in_season(None, "2026") is None` | `utils.age_in_season` | The function doesn't exist, and `_AGE_CUTOFFS` has no 2026 entry |
| `build_players_table()` on a synthetic `players.csv` (monkeypatch `build_league_db.PLAYERS_CSV`) writes a `birthDate` column | `build_league_db.build_players_table` | `birthDate` isn't in `keep` |
| `_recover_missing_players()` on a synthetic player JSON writes that player's `birthDate`. The `_setup_recovery_db()` fixture in `test_player_metrics.py` gains the column. | `build_league_db._recover_missing_players` | The recovered row has no `birthDate` |
| `player_meta` returns the newest season's row for a player in both seasons, the 2026 row for a player only in 2026, and `None` for an unknown player. Two synthetic `league.db` files under a monkeypatched `DATA_DIR`. | `db.player_meta` | The function doesn't exist |
| `bursts_for("2026")` with no CSV returns an empty frame in local dev, and `bursts_for` returns each season's own CSV. The test monkeypatches `burst_data.player_bursts_csv` to `tmp_path` files and calls `bursts_for.cache_clear()` in a fixture. | `burst_data.bursts_for` | The function doesn't exist |
| The `birthDate` check fails for a DB whose `players` table has no `birthDate` column, and for one where under 95% of F/D skaters have a birth date | `verify_runtime_data` | The check doesn't exist |
| `season_ready` in production mode is false when either file is missing and true when both exist; in local dev it depends only on `league.db`. Files under a monkeypatched `DATA_DIR` in `tmp_path`. | `runtime_paths.season_ready` | The function doesn't exist |

`load_bursts()`'s production-raise behavior already has tests in `test_burst_data.py`, which stay as is.

Verify the sync script by running `./tools/sync-runtime-data.sh` four ways:

1. With 2026 files present and passing: exits 0, and `runtime_data/2026/` holds both files.
2. With the 2026 burst CSV missing: exits 0, prints a `WARNING` for 2026, and `runtime_data/2026/` doesn't exist, even if an earlier sync created it.
3. With a 2026 burst CSV that has a header only, or covers under 80% of skaters: same as case 2, with the failed check named.
4. With a 2025 file missing or failing a check: exits non-zero.

Before finishing, run `python -m pytest v2/ -v`, then start the app locally and check each item:

- Switch seasons on each season-aware page.
- Select 2026-27 on Skaters, click a player link, and confirm the player page shows 2026-27. Reload, and confirm the radio and page content still agree.
- The season filter shows only on season-aware pages and matches DESIGN.md at desktop and phone widths.
- SB/a60, Max MPH, and Age show an em dash where data is missing and still sort numerically.

## Rollover next season

1. Add the new start year to `SEASONS` in `v2/browser/seasons.py`.
2. Add the new season to the optional tier in `tools/sync-runtime-data.sh`, and add its `runtime_data/<season>/` directory to `.gitignore`.
3. When the new season has enough games, set `DEFAULT_SEASON` to it, move it to the required tier in `tools/sync-runtime-data.sh`, and add its files to the Dockerfile guard.
