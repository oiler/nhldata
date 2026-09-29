---
lens: data
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/specs/2026-09-29-season-toggle-design.md
---

# data review

## Verdict

ready with changes

## Findings

### F-1 [major] `birthDate` source is named wrong: `build_players_table()` reads the players CSV, not player JSONs

- Where: Design > Age from player data, bullet 1 ("from each player JSON's `birthDate` field"); Testing table row 4 ("`build_players_table()` on synthetic player JSONs")
- Evidence: `v2/browser/build_league_db.py:64-76` loads `PLAYERS_CSV` (`data/<season>/generated/players/csv/players.csv`, defined at `:42`) with `pd.read_csv(PLAYERS_CSV, usecols=keep)`. It never opens a JSON. `head -1` of `data/2025/generated/players/csv/players.csv` and `data/2026/generated/players/csv/players.csv` both already list `birthDate` as a column; the same holds for the 2021-2024 CSVs. Per-player JSON is read only by `_recover_missing_players()` (`:79-115`).
- Problem: An implementer following the text literally would rewrite `build_players_table()` to read JSONs, or write a test against a code path that doesn't exist. The real change to `build_players_table()` is one list entry.
- Fix: Replace bullet 1 with: "`build_players_table()` adds `"birthDate"` to its `keep` list (the players CSV already carries it as ISO `YYYY-MM-DD` text), and `_recover_missing_players()` adds `"birthDate": d.get("birthDate")` to each recovered row." Change the test row to "`build_players_table()` on a synthetic players CSV writes a `birthDate` column, and `_recover_missing_players()` on a synthetic player JSON writes its `birthDate`".

### F-2 [major] Adding `birthDate` only to the CSV path drops Age for 21% of 2025 skaters

- Where: Design > Age from player data
- Evidence: Read-only query against `data/2025/generated/browser/league.db`: the `players` table holds 1017 rows, but `players.csv` holds 819. The 198 extra rows (D 64, C 61, L 38, R 35) come from `_recover_missing_players()`. All 198 appear in `competition` as F/D (198 of 940 skaters), all 198 have a JSON with non-null `birthDate` in `data/2025/players/`, and the 198 burst-CSV rows that have no `players.csv` match are exactly these players. Today their Age comes from the burst CSV's `birth_date`, which has 0 nulls across 940 rows.
- Problem: Without the recovery-path change, the `birthDate` column is NULL for those 198 players, so Age goes from populated to an em dash for about one skater in five. That's a regression the success criterion ("Age displays for every season whose players table carries `birthDate`") would technically pass while the data got worse.
- Fix: Include the `_recover_missing_players()` change from F-1 and say why ("198 of 940 2025 skaters enter `players` through the JSON recovery path"). Note that the existing fixture `_setup_recovery_db()` (`v2/browser/tests/test_player_metrics.py:188-196`) creates `players` without `birthDate`, so `to_sql(..., if_exists="append")` with the new key will raise `table players has no column named birthDate`. The fixture has to gain the column. Add a test row: "`_recover_missing_players()` carries `birthDate` from the raw JSON" (it fails before the change because the recovered dict has no such key).

### F-3 [major] No deploy guard checks the new `players.birthDate` column, and the page deliberately doesn't guard either

- Where: Design > Age from player data, bullet 3 ("The skaters page doesn't guard against a missing column"); Design > Deploy guard
- Evidence: `PRAGMA table_info(players)` on the shipped `v2/browser/runtime_data/2025/league.db` shows `playerId, currentTeamAbbrev, firstName, lastName, position, heightInInches, weightInPounds, shootsCatches`, with no `birthDate`. `v2/browser/verify_runtime_data.py:45-51` queries only `competition`, and `tools/sync-runtime-data.sh:27-32` checks only that files are non-empty. `db.league_query()` (`v2/browser/db.py:31-43`) doesn't catch SQL errors.
- Problem: If code ships before the rebuilt DB is synced (or with a DB rebuilt by pre-change code, see F-6), `_COMP_SQL` raises `no such column: p.birthDate` and `/skaters` returns an error on every request in production. The burst-CSV guard exists specifically to stop a silent Age regression. Moving Age off the burst CSV moves the failure to a place no guard watches.
- Fix: Add to the Deploy guard section: "`verify_runtime_data.py` gains a check, run for each synced season, that `players` has a `birthDate` column and that at least N% (for example 95%) of distinct F/D `playerId`s in `competition` have a non-null `birthDate`." Add a matching test row. The coverage floor also catches F-2.

