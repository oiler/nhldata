---
lens: accuracy
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/specs/2026-09-29-season-toggle-design.md
---

# accuracy review

## Verdict

ready with changes

## Findings

### F-1 [major] `build_players_table()` reads a CSV, not player JSONs

- Where: Design > Age from player data, first bullet; Testing table row 4
- Evidence: `v2/browser/build_league_db.py:64-76`. `build_players_table()` runs `pd.read_csv(PLAYERS_CSV, usecols=keep)`, where `PLAYERS_CSV = data/<season>/generated/players/csv/players.csv` (line 44). Player JSONs are read only by `_recover_missing_players()` (lines 79-115), which fills gaps and builds its row dicts field by field. The CSV already has a `birthDate` column: header field 10 in both `data/2025/.../players.csv` (819 rows, 0 empty, all `YYYY-MM-DD`) and `data/2026/.../players.csv` (778 rows, 0 empty).
- Problem: The spec says the column comes "from each player JSON's `birthDate` field" and tests `build_players_table()` "on synthetic player JSONs". Neither matches the code. An implementer who follows the text writes JSON parsing that the function doesn't do, and a test fixture that the function never reads. The spec also misses `_recover_missing_players()`. Recovered players get appended without `birthDate`, so they get NULL and an em dash for Age, even though their JSON has the field (checked: `data/2025/players/8470613.json` has `birthDate: 1985-03-09`).
- Fix: Replace the bullet with: "`build_players_table()` adds `birthDate` to its `keep` list (the players CSV already carries it as ISO `YYYY-MM-DD` text), and `_recover_missing_players()` adds `"birthDate": d.get("birthDate")` to each recovered row." Change the test row to: "`build_players_table()` on a synthetic players CSV writes a `birthDate` column, and `_recover_missing_players()` carries `birthDate` from a synthetic player JSON."

### F-2 [major] "Same rendering as missing TOI" would turn numeric columns into strings

- Where: Design > Edge bursts per season, fourth bullet; Goal bullet 4; Age from player data, last bullet
- Evidence: Commit `53c2290` changed `utils.seconds_to_mmss()` to return the string `"—"` for None/NaN. That works because TOI is already a string column (`toi_display`, `skaters.py:175`, declared with no `type` at line 196). SB/a60, Max MPH and Age are `"type": "numeric"` columns with a `Format(...)` (`skaters.py:188`, `:201-202`), and the table sorts and filters them natively (`sort_action="native"`, `filter_action="native"`, lines 219-220). Dash 4.0.0, the version pinned in `requirements.txt`, provides `Format.nully()` (`dash/dash_table/Format.py:257`). No code in `v2/` uses it yet (`grep -rn nully v2` finds nothing).
- Problem: Putting the string `"—"` into those columns, as `53c2290` does for TOI, breaks numeric sort and filter and drops the precision `Format`. The spec gives no other mechanism. Also, today a missing CSV in local dev doesn't fail: `load_bursts()` returns an empty frame and the columns render blank (`burst_data.py:43-44`). "Instead of failing" describes production only.
- Fix: Replace the bullet with: "A season without a CSV shows an em dash in SB/a60 and Max MPH. The column formats become `Format(precision=2, scheme=Scheme.fixed).nully("—")`, so values stay numeric. Age uses `Format().nully("—")` for a null `birthDate`." In Goal bullet 4, change "instead of failing" to "instead of blank cells".

### F-3 [minor] The Goal says elites follows the season filter, but the Design keeps the URL

- Where: Goal, "Success means" bullet 2, versus Design > Pages and shared modules, bullet 3
- Evidence: `pages/elites.py:122` is `def layout(season=None)`, so the season comes from the URL query string. The page has no `store-season` input (`grep -n season pages/elites.py` shows only lines 122, 123, 127 and 137). It's also left out of the nav (`app.py:76`).
- Problem: The Goal lists elites among the pages that "follow the selected season". The Design keeps elites on the URL, so changing the filter won't change it. The two sections contradict each other.
- Fix: Change the Goal bullet to: "Games, teams, team, skaters, player, and goalies pages follow the selected season; elites reads `?season=` and defaults to `DEFAULT_SEASON`. No page falls back to a hard-coded `"2025"`."

### F-4 [minor] "Rollover is a change to one file" contradicts the Rollover section

