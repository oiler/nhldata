---
lens: completeness
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/specs/2026-09-29-season-toggle-design.md
---

# completeness review

## Verdict

not ready

## Findings

### F-1 [blocker] Early-season 2026 build crashes, and pages raise on the missing `player_metrics` and `constants` tables

- Where: "Age from player data" (third bullet: "once `data/2026` has games ... The daily orchestrator run keeps the 2026 database current after that"); Goal ("every page shows the selected season's data, or says plainly that data for that season isn't available").
- Evidence: `build_player_metrics_table()` returns without creating the table when no skater has GP >= 5 (`v2/browser/build_league_db.py:156-158`). `build_constants_table()` then reads `player_metrics` unconditionally (`build_league_db.py:825`). I copied `build_league_db.py` and `metrics.py` into a `mktemp -d` directory and ran both functions against an in-memory competition table with 3 skaters and 2 games each. Output: `player_metrics: 0 rows (no eligible players)`, then `constants raised: DatabaseError ... no such table: player_metrics`, and the skaters page's `_PPI_SQL` raised the same error. `league_query()` (`v2/browser/db.py:31-43`) doesn't catch a missing-table error, and skaters, teams, team, and player all query `player_metrics` (`skaters.py:95`, `teams.py:75`, `team.py:193`, `player.py:188`). teams also queries `constants` (`teams.py:142`).
- Problem: For the first 5 or so games of each team's 2026-27 schedule (about two weeks from 2026-09-30), `build_league_db.py 2026` fails partway through. It leaves a partial `league.db` with no `player_metrics` or `constants`. The spec's closing step ("run `build_league_db.py 2026`") fails, the claim that the daily run keeps the 2026 database current is false for that window, and selecting 2026-27 in the filter throws callback errors instead of showing data or a "not available" message. This is exactly the window the spec is written for.
- Fix: Add a design section, "Early-season database." When nothing is eligible, `build_player_metrics_table()` writes an empty `player_metrics` table with its schema (`playerId, ppi, ppi_plus, wppi, wppi_plus, avg_toi_share`). `build_constants_table()` skips cleanly when `player_metrics` is empty or absent. Pages treat an empty `player_metrics` or `constants` as missing data (em dash or no wPPI+), not an error. Add a red-first test to the Testing table: "`main()`-equivalent build on synthetic competition rows where every skater has GP < 5 completes, and `player_metrics` exists with 0 rows." Fails before because `build_constants_table` raises `no such table`.

### F-2 [blocker] Goal says elites follows the season filter; Design says it reads the URL

- Where: Goal, second success bullet ("Games, teams, team, skaters, player, goalies, and elites pages all follow the selected season"); Design, "Pages and shared modules" ("`elites.py` keeps reading its season from the URL").
- Evidence: `elites.py:122-123` is `def layout(season=None): season = season or "2025"`, a query-string parameter with no `store-season` input. `/elites` is excluded from the nav (`app.py:76`), and a grep for `/elites` under `v2/browser` finds no inbound link anywhere.
- Problem: The two statements contradict each other. Built as designed, switching the filter to 2026-27 doesn't change `/elites`, so the success criterion fails.
- Fix: Pick one. (a) Remove elites from the success bullet and add a non-goal: "`/elites` is an unlinked page that takes its season from `?season=`; it doesn't follow the filter." (b) Make elites a callback on `Input("store-season", "data")` like the other pages, and drop the URL parameter.

### F-3 [blocker] "Rollover is a change to one file" contradicts the three-file Rollover section

