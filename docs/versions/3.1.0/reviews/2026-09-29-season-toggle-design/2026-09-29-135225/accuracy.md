---
lens: accuracy
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/specs/2026-09-29-season-toggle-design.md
---

# accuracy review

## Verdict

ready with changes

## Findings

### F-1 [major] `build_players_table()` reads `players.csv`, not player JSONs

- Where: Design > Age from player data, bullet 1; Testing table row 4 ("`build_players_table()` on synthetic player JSONs writes a `birthDate` column")
- Evidence: `v2/browser/build_league_db.py:64-76` loads `PLAYERS_CSV` (`data/<season>/generated/players/csv/players.csv`, defined at `:43`) with `pd.read_csv(PLAYERS_CSV, usecols=keep)`. It never opens a JSON. Only `_recover_missing_players()` (`:79-115`) reads `data/<season>/players/<pid>.json`, to fill gaps. The CSV already has the column: `head -1 data/{2024,2025,2026}/generated/players/csv/players.csv | tr ',' '\n' | grep -n birthDate` prints `10:birthDate` for all three; a Python check found 0 blank values and all values 10 characters (`YYYY-MM-DD`) in 2025 (819 rows) and 2026 (778 rows).
- Problem: An implementer following the spec would either rewrite the players build to read JSONs or write a test against an input the function doesn't take. The recovery path, which does read JSONs, isn't mentioned, so recovered players would get a null `birthDate` and an em dash for Age.
- Fix: Replace bullet 1 with: "`build_players_table()` adds `birthDate` to its `keep` list; `players.csv` already carries it as ISO `YYYY-MM-DD`. `_recover_missing_players()` adds `"birthDate": d.get("birthDate")` from the player JSON." Change the test row to: "`build_players_table()` on a synthetic `players.csv` (monkeypatch `build_league_db.PLAYERS_CSV`) writes a `birthDate` column, and `_recover_missing_players()` carries `birthDate` from a synthetic player JSON."

### F-2 [major] Elites can't "follow the selected season" if it reads the season from the URL

- Where: Goal > Success means, bullet 2 ("Games, teams, team, skaters, player, goalies, and elites pages all follow the selected season"), against Design > Pages and shared modules ("`elites.py` keeps reading its season from the URL")
- Evidence: `v2/browser/pages/elites.py:122-123` is `def layout(season=None): season = season or "2025"`, a query-string argument. The page has no callback on `store-season` (`grep -n "store-season\|callback" v2/browser/pages/elites.py` finds nothing), and `app.py:76` hides `/elites` from the nav.
- Problem: The success criterion and the design contradict each other. As designed, switching the filter to 2026-27 and opening `/elites` shows 2025-26.
- Fix: Pick one. Either drop "elites" from success bullet 2 and add "`/elites` is URL-driven (`/elites?season=2026`) and ignores the filter", or add a design bullet that moves the elites tables into a callback on `Input("store-season", "data")`.

### F-3 [major] Switching `store-season` to session storage doesn't keep the selected season across page loads

- Where: Design > App shell, bullet 3; Goal ("every page shows the selected season's data")
- Evidence: `app.py:89-92`: `dcc.RadioItems(id="filter-season", ..., value=DEFAULT_SEASON)` has no `persistence`. `app.py:302-304`: `sync_season` writes `filter-season.value` into `store-season` and doesn't set `prevent_initial_call`, so on every full page load it overwrites the store with `DEFAULT_SEASON`. Every in-table link is a DataTable markdown link rendered as a plain anchor (`markdown_options={"link_target": "_self"}`, for example `skaters.py:218`, `team.py:140`, `goalies.py:76`). Dash's router doesn't intercept plain anchors, so clicking one reloads the page. Not confirmed in a browser: I read the code and checked that dash 4.0.0's `dash_table/bundle.js` treats `link_target` only as an anchor target.
- Problem: Pick 2026-27 on Skaters, click a player, and the player page opens on 2025-26. Session storage on the store changes nothing because the initial callback overwrites it. The comment at `app.py:58-60` assumed the store was the only thing that needed to persist.
- Fix: Add to the App shell section: "`filter-season` gets `persistence=True, persistence_type="session"` so the selected season survives full page loads (table links reload the page). `store-season` then follows it through `sync_season`." Keep or drop the store's `storage_type` change, but explain why. Add a manual check to Testing: pick 2026-27, click a player link from Skaters, and confirm the player page shows 2026-27.