- Where: Goal, last success bullet, versus Rollover next season, step 2
- Evidence: The Goal says "Next season's rollover is a change to one file, `v2/browser/seasons.py`." The Rollover steps edit `seasons.py`, `tools/sync-runtime-data.sh` and the Dockerfile.
- Problem: The success criterion can't pass under the spec's own procedure.
- Fix: Change the Goal bullet to: "Next season's browser rollover is a change to `v2/browser/seasons.py`, plus the season's files in the two deploy guards (`tools/sync-runtime-data.sh`, `Dockerfile`)."

### F-5 [minor] The fallback window starts after the season opens

- Where: Design > Date-range fallback; Testing row 1
- Evidence: The spec's own Problem section says 2026-27 opens on 2026-09-29. NHL.com confirms the season starts Tuesday, Sept. 29 with Carolina-Florida (https://www.nhl.com/news/nhl-home-openers-for-2026-27-season). The new fallback begins `f"{yr}-10-01"`.
- Problem: The fallback window leaves out the first two days of the season it stands for. The effect is small, because the fallback applies only when no completed games exist. But the test would lock in a range that is wrong for this very season.
- Fix: Use `f"{yr}-09-01"` through `f"{yr + 1}-06-30"`, and expect `("2026-09-01", "2027-06-30")` in the test.

### F-6 [minor] Today the team goalie section is omitted, not empty

- Where: Design > Goalie sections for seasons without goalie data, bullet 2
- Evidence: `pages/team.py:82-83` returns `None` when `env.empty`. Lines 343-344 append the section only `if env_section is not None`.
- Problem: "Instead of an empty section" misstates current behavior. Today no heading or container renders at all. The change adds a new element to the layout, which the implementer should know.
- Fix: Change to: "`_goalie_environment_section()` returns the message (under the `Goalie environment` heading) instead of `None` when `team_environment` has no rows for the season, so the section appears with that message instead of being omitted."

### F-7 [minor] Switching `store-season` to session storage has no visible effect

- Where: Design > App shell, bullet 3
- Evidence: `app.py:302-304`. `sync_season` writes `store-season` from `filter-season.value` and has no `prevent_initial_call`, so it fires on every page load. `filter-season` is created with `value=DEFAULT_SEASON` and has no `persistence` (`app.py:89-97`). On reload, the store gets reset to `DEFAULT_SEASON` whatever the storage type. Within the single-page app, navigation keeps the layout, so the choice already survives page changes with `memory`.
- Problem: The spec presents session storage as restoring persistence across reloads, which the code doesn't do. The claim that the comment at `app.py:58` directs this change is accurate. The change still doesn't achieve its purpose.
- Fix: Either add `persistence=True, persistence_type="session"` to the `filter-season` RadioItems (matching `goalie-situation`, `app.py:111`) and say that this is what keeps the choice across reloads, or state that `storage_type` stays `memory` because `sync_season` overwrites the store on load.

### F-8 [minor] The tests target helpers in page modules, which can't be imported on their own

- Where: Testing table rows 3, 5 and 6
- Evidence: Each `pages/*.py` calls `dash.register_page()` at import. In Dash 4.0.0, `_validate.validate_use_pages` (`dash/_validate.py:507-511`) raises `PageError("dash.register_page() must be called after app instantiation")` when no app exists. Existing tests get page code only through `import app` (`tests/test_smoke.py:25,33,66`). `_age_on` and the proposed `_bursts_for` live in `skaters.py`. The metadata lookup is inline in `player.py`'s `layout()` (lines 105-107), not a function. Row 6's "no CSV in local dev" case would resolve `player_bursts_csv("2026")` to the real `data/2026/generated/edge/player_bursts.csv`. It passes only while that file is absent, and it depends on real paths, which the spec's synthetic-data rule rules out.
- Problem: As written, these tests need a full `import app`, or they can't be written. Row 6 also breaks after the first 2026 Edge run, and the `lru_cache` leaks state between tests.
- Fix: Name where each helper goes. Put `bursts_for(season)` (the `lru_cache` wrapper) in `burst_data.py`, `age_on()` in `seasons.py` or `utils.py`, and `player_meta(pid)` (the newest-first loop over `SEASONS`) in `db.py`. In row 6, monkeypatch `burst_data.player_bursts_csv` to a `tmp_path` and call `bursts_for.cache_clear()` in the test.

