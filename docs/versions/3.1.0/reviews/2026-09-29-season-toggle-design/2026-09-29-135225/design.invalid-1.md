---
lens: design
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/specs/2026-09-29-season-toggle-design.md
---

# design review

## Verdict

not ready

## Findings

### F-1 [blocker] Elites is a success criterion but the design keeps it off the season filter

- Where: Goal, success bullet 2 (line 24) vs. Design > Pages and shared modules, bullet 3 (line 64)
- Evidence: Line 24 says "Games, teams, team, skaters, player, goalies, and elites pages all follow the selected season." Line 64 says "`elites.py` keeps reading its season from the URL, defaulting to `DEFAULT_SEASON`." `v2/browser/pages/elites.py:122-123` is `def layout(season=None): season = season or "2025"`, a query-string argument with no `Input("store-season")`. Once the filter bar is visible it also shows on `/elites`, where toggling it changes nothing.
- Problem: The two sections contradict each other. An implementer can't satisfy both, and a verifier checking line 24 will fail the elites page.
- Fix: Pick one. (a) Remove "and elites" from line 24 and add a Non-goals bullet: "`/elites` is an unlinked page that takes its season from `?season=`. It doesn't follow the season filter." Or (b) replace line 64 with: "`elites.py` moves its body into a callback on `Input("store-season", "data")`, like `goalies.py`. The `?season=` parameter goes away." Option (a) is smaller, since `/elites` is excluded from the nav (`app.py:76`).

### F-2 [blocker] "Rollover is a change to one file" contradicts the three-step rollover