### F-4 [major] "Same rendering as missing TOI" doesn't work for numeric columns

- Where: Design > Edge bursts per season, bullet 4; Design > Age from player data, bullet 4 (em dash for a null `birthDate`); Goal bullet 4
- Evidence: Commit `53c2290` changed `seconds_to_mmss()` in `v2/browser/utils.py` to return the string `"—"` for None/NaN, which works because TOI columns are text columns (`toi_display`). SB/a60, Max MPH and Age are numeric DataTable columns: `skaters.py:188` (`"type": "numeric"`), `:201-202` (`Format(precision=2, scheme=Scheme.fixed)`). A NaN in a numeric column renders as an empty cell, not an em dash. Putting `"—"` strings into those columns would break native numeric sort and filter. dash 4.0.0 `dash_table/Format.py:257` has `def nully(self, value)`, which sets the display for null values in a numeric column.
- Problem: The spec points the implementer at a mechanism that can't be reused here. Without an explicit mechanism these cells render blank, not as an em dash, which fails Goal bullet 4.
- Fix: Replace "using the same rendering as missing TOI (commit `53c2290`)" with "through `Format(...).nully("—")` on the SB/a60, Max MPH and Age column formats, so the columns stay numeric for sort and filter. Age needs a `Format(...)` added, since it has none today."

### F-5 [major] "Rollover is a change to one file" contradicts the three-file rollover procedure

- Where: Goal > Success means, last bullet, against Rollover next season, steps 1-2, and Design > Deploy guard
- Evidence: The Goal says "Next season's rollover is a change to one file, `v2/browser/seasons.py`." The Rollover section edits `seasons.py`, `tools/sync-runtime-data.sh`, and the `Dockerfile` guard. `.gitignore:11-12` also names seasons explicitly (see F-6).
- Problem: This is an internal contradiction, and the success criterion can't be verified as written.
- Fix: Change the Goal bullet to: "Next season's browser rollover is a one-line change to `SEASONS` in `v2/browser/seasons.py`; the deploy guards (`tools/sync-runtime-data.sh`, `Dockerfile`, `.gitignore`) name each season's files explicitly and change with it."

### F-6 [minor] `runtime_data/2026/` isn't gitignored

- Where: Design > Deploy guard; Rollover next season, step 2
- Evidence: `.gitignore:10-13` ignores only `v2/browser/runtime_data/2024/` and `v2/browser/runtime_data/2025/`. The `Dockerfile:37` comment says these directories "are gitignored — they're built locally and baked in".
- Problem: After the sync script starts writing `runtime_data/2026/league.db` and `player_bursts.csv`, they show up as untracked files, and a manual commit could pick up large binary data.
- Fix: Add to Deploy guard: "`.gitignore` adds `v2/browser/runtime_data/2026/`, and the `Dockerfile:37` comment names 2026." Add `.gitignore` to rollover step 2.

### F-7 [minor] The hard-coded `"2025"` survey misses entries, and the design keeps one of them