### F-4 [minor] Deploy guard couples every deploy, including a 2025 hotfix, to 2026 Edge freshness

- Where: Design > Deploy guard, final paragraph
- Evidence: `tools/sync-runtime-data.sh:48-49` runs `verify_runtime_data.py` with the default `DEFAULT_MIN_OVERLAP = 0.80` (`verify_runtime_data.py:19`). The spec extends this to 2026 and says a stale 2026 CSV "fails that check as the season adds skaters". `data/2026/generated/edge/` doesn't exist yet. Per `BACKLOG.md`, Edge refresh is manual (about 800 requests).
- Problem: Any deploy now needs a fresh 2026 Edge run (and a 2026 `league.db`) first. That includes one that only fixes a 2025 page. Non-goals put deploy freshness out of scope, but this guard makes freshness a precondition for every deploy. The spec doesn't say whether that's intended. I didn't verify whether Edge data lags at season start enough to keep coverage under 80% for days. That's still open.
- Fix: State the decision explicitly. One option: keep the guard as designed and add a sentence to Non-goals ("every deploy requires a same-week Edge run for 2026-27"). The other: have the sync script take an optional lower threshold for the in-progress season (verify_runtime_data already takes `[min_overlap]`), or allow a missing 2026 burst CSV once the em-dash path exists in production.

### F-5 [minor] Non-atomic `league.db` rebuild can be synced or read mid-build

- Where: Design > Age from player data, bullet 3 ("The daily orchestrator run keeps the 2026 database current"); Design > Deploy guard
- Evidence: `build_league_db.py:993-1021` deletes `OUTPUT_DB`, then creates tables one by one with `competition` first. The orchestrator calls it with a 300 s timeout (`v2/orchestrator/tools/build.py:13`) at 08:00 daily (`com.nhl.orchestrator.plist`, `StartCalendarInterval` Hour 8). `league_query()` only checks `db_path.exists()`.
- Problem: While the build runs, and after any failure or timeout partway through, the 2026 DB exists but lacks `players`/`games`/`player_metrics`. Local pages raise on missing tables instead of hitting the `season_date_range()` fallback, which triggers only on `df.empty`. Worse, a `sync-runtime-data.sh` run in that window copies a partial DB that passes the `-s` check and the burst-coverage check, because that check reads only `competition`, which is built first. The risk already existed for 2025, but this spec makes a daily-rebuilt 2026 DB a deployed input.
- Fix: Add a bullet: "`build_league_db.py` writes to `league.db.tmp` and `os.replace()`s it into place after the last table, so readers and the sync script see either the old or the complete new DB." If that's out of scope, add a sync-script check that the DB has all expected tables (`competition, players, games, points_5v5, events_5v5, onice_5v5, elite_forwards, elite_defensemen, player_metrics, constants`).

### F-6 [minor] Migration order: the daily run rebuilds 2026 without `birthDate` until the change reaches master

- Where: Design > Age from player data, bullet 3
- Evidence: The orchestrator runs `v2/browser/build_league_db.py` from the main checkout (`v2/orchestrator/config.py:43`). `data/` is gitignored (`.gitignore:3`), so a worktree or branch has no data tree of its own.
- Problem: "Once `data/2026` has games, run `build_league_db.py 2026`" is undone the next morning if the change isn't yet in the main checkout. The 08:00 run rebuilds the 2026 DB with the old `keep` list, and the unguarded skaters page errors for 2026-27 (F-3).
- Fix: Say "run the 2025 and 2026 rebuilds from the main checkout after the change is merged. Until then, 2026-27 skaters will error after each 08:00 run." Or make the 2026 rebuild a post-merge step in the plan.

### F-7 [minor] Replacing the 2024 metadata fallback with `SEASONS` orphans the shipped 2024 `league.db`

- Where: Design > Pages and shared modules, bullet 2; Non-goals ("Re-enabling 2024-25")
- Evidence: `v2/browser/pages/player.py:105-107` is the only browser read of season `"2024"` (grep of `v2/browser/*.py` and `pages/*.py`). `tools/sync-runtime-data.sh:17-19,27` and `Dockerfile:44` still require `runtime_data/2024/league.db`.
- Problem: With the lookup limited to `SEASONS` (2025, 2026), nothing reads the 2024 DB, but deploys still require and ship it. Alternatively, if keeping names for 2024-only player IDs matters, the spec silently removes that.
- Fix: Pick one and write it down. Either "metadata lookup covers `SEASONS` plus `"2024"`" (for example a `META_SEASONS` tuple in `seasons.py`), or "drop `runtime_data/2024/` from `sync-runtime-data.sh`, the Dockerfile guard, and `.gitignore`."