- Where: Goal, success bullet 6 (line 28) vs. Rollover next season (lines 119-121)
- Evidence: Line 28 says "Next season's rollover is a change to one file, `v2/browser/seasons.py`." Lines 119-121 list edits to `seasons.py`, `tools/sync-runtime-data.sh`, and the Dockerfile guard. The Deploy guard section (lines 95-96) hard-codes the 2026 paths into both of those files.
- Problem: The success criterion is false under the design as written.
- Fix: One option makes the claim true. Have both guards read the list from `seasons.py`. In `sync-runtime-data.sh`, loop over `$(python3 -c 'import sys; sys.path.insert(0, "v2/browser"); from seasons import SEASONS; print(" ".join(SEASONS))')` for the copy, the non-empty check, and `verify_runtime_data.py`. In the Dockerfile, replace the fixed `for f in ...` list with a `RUN python -c` that imports `seasons` from `/app` (the runtime stage has Python and `seasons.py` ships because `.dockerignore` doesn't exclude it) and checks `runtime_data/<s>/league.db` and `runtime_data/<s>/player_bursts.csv` for each season. Rollover then shrinks to steps 1 and 3. The other option is to reword line 28 to "Next season's browser rollover touches `seasons.py`, `tools/sync-runtime-data.sh`, and the Dockerfile guard (see Rollover next season)."

### F-3 [blocker] Unhiding the filter bar ships a control that conflicts with DESIGN.md

- Where: Design > App shell, bullet 2 (line 57)
- Evidence: The RadioItems at `app.py:95-96` sets `labelStyle={... "color": "#212529"}`, Bootstrap's body color. DESIGN.md §2 sets Primary Text to `#171717`, and §7 says "Don't ship purple/blue Bootstrap defaults — override dbc component colors to the tokens." DESIGN.md §4 Inputs & Forms says "Radio/checkbox accent: navy." `grep -n 'accent-color' v2/browser/assets/style.css` finds nothing. DESIGN.md §8 Touch Targets says "Radio/checkbox controls padded to `40px` rows" on mobile, and nothing in `.filter-bar` (`style.css:86-101`) provides that. The control has been `display:none` until now, so none of this was visible.
- Problem: The spec says only "The filter bar loses `display:none`." Doing exactly that ships a visible control that breaks three DESIGN.md rules.
- Fix: Add to the App shell section: "Restyle the season radios to DESIGN.md. Drop the inline `labelStyle` color and set it in `style.css` as `.filter-bar input[type=radio] { accent-color: var(--navy); }`, with option labels in the primary text token. Under the `< 640px` breakpoint, pad each option to a 40px tap row." Use the actual token names from `style.css`.

### F-4 [major] Age source misstated: `build_players_table()` reads players.csv, not player JSON; recovered players would lose Age

- Where: Design > Age from player data, bullet 1 (line 73); Testing table row 4 (line 109)
- Evidence: `v2/browser/build_league_db.py:64-76` builds `players` from `PLAYERS_CSV` (`data/<season>/generated/players/csv/players.csv`) using a `keep` column list. Player JSON is read only by `_recover_missing_players()` (lines 79-115), which appends rows through a hand-built dict with no `birthDate`. `players.csv` already carries `birthDate` (column 10 of the 2025 and 2026 headers). A pandas check on the 2025 file printed `0 1.0`: zero nulls, and every value matches `^\d{4}-\d{2}-\d{2}$`.
- Problem: An implementer following line 73 goes looking for JSON parsing inside `build_players_table()` that doesn't exist. Even the correct change (adding to `keep`) leaves recovered players with a null `birthDate`, so they show an em dash for Age even though their JSON has the field. Test row 4 describes the wrong input.
- Fix: Replace line 73 with: "`build_players_table()` adds `"birthDate"` to its `keep` list; `players.csv` already has the column in ISO format. `_recover_missing_players()` adds `"birthDate": d.get("birthDate")` to each recovered row." Replace test row 4 with two rows: "`build_players_table()` with `PLAYERS_CSV` monkeypatched to a synthetic CSV writes a `birthDate` column" and "`_recover_missing_players()` on a synthetic player JSON writes that player's `birthDate`." The second follows the pattern in `test_player_metrics.py:205`.

### F-5 [major] Every deploy is tied to a same-day 2026 Edge run, and the spec lists no risks

- Where: Design > Deploy guard (lines 93-98); the spec has no Risks section
- Evidence: `v2/edge/compute_burst_rates.py` `build_burst_table()` writes one row for every skater in `league.db` at build time, including skaters with no Edge JSON ("Players present in league.db but missing an EDGE JSON file are included"). Coverage is therefore about 100% on the day the CSV is built and falls as new skaters debut. `verify_runtime_data.py:19` requires 80%. In the first weeks of 2026-27 the skater count grows from a handful of games to about 600 players, so a CSV built on day 3 falls below 80% within days. The Edge run is manual and makes about 800 requests (BACKLOG.md "Scheduled and on-demand Edge refresh"). Until `data/2026` has both a `league.db` and a burst CSV, no deploy can proceed, including a fix to a 2025 page. Neither file exists today: `ls data/2026/generated` shows only `players`.
- Problem: Line 98 presents the decay as a helpful signal. In practice it makes every deploy wait on a same-day manual Edge refresh, which conflicts with the non-goal that makes Edge refresh manual (line 34). The em-dash fallback for a season without bursts (line 26) can only happen in local dev, because `load_bursts()` raises in production (`burst_data.py:41-42`). The spec doesn't mention this.
- Fix: Add a Risks section that states the coupling and records oiler's decision. Three options: (a) accept it, and write that every deploy is preceded by an Edge run for the active season; (b) set a lower minimum overlap for the in-progress season (`verify_runtime_data.py` already takes a third `min_overlap` argument); or (c) add a `DEPLOYED_SEASONS` subset in `seasons.py` that the guards and the production filter use, so 2026-27 appears in production only once its data is synced.

### F-6 [major] Lazy burst loading removes the fail-at-boot guarantee; loading every season at import is simpler

- Where: Design > Edge bursts per season, bullets 1-3 (lines 80-82)
- Evidence: The module docstring at `burst_data.py:4-9` explains that the production raise exists to turn a blank-columns bug "into a boot failure that Fly's deploy health check catches before the bad image takes traffic." The Dockerfile comment at line 40 relies on the skaters page raising at import. `healthz.py:12-14` returns 200 unconditionally, and `fly.toml` checks `/healthz`. With `_bursts_for()` loading on first request, a bad image passes the health check, takes traffic, and returns errors on the first skaters request.
- Problem: The spec acknowledges the raise moves (line 82) but doesn't say this defeats the health-check rationale, and it lists no updates to the docstring or the Dockerfile comment. The `lru_cache` also adds test friction (F-12).
- Fix: Replace bullets 1-2 with: "`skaters.py` replaces `_BURSTS_DF` with `_BURSTS = {s: load_bursts(s).set_index("playerId") for s in SEASONS}` at import. The callback joins `_BURSTS.get(season, <empty frame>)`." This keeps per-season loading and the boot-time failure, drops `lru_cache`, and keeps the restart-after-Edge-run behavior the spec already accepts. If lazy loading stays, add bullets to update `burst_data.py:4-9` and `Dockerfile:37-41` so they stop claiming a boot failure.

### F-7 [major] The em-dash rendering from commit 53c2290 doesn't apply to numeric columns

- Where: Design > Edge bursts per season, bullet 4 (line 83); Age bullet 4 (line 76); Goal bullet 4 (line 26)
- Evidence: `git show 53c2290` changed only `seconds_to_mmss()` in `utils.py`, which returns the string `"—"` for None or NaN into a text column. SB/a60, Max MPH, and Age are `"type": "numeric"` DataTable columns (`skaters.py:188, 201-202`), and DataTable renders a null numeric cell as blank. Running `python3 -c "from dash.dash_table.Format import Format; print(hasattr(Format,'nully'))"` printed `True` (dash 4.0.0).
- Problem: "Using the same rendering as missing TOI" can't be done without turning the columns into strings, which would break native numeric sort and filter. As written, the cells come out blank, not as the em dash the success criterion names.
- Fix: Replace line 83 with: "SB/a60 and Max MPH use `Format(precision=2, scheme=Scheme.fixed).nully("—")`, and Age gets `Format().nully("—")`, so null cells render an em dash and the columns stay numeric." Make line 76 point to the same mechanism.

### F-8 [minor] The date-range fallback starts after the opener the spec names

- Where: Design > Date-range fallback (line 69); Problem bullet 5 (line 15); Testing row 1 (line 106)
- Evidence: Line 9 says the 2026-27 season opens on 2026-09-29, and nhl.com confirms it: "2026-27 NHL season to start on Sept. 29 with Carolina-Florida" (https://www.nhl.com/news/nhl-home-openers-for-2026-27-season). The new fallback starts on `f"{yr}-10-01"`. `filters.py:16` also has a bare int `2025` (`int(season) if season else 2025`) that the spec's list of hard-coded values (line 12, "filters.py:9 and :97") misses.
- Problem: The fallback window leaves out opening week. The fallback applies only while the DB has no games, but it sets the pickers' min and max, and those persist until the season is toggled again or the page reloads. With the app running locally when the first 2026 `league.db` lands, Sept 29-30 stay unreachable in the picker.
- Fix: Use `f"{yr}-09-01"` through `f"{yr + 1}-06-30"`, change test row 1's expected value to `("2026-09-01", "2027-06-30")`, and add `filters.py:16` to the replacement list (`int(season or DEFAULT_SEASON)`).

### F-9 [minor] `runtime_data/2026/` isn't gitignored

- Where: Design > Deploy guard, bullet 1 (line 95)
- Evidence: `.gitignore:11-12` lists `v2/browser/runtime_data/2024/` and `v2/browser/runtime_data/2025/` by name. `git check-ignore -v v2/browser/runtime_data/2026/league.db` matched nothing; only the 2025 path matched. The 2025 `league.db` is 8.2 MB.
- Problem: The first sync after this change leaves an untracked SQLite database and CSV in the working tree, and oiler commits by hand. The Dockerfile comment at lines 37-38 also names only 2024 and 2025.
- Fix: Add a bullet to the Deploy guard: "`.gitignore` ignores `v2/browser/runtime_data/*/` (keeping `!v2/browser/runtime_data/.gitkeep`) instead of listing seasons; update the Dockerfile comment at lines 37-38 to match." Add the `.gitignore` edit to Rollover if it stays per-season.

### F-10 [minor] Switching `store-season` to session storage does nothing

- Where: Design > App shell, bullet 3 (line 58)
- Evidence: `sync_season` (`app.py:302-304`) has no `prevent_initial_call`, and the `filter-season` RadioItems (`app.py:89-97`) has no `persistence`. On every full load, the radio starts at `DEFAULT_SEASON` and its initial callback overwrites whatever session storage restored into the store. I reasoned this from the code and didn't verify it in a browser. Within a session, page changes keep the app shell mounted, so memory storage already carries the selection across pages.
- Problem: The change adds a storage mode without changing behavior, and the rewritten comment would describe persistence that doesn't exist. If the intent is for the selection to survive a reload, this change doesn't achieve it.
- Fix: Decide which behavior you want. If the selection should survive a reload, keep `storage_type="memory"` and add `persistence=True, persistence_type="session"` to the RadioItems (the pattern at `app.py:111`). If not, keep memory storage and just rewrite the comments at `app.py:58-60` and `:82-85`.

### F-11 [minor] The client-supplied season is never checked against SEASONS

- Where: Design > Pages and shared modules, bullet 1 (line 62)
- Evidence: The store value comes from the client, and `/elites` reads `?season=` from the URL. `season or DEFAULT_SEASON` passes any string into `league_db(season)` path construction (`runtime_paths.py:44-47`), into `int(season)` (`goalies.py:44`, `team.py:81`), and, under the spec's design, into `_bursts_for(season)`, which raises `RuntimeError` in production for any season without a file. `runtime_data/2024/league.db` ships in the image and stays reachable through `/elites?season=2024`. The standing `web-security` instruction in the global CLAUDE.md applies.
- Problem: A crafted season string causes errors, fills the burst cache, and reaches data outside `SEASONS`. Repeating `season or DEFAULT_SEASON` at ten call sites is also the duplication `seasons.py` exists to remove.
- Fix: Add `resolve_season(season) -> str` to `seasons.py`, returning `season if season in SEASONS else DEFAULT_SEASON`, and use it at every site line 62 lists, `elites.py` included. Add a test for it: `resolve_season("2024")`, `resolve_season("../x")`, and `resolve_season(None)` each return `DEFAULT_SEASON`.

### F-12 [minor] Several test rows can't fail for the right reason, test a callback, or read real data paths

- Where: Testing table rows 1, 3, 5, 6 and the paragraph after it (lines 106-113)
- Evidence:
  - Row 3 (Age): `_age_on()` (`skaters.py:25-32`) already accepts any cutoff. Before the change, the test fails only on `ImportError` for `age_cutoff`, which row 2 already covers. The Age assignment lives inside the `update_skaters` callback (`skaters.py:160-165`), and project CLAUDE.md says "Test computations, not callbacks."
  - Row 5 (player meta): the lookup is inline in `layout()` (`player.py:105-107`), so the spec names no function to test.
  - Rows 1 and 6: in local dev mode, `league_db("2026")` and `player_bursts_csv("2026")` resolve to real paths under `data/2026/generated/` (`runtime_paths.py:41-59`). Those files start existing once the daily run builds the 2026 database, the first run after 2026-09-29's games, and the "missing DB" and "no CSV" cases then change meaning. `lru_cache` keeps state between tests. Importing `pages/skaters.py` requires `app` to be imported first, because of `dash.register_page`.
  - Deploy guard: with the 2026 CSV missing, the sync script fails at `cp` under `set -e` (`sync-runtime-data.sh:11`) before the new non-empty check or `verify_runtime_data.py` runs, so the non-zero exit proves nothing about the new lines.
- Problem: Some tests go red for the wrong reason, one test would have to drive a callback, and others become order-dependent or depend on data state.
- Fix: Name the pure functions to extract and test: `_add_age(grouped, season)` (or `age_on_for_season(birth_date, season)`) and `player_meta(pid, seasons=SEASONS)` in a non-page module. Row 3's "fails before" then becomes "the function doesn't exist". State that rows 1, 5, and 6 set `DATA_DIR` to `tmp_path`, or monkeypatch `player_bursts_csv` for the local-dev empty-frame case, and call `cache_clear()` if `lru_cache` stays. For the deploy guard, add a run with a present but low-coverage 2026 CSV (for example, one row) that must fail with `FAIL: burst coverage`.

### F-13 [minor] Stale text that becomes wrong when 2026-27 is selected or once Age moves

- Where: Not addressed anywhere in Design
- Evidence: The Max MPH glossary entry at `app.py:160-163` reads "A single peak value across all 2025-26 regular-season ice time." `burst_data.py:1-2` and `:40` say Age depends on the burst CSV, and `BURST_COLUMNS` (`:21`) still requires `birth_date`. `verify_runtime_data.py:6` names "Age/SB-a60/Max-MPH". `Dockerfile:40` says the skaters page "raises at import".
- Problem: After the change, the glossary shows 2025-26 wording while the user views 2026-27, and the code comments misstate what depends on the CSV. If `birth_date` stays in `BURST_COLUMNS`, a future burst CSV without that column raises `KeyError` for a field nothing reads.
- Fix: Add a bullet: "Make the Max MPH glossary season-neutral ('across the selected season's regular-season ice time'). Remove `birth_date` from `BURST_COLUMNS` and drop Age from the `burst_data.py` and `verify_runtime_data.py` docstrings and error message."

### F-14 [minor] Dropping the 2024 metadata fallback leaves 2024 data shipping with no page that uses it

- Where: Design > Pages and shared modules, bullet 2 (line 63); Deploy guard
- Evidence: After the change, `player.py` looks up only `SEASONS` (2025, 2026). Every `/player/<id>` link comes from skaters, team, or elites, and all of those link only players in the season they show. `sync-runtime-data.sh:19` and `Dockerfile:44` still copy and require `runtime_data/2024/league.db`, and after this change only `/elites?season=2024` can reach it (see F-11).
- Problem: The image keeps a required file no page uses, and the guard fails if it's missing. The spec doesn't say whether that's intended.
- Fix: Add a decision to Non-goals or Deploy guard: either "Drop 2024 from `sync-runtime-data.sh`, the Dockerfile guard, and `.gitignore`," or "Keep `runtime_data/2024/` for `/elites?season=2024`," with the reason.

### F-15 [minor] The 2025 rebuild has side effects the spec doesn't list

- Where: Design > Age from player data, bullet 3 (line 75)
- Evidence: `build_league_db.py:992-1025` deletes the database and rebuilds every table from current inputs, and `_log_elite_changes()` appends to an elite changelog. `OUTPUT_DB` is a relative path (`build_league_db.py:40-41`), so the command works only from the repo root. MEMORY.md notes staleness and ordering pitfalls when rebuilding seasons.
- Problem: A 2025 rebuild whose only goal is to add one column can silently change other 2025 outputs (elite sets, `player_metrics`) if any upstream input has changed since the last build, and it writes changelog entries.
- Fix: Add: "Run from the repo root. Before and after the 2025 rebuild, compare row counts and `elite_forwards`/`elite_defensemen`/`player_metrics` contents; any difference beyond the new `birthDate` column stops the change." The alternative is `ALTER TABLE players ADD COLUMN birthDate` plus an `UPDATE` from `players.csv` for 2025 only.

### F-16 [nit] Wrong line reference for `display:none`

- Where: Problem bullet 1 (line 11)
- Evidence: `display:none` for the season bar is at `app.py:99`. Line 84 is inside the comment that describes it.
- Problem: The reference is off.
- Fix: Change `app.py:84` to `app.py:99`.

### F-17 [nit] Age needs its own aggregation in the skaters callback

- Where: Design > Age from player data, bullet 2 (line 74)
- Evidence: `update_skaters` aggregates `comp_df` with a named `groupby().agg()` (`skaters.py:98-111`), and today Age comes in through the burst join (`:160`). Selecting `p.birthDate` in `_COMP_SQL` doesn't reach `grouped` by itself.
- Problem: A small detail the implementer has to infer.
- Fix: Append to line 74: "Add `birthDate=("birthDate", "first")` to the per-player aggregation."

## Checked and sound

- Every file:line reference in Problem matches the code: `app.py:7`, `:61`, `:58`, `:82`; `games.py:37`, `teams.py:65`, `team.py:181`, `skaters.py:81`, `player.py:138`, `goalies.py:42`, `elites.py:123`, `filters.py:9`, `:97`; `db.py:31`, `:46`; `skaters.py:22`, `:35`; `player.py:105-107`. The only exception is F-16.
- The circular-import diagnosis is correct. `app.py` loads pages through `use_pages=True`, and a `seasons.py` with no app or page imports removes the cycle.
- `season_date_range()`'s current fallback (`filters.py:16-17`) returns the previous season's window for a start-year key, as the spec says.
- The boundary math in test row 3 is right. With a 2026-09-15 cutoff, a player born 2000-09-15 is 26 and one born 2000-09-16 is 25.
- `players.csv` carries ISO `birthDate` for 2025 (no nulls) and 2026 (header present), so moving Age to the players table does deliver "Age with or without Edge data" (Goal bullet 3).
- `player.py._load_bursts()` (`player.py:87-94`) is already per-season and returns an empty frame for a missing file. No change is needed.
- `game.py:121` derives the season from the game ID (`str(gid)[:4]`), so it needs no change.
- `goalies.py:45-46` already renders a message for an empty result, and `team.py:82-83` returns `None` for an empty `team_environment`, so the two goalie-section changes are one-line edits at the places the spec names.
- `verify_runtime_data.py` takes explicit CSV and DB paths, so running it for 2026 needs no code change, only a second call in the sync script.
- `.dockerignore` excludes only named build scripts under `v2/browser/`, so a new `seasons.py` ships in the image.
- `db.query()` / `available_teams()` (the `edm.db` path) have no callers outside tests. The `edm.db` non-goal is accurate.
- Dash resolves callback ordering, so on a season switch `register_season_callback`'s date update runs before each page's content callback. The design adds no ordering hazard there.
- The 2026-27 opener date the spec states (2026-09-29) is correct according to nhl.com.
- The testing plan complies with project CLAUDE.md in general: synthetic data, tests on computations, `pytest v2/` before finishing, and no commits. The exceptions are in F-12.