- Where: Goal, last success bullet ("Next season's rollover is a change to one file, `v2/browser/seasons.py`"); "Rollover next season" steps 1-3; "Deploy guard".
- Evidence: Rollover step 2 edits `tools/sync-runtime-data.sh` and the `Dockerfile`. `.gitignore:11-12` also names each runtime season directory (see F-9), `app.py:162` hard-codes "2025-26" in the Max MPH glossary (see F-14), and `build_goalies_db.py:25` has its own `SEASONS`.
- Problem: The success criterion can't be met by the design, so a plan's acceptance check for it fails by construction.
- Fix: Reword the success bullet to "Next season's browser rollover is a change to `SEASONS` in `v2/browser/seasons.py`. The deploy guard (`tools/sync-runtime-data.sh`, `Dockerfile`, `.gitignore`) takes one line per file, listed under 'Rollover next season'." Alternatively, have the sync script and Dockerfile loop over seasons read from `seasons.py`, and keep the one-file claim.

### F-4 [blocker] Un-hiding the season filter ships a control that conflicts with DESIGN.md

- Where: "App shell: `app.py`" ("The filter bar loses `display:none`. The radio options use `season_label()` for labels.").
- Evidence: The radio keeps its inline `labelStyle` with `"color": "#212529"` (`app.py:95-96`), which is Bootstrap's body color. DESIGN.md sets primary text to `#171717` (line 41) and says "Radio/checkbox accent: navy" (line 108), "Don't ship purple/blue Bootstrap defaults — override dbc component colors to the tokens" (line 168), and "Radio/checkbox controls padded to `40px` rows" on mobile (line 180). `v2/browser/assets/style.css` has no `accent-color` or `input[type=radio]` rule (grep returned nothing), so the browser's default blue radio shows. `git log` shows the filter was hidden on 2026-05-11 (`a9e109e`), before DESIGN.md landed on 2026-06-10 (`eaae3ae`), so this control was never styled to the system. `.filter-bar label` (`style.css:94-101`) also applies eyebrow styling (uppercase, 0.75rem, `--text-3`) to every `<label>` in the bar, and RadioItems renders its options as `<label>`. I read the CSS but didn't render the page.
- Problem: The spec makes a component visible that conflicts with the evergreen design system, and says nothing about styling it.
- Fix: Add to "App shell": "Style the season radio to DESIGN.md: drop the inline `labelStyle` color and font overrides in favor of a `.filter-bar` radio rule that uses `var(--text)` for option text, `accent-color: var(--navy)` for the radio, and 40px rows under 640px. Scope the eyebrow `.filter-bar label` rule to the group label only (for example `.filter-bar > div > label:first-child`, or a class on `html.Label('Season')`)." Add "the season filter matches DESIGN.md" to the manual check in Testing.

### F-5 [major] Session storage for `store-season` has no stated observable behavior, and as wired it likely does nothing

- Where: "App shell: `app.py`", third bullet (`store-season` switches back to `storage_type="session"`).
- Evidence: `filter-season` is initialized to `DEFAULT_SEASON` with no `persistence` (`app.py:89-97`). `sync_season` (`app.py:302-304`) writes the radio value into the store with no `prevent_initial_call`, so it fires on every page load. After a reload, a session-restored store value (for example `"2026"`) is overwritten by the radio's initial `"2025"`, and the pages' `store-season` callbacks may render twice, first with the restored value. Within one tab, `dcc.Location(refresh=False)` navigation already keeps the memory store. I inferred this from the code and didn't observe it in Dash 4.0.0, which is the installed version. What happens on a real reload is still open.
- Problem: A planner can't tell what "session" is supposed to buy or how to test it. As written, the change is either a no-op or a flicker.
- Fix: State the intended behavior and pick a mechanism. Either: "On reload in the same tab, the selected season persists: `filter-season` gets `persistence=True, persistence_type='session'`, and `store-season` can stay `memory`." Or: "Reload returns to `DEFAULT_SEASON`; `store-season` stays `memory`," and drop the switch. Either way, add a manual check: "Select 2026-27, reload, and confirm the radio and page content agree."

### F-6 [major] No mechanism exists for the em dash in numeric columns, and "same rendering as missing TOI" has two readings

