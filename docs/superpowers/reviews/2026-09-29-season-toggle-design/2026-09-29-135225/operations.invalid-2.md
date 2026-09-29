---
lens: operations
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/specs/2026-09-29-season-toggle-design.md
---

# operations review

## Verdict

not ready

## Findings

### F-1 [major] The 80% coverage guard does not detect a stale burst CSV mid-season, contrary to the spec's claim

- Where: "Deploy guard", last paragraph (line 98): "A stale 2026 burst CSV fails that check as the season adds skaters, which signals that an Edge refresh is due."
- Evidence: `verify_runtime_data.py:22-28,53` measures the share of league.db F/D skaters that have a row in the CSV. `v2/edge/compute_burst_rates.py:96-131` (`build_burst_table`) writes a row for every league.db skater even when no Edge JSON exists; the Edge fields are just null. I ran a first-appearance query on a copy of `data/2025/generated/browser/league.db`, placed in a mktemp dir, to simulate a CSV built on date A and checked on date B. Results: built 2025-11-01, checked 2025-12-01: 90.5% coverage. Built 2025-12-01, checked 2026-01-15: 93.5%. Built 2026-01-15, checked 2026-03-01: 97.1%. All three pass the 0.80 threshold with burst data that is 30 to 45 days old. Rerunning only `compute_burst_rates.py` against a fresh league.db, with no Edge refetch, gives 100% coverage. Those rows pair old burst counts with the current, larger TOI, so `bursts_per_60` comes out understated.
- Problem: The guard only notices staleness in roughly the first month of the season. After that it passes months-old data. The spec relies on it as the signal that an Edge refresh is due. It also can't tell an Edge fetch that returned nothing apart from a good one, because null-field rows count as covered.
- Fix: Either (a) remove the sentence and say plainly that the guard checks row coverage, not freshness, or (b) extend `verify_burst_csv` with a freshness check and add it to the design and the Testing table. Two workable options: require the fraction of non-null `bursts_per_60` to be at least 0.80, and require the burst CSV's mtime (or a stamped max `gameDate`) to be within N days of `max(games.gameDate)` in the season's league.db.

### F-2 [major] Once this merges, every deploy, hotfixes included, depends on a fresh manual Edge run, and no deploy is possible until 2026 data exists

- Where: "Deploy guard"; "Non-goals" ("Automated Edge refresh")
- Evidence: `data/2026/generated/` currently holds only `players/`. There is no `browser/league.db` and no `edge/` directory (`ls data/2026/generated/*`). `fetch_skater_detail.py:3` reads its skater list from the season's league.db, so the Edge run can't start until the first daily build has run. BACKLOG.md:54,59 says the Edge refresh is manual and makes about 800 requests. I simulated early-season coverage from the 2025 data (distinct F/D skaters by first game date). A CSV built 2025-10-08 covers 234 of 634 skaters (37%) one week later. A CSV built 2025-10-15 covers 634 of 718 (88%) on 2025-11-01. So for roughly the first two to three weeks, any CSV older than a few days fails the guard.
- Problem: The spec presents the guard as a safety net, but it also changes the deploy procedure. From the merge until the first 2026 league.db and Edge run exist, `sync-runtime-data.sh` exits non-zero, so no deploy can go out, including fixes that have nothing to do with seasons. During the early season, every deploy needs a fresh 800-request Edge run first. The spec doesn't state this, doesn't sequence it, and doesn't say whether it's intended.
- Fix: Add a "Deploy procedure" subsection that states the coupling and the order: daily build (or `build_league_db.py 2026`) → `NHL_SEASON=2026 python v2/edge/fetch_skater_detail.py` → `NHL_SEASON=2026 python v2/edge/compute_burst_rates.py` → `./tools/sync-runtime-data.sh` → `fly deploy`. Also add the step "deploy current master before merging this branch" so nothing already merged gets stuck behind the new guard. If the coupling isn't acceptable, record the other decision: production-only `SEASONS` (for example, 2026 is included in runtime mode only when its runtime files exist and pass verification). Note that this trades away the "dataless image can't ship" guarantee in BACKLOG.md:16.

### F-3 [major] Moving the burst load from import time to first request removes the boot failure that Fly's health check relied on