### F-9 [minor] The glossary hard-codes 2025-26 for Max MPH

- Where: Goal, "No page falls back to a hard-coded `"2025"`"; the Design doesn't touch the glossary
- Evidence: `app.py:162`: "A single peak value across all 2025-26 regular-season ice time." `app.py:143` (Age) uses 2025 only as an example, which stays true. `app.py:207` (goalies, "2021-22 through 2025-26") stays true under this spec's non-goals.
- Problem: With 2026-27 selected, the Max MPH definition names the wrong season.
- Fix: Add to App shell: "Change the Max MPH glossary entry (`app.py:162`) to 'across the selected season's regular-season ice time'."

### F-10 [minor] Comments that promise a boot-time failure go stale, and "a deploy refuses" overstates the guard

- Where: Design > Edge bursts per season, bullet 3; Deploy guard, closing paragraph
- Evidence: The `burst_data.py:4-9` docstring says a missing production CSV causes "a boot failure that Fly's deploy health check catches". The Dockerfile comment at lines 37-41 says the skaters page "raises at import". `healthz.py` returns 200 unconditionally. The Dockerfile `RUN` guard (lines 42-57) checks only `-s` (present and non-empty). The 80% coverage check runs only inside `tools/sync-runtime-data.sh` (lines 48-49).
- Problem: With lazy loading, both comments become false, and Fly's health check no longer catches a missing CSV. The spec says this but doesn't update the comments. "A deploy refuses to proceed until ... covering at least 80%" is also too strong. `fly deploy` enforces only presence. Coverage is enforced when the sync runs, and a stale `runtime_data/` from an earlier sync still builds.
- Fix: Add a bullet: "Update the `burst_data.py` module docstring and the Dockerfile comment at lines 37-41: the production error now fires on the first skaters request for the season, and the sync script's coverage check is the guard." Reword the closing paragraph to: "The sync refuses to finish until 2026-27 has a `league.db` and a burst CSV covering at least 80% of its skaters. The Dockerfile guard refuses to build without both files."

### F-11 [minor] Dropping the 2024 metadata fallback blanks names for 2024-only players

- Where: Design > Pages and shared modules, bullet 2
- Evidence: `pages/player.py:105-107` looks up 2025, then 2024. `SEASONS` excludes 2024 (Non-goals). `data/2024/generated/browser/league.db` exists and still ships (`sync-runtime-data.sh:19`).
- Problem: After the change, `/player/<id>` for a player who appears only in 2024 renders "Player <id>" with no subtitle. The spec doesn't say whether that's intended.
- Fix: Either state it as intended ("players seen only in 2024-25 lose their name header; accepted"), or have the lookup iterate `SEASONS` newest first and then `"2024"` as a metadata-only fallback.

### F-12 [nit] The `display:none` line reference is off

- Where: Problem, bullet 1
- Evidence: `app.py:84` is inside the comment. The `style={"display": "none"}` is on `app.py:99`.
- Fix: Change `app.py:84` to `app.py:99`.

### F-13 [nit] The hard-code inventory misses `filters.py:16`

- Where: Problem, bullet 2; Design > Date-range fallback
- Evidence: `filters.py:16` is `yr = int(season) if season else 2025`. The spec's replacement formula `yr = int(season)` drops it silently.
- Fix: Add `filters.py:16` to the list, and say in Date-range fallback: "The `if season else 2025` guard goes away; callers pass `season or DEFAULT_SEASON`."

### F-14 [nit] `db.query()` has one caller, which is itself uncalled

- Where: Non-goals, `edm.db` bullet
- Evidence: `db.py:25`: `available_teams()` calls `query()`. A grep across `v2/` shows no caller of `available_teams()` or `query()` outside `db.py` and `tests/test_smoke.py:18-19`.
- Fix: Change to "(no page calls `db.query()` or `db.available_teams()`)".

### F-15 [nit] Small sync-script and rollover details are missing