- Where: "Edge bursts per season" fourth bullet; "Age from player data" last bullet; Goal bullet 4.
- Evidence: Commit `53c2290` changed only `seconds_to_mmss()` (`v2/browser/utils.py:8-9`), a string formatter used for the string column `toi_display`. SB/a60, Max MPH, and Age are `"type": "numeric"` DataTable columns (`skaters.py:188`, `:201-202`), and NaN or None in them renders as a blank cell. A grep for `nully` under `v2/browser` finds no existing use.
- Problem: One reading converts the values to strings with an em dash, which breaks native numeric sort and filter on those columns. The other keeps the columns numeric and sets `Format(...).nully("—")`, or `Format(nully="—")`, on the column format. The spec names a commit that implements neither.
- Fix: Replace the sentence with "Missing SB/a60, Max MPH, and Age values stay NaN and render as an em dash through the column's `Format(..., nully='—')`. The columns stay numeric so sort and filter still work." Add a test that the three column definitions carry `nully='—'`, or a render check in the manual step.

### F-7 [major] `build_players_table()` reads a CSV, not player JSONs, and `_recover_missing_players()` is left out

- Where: "Age from player data" first bullet ("from each player JSON's `birthDate` field"); Testing row 4 ("`build_players_table()` on synthetic player JSONs").
- Evidence: `build_players_table()` reads `PLAYERS_CSV` = `data/<season>/generated/players/csv/players.csv` with a fixed `keep` list (`build_league_db.py:43`, `:64-76`). That CSV already has a `birthDate` column, and the header of both `data/2025/.../players.csv` and `data/2026/.../players.csv` includes it. JSON is read only by `_recover_missing_players()` (`build_league_db.py:79-115`), whose row dict (`:102-111`) has no `birthDate`.
- Problem: The data source is stated wrongly, the test row is designed against an input the function doesn't take, and recovered players would get a null Age with no spec coverage.
- Fix: Replace the bullet with "`build_players_table()` adds `birthDate` to its `keep` list (`players.csv` already carries it). `_recover_missing_players()` adds `'birthDate': d.get('birthDate')` to each recovered row." Split Testing row 4 into (a) "`build_players_table()` with `PLAYERS_CSV` monkeypatched to a synthetic CSV writes `birthDate`" and (b) "`_recover_missing_players()` on a synthetic JSON writes `birthDate`." That extends the existing `test_recover_missing_players_from_raw_json`, which already monkeypatches `SEASON_DIR` (`tests/test_player_metrics.py:205-222`).

### F-8 [major] The deploy-guard verification and the 2026 build depend on artifacts nobody is scheduled to produce

- Where: "Deploy guard"; Testing, paragraph after the table ("once with the 2026 files present"); non-goal "Automated Edge refresh" ("Edge bursts for 2026-27 come from a manual run").
- Evidence: `data/2026/generated/` holds only `players/`, and there's no `edge/player_bursts.csv` and no `browser/league.db`. The Edge scripts need the season's `league.db` first (`v2/edge/fetch_skater_detail.py:3`). The 80% coverage check (`verify_runtime_data.py:19`, `:53-58`) also needs that build. Given F-1, the build doesn't succeed until about two weeks of games exist.
- Problem: The "files present" verification can't run until someone does a manual Edge run on a healthy 2026 build. The spec doesn't say who does it or when, or whether the plan waits for it. Until then, every production deploy, including a 2025-only hotfix, is refused. The spec states that consequence but doesn't say whether it's accepted.
- Fix: Add to "Deploy guard": "Until 2026-27 has a `league.db` and an Edge run covering at least 80% of skaters, deploys are blocked. oiler accepts this and runs `NHL_SEASON=2026 python v2/edge/fetch_skater_detail.py` and `compute_burst_rates.py` once the 2026 build succeeds (see 'Early-season database'). The 'files present' check in Testing runs then. Until then, the plan verifies only the 'CSV missing' case." Alternatively, add a documented override such as `SKIP_SEASONS=2026` for an emergency deploy, and state the decision either way.

### F-9 [minor] `runtime_data/2026/` isn't gitignored

