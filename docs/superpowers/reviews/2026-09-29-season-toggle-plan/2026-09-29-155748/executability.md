---
lens: executability
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/plans/2026-09-29-season-toggle-plan.md
---

# executability review

## Verdict

not ready

## Findings

### F-1 [blocker] The "already shipped" early-season build fix is not in git, so a branch cut from HEAD doesn't have it

- Where: Global Constraints, last bullet ("The early-season `build_league_db.py` fix ... already shipped on 2026-09-29. Don't redo it."); Task 6 Step 4; Task 13 Step 1
- Evidence: `git status` shows ` M v2/browser/build_league_db.py` and ` M v2/browser/tests/test_player_metrics.py` on master (HEAD `78ce20f`). `git diff` on those files shows exactly the early-season fix: `PLAYER_METRICS_COLUMNS`, `_write_empty_player_metrics()`, the empty `constants` table, and the tests `test_player_metrics_empty_table_when_no_one_eligible` and `test_constants_empty_table_when_no_one_eligible`. None of it is committed. The same checkout also has uncommitted edits to `CLAUDE.md`, `v1/nhlgame.py`, `v2/orchestrator/config.py` (`NHL_SEASON` default `"2026"`), and the plist. `docs/superpowers/` (this plan and its spec) is untracked (`?? docs/superpowers/`).
- Problem: Task 13 says a worktree has no `data/`, so Tasks 1-12 are meant to run on a feature branch or worktree. A worktree cut from HEAD has none of the fix. So Task 6 Step 4's "PASS (all, including the two early-season tests already there)" is false, and the branch's `build_league_db.py` still raises `no such table: player_metrics` early in the season. Task 6 also edits the same two files, so merging the branch into the dirty main checkout is refused ("Your local changes ... would be overwritten"). The worktree also lacks the spec and plan files that the plan header cites. If the work runs in the main checkout on a new branch instead, the unrelated uncommitted edits go along with it and can end up in the per-task commits.
- Fix: Add a precondition before Task 1: "oiler commits the early-season fix (`v2/browser/build_league_db.py`, `v2/browser/tests/test_player_metrics.py`) on master by itself, and commits or stashes the other working-tree edits, before the branch is cut. Record the SHA here." Then reword the Global Constraint to "shipped in commit `<sha>`". Also say where the implementer reads the spec when `docs/superpowers/` isn't in the worktree: commit it first, or paste the needed sections into the tasks.

### F-2 [major] The skaters page raises for 2026-27 until a forward has 10 GP and a defenseman has 20 GP

- Where: Task 10 (skaters `_COMP_SQL`); Task 13 Step 4 ("In 2026-27 ... no page errors")
- Evidence: `pages/skaters.py:41` selects `c.pct_any_elite_fwd, c.pct_any_elite_def`. Those columns aren't in the competition CSVs. The header of `data/2025/generated/competition/*.csv` ends at `...line_number,deployment_score`. They're added only by `ALTER TABLE` inside `recompute_pct_vs_elite_fwd` (`build_league_db.py:560-563`) and `recompute_pct_vs_elite_def` (`:753-756`), after early returns when no elites exist (`:554-556`, `:748-750`). Elites need `gp >= 10` for forwards (`:436`) and `gp >= 20` for defensemen (`:685`). In a scratch copy I built a synthetic 3-game competition table and ran `build_elite_forwards_table`, `recompute_pct_vs_elite_fwd`, `build_elite_defensemen_table`, and `recompute_pct_vs_elite_def`. The output was `pct_vs_elite_fwd: skipped (no elite forwards)`, and `SELECT c.pct_any_elite_fwd, c.pct_any_elite_def FROM competition c` then raised `OperationalError no such column: c.pct_any_elite_fwd`.
- Problem: For the first 3-6 weeks of 2026-27, which is the launch window for this feature, a 2026-27 selection on `/skaters` makes the callback raise. That breaks the spec requirement that pages don't raise early in the season, and Task 13's manual check fails with no task to fix it. No other page reads those columns: with the columns present, I ran games, teams, team, and player on a synthetic early-season 2026 DB with empty `player_metrics` and `constants`, and all four returned without error.
- Fix: Add a task before Task 10, or extend Task 6. In `build_league_db.py`, add the two columns before the early returns: move the `ALTER TABLE competition ADD COLUMN pct_any_elite_fwd REAL DEFAULT 0.0` and `..._def` blocks above the `if not elite_rows: return` in each function, or add an `_ensure_pct_any_elite_columns(conn)` call in `main()` after `build_competition_table`. The test must fail first: on a synthetic competition table where every skater has fewer than 10 games, run both recompute functions and assert that `PRAGMA table_info(competition)` lists `pct_any_elite_fwd` and `pct_any_elite_def`.