- Where: "Edge bursts per season", third bullet ("That error now fires on the first request for the season instead of at import.")
- Evidence: `burst_data.py:4-9` gives the reason for raising: "Failing loudly there turns a silent 'blank columns' regression into a boot failure that Fly's deploy health check catches before the bad image takes traffic." Today `skaters.py:35` calls `load_bursts("2025")` at import. `healthz.py:1-14` returns 200 unconditionally, and `fly.toml` checks only `/healthz`. With lazy `_bursts_for(season)`, a bad CSV in production boots cleanly, passes the health check, and takes traffic. The first skaters request for that season then raises inside a Dash callback, which shows up only in the gunicorn error log.
- Problem: This is the only runtime check that catches a bad burst CSV, and the design removes it. The spec's answer is that the sync guard prevents this, but the Dockerfile `RUN` guard only checks for non-empty files, so an image built without running `verify_runtime_data.py` still ships. Nobody would notice until a user loaded /skaters. The `burst_data.py` docstring and the Dockerfile comment at lines 37-41 ("raises at import, which crash-loops the machine") also become false, and the spec doesn't update them.
- Fix: Keep the lazy cache, but in runtime mode warm it at import: `if is_runtime_mode(): for s in SEASONS: _bursts_for(s)` in `skaters.py`. That keeps the boot failure in production and lazy loading in local dev. Add a Testing row: with `DATA_DIR` set and a season's CSV missing, importing `pages.skaters` raises. Update the `burst_data.py` docstring to match.

### F-4 [major] Nothing stops a league.db without `birthDate` from shipping, and in production that failure is silent

- Where: "Age from player data", third bullet ("The skaters page doesn't guard against a missing column; a database without it is a build that hasn't been rerun.")
- Evidence: `sync-runtime-data.sh:27-49` checks that files are non-empty, that goalies.db has both situation cuts, and that the burst CSV covers the season's skaters. It checks no league.db schema. The Dockerfile guard (lines 42-57) checks only for non-empty files. `PRAGMA table_info(players)` on the current `data/2025/generated/browser/league.db` lists 8 columns and no `birthDate`, and `runtime_data/2025/league.db` (Aug 11) is a copy of that build. `healthz` always returns 200 (see F-3).
- Problem: If code with `p.birthDate` in `_COMP_SQL` deploys before the 2025 rebuild is synced, the skaters callback fails with `no such column: p.birthDate` on every request, and every guard and health check passes. "A build that hasn't been rerun" is an operator mistake the existing guards are designed to catch.
- Fix: Add a schema check to `sync-runtime-data.sh` for each shipped season: a Python heredoc like the goalies.db check that asserts `birthDate` is in `PRAGMA table_info(players)` for `runtime_data/2025/league.db` and `runtime_data/2026/league.db`. Also extend `test_smoke.py::test_league_db_exists` (`requires_data`) to assert the column, so a local run of `pytest v2/` catches an un-rebuilt DB.

### F-5 [major] No rollback plan, and the 2025 rebuild can't be undone

- Where: "Age from player data", third bullet; the spec has no rollback section.
- Evidence: `build_league_db.py:999-1001` deletes the existing `league.db` before rebuilding. `sync-runtime-data.sh:20` then overwrites `runtime_data/2025/league.db`, so after both run there is no prior copy of the deployed 2025 DB anywhere. The 2025 inputs are also not unchanged since the last build: `data/2025/generated/competition/2025020001.csv` has an mtime of 2026-09-29 11:57, while `data/2025/generated/browser/league.db` has 2026-06-22 11:47 (`find data/2025 -newer .../league.db`). I didn't determine what changed in that file. The rebuild also recomputes elite sets, `player_metrics`, and `constants`, not just the players table.
- Problem: The spec treats the 2025 rebuild as adding one column, but it recomputes the whole deployed 2025 DB from inputs that have changed since the last build, and it destroys the only copy of the current DB. If the numbers shift, there's nothing to diff against or restore. The spec also never says how to undo a bad release.
- Fix: Add a "Rollback" section. (1) Before the rebuild, `cp data/2025/generated/browser/league.db data/2025/generated/browser/league.db.pre-season-toggle`. (2) After the rebuild, compare row counts per table, check the `_log_elite_changes` output for zero changes, and diff `player_metrics`. Any difference other than the new column blocks the sync. (3) Code or data rollback: the image carries its data, so `fly releases` then `fly deploy --image <previous image ref>` restores both. Locally, restore the `.pre-season-toggle` copy. (4) Irreversible part: none remains once step 1 is done. Alternatively, avoid the full rebuild for 2025 by adding the column with `ALTER TABLE players ADD COLUMN birthDate TEXT` and populating it from `players.csv`.