- Where: "Deploy guard" first bullet; "Rollover next season" step 2.
- Evidence: `.gitignore:11-12` lists `v2/browser/runtime_data/2024/` and `v2/browser/runtime_data/2025/` only. `git check-ignore -v v2/browser/runtime_data/2026/league.db` printed nothing and exited 1.
- Problem: The first sync puts a multi-MB SQLite file and a CSV into `git status` as untracked files, where a manual commit could pick them up.
- Fix: Add "Add `v2/browser/runtime_data/2026/` to `.gitignore`" to the "Deploy guard" bullets and to Rollover step 2.

### F-10 [minor] The season value from the client is never validated against `SEASONS`

- Where: "Pages and shared modules" first bullet (`season or DEFAULT_SEASON`) and third bullet (elites from the URL).
- Evidence: `store-season` data is supplied by the client on every callback request, and with `session` storage it also persists in `sessionStorage`. `/elites?season=...` goes straight to `league_query(..., season=season)`, and `runtime_paths.league_db()` joins it into a path (`runtime_paths.py:44-47`). So `/elites?season=2024` loads the 2024 database today, which works against the non-goal "Re-enabling 2024-25". `goalies.py:44` and `team.py:81` call `int(season)`, which raises `ValueError` on a non-numeric value.
- Problem: An unknown or stale season value either reaches data the spec says stays hidden or throws a callback error.
- Fix: Add `normalize_season(value) -> str` to the `seasons.py` table: it returns `value` if `value in SEASONS`, else `DEFAULT_SEASON`. Every `season or DEFAULT_SEASON` becomes `normalize_season(season)`, including the elites URL parameter. Add a Testing row: "`normalize_season('2024')`, `normalize_season('../x')`, and `normalize_season(None)` all return `DEFAULT_SEASON`."

### F-11 [minor] Two proposed tests target code that can't be imported or called in isolation as specified

- Where: Testing rows 3, 5, and 6; "Edge bursts per season" first bullet; "Pages and shared modules" second bullet.
- Evidence: Importing `pages/skaters.py` without the app raises `PageError: dash.register_page() must be called after app instantiation`. I checked this by copying `v2/browser` into a `mktemp -d` directory and running `import pages.skaters`. The player metadata lookup is inline in `player.py`'s `layout()` (`player.py:105-116`) with no helper to call. `_bursts_for` has an `lru_cache`, so results carry over between tests unless `cache_clear()` is called. With `DATA_DIR` unset, `player_bursts_csv("2025")` resolves to the real `data/2025/.../player_bursts.csv`, so "loads each season's own CSV" would read real data unless the path is monkeypatched. Row 3 ("through `birthDate`") tests only `_age_on` plus `age_cutoff`, not the DB column path.
- Problem: A planner has to invent where these functions live and how the tests isolate them.
- Fix: Put the cached loader in `burst_data.py` as `bursts_for(season)` (no Dash import). Extract `player_meta(pid, seasons=SEASONS)` as a module-level function in `player.py`, or put it in `db.py`, and name it in the spec. In Testing, say that the burst test monkeypatches `burst_data.player_bursts_csv` to a `tmp_path` file and calls `bursts_for.cache_clear()` in setup. Retitle row 3 "`_age_on` with `age_cutoff`: boundary", or add a skaters-callback test against a synthetic `league.db`.

### F-12 [minor] The Goal promises a plain "not available" message on every page, but the design specifies one only for goalies

- Where: Goal ("or says plainly that data for that season isn't available"); "Goalie sections for seasons without goalie data".
- Evidence: With no 2026 `league.db`, `league_query` returns an empty frame and the pages show their existing range messages: "No games found in this range." (`games.py:42`), "No games found for this range." (`teams.py:71`), "No data found for this range." (`skaters.py:93`), and "No game data for this range." (`player.py:151`). Those messages describe a date range, not a missing season.
- Problem: Two readings: (a) the existing range messages count as "plainly", so there's nothing to build; (b) each page needs a season-level message such as "2026-27 data isn't available yet" when the season's `league.db` is missing. The test for the Goal depends on which reading holds.
- Fix: State the rule: "When `league_db(season)` doesn't exist, games, teams, team, skaters, and player show `'{season_label(season)} data isn't available yet.'`; otherwise the existing range messages stay." Or say explicitly that the range messages satisfy the Goal.

