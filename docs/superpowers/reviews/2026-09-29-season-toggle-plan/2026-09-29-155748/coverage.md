---
lens: coverage
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/plans/2026-09-29-season-toggle-plan.md
---

# coverage review

## Verdict

not ready

## Findings

### F-1 [blocker] The early-season build fix the plan treats as shipped isn't committed, so a feature branch won't have it

- Where: Global Constraints, last bullet ("The early-season `build_league_db.py` fix ... already shipped on 2026-09-29. Don't redo it."); Task 6 Step 4 ("PASS (all, including the two early-season tests already there)"); Task 13 preamble ("after oiler merges").
- Evidence: `git show HEAD:v2/browser/build_league_db.py | grep -c _write_empty_player_metrics` prints `0`, and `git show HEAD:v2/browser/tests/test_player_metrics.py | grep -c no_one_eligible` prints `0`. `git status` shows both files as ` M` (modified, uncommitted) on master. The fix (`_write_empty_player_metrics`, the empty `constants` table) and the two tests exist only in the main checkout's working tree. The plan's Global Constraints expect execution on a feature branch, and Task 13 says "a worktree has none" of the data, so a worktree is the expected setup.
- Problem: A branch cut from HEAD (78ce20f) has neither the fix nor the tests. Task 6 Step 4's expected output can't happen there, and "Don't redo it" tells the implementer not to add the fix. Task 6 then modifies `build_league_db.py` and `test_player_metrics.py` on the branch while master's working tree holds uncommitted edits to the same two files, so the merge before Task 13 fails with "Your local changes would be overwritten". The master working tree also has other uncommitted files (`CLAUDE.md`, `v1/nhlgame.py`, `v2/orchestrator/*`), so "branch from master" doesn't say which state the branch starts from.
- Fix: Add a precondition before Task 1: "oiler commits the working-tree changes to `v2/browser/build_league_db.py` and `v2/browser/tests/test_player_metrics.py` (the early-season fix) to master; the feature branch is cut from that commit. Confirm with `git show HEAD:v2/browser/build_league_db.py | grep -c _write_empty_player_metrics` returning 1." The agent can't commit on master under CLAUDE.md, so this has to be oiler's step. If oiler won't commit first, replace the "Don't redo it" constraint with a Task 0 that applies the working-tree diff to the branch.

### F-2 [major] The skaters page raises for 2026-27 for about six weeks, and no task covers it or the spec's full-build test

- Where: Spec "Early-season database", bullets 3 and 4 ("Every other table builder must also complete on a season's first games. The test in the 'Testing' section runs the full build to prove it" / "Pages ... don't raise"), and Testing table row 1 (a full build in `main()` order). The plan has no task for either. Its Global Constraints fold them into "already shipped".
- Evidence: The competition CSVs carry only `pct_vs_top_fwd` and `pct_vs_top_def` (`head -1` of a `data/2025/generated/competition/*.csv` shows columns 9-10; no `pct_any_elite_*`). `pct_any_elite_fwd` and `pct_any_elite_def` are added only by `ALTER TABLE` inside `recompute_pct_vs_elite_fwd` (`build_league_db.py:559-562`) and `recompute_pct_vs_elite_def`. Both functions return before the `ALTER` when the elite table is empty (`build_league_db.py:553-556`, `:745-750`). Elite forwards need GP >= 10 (docstring "Phase 1 (GP < 10): no designation", `build_league_db.py:377`), and elite defensemen need GP >= 20 (`build_league_db.py:686`, `if gp < 20`). `pages/skaters.py:41` selects `c.pct_any_elite_fwd, c.pct_any_elite_def`. A scratch check (`pd.read_sql_query` of a missing column) raises `DatabaseError: ... no such column: c.pct_any_elite_fwd`. The shipped tests (`test_player_metrics_empty_table_when_no_one_eligible`, `test_constants_empty_table_when_no_one_eligible`) exercise only two builders, not `main()` order.
- Problem: From the first 2026 build until 2026-27 defensemen reach 20 GP, `update_skaters` for 2026 raises instead of showing data or the not-available message. The spec's Goal says every season-aware page must do one or the other. Locally this starts on 2026-09-30, when the daily run creates `data/2026/generated/browser/league.db`. The spec's own row 1 assertions (player_metrics and constants exist with 0 rows) wouldn't catch this schema gap either.
- Fix: Add a task before Task 10. (a) In both `recompute_pct_vs_elite_*` functions, move the "Ensure ... column exists" block above the `if not elite_rows: return`, or add both columns with default 0.0 in `build_competition_table`. (b) Add the spec's full-build test: synthetic early-season inputs (every skater under 5 GP), builders run in `main()` order. Assert that `player_metrics` and `constants` exist with 0 rows and that `competition` has `pct_any_elite_fwd` and `pct_any_elite_def`. Also update the spec's row 1 to name the schema assertion.