### F-6 [major] Production would serve a frozen 2026-27 snapshot with no "data through" date

- Where: "Deploy guard", first paragraph; "Non-goals" ("Deploy freshness")
- Evidence: The Deploy guard section guarantees that any deploy ships a 2026-27 option backed by data. BACKLOG.md:11 says the live site shows 2026-27 "only as of the last manual `./tools/sync-runtime-data.sh` + `fly deploy`", and BACKLOG.md:22 lists "show the data date in the app header" as the cheap option. CLAUDE.md Core Principles: "Validation First: All outputs must match official NHL statistics exactly."
- Problem: After the first deploy, the 2026-27 pages on `app.nhldata.org` are labeled as the current season but stop at the deploy date, and from the next game day on they no longer match NHL.com. Users can't tell. This is at least a tension with the evergreen "Validation First" principle. Rate it a blocker if the orchestrator reads it as an outright conflict.
- Fix: Put a minimal staleness indicator in scope: show "through <max(games.gameDate)>" next to the season filter or in the filter label for the selected season, from one query per season. Or decide explicitly that production `SEASONS` stays `["2025"]` until the BACKLOG freshness item lands, and remove the 2026 entries from the deploy guard.

### F-7 [minor] `runtime_data/2026/` is not gitignored

- Where: "Deploy guard", first bullet; "Rollover next season", step 2
- Evidence: `.gitignore:11-12` lists only `v2/browser/runtime_data/2024/` and `v2/browser/runtime_data/2025/`. `git check-ignore -v v2/browser/runtime_data/2026/league.db v2/browser/runtime_data/2026/player_bursts.csv` printed nothing, so neither path is ignored. For comparison, the 2025 league.db is about 8 MB.
- Problem: The first sync with the new script leaves an untracked DB and CSV in `git status`, and a broad `git add` during oiler's manual commits would put data into history. The rollover procedure would repeat this every season.
- Fix: Change `.gitignore` to `v2/browser/runtime_data/*/`, which keeps the intentionally tracked root-level `goalies.db` and `.gitkeep`. Name the change in the Deploy guard section. If you keep per-season lines instead, add "add the season to `.gitignore`" to the rollover steps.

### F-8 [minor] The manual guard check exercises the wrong line

- Where: "Testing", paragraph after the table ("once with the 2026 burst CSV missing. The second run must exit non-zero.")
- Evidence: `sync-runtime-data.sh` runs `cp` under `set -euo pipefail` (line 11) before the non-empty loop and the verify step. If the source CSV is missing, the new `cp` line fails first, so a non-zero exit proves only that `cp` failed. The empty-file case, the below-80% case, and the Dockerfile `RUN` guard are never exercised.
- Fix: Replace it with three checks, run against a copy of the repo in a `mktemp -d` directory so the real `runtime_data/` isn't touched: (a) a zero-byte 2026 CSV must make the non-empty loop fail; (b) a 2026 CSV holding under 80% of the league.db skaters must make `verify_runtime_data.py` fail; (c) `docker build .` with `runtime_data/2026/` removed must fail at the `RUN` guard.

### F-9 [minor] Two Testing-table tests depend on real data paths that fill in tomorrow