### F-13 [minor] Team-page goalie message: which empty case, and "empty section" misdescribes current code

- Where: "Goalie sections for seasons without goalie data" second bullet.
- Evidence: `_goalie_environment_section()` returns `None` when `env` is empty, and `update_team` then omits the section entirely (`team.py:80-83`, `:336-345`). There's no empty section today. The query filters by season, team, and situation (`team.py:76`), so "no rows for the season" could also mean "no row for this team" in a season that has goalie data, or a missing `goalies.db` in local dev, where the message would read "2025-26 goalie data isn't available yet." That wording is misleading, because the data exists but wasn't built. The goalie-situation dropdown still shows on `/team/` for 2026 (`app.py:314-318`) with nothing to filter.
- Problem: A planner can't tell whether to show the message whenever that team's row is missing or only when the whole season is absent from `goalies.db`.
- Fix: Replace the bullet with "When `goalie_seasons` has no rows for the season, `_goalie_environment_section()` returns the heading and the `/goalies` message instead of `None`. A missing single-team row keeps today's behavior and omits the section." Optionally, hide `goalie-situation-bar` when the selected season has no goalie data, or state that it stays visible.

### F-14 [minor] Stale prose the design makes wrong isn't listed for update

- Where: "Edge bursts per season", "Age from player data", "App shell".
- Evidence: `burst_data.py:1-9` and `:40` ("skater Age, SB/a60 and Max MPH depend on it") and `verify_runtime_data.py:6` ("blank Age/SB-a60/Max-MPH") become wrong once Age comes from `players`. `burst_data.py:5-7` says a missing CSV causes "a boot failure that Fly's deploy health check catches", and `Dockerfile:37-41` says the skaters page "raises at import". Both are false once loading is lazy. The Max MPH glossary says "across all 2025-26 regular-season ice time" (`app.py:162`), which is wrong when 2026-27 is selected. The spec also doesn't say whether `BURST_COLUMNS` (`burst_data.py:21`) keeps `birth_date`. Keeping it means a 2026 CSV without that column raises `KeyError` at `pd.read_csv(path)[BURST_COLUMNS]`.
- Problem: A planner following only the listed edits leaves misleading docstrings, error messages, and glossary text, and has to guess the burst CSV contract.
- Fix: Add a short "Text and contract updates" list covering those comments, messages, and docstrings, and change the Max MPH glossary to "the selected season's regular-season ice time". Decide `BURST_COLUMNS`: either "drops `birth_date`" or "keeps `birth_date` for the Edge CSV contract; the browser ignores it."

### F-15 [minor] The player metadata lookup silently drops the 2024 fallback

- Where: "Pages and shared modules" second bullet.
- Evidence: Today's lookup is 2025, then 2024 (`player.py:105-107`). The new lookup covers only `SEASONS` (`["2025", "2026"]`). `runtime_data/2024/league.db` still ships (`sync-runtime-data.sh:19`, `Dockerfile:44`), and `/elites?season=2024` still links to 2024 players (`elites.py:40`).
- Problem: A player who appears only in 2024-25 now renders as "Player {id}" with no subtitle. That may be intended given the non-goal, but the spec doesn't say so.
- Fix: Add "The 2024 fallback is dropped; a 2024-only player shows as `Player {id}`." Or look up `SEASONS` plus `"2024"` and say why.

### F-16 [nit] The sync-script failure test passes for a different reason than the guard it claims to check