### F-8 [minor] `runtime_data/2026/` isn't gitignored

- Where: Design > Deploy guard
- Evidence: `.gitignore:10-13` ignores only `v2/browser/runtime_data/2024/` and `v2/browser/runtime_data/2025/`. The 2025 `league.db` alone is 8.5 MB, and `edm.db` is 34.8 MB.
- Problem: After the first sync with 2026 files, `runtime_data/2026/league.db` and `player_bursts.csv` appear as untracked files that can be committed by accident.
- Fix: Add "add `v2/browser/runtime_data/2026/` to `.gitignore`" to the Deploy guard bullets and to Rollover step 2. Alternatively, switch to `v2/browser/runtime_data/*/` with the existing `.gitkeep` negation.

### F-9 [minor] Switching `store-season` to session storage doesn't persist the selection, and season values aren't validated

- Where: Design > App shell, bullet 3; Design > Pages and shared modules, bullet 3 (elites reads season from the URL)
- Evidence: `v2/browser/app.py:302-304` has `sync_season` copy `filter-season.value` into `store-season`. The callback has no `prevent_initial_call`, and the RadioItems (`app.py:89-97`) has no `persistence`, so on every page load it writes `DEFAULT_SEASON` over whatever session storage held. The comment at `app.py:58-60` records the stale-value concern that motivated `memory`. Season strings flow unchecked into filesystem paths (`runtime_paths.league_db(season)` → `data_root() / season / ...`) and into `int(season)` (`goalies.py:44`, `team.py:81`). `elites.py:122-123` takes `season` from the URL query string.
- Problem: The storage switch either does nothing (the value is overwritten on load) or, with persistence added later, lets a stale value survive a rollover that removes a season. A value outside `SEASONS` from session storage or `?season=` reaches path construction and `int()` unchecked.
- Fix: Either keep `storage_type="memory"` and put `persistence=True, persistence_type="session"` on `filter-season` (Dash persistence resets when options change), or drop the bullet. Add to `seasons.py` a `normalize_season(s)` that returns `s if s in SEASONS else DEFAULT_SEASON`, and replace every `season or DEFAULT_SEASON` with `normalize_season(season)`, including `elites.layout()`. Add a test row for it.

### F-10 [minor] Team goalie "not yet available" check conflates a missing season with a missing team row

- Where: Design > Goalie sections for seasons without goalie data, bullet 2
- Evidence: `team.py:80-83` returns `None` when `team_environment` has no row for `(season, team_abbrev, situation)`. `goalies.db` `team_environment` has 64 rows per season (32 teams × 2 situations) for 2021-2025.
- Problem: The spec keys the message on "no rows for the season", but the code as it stands can only see "no row for this team in this season and situation". For a team absent from a season that has goalie data (a relocation or abbreviation change), it would print "2025-26 goalie data isn't available yet", which is false.
- Fix: Specify that the section shows the message only when `SELECT 1 FROM team_environment WHERE season = ? LIMIT 1` returns nothing, and returns `None` (as today) when the season exists but the team row doesn't.

### F-11 [minor] "Same rendering as missing TOI" doesn't carry over to numeric columns; Age and burst NULLs render blank, not as an em dash

- Where: Design > Edge bursts per season, bullet 4; Design > Age from player data, bullet 4
- Evidence: TOI's em dash comes from `seconds_to_mmss()` returning the string `"—"` into a text column (commit `53c2290`, `v2/browser/utils.py`). Age, SB/a60, and Max MPH are `"type": "numeric"` DataTable columns (`skaters.py:188,201-202`). NaN or None serializes to `null`, which DataTable shows as an empty cell. `Format(precision=2, scheme=Scheme.fixed, nully='—')` is accepted by the installed Dash (checked in a scratch dir; it serializes `'nully': '—'`).
- Problem: The two em-dash success criteria won't be met by the approach as written. The obvious alternative, converting to strings, breaks numeric sort.
- Fix: Replace "using the same rendering as missing TOI" with "set `nully="—"` on the `Format` of the Age, SB/a60, and Max MPH columns (Age needs a `Format(nully="—")` added)". Add the same to the Age bullet.