### F-3 [minor] Checkpoints say "all pass", but 5 `requires_data` tests fail in any checkout without `data/`

- Where: Step 5 "Checkpoint" of Tasks 1-12 (`python -m pytest v2/ -q`, "Expected: all pass"); Task 11 Step 4 (includes `test_smoke.py`)
- Evidence: I copied `v2/`, `tools/`, and `pyproject.toml` into a scratch dir without `data/` and ran `python -m pytest v2/ -q`. Result: `5 failed, 317 passed` (`test_build_goalies_db.py::test_5v5_toi_is_strictly_less_than_all_situations_toi`, `test_smoke.py::test_league_db_exists`, two in `test_compute_competition.py`, and `test_toi_5v5.py::test_zero_5v5_toi_implies_no_5v5_shots`). All five are `@pytest.mark.requires_data`. The marker text in `pyproject.toml` says: "CI deselects these with -m 'not requires_data'". With every plan change applied, the result is `355 passed, 5 deselected` under `-m "not requires_data"`.
- Problem: An implementer in a worktree sees 5 failures at every checkpoint and either stops or learns to ignore red. Task 11 Step 4 also runs `test_smoke.py`, which includes `test_league_db_exists`.
- Fix: For Tasks 1-12, change the checkpoint command to `python -m pytest v2/ -q -m "not requires_data"` and add a Global Constraint explaining why. Keep the unfiltered `python -m pytest v2/ -v` in Task 13 Step 5, which runs in the main checkout with `data/`. In Task 11 Step 4, add `-m "not requires_data"`.

### F-4 [minor] Two new tests never go red, which breaks the plan's own "every test goes red" rule

- Where: Task 9 `test_team_goalie_section_team_absent_is_omitted`; Task 12 `test_required_season_failure_is_fatal` and the Step 2 note
- Evidence: In the scratch Task 9 red run, only 4 of the 5 new tests failed. `test_team_goalie_section_team_absent_is_omitted` passes on current code, because `_goalie_environment_section` already returns `None` for a missing row (`team.py:82-83`). In the scratch Task 12 red run against the current script (no `data/`), 3 tests failed and `test_required_season_failure_is_fatal` PASSED. The old script ignores `SYNC_SRC` and exits non-zero on its first `cp "$SRC/2024/..."`, not because of the 2025 check. The same run created `v2/browser/runtime_data/2024/` and `2025/` in the checkout (`mkdir -p` at old script line 17).
- Problem: Both are guard tests for existing behavior, and the plan doesn't say so or give a way to prove they can fail. In the main checkout, where `data/` exists, the old script instead copies the real tree into the real `runtime_data/`. That contradicts Step 2's "Don't let the current script write into the real `runtime_data/`", and the note's remedy ("rerun `./tools/sync-runtime-data.sh` afterward to restore it") can't work in a worktree, which has no `data/`.
- Fix: In Task 9 Step 2, add: "`test_team_goalie_section_team_absent_is_omitted` passes before the change: it guards existing behavior. Prove it can fail by temporarily changing the new `return None` to return the message `Div`." In Task 12 Step 2, add: "`test_required_season_failure_is_fatal` is a guard. After Step 3, prove it by temporarily appending `|| true` to the required-season bursts `cp` line, then revert." Replace the runtime_data note with: "Run Step 2 only in a worktree (no `data/`), where the old script fails on its first `cp`. It may create empty `v2/browser/runtime_data/2024/` and `2025/` dirs there, which are gitignored and harmless."