- Where: "Testing" table, rows 1 and 6
- Evidence: The orchestrator runs daily with `NHL_SEASON=2026`: `v2/orchestrator/config.py:11`, the installed `~/Library/LaunchAgents/com.nhl.orchestrator.plist`, and the 11:57 run log in `data/2026/logs/2026-09-29.md`. From 2026-09-30, `data/2026/generated/browser/league.db` exists, and a manual Edge run creates `data/2026/generated/edge/player_bursts.csv`. `_bursts_for` is an `lru_cache`, so its results carry over between tests.
- Problem: If "against a missing or empty DB" and "`_bursts_for("2026")` with no CSV" resolve through `runtime_paths` against the real tree, they pass today and fail once the data arrives. In CI, where `data/` is absent, they pass for the wrong reason. The cached value also lets one test's result leak into the next.
- Fix: State in the table that both tests `monkeypatch` `runtime_paths.league_db` / `player_bursts_csv` (or the modules' imported names) to `tmp_path`, run `monkeypatch.delenv("DATA_DIR", raising=False)`, and call `_bursts_for.cache_clear()` in a fixture.

### F-10 [minor] Switching `store-season` to session storage has no effect, and the obvious fix brings back the stale-value problem after a rollback

- Where: "App shell: `app.py`", third bullet
- Evidence: `app.py:302-304`: `sync_season` writes `filter-season.value` into `store-season` and has no `prevent_initial_call`. `app.py:89-97`: `filter-season` has `value=DEFAULT_SEASON` and no `persistence`. On a full reload, the radio starts at `DEFAULT_SEASON`, and the initial `sync_season` call overwrites whatever session storage restored. Page callbacks wait on `store-season`, which is an output of that callback. I reasoned this from Dash's initial-call semantics and did not verify it in a browser.
- Problem: The change doesn't persist the choice across a reload. If an implementer then adds `persistence_type="session"` to the radio, as the goalie dropdown does at `app.py:111`, a user holding "2026" in session storage after a rollback to a single-season image would query a season with no DB and get empty pages. That's the scenario the comment at `app.py:58-60` warns about.
- Fix: Decide and state it. Either keep `memory` storage and rewrite the comment to say reloads reset to `DEFAULT_SEASON`, or add `persistence=True, persistence_type="session"` to `filter-season`, add `if season not in SEASONS: return DEFAULT_SEASON` to `sync_season`, and test that guard.

### F-11 [minor] The 2024 league.db stops being read but stays required by the deploy guard

- Where: "Pages and shared modules", second bullet (`player.py` looks up metadata in each season of `SEASONS`)
- Evidence: `grep -rn 2024` over non-test browser `.py` files shows `pages/player.py:107` as the only runtime read of the 2024 DB. `sync-runtime-data.sh:17,19,27` and `Dockerfile:44` still require `runtime_data/2024/league.db` (8.0 MB).
- Problem: After the change, the image ships and the guard enforces a file that nothing reads. Players whose only metadata is in 2024 also lose their name fallback.
- Fix: Pick one and write it into the spec: drop 2024 from the sync script, the Dockerfile guard, and the ship list, or keep a metadata-only fallback such as `METADATA_SEASONS = [*reversed(SEASONS), "2024"]` in `seasons.py`.

### F-12 [minor] In local dev, the daily 08:00 rebuild replaces a DB the running app now reads, and not atomically

- Where: "Goal" (local dev); "Age from player data", third bullet ("The daily orchestrator run keeps the 2026 database current")
- Evidence: `build_league_db.py:999-1002` deletes `OUTPUT_DB`, then builds tables one at a time into the same path. `db.py:36-38` checks only `db_path.exists()`. Until now the browser read only 2025, which is frozen. Under this design it reads 2026, which the orchestrator rebuilds every morning.
- Problem: A local app running during the rebuild window gets `no such table` errors or partial results for 2026-27.
- Fix: Either note it under the local-dev goal ("reload after the 08:00 run"), or have `build_league_db.py` write to `league.db.tmp` and `os.replace` it into place at the end. That change is small and also protects the Edge fetch, which reads the same file.

### F-13 [minor] The spec names the wrong source for `birthDate`, and the recovery path would drop it

- Where: "Age from player data", first bullet ("from each player JSON's `birthDate` field")
- Evidence: `build_players_table()` (`build_league_db.py:64-76`) reads `generated/players/csv/players.csv` with an explicit `keep` list. That CSV already has `birthDate` as column 10, in both 2025 and 2026. Player JSONs are read only by `_recover_missing_players()` (`:79-115`), which builds its own dict without `birthDate`.
- Problem: Following the spec literally puts the change in the wrong function. Adding the column only to `keep` leaves recovered players with a null `birthDate`, and they would show an em dash for Age after the rebuild.
- Fix: "Add `birthDate` to the `keep` list in `build_players_table()` and to the dict in `_recover_missing_players()` (from the JSON's `birthDate`)." Add a recovered-player case to the `build_players_table` test row.

### F-14 [nit] The spec's command list, the script comments, and the workflow comments are incomplete

- Where: "Deploy guard", bullets; "Age from player data", third bullet
- Evidence: `sync-runtime-data.sh:5-10` gives the rebuild sequence as `build_league_db.py 2025` only. Line 17 runs `mkdir -p "$DST/2024" "$DST/2025"`, and line 52 runs `ls -lh "$DST/2024" "$DST/2025"`. `Dockerfile:37` and `.github/workflows/fly-deploy.yml:3-4` name only 2024 and 2025. `build_league_db.py:39` uses the relative path `data/{season}`, so it has to run from the repo root.
- Fix: List these edits in the Deploy guard section: add `$DST/2026` to `mkdir -p` and `ls -lh`; add `build_league_db.py 2026` and the two Edge commands to the header comment; update the season list in the Dockerfile and fly-deploy.yml comments. Add "from the repo root" to the rebuild commands.

### F-15 [minor] The filter bar being un-hidden carries Bootstrap-default styling that conflicts with DESIGN.md (outside the operations lens)

- Where: "App shell: `app.py`", second bullet ("The filter bar loses `display:none`")
- Evidence: `app.py:95-96` sets `labelStyle` `"color": "#212529"`, which is Bootstrap's body color. DESIGN.md §2 sets Primary Text to `#171717`, §4 Inputs sets "Radio/checkbox accent: navy", §7 says "Don't ship purple/blue Bootstrap defaults", and §8 asks for "Radio/checkbox controls padded to `40px` rows" on mobile. `assets/*.css` has no `accent-color` or radio rule (grep).
- Problem: Making the filter visible ships an evergreen-doc violation that was invisible while the bar was hidden. I rated this minor because the code already exists and the fix is small. The rubric treats evergreen conflicts as blockers, so the orchestrator may raise it.
- Fix: Add a bullet: "Replace the inline `labelStyle` color with `var(--text)` (#171717), set `accent-color: #00205B` on `.filter-bar input[type=radio]`, and give the labels a 40px tap height below 640px."

## Checked and sound

- `runtime_paths.py:44-59` resolves any season string in both modes (`<DATA_DIR>/<season>/…` and `data/<season>/generated/…`). 2026 needs no path changes.
- `fly.toml` `[env]` and the Dockerfile `ENV` agree on `DATA_DIR=/app/runtime_data`, so runtime mode is detected the same way the design assumes.
- CI (`.github/workflows/tests.yml`) runs `pytest v2/ -q -m "not requires_data"` on push and PR. The synthetic tests in the Testing table will run there. CI never builds the image (`fly-deploy.yml` is `workflow_dispatch`-only, and `.dockerignore` excludes `tools/` and `verify_runtime_data.py`), so the Dockerfile guard change can't break CI.
- `verify_runtime_data.py` takes CSV and DB paths as CLI arguments (`:62-69`), so a second call for 2026 in the sync script needs no code change.
- The orchestrator really is on 2026: `v2/orchestrator/config.py:11` defaults to `"2026"` (an uncommitted working-tree change), the installed LaunchAgent plist sets `NHL_SEASON=2026`, and `data/2026/logs/2026-09-29.md` records the 11:57 run for the 2026 season.
- The Edge pipeline honors `NHL_SEASON` (`fetch_skater_detail.py:6`, `compute_burst_rates.py:20-21`) and writes to the `data/<season>/generated/edge/player_bursts.csv` path the sync step expects.
- `birthDate` exists in both `data/2025/generated/players/csv/players.csv` and `data/2026/generated/players/csv/players.csv` (column 10), so the rebuild has a source.
- Code rollback is schema-safe: `skaters.py` `_COMP_SQL` and the other page queries name their columns (grep found no `p.*` or `SELECT *` in the pages, `filters.py`, or `db.py`), so an older image reading a DB with the extra `birthDate` column still works.
- Capacity: 2025 league.db is 8.1 MB and goalies.db is 3.0 MB. A second season DB plus per-worker cached burst frames (940 rows in the 2025 CSV) fit within the 512 MB `shared-cpu-1x` VM running 2 gunicorn workers.
- `goalies.db` is intentionally tracked (`git ls-files v2/browser/runtime_data`), and the design leaves it unchanged. The existing two-cut goalie check in the sync script still applies.
- `game.py:121` derives the season from the game ID, so it needs no change, as the spec says.
- The spec's final step (`python -m pytest v2/ -v`, then a manual season switch on each page) matches the CLAUDE.md testing rule. The spec asks for no git commits, which matches the CLAUDE.md workflow rule.