- Where: Deploy guard, bullet 1; Rollover next season, step 2
- Evidence: `tools/sync-runtime-data.sh:17` runs `mkdir -p "$DST/2024" "$DST/2025"`, and line 52 lists those two directories only. Its usage header (lines 6-10) names only `build_league_db.py 2025`.
- Fix: Add "creates `runtime_data/2026/`, and lists it in the closing `ls` and the usage header" to bullet 1. Add "and its `verify_runtime_data.py` call" to Rollover step 2.

### F-16 [nit] Skaters needs `birthDate` carried through the groupby

- Where: Design > Age from player data, bullet 2
- Evidence: `skaters.py:98-111` builds `grouped` with named aggregations. Age is computed on `grouped` (lines 161-165), and `birth_date` currently arrives there only through the burst join at line 160.
- Fix: Add: "`update_skaters` aggregates `birthDate=("birthDate", "first")` and computes Age from it. The burst join no longer contributes `birth_date`."

## Checked and sound

- These line references are correct: `app.py:7` (`SEASONS = ["2025"]`), `app.py:58` (storage comment), `app.py:61` (`storage_type="memory"`), `app.py:82` (filter-bar comment), `games.py:37`, `teams.py:65`, `team.py:181`, `skaters.py:22` (`_AGE_CUTOFFS`), `skaters.py:35` (`_BURSTS_DF`), `skaters.py:81`, `player.py:105` (2025, then 2024 at 107), `player.py:138`, `goalies.py:42`, `elites.py:123`, `filters.py:9`, `filters.py:97`, and the `db.py` defaults (lines 31, 46). `burst_data.py:24` also defaults to `"2025"`, as the Design says.
- The current fallback in `season_date_range()` is `(yr-1)-10-01` through `yr-06-30` (`filters.py:16-17`), so `"2026"` gets the 2025-26 window, as the spec says.
- Age depends on the Edge CSV's `birth_date`: `BURST_COLUMNS` in `burst_data.py:21`, the join and Age at `skaters.py:160-165`, and the column is in `data/2025/generated/edge/player_bursts.csv`.
- The Age boundary test is arithmetically correct under `_age_on` (`skaters.py:25-32`): born 2000-09-16 is 25 and born 2000-09-15 is 26 on 2026-09-15.
- `load_bursts()` returns an empty frame and logs a warning in local dev, and raises `RuntimeError` in runtime mode (`burst_data.py:41-44`). `tests/test_burst_data.py` covers both.
- `player.py`'s `_load_bursts()` is per-season and returns an empty indexed frame for a missing file (`player.py:87-94`).
- `/goalies` renders "No goalie data for this season." on an empty result (`goalies.py:45-46`).
- `game.py` derives the season from the game ID (`game.py:121`).
- The circular-import premise holds: in Dash 4.0.0, `Dash.init_app` calls `enable_pages()`, which imports the pages folder (`dash/dash.py:752`, `:2531-2535`).
- `DEFAULT_MIN_OVERLAP = 0.80` in `verify_runtime_data.py:19`. Coverage counts distinct F/D `playerId`s in `competition`.
- The current sync script copies 2025 `league.db` and `player_bursts.csv` and runs `verify_runtime_data.py` for 2025. The Dockerfile `RUN` guard lists the 2024/2025 files and `goalies.db`. Under `set -euo pipefail`, a missing 2026 CSV makes `cp` exit non-zero, so the spec's second verification run will fail as intended.
- The orchestrator is set to 2026: `v2/orchestrator/config.py:11` and the plist's `NHL_SEASON` (uncommitted working-tree changes). `data/2026/` exists with `players/` and `generated/players/` but no `league.db` yet, which matches "until the first daily run builds its league.db".
- The 2026-27 season opens 2026-09-29 ([NHL.com](https://www.nhl.com/news/nhl-home-openers-for-2026-27-season), [Yahoo Sports](https://sports.yahoo.com/articles/nhl-games-today-2026-opening-170904210.html)).
- The three `BACKLOG.md` item titles match the spec word for word (`BACKLOG.md:7`, `:29`, `:50`), and the goalie pipeline's 2021-2025 scope matches `build_goalies_db.py:25`.
- `edm.db` has no page readers (grep across `v2/`).
- Evergreen constraints: the spec follows `CLAUDE.md`'s testing practices (red-first tests, synthetic data, `python -m pytest v2/ -v`) and doesn't ask for commits. It has no conflict with `DESIGN.md`. The em-dash and message text don't touch tokens or components.