### F-5 [minor] DESIGN.md conflict: Dash 4's hover and focus rule turns the season option text purple

- Where: Task 11 Step 3, `style.css` block (`.season-options label { color: var(--text); ... margin-right: 1rem; }`)
- Evidence: The installed Dash is 4.0.0 (`python -c "import dash; print(dash.__version__)"`). Its `dash_core_components.js` injects `optionslist.css` with `.dash-options-list-option:not(:has(input[disabled])):hover, .dash-options-list-option:not(:has(input[disabled])):focus-within { color: var(--Dash-Fill-Interactive-Strong); }`, and the same bundle defines `--Dash-Fill-Interactive-Strong: #7f4bc4`. RadioItems labels carry that class (`radioitems.css`: `.dash-options-list-option.dash-radioitems-inline { display: inline-flex; margin-right: calc(var(--Dash-Spacing) * 4); }`). The hover rule's specificity is (0,3,1), which beats the plan's `.season-options label` at (0,1,1). The inline rule's (0,2,0) also beats it, so the plan's `margin-right: 1rem` never applies. `style.css` doesn't override any `--Dash-*` variable (grep found none).
- Problem: Hovering or keyboard-focusing a season option turns its text `#7f4bc4` purple. DESIGN.md §3 says "Navy is the only chromatic text color", and §7 says "Don't ship purple/blue Bootstrap defaults — override ... component colors to the tokens."
- Fix: Add to the Task 11 CSS: `.season-options { --Dash-Fill-Interactive-Strong: var(--navy); --Dash-Text-Strong: var(--text); }`. Raise the label selector to `.filter-bar .season-options label` (0,2,1) so the margin and color apply. Add "hover an option: text stays navy or near-black, never purple" to Task 13 Step 4.

### F-6 [minor] Conflict with the evergreen CLAUDE.md on commits

- Where: Global Constraints ("Under subagent-driven execution on a feature branch, one local commit per reviewed task is allowed.")
- Evidence: Project `CLAUDE.md`, Development Workflow step 6: "Git: Do no commit files to the git repo. Those actions will be done manually". The auto-memory index notes an authorized exception for local per-task commits during SDD builds (`feedback_sdd_local_commits.md`), but that exception isn't in any evergreen doc.
- Problem: The plan permits something the evergreen doc forbids. The global CLAUDE.md treats a conflict with evergreen as a stop sign, not a tiebreaker. An implementer who reads only the project CLAUDE.md gets contradictory instructions.
- Fix: Either cite the authorization in the constraint ("per oiler's standing SDD exception, recorded in memory `feedback_sdd_local_commits.md`"), or ask oiler to add the exception to project `CLAUDE.md` step 6. Don't leave the two in silent conflict.

### F-7 [minor] The spec's full-build early-season test was dropped, and two builders still fail on a season's first day