- Where: Testing paragraph ("once with the 2026 burst CSV missing. The second run must exit non-zero").
- Evidence: `tools/sync-runtime-data.sh:11` sets `set -euo pipefail`, and the copy lines (`:19-23`) run before the non-empty loop (`:27-32`). With the source CSV missing, `cp` fails and the script exits before the guard or `verify_runtime_data.py` runs.
- Problem: The test proves `cp` fails, not that the new non-empty and coverage checks work.
- Fix: Add a second negative case: "a 2026 burst CSV with a header only, or with coverage under 80%, makes the run exit non-zero at `verify_runtime_data.py`."

### F-17 [nit] "Only the filter labels use `season_label()`" contradicts the goalie message

- Where: "Season config" paragraph under the table; "Goalie sections" first bullet.
- Evidence: The goalie message is `"{season_label(season)} goalie data isn't available yet."`
- Problem: Two statements disagree about where labels appear.
- Fix: "Only user-facing text (filter labels and 'not available' messages) uses `season_label()`."

### F-18 [nit] The `app.py` line citation for `display:none` is wrong

- Where: Problem, first bullet ("`display:none`, `app.py:84`").
- Evidence: `app.py:84` is a comment line. The `style={"display": "none"}` for the filter bar is at `app.py:99`.
- Problem: Wrong citation.
- Fix: Change it to `app.py:99`.

### F-19 [nit] `season_label()` is specified only by one example

- Where: "Season config" table, `season_label(season)` row.
- Evidence: The row gives only `"2025"` → `"2025-26"`.
- Problem: Century rollover and non-numeric input are undefined. The rollover case is academic; with F-10 in place, non-numeric input never reaches the function.
- Fix: "`season_label(season)` returns `f'{y}-{(y + 1) % 100:02d}'` where `y = int(season)`."

## Checked and sound

- Problem-section citations `skaters.py:22` (`_AGE_CUTOFFS`), `skaters.py:35` (`_BURSTS_DF` at import), `player.py:105` (2025, then 2024 lookup), `filters.py:9` and `:97`, `app.py:7`, `app.py:61`, `app.py:58` and `:82` comments, and the hard-coded `"2025"` lines in games, teams, team, skaters, player, goalies, and elites all match the code.
- The `season_date_range()` bug is real. `filters.py:15-17` returns `(yr-1)-10-01` through `yr-06-30`, so `"2026"` yields the 2025-26 window. The fallback triggers both for a missing database (`league_query` returns an empty frame) and for a database with no completed games (`MIN` is `None`).
- The Age boundary arithmetic in Testing row 3 is correct. With cutoff 2026-09-15, a player born 2000-09-16 is 25 and one born 2000-09-15 is 26, matching `_age_on` (`skaters.py:25-32`).
- `game.py` derives its season from the game ID (`game.py:121`), so "no change" holds.
- `db.query()` and `available_teams()` have no page callers. The only call site outside `db.py` is `tests/test_smoke.py:19`, so the `edm.db` non-goal is accurate.
- `players.csv` for both 2025 and 2026 already has a `birthDate` column, and `data/2026/players/*.json` carries `birthDate` (for example `8482877.json` → `2003-07-20`).
- The Edge scripts already honor `NHL_SEASON` (`v2/edge/compute_burst_rates.py:19-26`, `fetch_skater_detail.py:6`), so a manual 2026 Edge run needs no code change.
- `DEFAULT_MIN_OVERLAP = 0.80` and the coverage check against `competition` F/D skaters (`verify_runtime_data.py:19`, `:47-58`) match the spec's description.
- `load_bursts()` keeps its contract: it raises in runtime mode and returns an empty frame in dev (`burst_data.py:24-44`), and `tests/test_burst_data.py` covers both paths. `player.py`'s `_load_bursts()` is per-season and tolerates a missing file (`player.py:87-94`).
- `goalies.py` already shows a message for an empty result (`goalies.py:45-46`), so only its text changes.
- Nothing in the spec conflicts with the project's CLAUDE.md. It uses synthetic-data tests, runs `python -m pytest v2/ -v` before finishing, and doesn't mention git commits.
- `seasons.py` needs no app or page import (only `datetime.date`), and `Dockerfile:35` copies all of `v2/browser/`, so the new module ships.