- Where: Problem, bullet 2; Goal bullet 2 ("No page falls back to a hard-coded `"2025"`"); Design > Pages and shared modules, bullet 1
- Evidence: `grep -rn '"2025"\|2025\b' v2/browser/*.py v2/browser/pages/*.py` also finds `burst_data.py:24` (`season: str = "2025"`), `filters.py:16` (`yr = int(season) if season else 2025`, an int that the `season or "..."` and `season: str = "..."` patterns don't match), and the `build_league_db.py:39` CLI default. The Design bullet does list `burst_data.py`, but the Problem list doesn't. Nothing covers `filters.py:16`, and the Date-range fallback section's `yr = int(season)` doesn't say what happens to the `else 2025` branch.
- Problem: `filters.py:16` survives the change as written, which breaks Goal bullet 2.
- Fix: Add `burst_data.py:24` and `filters.py:16` to the Problem list. In the Date-range fallback section, write `yr = int(season or DEFAULT_SEASON)`. State whether `build_league_db.py:39` keeps its `"2025"` CLI default (it isn't a page, so keeping it is defensible, but say so).

### F-8 [minor] The season-specific glossary text isn't addressed

- Where: Design > App shell (missing bullet)
- Evidence: `app.py:162`: Max MPH is "A single peak value across all 2025-26 regular-season ice time." `app.py:143`: the Age example names 2025-26. `app.py:207`: goalies cover "Seasons 2021-22 through 2025-26".
- Problem: With 2026-27 selected, the Max MPH definition names the wrong season. The Age and goalie lines stay true but read as tied to 2025-26.
- Fix: Add an App shell bullet: "Glossary Max MPH text becomes season-neutral ('across the selected season's regular-season ice time'). The Age example and the goalie coverage line stay, since both remain accurate."

### F-9 [minor] "Instead of failing" misdescribes today's missing-burst behavior

- Where: Goal, bullet 4 ("shows an em dash in SB/a60 and Max MPH instead of failing")
- Evidence: `burst_data.py:43-44` returns an empty frame in local dev, and `skaters.py:160` joins it without error, so nothing fails locally. Today a 2026 selection doesn't fail. It joins `_BURSTS_DF`, which holds the 2025 CSV (`skaters.py:35`), and shows 2025-26 burst values beside 2026-27 stats. In production a missing CSV raises at import (`burst_data.py:41-42`).
- Problem: The defect being fixed is wrong-season data, not a failure. Describing it as a failure hides the more serious current bug.
- Fix: Change to "A season without Edge bursts shows an em dash in SB/a60 and Max MPH, never another season's values." Add the wrong-season join to the Problem bullet about `skaters.py:35`.

### F-10 [minor] Stale docs and messages after moving Age off the burst CSV and the raise off import

- Where: Design > Age from player data; Design > Edge bursts per season, bullet 3
- Evidence: `burst_data.py:1-2` and `:40` say the burst CSV is "behind the skaters leaderboard's Age, SB/a60 and Max MPH columns" and that "skater Age ... depend[s] on it". `burst_data.py:6-8` says a missing file becomes "a boot failure that Fly's deploy health check catches". `Dockerfile:39-40` says the skaters page "raises at import". `verify_runtime_data.py:6` mentions "blank Age/SB-a60/Max-MPH". `healthz.py:3` returns 200 unconditionally, so after the change a missing CSV no longer fails the boot check.
- Problem: After the change these comments and error messages describe behavior that no longer exists.
- Fix: Add a bullet: "Update `burst_data.py`'s module docstring and error text, the `Dockerfile:37-41` comment, and `verify_runtime_data.py`'s docstring: Age no longer depends on the burst CSV, and a missing CSV now raises on the first request for that season instead of at boot."

### F-11 [minor] Player metadata lookup silently drops the 2024 fallback

- Where: Design > Pages and shared modules, bullet 2
- Evidence: `player.py:105-107` falls back to the 2024 `league.db`. The new lookup iterates `SEASONS` (`["2025", "2026"]`), and Non-goals keeps 2024 out of `SEASONS`.
- Problem: A player whose only `players` row is in 2024 would change from a name to "Player <id>". The spec doesn't say whether that's intended.
- Fix: State it: either "look up `SEASONS` newest first, then `"2024"` as a legacy fallback", or "the 2024 fallback is dropped; players reachable from 2025-26 and 2026-27 pages have rows in those seasons."

### F-12 [minor] Test rows don't name the unit under test, and the "fails because" reasons depend on that

- Where: Testing table, rows 3 and 5
- Evidence: Row 3 (Age boundary): `_age_on()` already exists (`skaters.py:25-32`) and handles any cutoff. If the test calls `_age_on(b, age_cutoff("2026"))`, it fails only because `seasons.py` is missing (row 2's reason), not "because Age comes from the 2025-only dict". Row 5 (metadata lookup): the lookup is inline in `player.py` `layout()` (`:105-107`), and no function exists to test.
- Problem: Neither test can be written as described without an unstated decision, and row 3's stated red reason is wrong if the test calls `_age_on()` directly.
- Fix: Name the functions: "row 3 tests a new `skaters._age_column(df, season)` (or the callback's age step) so the failure is the missing 2026 cutoff". "Row 5 tests a new `player._lookup_meta(pid)` extracted from `layout()`." Also note that `_bursts_for` tests must call `_bursts_for.cache_clear()` between cases because of the `lru_cache`.

### F-13 [nit] `app.py:84` is not where `display:none` is

- Where: Problem, bullet 1
- Evidence: `app.py:84` is a comment line ("firing with DEFAULT_SEASON. Remove the display:none and restore SEASONS"). The style is at `app.py:99`: `], className="filter-bar", style={"display": "none"}),`.
- Problem: Wrong line reference.
- Fix: Change `app.py:84` to `app.py:99`.

### F-14 [nit] `db.query()` does have a caller

- Where: Non-goals, `edm.db` bullet
- Evidence: `db.py:25`: `available_teams()` calls `query(season, ...)`, and `tests/test_smoke.py:18-19` calls `query`. `grep -rnwE "available_teams" v2 --include='*.py'` finds only its definition, so no page reaches `edm.db`.
- Problem: The conclusion is right, but the stated evidence isn't.
- Fix: "No page reads it: `db.query()` is called only by `available_teams()`, which has no callers."

### F-15 [nit] Team goalie section today is omitted, not empty

- Where: Design > Goalie sections, bullet 2 ("instead of an empty section")
- Evidence: `team.py:82-83` returns `None` when `env.empty`, and `team.py:344-345` appends the section only if it isn't None.
- Problem: This slightly misdescribes current behavior.
- Fix: "... renders the same message instead of omitting the section."

### F-16 [nit] Fallback start date misses the 2026-27 opener, and the empty-DB test case is ambiguous

- Where: Design > Date-range fallback; Testing row 1
- Evidence: The 2026-27 regular season opened Tuesday, September 29, 2026 ([NHL.com](https://www.nhl.com/news/nhl-home-openers-for-2026-27-season)), before the proposed fallback start `f"{yr}-10-01"`. The fallback applies only when the DB has no scored games, so the difference is harmless. For the test: a zero-byte or tableless SQLite file makes `league_query` raise `no such table: games` (`db.py:39-41` doesn't catch it). Only a missing file (`db.py:37-38`) or a `games` table with no scored rows reaches the fallback at `filters.py:15`.
- Problem: "Empty DB" could be read as a file the code doesn't tolerate.
- Fix: In Testing row 1, change "a missing or empty DB" to "a missing DB, or one whose `games` table has no scored games". Optionally use `f"{yr}-09-01"` as the fallback start.

### F-17 [minor] Unhiding the season filter exposes an inline Bootstrap text color that DESIGN.md rules out

- Where: Design > App shell, bullet 2 (filter bar loses `display:none`)
- Evidence: `app.py:95-96`: `labelStyle={..., "color": "#212529"}`, Bootstrap's body color, set inline so it overrides `.filter-bar label` in `assets/style.css:94-100`. `DESIGN.md` §2 sets Primary Text to `#171717`, and its Do's and Don'ts say "Don't ship ... Bootstrap defaults — override dbc component colors to the tokens." `DESIGN.md` §8 Touch Targets: "Radio/checkbox controls padded to `40px` rows."
- Problem: The control has been hidden until now. Making it visible ships a color that departs from the evergreen DESIGN.md. The spec doesn't create the conflict, but it exposes it, which is why this is rated minor rather than blocker.
- Fix: Add to the App shell section: "Replace the inline `labelStyle` color with the Primary Text token (`#171717`, or move label styling into `style.css`), and give the radio rows the 40px mobile tap height from DESIGN.md §8."

## Checked and sound

- `SEASONS = ["2025"]` at `app.py:7`; `store-season` `storage_type="memory"` at `app.py:61`; the comment at `app.py:58-60` does say to switch back to "session" when `SEASONS` grows; the comment block starts at `app.py:82`.
- Hard-coded `"2025"` line references: `games.py:37`, `teams.py:65`, `team.py:181`, `skaters.py:81`, `player.py:138`, `goalies.py:42`, `elites.py:123`, `filters.py:9` and `:97`, `db.py:31` and `:46` defaults. All match.
- `skaters.py:22` `_AGE_CUTOFFS = {"2025": date(2025, 9, 15)}`, `skaters.py:35` import-time `load_bursts("2025")`, and Age read from the burst CSV's `birth_date` (`skaters.py:160-165`).
- `player.py:105-107` looks up 2025, then 2024.
- `season_date_range()` fallback (`filters.py:15-17`) returns `(yr-1)-10-01`..`yr-06-30`, so `"2026"` gives the 2025-26 window. The spec's analysis is correct.
- Age boundary arithmetic: with cutoff 2026-09-15, born 2000-09-16 gives 25 and born 2000-09-15 gives 26 under `_age_on()`'s logic.
- `game.py:121` derives the season from `str(gid)[:4]`; no change needed.
- `player.py:87-94` `_load_bursts(season)` is per-season and returns an empty frame for a missing file; it's called with `season` at `:268`.
- `goalies.py:46` renders "No goalie data for this season." for an empty result.
- `team_environment` in `data/generated/browser/goalies.db` has 32 rows for each season 2021-2025 in both situations, so the "not yet available" message won't appear for a covered season with a valid team.
- `load_bursts()` contract (`burst_data.py:24-44`): empty frame plus warning in dev, `RuntimeError` in runtime mode. `tests/test_burst_data.py` has the production-raise tests (`:32`, `:38`).
- `tools/sync-runtime-data.sh` currently copies and checks only 2024/2025 files and runs `verify_runtime_data.py` for 2025 only (`:48-49`). `set -euo pipefail` means a missing 2026 source CSV makes the `cp` fail and exits non-zero, which matches the spec's second manual check.
- The `Dockerfile:42-57` `RUN` guard lists the files by name. `DEFAULT_MIN_OVERLAP = 0.80` at `verify_runtime_data.py:19`, measured against `competition` F/D skaters, so a stale 2026 CSV fails as the season adds skaters.
- The orchestrator is on 2026: `v2/orchestrator/config.py:11` defaults to `"2026"` and the plist sets `NHL_SEASON=2026` (working-tree changes). `data/2026/logs/2026-09-29.md` shows the first run, for 2026-09-28, which had no games. `data/2026/generated/browser/league.db` doesn't exist yet, so the fallback claim holds. The orchestrator includes a `build_league_db` step (`agent.py:34`, `sync_season.py:25`).
- The 2026-27 regular season opening on 2026-09-29 is confirmed by NHL.com ("2026-27 NHL season to start on Sept. 29").
- The three `BACKLOG.md` item titles the spec quotes match `BACKLOG.md:7`, `:29`, `:50` word for word, and their contents agree with the Non-goals.
- Test files named in the spec exist: `v2/browser/tests/test_player_metrics.py`, `test_deployment_metrics.py`, `test_burst_data.py`. The spec's `python -m pytest v2/ -v` step matches `CLAUDE.md` Testing Practices.
- The circular-import rationale holds: `app.py:10-15` constructs `dash.Dash(use_pages=True)`, which imports the pages, so a page importing from `app` re-enters `app.py` (and re-executes it under `python app.py`). A standalone `seasons.py` avoids this.
- No conflict found with `CLAUDE.md` (synthetic-data tests, pytest before finishing, no git commits by the agent). Apart from F-17, no conflict found with `DESIGN.md`.