- Where: Global Constraints (early-season fix "don't redo"); Task 13 Step 1; spec "Early-season database" and Testing row 1
- Evidence: The spec requires "Every other table builder must also complete on a season's first games. The test in the "Testing" section runs the full build to prove it". The shipped, uncommitted diff adds only the two unit tests (see F-1). Two gaps remain in `build_league_db.py`. First, `build_competition_table` returns without creating the table when no CSVs exist (`:55-57`), and `_recover_missing_players` then queries `FROM competition c` (`:81-86`), so it raises `no such table`. Second, `build_points_5v5_table` creates no table when there are no 5v5 goals (`:215-217`), and `build_elite_forwards_table` then reads `points_5v5` (`:417-420`). `ls data/2026/generated/` currently shows only `players`.
- Problem: If Task 13 Step 1 runs before the orchestrator has processed a 2026 game, `python v2/browser/build_league_db.py 2026` crashes, and no task covers the fix. F-2's gap would also have been caught by the spec's full-build test if the test ran the skaters query.
- Fix: Either add the spec's full-build test as a task (run the builders in `main()` order on a synthetic sparse season and assert `player_metrics`, `constants`, `points_5v5`, `elite_forwards`, `elite_defensemen`, and the F-2 columns exist), or record the gap as a known limitation. At minimum, add a precondition to Task 13 Step 1: "at least one 2026 game has been processed (`ls data/2026/generated/competition/*.csv` is non-empty)".

### F-8 [nit] Spec sync case 3 (a header-only 2026 burst CSV) has no test

- Where: Task 12 Step 1
- Evidence: Spec "Verify the sync script" case 3: "With a 2026 burst CSV that has a header only, or covers under 80% of skaters". The plan covers only the under-80% case (`bursts_2026=[0, 1]`). A header-only file passes `-s`, so it reaches the `verify_runtime_data.py` path, which is a different path from the one the test covers.
- Problem: The spec requires a check that no test covers.
- Fix: Add `test_optional_season_header_only_csv_is_removed_not_fatal`. It writes `playerId,bursts_per_60,speed_max_mph,birth_date\n` to `2026/generated/edge/player_bursts.csv`, then asserts exit 0, a `WARNING: 2026 not synced` line, `"empty burst CSV" in r.stderr`, and no `dst/2026`.

### F-9 [nit] The docstring phrase Task 8 says to replace is split across two lines

- Where: Task 8 Step 3 ("change the docstring phrase "blank Age/SB-a60/Max-MPH columns"")
- Evidence: `verify_runtime_data.py:6-7` reads `*before* \`fly deploy\` — instead of silently shipping blank Age/SB-a60/Max-MPH` followed by a line break and `columns (the exact failure this guards against).`
- Problem: An exact-string Edit on "blank Age/SB-a60/Max-MPH columns" fails.
- Fix: Quote the full two-line text to replace, or give the replacement docstring in full.

### F-10 [nit] Some line references are stale or imprecise

- Where: Task 4 Files (`player.py ... :105-107`); Task 10 Files and Step 3 (`team.py:117-119` / `:118-119`, `teams.py:239-242`)
- Evidence: The lookup block Task 4 replaces is `player.py:105-116` (through `pos_code = ...`), not 105-107. Task 9 edits `team.py` and `teams.py` before Task 10: it adds a `seasons` import line to both, plus `_ENV_SEASON_SQL` and a 6-line branch to `team.py`. So by Task 10, the PPI+ and wPPI+ entries sit at about `team.py:126-127` and `teams.py:240-243`.
- Problem: The ranges point at the wrong lines. The text around them still identifies the target.
- Fix: Replace the line numbers with content anchors: "the PPI+ and wPPI+ entries in `_make_position_table`'s `columns`" and "the PPI+ and wPPI+ entries in `update_teams`'s `columns`". For Task 4, use `:105-116`.

### F-11 [nit] Appended test code puts imports in the middle of the file

- Where: Task 5 Step 1 (`import burst_data` / `from burst_data import bursts_for` appended); Task 10 Step 1 (`import pages.skaters as skaters` appended)
- Evidence: Both snippets are appended at the end of an existing test file, below existing test functions. No linter is configured in `pyproject.toml`, so nothing fails.
- Problem: The style differs from the rest of the test files, whose imports sit at the top. A later ruff run flags E402.
- Fix: Tell the implementer to merge the new imports into the file's top import block.

## Checked and sound