### F-12 [nit] Implementation details the Age change needs

- Where: Design > Age from player data, bullet 2; Design > Edge bursts per season, bullet 1
- Evidence: `skaters.py:98-111` aggregates `comp_df` by `playerId` with an explicit `agg()` list, so any column not listed is dropped. `burst_data.BURST_COLUMNS` (`burst_data.py:21`) still includes `birth_date`, and `grouped.join(...)` (`skaters.py:160`) pulls it in.
- Problem: Selecting `p.birthDate` in `_COMP_SQL` isn't enough on its own. The groupby has to carry it through, and after the join the frame has both `birthDate` and `birth_date` columns, which invites the wrong one being read.
- Fix: Add "`update_skaters` adds `birthDate=("birthDate", "first")` to the groupby" and either "drop `birth_date` from `BURST_COLUMNS` (and `test_burst_data.py`/`test_verify_runtime_data.py` fixtures)" or "join only `bursts_per_60, speed_max_mph`".

### F-13 [nit] The fallback window starts after the opening date the spec states

- Where: Problem, paragraph 1 ("opens on 2026-09-29"); Design > Date-range fallback
- Evidence: The fallback is `f"{yr}-10-01"` through `f"{yr + 1}-06-30"`. The Problem section says the 2026-27 regular season opened on 2026-09-29.
- Problem: The fallback only applies before any game is in the DB, so the real range takes over after that. But the window doesn't contain the season's own first games, and the test pins that value.
- Fix: Use `f"{yr}-09-01"` (and update the test row to `("2026-09-01", "2027-06-30")`), or add a sentence explaining that the fallback is only a placeholder range.

## Checked and sound

- Every season's `players.csv` (2021-2026) has a `birthDate` column. In 2025 and 2026 its values are ISO `YYYY-MM-DD` text with 0 nulls, which `_age_on()`'s `date.fromisoformat` parses. The raw player JSON `birthDate` uses the same format (checked `data/2026/players/8470613.json`).
- `players.playerId` is unique in the 2025 `league.db` (1017 rows, 1017 distinct), so the `LEFT JOIN players` in `_COMP_SQL` won't duplicate competition rows. No 2025 or 2024 F/D competition player is missing from `players`.
- A full rebuild is the right migration for the new column. `build_league_db.py` recreates every table from source, and no schema-migration machinery exists to bypass. `metrics.py` changes since the 2025 DB was built (commits `a016b7c`, `165fc09`) touch goalie rate helpers, not `compute_wppi_and_toi_share`. `elite_changelog.csv` isn't read by the browser.
- The age cutoff boundary test is correct: with cutoff 2026-09-15, a 2000-09-15 birth gives 26 and a 2000-09-16 birth gives 25 under `_age_on()` (`skaters.py:25-32`).
- The problem statement's `season_date_range()` bug is real: `filters.py:15-17` returns `(yr-1)-10-01` to `yr-06-30`, the prior season for a start-year key. The fallback triggers both when the DB is missing and when `MIN(gameDate)` is NULL.
- `game.py:121` derives the season from the game ID (`str(gid)[:4]`), which is correct for start-year keys.
- `player._load_bursts()` (`player.py:87-94`) is per-season and returns an empty indexed frame when the CSV is missing.
- `load_bursts()` behavior as described (empty frame plus warning locally, `RuntimeError` when `DATA_DIR` is set) matches `burst_data.py:24-44`. `functools.lru_cache` doesn't cache exceptions, so a production raise repeats on every request instead of sticking.
- `goalies.db` keys seasons by start year (`goalie_seasons` and `team_environment` hold 2021-2025), consistent with `int(season)` lookups. 2026 correctly returns empty.
- The orchestrator passes the season to `build_league_db.py` (`v2/orchestrator/tools/build.py:12`, `sync_season.py:25`), and `NHL_SEASON` defaults to `"2026"` (`config.py:11`).
- The `edm.db` non-goal is accurate: `db.query()` is called only by `available_teams()`, which has no callers in `v2/browser/*.py` or `pages/*.py`.
- No personal-data or retention concern beyond the status quo. `birthDate` is public NHL API player data already stored in `players.csv` and the burst CSV, and it's already shipped in `player_bursts.csv`.