### F-3 [major] `game.py` raises on an empty `player_metrics`; the spec contradicts itself here and the plan followed the "no change" side

- Where: Spec "Pages and shared modules" ("`game.py` needs no change") versus spec "Early-season database" bullet 4 ("Pages treat an empty `player_metrics` or `constants` as missing values ... They don't raise"). The plan has no task touching `pages/game.py`. Task 13 Step 4's manual checks don't visit a game page.
- Evidence: `pages/game.py:196-197` runs `SELECT AVG(wppi) ... FROM player_metrics` and then `float(league_mean_df.iloc[0]["mean_wppi"])`. On an empty table this returns one row holding `None`. In scratch: `float(None)` raises `TypeError: float() argument must be a string or a real number, not 'NoneType'`. `pages/game.py:204`, `players_df["ppi_plus"].round(1)`, also raises on the all-NULL LEFT JOIN column (`TypeError: type NoneType doesn't define __round__ method`, pandas 3.0.0). The games page links every 2026 game to `/game/<id>`.
- Problem: While 2026 has no eligible skaters, every 2026-27 game page raises. The spec's "no change" line and its "don't raise" line can't both hold, and the plan kept the first without comment.
- Fix: Add a task (it can merge into Task 10). Set `league_mean_wppi` to `None` when the value is null (`v = league_mean_df.iloc[0]["mean_wppi"]; league_mean_wppi = float(v) if not league_mean_df.empty and pd.notna(v) else None`). Round with `pd.to_numeric(players_df["ppi_plus"], errors="coerce").round(1)`. Add `Format(precision=1, scheme=Scheme.fixed).nully("—")` to the PPI+ and Game wPPI+ columns in `_make_position_table`. Add a regression test that calls the game page's data path on a synthetic DB with an empty `player_metrics`. Correct the spec line to say game.py only needs the empty-metrics guard.

### F-4 [minor] The sync script keys the required tier on one variable, not the explicitly named files the spec calls for, and the spec's rollover steps break it

- Where: Task 12, `REQUIRED_SEASON="2025"` and `cp "$SRC/$REQUIRED_SEASON/generated/browser/edm.db"`.
- Evidence: The spec's Goal says the deploy guards "name each season's files explicitly". Spec "Rollover next season" step 3 says to "move [the new season] to the required tier". `build_edm_db.py:27` hard-codes `SEASON_DIR = "data/2025"`, and the Dockerfile guard lists `runtime_data/2025/edm.db` (`Dockerfile:44-48`).
- Problem: Following the spec's rollover step 3 with the plan's script means setting `REQUIRED_SEASON="2026"`. That stops syncing 2025 at all, leaves a stale `runtime_data/2025/` in the image because only optional seasons get `rm -rf`, and requires a `data/2026/.../edm.db` that nothing builds.
- Fix: Use `REQUIRED_SEASONS=("2025")` with a loop for each season's `league.db` and `player_bursts.csv`. Name `edm.db` with a literal `2025` path, as the script already does for `2024/league.db`. Add a rollover note in the script header: "a season leaving the required tier moves to OPTIONAL_SEASONS, never out of both lists".

### F-5 [minor] The optional-season `WARNING` line doesn't name the failed check, so the plan reverses a spec decision