- I applied every task's code and tests exactly as written in a scratch copy (`mktemp -d` under the scratchpad). Each task's own test run passed. The full suite gave `355 passed, 5 deselected` with `-m "not requires_data"`.
- Red-phase failures match the stated expectations: Task 1 (`ModuleNotFoundError`), Task 2 (`ImportError ... age_in_season`), Tasks 3, 4, 5, 7, 8 (ImportError), Task 6 (`no such column: birthDate`; `(None,) != ('2004-02-29',)`), Task 9 (date-range text, "No goalie data for this season.", `None` section, elites seeing `'../x'` and `'2024'`), Task 10 ("No data found for this range.", `_BURSTS_DF` present), Task 11 (`AttributeError ... toggle_season_bar`, `'2019' != '2025'`, `['2025'] != [...]`), and Task 12 (the 3 optional-season tests fail).
- Dash 4.0.0 `@callback` functions can be called directly, and `import pages.x` after `import app` returns the registered page modules. Tests in Tasks 9-11 rely on both.
- Callback signatures used in tests match the code: `update_games(d0, d1, season)`, `update_teams(d0, d1, ha, season)`, `update_team(d0, d1, ha, abbrev, season, situation)`, `update_player(d0, d1, ha, pid, position, season)`, `update_skaters(d0, d1, ha, season)`, `update_goalies(season, situation)`, `elites.layout(season=None)`.
- File, symbol, and line references are correct: `app.py:6-8` (comment, `SEASONS`, `DEFAULT_SEASON`), `filters.py:9-19` and `:97`, `player.py:19-22` (`_META_SQL`), `db.py` defaults at `:31` and `:46`, `burst_data.py:24` and `:40`, `build_players_table` `keep`, `_recover_missing_players` row dict, `PLAYERS_CSV`, `SEASON_DIR`, `_setup_recovery_db`, `_write_csv`, `_VALID_ROW` (playerId 8478402, speed 24.6), `_make_db`, `_make_csv`, `.gitignore:10-13`, and the `Dockerfile:37-41` comment block.
- The grep checkpoints give the stated output: after Task 9, only `skaters.py` matches `"2025"`; after Task 10, `pages/` has none.
- Task order and dependencies hold: `seasons` (1), then `utils` (2), `runtime_paths` (3), `db` (4), `burst_data` (5), `filters` (7, which needs 1 and 3), pages (9, which needs 7), skaters (10, which needs 2, 3, 5, 6, 7), app (11), and the sync script (12, which needs 8's CLI). No module import cycle: `seasons` imports only `datetime`.
- `REPO = Path(__file__).resolve().parents[3]` in Task 12 resolves to the repo root. `python3` on PATH (pyenv 3.11.6) has pandas 3.0.0. The plan's sync script passes all 4 of its tests, including removing a stale `runtime_data/2026/`.
- `players.csv` has a `birthDate` column in both `data/2025` and `data/2026`, and player JSON carries `birthDate`. In a read-only check, 2025 coverage is 940 of 940 F/D skaters (742 from `players.csv`, 198 via JSON recovery), so the 95% check in Task 13 Step 2 will pass.
- With the plan's changes, the skaters callback on a synthetic 2026 DB with no burst CSV returns ages from `birthDate` (25 for `2000-09-16`, null for a missing date). NaN values serialize to `null` for `.nully("—")`. Games, teams, team, and player don't raise on empty `player_metrics` and `constants`.
- The CSS tokens the plan uses (`--text`, `--text-3`, `--navy`) exist in `assets/style.css:3-15`. The eyebrow values (0.75rem, 600, tertiary, uppercase, 0.05em) match the DESIGN.md typography table. Navy radio accent and 40px rows under 640px match DESIGN.md §4 and §8.
- `season_date_range`'s new `pd.isna` check handles the NULL `MIN(gameDate)` from a table with no scored games. The Task 7 tests cover a missing DB and an unscored DB.