- Where: Task 12, `sync_optional_season`, third `echo "WARNING: ... failed the check named in the FAIL line above ..."`.
- Evidence: The spec's Deploy guard table says the sync "prints a `WARNING` line naming the failed check". Spec Testing case 3: "same as case 2, with the failed check named". The plan's test looks for `"burst coverage"` anywhere in stderr, which the separate `FAIL:` line from `verify_runtime_data.py` satisfies.
- Problem: The WARNING line points at another line instead of naming the check. The spec says the WARNING line itself names it, so a grep for `WARNING` in deploy logs loses the reason.
- Fix: Capture the output: `if ! out="$(python3 "$VERIFY" "$stage/player_bursts.csv" "$stage/league.db" 2>&1)"; then echo "WARNING: $season not synced — ${out//$'\n'/; } ..." >&2`. Tighten the test to assert that one stderr line contains both `WARNING: 2026 not synced` and `burst coverage`.

### F-6 [minor] The sync tests skip two of the spec's verification cases: burst CSV missing alone, and a header-only CSV

- Where: Task 12 Step 1, `test_optional_season_missing_is_removed_not_fatal` (uses `_src(tmp_path, with_2026=False)`) and the test list.
- Evidence: Spec case 2 is "With the 2026 burst CSV missing", with `league.db` present. That's the state Task 13 Step 3 expects in real life ("Until a 2026 Edge run exists"). `with_2026=False` removes both 2026 files. Spec case 3 names "a 2026 burst CSV that has a header only, or covers under 80%". The plan tests only the under-80% case.
- Problem: The real-world path (league.db present, CSV absent) and the header-only path (it passes `-s` and relies on `verify_burst_csv`'s `df.empty` branch) are unverified.
- Fix: Add a `bursts_2026=False` option to `_src` that builds the 2026 `league.db` but no CSV, and use it in the case 2 test. Add a case 3b test that writes `playerId,bursts_per_60,speed_max_mph,birth_date\n` only and asserts exit 0, the `WARNING`, `empty burst CSV` in stderr, and no `runtime_data/2026/`.

### F-7 [minor] The plan keeps the season bar's hard-coded `display:none`; the spec says to remove it

- Where: Task 11 Step 3 item 3: `], id="season-bar", className="filter-bar", style={"display": "none"}),`.
- Evidence: Spec "App shell": "The filter bar gets an `id` (`season-bar`) and loses its hard-coded `display:none`."
- Problem: This quietly reverses the spec. The plan's choice (start hidden, let `toggle_season_bar` show it, the same pattern as `goalie-situation-bar` at `app.py:115-116`) is defensible, since it avoids a flash on non-season pages. But the plan should say so, not diverge silently.
- Fix: Either drop the `style` argument, or keep it and add one sentence to Task 11: "Starts hidden like `goalie-situation-bar`; `toggle_season_bar` shows it. This deviates from the spec's 'loses its display:none' to avoid a flash on non-season pages." Update the spec to match.

### F-8 [minor] Task 12 adds a test-only env interface and a permanent test file; the spec asked for four verification runs

- Where: Task 12, the `SYNC_SRC`/`SYNC_DST` overrides and `v2/browser/tests/test_sync_runtime_data.py`.
- Evidence: Spec Testing: "Verify the sync script by running `./tools/sync-runtime-data.sh` four ways". It asks for no env overrides and no pytest file. CLAUDE.md: "Scratch checks stay scratch; don't promote them into permanent test files", though it also lists security and deploy boundaries as places where tests pay off.
- Problem: The plan builds something the spec didn't ask for: a new script interface, plus a subprocess test that needs `python3` with pandas on PATH during every `pytest v2/` run. It may well be the better choice, since the deploy guard is a high-risk boundary, but it's a scope decision the spec didn't make.
- Fix: Record the decision in Task 12 ("Promotes the spec's four manual runs to a permanent test because the deploy guard is a high-risk boundary; adds `SYNC_SRC`/`SYNC_DST` for it") and add it to the spec's Testing section. Otherwise, run the four cases as scratch checks in a `mktemp -d` copy and drop the env overrides.

### F-9 [minor] Two tests can't go red before their change, which conflicts with the evergreen "every test goes red" rule

- Where: Task 9, `test_team_goalie_section_team_absent_is_omitted`; Task 12, `test_required_season_failure_is_fatal`.
- Evidence: Current `_goalie_environment_section` (`pages/team.py:80-83`) already returns `None` for a missing team and a section for EDM, so the first test passes today. The current sync script hard-codes `SRC="$REPO_ROOT/data"` (`tools/sync-runtime-data.sh:14`), and in a worktree with no `data/` its `cp` fails, so it exits non-zero and the second test passes today. CLAUDE.md (evergreen): "Every test goes red before it goes green", and for guards on existing behavior, "prove the test can fail by temporarily breaking the code it covers."
- Problem: The plan's Step 2 "Expected: FAIL" holds for the file as a whole but not for these two tests, so they never prove anything.
- Fix: In each Step 2, add a line. Task 9: "`test_team_goalie_section_team_absent_is_omitted` already passes; temporarily make the empty branch return the message unconditionally and confirm it goes red, then restore." Task 12: "`test_required_season_failure_is_fatal` passes on the old script for the wrong reason; after Step 3, temporarily remove the `exit 1` in the required-file loop and the verify call and confirm it goes red, then restore."

### F-10 [nit] Task 13's manual checks drop the desktop width and the Age em dash

- Where: Task 13 Step 4.
- Evidence: Spec final checks: "matches DESIGN.md at desktop and phone widths" and "SB/a60, Max MPH, and Age show an em dash where data is missing". The plan checks only "under `640px`" and says "Age still shows".
- Problem: The desktop check and the Age em dash check are missing.
- Fix: Add "At desktop width, the season filter sits in the filter bar with the eyebrow `SEASON` label and inline options" and "A skater with no `birthDate` shows `—` in Age."

### F-11 [nit] The Dockerfile comment generalizes the gitignored season list

- Where: Task 12, the Dockerfile comment ("runtime_data/<season>/ folders are gitignored").
- Evidence: Spec "Text and contract updates": "Also update its list of gitignored season directories". The current comment names `runtime_data/2024/ and /2025/` (`Dockerfile:37`).
- Problem: The spec asks for an updated list, and the plan swaps the list for a placeholder. That's functionally fine, but it's a wording deviation.
- Fix: Use "runtime_data/2024/, /2025/ and /2026/ are gitignored", or record the generalization as intended.

### F-12 [nit] The team page's PPI column gets no em dash (a spec omission, not a plan gap)

- Where: Task 10, `team.py:118-119` edit.
- Evidence: `pages/team.py:117` shows `PPI` (`ppi`) with `Format(precision=2, scheme=Scheme.fixed)`. It's null early in the season for the same reason PPI+ is. The spec names only PPI+ and wPPI+.
- Problem: A blank cell sits beside em-dash cells in the same row group.
- Fix: Optionally add `.nully("—")` to the `PPI` format at `team.py:117`, and note it in the spec.

## Checked and sound

- Every spec requirement outside F-1 to F-12 maps to a task: `seasons.py` (T1), `age_in_season` (T2), `season_ready` (T3), `player_meta` with 2024 dropped plus the `db.py` defaults (T4), `bursts_for` with `lru_cache`, the docstring, and the `:40` error text (T5), `birthDate` in `keep` and in recovery (T6), the date-range fallback and not-ready message (T7), the `birthDate` verify check and the `:6` docstring (T8), page normalization, the goalie texts, the team goalie section, and `/elites` (T9), skaters bursts, Age, and em dashes, plus PPI+/wPPI+ `nully` on team and teams (T10), the app shell, persistence, CSS, and glossary (T11), the two-tier sync, Dockerfile comment, and `.gitignore` (T12), and the rollout rebuild (T13).
- Restated values match the spec word for word: `SEASONS = ["2025", "2026"]`, `DEFAULT_SEASON = "2025"`, `f"{season_label(season)} data isn't available yet."`, `f"{season_label(season)} goalie data isn't available yet."`, `season_label` formula `f"{y}-{(y + 1) % 100:02d}"`, `age_cutoff` `date(int(season), 9, 15)`, fallback `("2026-09-01", "2027-06-30")`, `Format(precision=2, scheme=Scheme.fixed).nully("—")` and `Format().nully("—")`, 80% `DEFAULT_MIN_OVERLAP`, 95% birthDate coverage, `.gitignore` entry `v2/browser/runtime_data/2026/`, id `season-bar`, class `season-options`, `persistence=True, persistence_type="session"`, and `store-season` staying `memory`.
- The season-aware path lists match the spec: shown on `/games`, `/teams`, `/team/*`, `/skaters`, `/player/*`, `/goalies`, and hidden on home, `/game/*`, `/goalie/*`, `/elites`, and notes.
- The spec's test values are carried over exactly: the age boundary (`2000-09-16` gives 25, `2000-09-15` gives 26), `normalize_season` rejecting `"2024"`, `"../x"`, and `None`, `player_meta` newest-first plus 2026-only plus unknown, `bursts_for` with `cache_clear()` in a fixture, and `season_ready` in both modes.
- CSS against DESIGN.md: Mobile is `< 640px` (DESIGN.md:175), so `@media (max-width: 639px)` is right. "Radio/checkbox controls padded to `40px` rows" (DESIGN.md:180) matches `min-height: 40px`. The navy radio accent (DESIGN.md:108) and `--text`/`--text-3`/`--navy` tokens exist in `assets/style.css:7-15`. The eyebrow spec (0.75rem/600/uppercase/0.05em, DESIGN.md:88) matches the rescoped `.filter-bar .filter-bar-label`. Adding `filter-bar-label` to the "Situations" label is needed because it's the only other `.filter-bar` label (`app.py:105`), not extra scope.
- All seven `Input("store-season", "data")` consumers are covered: `filters.py:94` (T7), `games.py:34`, `teams.py:62`, `team.py:177`, `player.py:135`, `goalies.py:38` (T9), and `skaters.py:78` (T10). Both `int(season)` sites (`goalies.py:44`, `team.py:81`) receive normalized values.
- Plan line references are accurate: `app.py:6-8`, `filters.py:9-19`, `player.py:19-22` and `:105-107`, `team.py:117-119`, `teams.py:239-242`, `Dockerfile:37-41`, `.gitignore:10-13`. The Task 9 and Task 10 grep checkpoints return what they claim, given the current `"2025"` sites (the `grep` output lists `skaters.py:22,35,81` as the only page sites left after T9).
- `players.csv` has `birthDate` (column 10) for 2024, 2025, and 2026, so `usecols=keep` won't fail. `build_league_db.PLAYERS_CSV` and `SEASON_DIR` are module constants, so the T6 monkeypatches work. The current 2025 `players` table has no `birthDate` (`PRAGMA table_info`), so T13's rebuild before sync is needed and is in the plan.
- `league_query` returns an empty frame without connecting when the DB file is absent (`db.py:36-38`), so a page query can't create `league.db` and flip `season_ready` to true.
- teams.py, team.py, and player.py tolerate an empty `player_metrics`/`constants` without raising: `teams.py:144` guards on `constants_df.empty`, `_tercile_styles` returns `[]` for an all-null column, `team.py:236-237` uses `pd.to_numeric(..., errors="coerce")`, player.py's `_pool_val` maps NaN to `None`, and `_fmt` renders `None` as `—`.
- `verify_birthdates` low-coverage fixture: 18 of 20 gives `90.0%`, matching the assertion. The existing verify tests don't call `main`, so the new `main` doesn't break them.
- Existing test helpers the plan reuses exist as described: `_write_csv` and `_VALID_ROW` (playerId 8478402, speed 24.6) in `test_burst_data.py`, the `from utils import`, `from runtime_paths import`, and `from verify_runtime_data import` lines, `_make_db` and `_make_csv`, and `_setup_recovery_db`.
- The tech-stack header matches the repo: `dash==4.0.0`, `pandas==3.0.0` (`requirements.txt`), local Python 3.11.6.
- The spec non-goals are respected: no deploy-freshness work, no goalie pipeline change, no Edge automation, 2024 kept out of `SEASONS` and still shipped, `/elites` still read from the query string, `edm.db` untouched, and the `build_league_db.py` CLI default left at `"2025"`.
