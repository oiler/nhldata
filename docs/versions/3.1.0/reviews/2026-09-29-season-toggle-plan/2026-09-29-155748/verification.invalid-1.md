---
lens: verification
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/plans/2026-09-29-season-toggle-plan.md
---

# verification review

## Verdict

not ready

## Findings

### F-1 [major] The "already shipped" early-season build fix is uncommitted, so a feature branch cut from HEAD won't have it

- Where: Global Constraints, last bullet ("already shipped on 2026-09-29. Don't redo it."); Task 6 Step 4 ("PASS (all, including the two early-season tests already there)")
- Evidence: `git status` shows ` M v2/browser/build_league_db.py` and ` M v2/browser/tests/test_player_metrics.py`. `git show HEAD:v2/browser/build_league_db.py | grep -c PLAYER_METRICS_COLUMNS` prints `0`, and `git show HEAD:v2/browser/tests/test_player_metrics.py | grep -c early_season` prints `0`. The fix exists only in the master working tree.
- Problem: A worktree or branch cut from HEAD has no `_write_empty_player_metrics`, no empty `constants` table, and neither early-season test. Task 6 Step 4's expected output then fails, the Task 10 and Task 13 em-dash behavior depends on tables that never get written, and Task 6 edits the same two files, so the later merge back onto the dirty master working tree will conflict.
- Fix: Add a Step 0 before Task 1: "oiler commits the early-season fix in `build_league_db.py` and `test_player_metrics.py` to master before the feature branch is cut. On the branch, run `grep -c PLAYER_METRICS_COLUMNS v2/browser/build_league_db.py` and `python -m pytest v2/browser/tests/test_player_metrics.py -k no_one_eligible -v`. Expected: a nonzero count and 2 passed. Stop if either fails."

### F-2 [major] The spec's full-build test is dropped, and the skaters page raises on an early-season 2026 database

- Where: Global Constraints ("Don't redo it"); Task 10; Task 13 Step 4 ("no page errors"). Spec lines 99-100 and Testing table row 1.
- Evidence: Spec line 99 says "Every other table builder must also complete on a season's first games. The test in the 'Testing' section runs the full build to prove it". Testing row 1 calls for a build in `main()` order. The only shipped tests run two builders (`test_player_metrics.py:82-97`). No test calls `main()` (`grep -rn 'main()' v2/browser/tests/` returns nothing). In the build, `recompute_pct_vs_elite_fwd` returns at `build_league_db.py:555` ("skipped (no elite forwards)") before the `ALTER TABLE competition ADD COLUMN pct_any_elite_fwd` at `:562`, and elite forwards need GP >= 10 (`:437`). The same holds for defense at `:749` and `:756`. `skaters.py:41` selects `c.pct_any_elite_fwd, c.pct_any_elite_def` without a guard, and `league_query` (`db.py:36-43`) doesn't catch errors. `build_points_5v5_table` returns at `:215-217` without creating `points_5v5`, which `skaters.py:56`, `team.py:72`, `teams.py:34` and `player.py:65` query. `build_competition_table` returns at `:56-58` without creating `competition`.
- Problem: With the plan as written, 2026-27 on /skaters raises `no such column: c.pct_any_elite_fwd` for about the first 10 games per skater, which is the launch window. In production, 2026 counts as ready once its files pass the checks, so the error reaches production too. Spec line 100 ("Pages ... don't raise") has no automated check. Task 13's manual check only covers it if someone happens to run it during the opening weeks.
- Fix: Add a task before Task 10 with two tests. (a) The spec's full-build test: synthetic competition CSVs, flatplays and flatboxscores where every skater has fewer than 5 games, with `SEASON_DIR`, `COMPETITION_DIR`, `FLATPLAYS_DIR`, `FLATBOXSCORES_CSV`, `PLAYERS_CSV` and `OUTPUT_DB` monkeypatched to `tmp_path`. Call `build_league_db.main()` and assert it completes, that `player_metrics` and `constants` exist with 0 rows, and that `competition` has `pct_any_elite_fwd` and `pct_any_elite_def` columns. (b) One callback-level test that runs `update_skaters`, `update_teams`, `update_team` and `update_player` for `"2026"` against that DB in local-dev mode and asserts each returns without raising. Both tests go red today. Then make the recompute functions add both columns (default 0.0) before their early return, and make `build_points_5v5_table` write an empty table with its schema.

### F-3 [major] No behavioral test covers the skaters rewiring; the only new test restates code

- Where: Task 10 Step 1 (`test_skaters_has_no_import_time_2025_bursts`)
- Evidence: The test asserts `not hasattr(skaters, "_BURSTS_DF")` and `not hasattr(skaters, "_AGE_CUTOFFS")`. Steps 3.3-3.6 change `_COMP_SQL` (`p.birthDate`), the groupby (`birthDate=("birthDate", "first")`), the burst join (`bursts_for(season)[["bursts_per_60", "speed_max_mph"]]`) and the Age computation. None of these changes is exercised by a test. The spec's success criteria at lines 31-32 ("Age displays ... with or without Edge data" and "never another season's values") have only the manual check in Task 13.
- Problem: An implementation that renames `_BURSTS_DF` but still joins 2025 bursts, or drops `p.birthDate` from the SQL, passes every test in the plan. Project CLAUDE.md says "Test computations, not callbacks", and user CLAUDE.md says "Don't write tests that restate code."
- Fix: Replace the `hasattr` test. Extract the burst join and Age step into a pure helper, for example `skaters.attach_bursts_and_age(grouped, season)` or a function in `burst_data`/`utils`. Test it with a synthetic `grouped` frame that has `birthDate` values (`"2000-09-16"`, `None`, `""`). Write a 2025 CSV only, monkeypatch `burst_data.player_bursts_csv`, and use the `clear_bursts_cache` fixture. Assert that season `"2026"` gives NaN `bursts_per_60` and `speed_max_mph` with Age 25/None/None, and that season `"2025"` gives the 2025 values. The callback-level early-season test in F-2 pins the SQL and groupby path.

### F-4 [minor] The team-absent goalie test (Review Focus 4) is never red

- Where: Task 9 Step 1 (`test_team_goalie_section_team_absent_is_omitted`); Review Focus 4
- Evidence: Current `team.py:80-83` returns `None` whenever `env` is empty, and returns a Div for a present row, so both assertions pass before the change and after it. The plan's own Global Constraints line 19 says "Every test goes red before the code that makes it pass."
- Problem: The test guards against an implementation that shows the message too broadly, but nothing ever shows that it can fail. User CLAUDE.md: "prove the test can fail by temporarily breaking the code".
- Fix: Add to Task 9 Step 4: "Mutation: in `_goalie_environment_section`, temporarily replace the `_ENV_SEASON_SQL` check so the empty branch always returns the message Div. Run `-k team_absent`. Expected: `test_team_goalie_section_team_absent_is_omitted` FAILS, and it's the only failure. Restore."

### F-5 [minor] The sync test's red step isn't hermetic, and test 4 passes on the old script

- Where: Task 12 Steps 1-2
- Evidence: I checked in a scratch fake repo holding the plan's test file and the current script, with no `data/`. pytest printed `3 failed, 1 passed`: `test_required_season_failure_is_fatal` passes on the old script because the old script exits 1 on the missing `data/`. The old script also created `v2/browser/runtime_data/2024` and `/2025` under the fake repo. In the real main checkout, the red run does a real sync into `runtime_data/`. The instruction "rerun `./tools/sync-runtime-data.sh` afterward to restore it" reproduces the same write, so it restores nothing. Separately, the plan's new script passed all 4 tests verbatim in the scratch repo.
- Problem: Test 4 never goes red, and the red step writes to real deploy inputs. The `SYNC_SRC`/`SYNC_DST` overrides exist only for tests.
- Fix: Make `_run` hermetic. Copy `tools/sync-runtime-data.sh` to `tmp_path/repo/tools/` and `v2/browser/verify_runtime_data.py` to `tmp_path/repo/v2/browser/`, build the fixture tree at `tmp_path/repo/data`, and run the copied script. `REPO_ROOT` then resolves to `tmp_path/repo` for both the old and new script, so drop `SYNC_SRC`/`SYNC_DST` and delete the "restore" sentence. For test 4, which already passes on the old script, add a mutation step: temporarily append `|| true` to the required `player_bursts.csv` `cp`. Expected: only test 4 goes red. Restore.

### F-6 [minor] Several spec sync cases and Review Focus 5 are only partly pinned

- Where: Task 12 Step 1; spec lines 176-181; Review Focus 5
- Evidence: Spec case 3 is "a 2026 burst CSV that has a header only, or covers under 80%". The plan tests only the under-80% case. Spec case 4 is "a 2025 file missing or failing a check". The plan tests only the missing file. No test covers a 2026 `league.db` that fails the new `birthDate` check. Review Focus 5 (remove a stale copy) is pinned only on the missing-file path: `test_optional_season_failing_coverage_is_removed_not_fatal` doesn't pre-create `runtime_data/2026/`. A refactor that moves `rm -rf "${DST:?}/$season"` into the cp-failure branch would pass every test.
- Fix: Pre-create a stale `dst/2026/league.db` in the coverage-failure test. Add three cases: a header-only 2026 CSV (WARNING, no `dst/2026`), a 2026 DB built with `birth=False` (WARNING plus `birthDate` in stderr, no `dst/2026`), and a 2025 CSV covering 2 of 10 skaters (nonzero exit).

### F-7 [minor] The WARNING line doesn't name the failed check, as the spec requires

- Where: Task 12 Step 3, `sync_optional_season`; spec line 143 ("prints a `WARNING` line naming the failed check")
- Evidence: The plan's line reads "failed the check named in the FAIL line above". The missing-file and empty-file lines say "league.db or player_bursts.csv". The test's `"burst coverage" in r.stderr` assertion passes on verify's `FAIL:` line, not on the WARNING line.
- Fix: Capture verify's stderr (`if ! out="$(python3 "$VERIFY" ... 2>&1 >/dev/null)"`) and print `WARNING: $season not synced — $out`. Name the missing file in the cp branch by checking each `cp` separately. Tighten the test to assert that the line containing `WARNING: 2026 not synced` also contains `burst coverage`. If the current wording is intended, amend spec line 143 instead.

### F-8 [minor] "all pass" checkpoints aren't plausible in a checkout without `data/`

- Where: Step 5 of Tasks 1-12 (`python -m pytest v2/ -q`, "Expected: all pass")
- Evidence: `requires_data` tests read `data/` directly: `test_smoke.py:39-52`, `test_build_goalies_db.py:120-135`, `v2/competition/tests/test_compute_competition.py:168,360` and `v2/goalies/tests/test_toi_5v5.py:63`. `pyproject.toml` defines the marker, and it says CI deselects these with `-m 'not requires_data'`. Task 13 says "a worktree has none" and implies that Tasks 1-12 run in one.
- Fix: State where Tasks 1-12 run. If they run in a worktree, change each checkpoint to `python -m pytest v2/ -q -m "not requires_data"`, and keep the unfiltered run for Task 13 Step 5.

### F-9 [minor] Every check on the built result runs only after merge, and the stated reason doesn't hold

- Where: Task 13 intro ("runs from the main checkout after oiler merges ... a worktree has none")
- Evidence: `data/` is gitignored (`.gitignore:3`), so it stays in place when the feature branch is checked out in the main checkout. `git worktree list` shows only master today, and nothing in the plan requires a worktree.
- Problem: The rebuild, the real sync and the manual app checks first run on master, after the merge. A failure there, for example F-2's skaters error, lands on the branch the daily orchestrator uses.
- Fix: Run Task 13 Steps 1-4 with the feature branch checked out in the main checkout before merge. After merge, repeat only Step 1, which the spec's "Rollout order" requires. If a pre-merge run truly can't happen, state the reason.

### F-10 [minor] Task 13 Step 1's expected output depends on 2026 game data that doesn't exist yet

- Where: Task 13 Step 1 ("both end with `Done.`")
- Evidence: `ls data/2026/generated` shows only `players`. With no competition CSVs, `build_competition_table` returns without creating `competition` (`build_league_db.py:56-58`). `_recover_missing_players` then runs `... FROM competition c` (`:81-86`) and raises. With no flatboxscores, the `games` table is skipped (`:120-122`). The plan's alternate message, "(no eligible players)", only appears once competition rows exist. The zero-row variant prints "(no competition data)".
- Fix: Add the precondition "`data/2026/generated/competition/` holds at least one CSV and `data/2026/generated/flatboxscores/boxscores.csv` exists (the orchestrator has processed at least one 2026 game)". Or have F-2's builder fixes create empty `competition` and `games` tables, and extend the full-build test to the zero-games case.

### F-11 [minor] Nothing checks 2026 birthDate coverage or the production preload

- Where: Task 13 Step 2; Task 10 Step 3.2 (runtime-mode preload)
- Evidence: Step 2 runs the verifier on 2025 only. The sync checks 2026 `birthDate` coverage only once a 2026 Edge CSV exists, which Step 3 says won't be true yet. Spec line 109 names the JSON recovery path as the risk, and 2026 adds new players through it. Separately, spec line 118 says the preload makes a present-but-empty CSV fail boot in production. No test imports skaters in runtime mode.
- Fix: In Task 13 Step 2, add `cd v2/browser && python -c "from verify_runtime_data import verify_birthdates; print(verify_birthdates('../../data/2026/generated/browser/league.db'))"`, with expected `(True, 'birthDate coverage ...')`. Move the preload loop into a Dash-free function such as `burst_data.preload_ready(seasons)`, called from `skaters.py`. Test it with `DATA_DIR` set: a ready season with a header-only CSV raises `RuntimeError`, and a not-ready season is skipped.

### F-12 [minor] No check covers the player page's use of `player_meta` for a 2026-only player

- Where: Task 4 (db-level test only); Task 13 Step 4
- Evidence: `test_player_meta.py` tests `db.player_meta`. Nothing calls `player.layout(player_id=...)`, and no manual item checks a player who appears only in 2026-27, although spec line 14 motivates the change with that case.
- Fix: Add a manual item to Task 13 Step 4: "Open `/player/<id>` for a skater whose first NHL game is in 2026-27. The heading shows his name, not `Player <id>`." Or add a test that calls `player.layout(player_id="2")` with the Task 4 fixtures and asserts on the `H2` text.

### F-13 [nit] "FAIL with ImportError" should read as a collection error

- Where: Step 2 of Tasks 2, 3, 4, 5, 7 and 8
- Evidence: Each step adds the new name to a module-level `from X import ...`, so pytest reports `ERROR collecting ... ImportError`, and none of the file's existing tests run.
- Fix: Write "Expected: collection ERROR, `ImportError: cannot import name '<name>'`".

### F-14 [nit] Task 11's test doesn't assert that the filter opens on 2025-26

- Where: Task 11 Step 1, `test_filter_labels_and_persistence`; spec line 25 ("opens on 2025-26")
- Fix: Add `assert r.value == "2025"`.

### F-15 [nit] Task 8 Step 4 hedges against a test that doesn't exist

- Where: Task 8 Step 4 ("If an existing `main` test now fails ...")
- Evidence: `test_verify_runtime_data.py` has no test that calls `main`. It tests only `burst_coverage` and `verify_burst_csv`.
- Fix: Delete the sentence.

### F-16 [nit] The tech stack says Python 3.11, but the deployed image runs 3.12

- Where: Header, "Tech Stack"
- Evidence: `Dockerfile:3` is `FROM python:3.12-slim`. The local interpreter is 3.11.6.
- Fix: "Python 3.11 locally, 3.12 in the image".

## Checked and sound

- In Dash 4.0.0, `@callback` returns the original function (`dash/_callback.py`, `register_callback.wrap_func` ends `return func`), so the plan's direct calls to callbacks in Tasks 9-11 work.
- Every callback call in Tasks 9 and 10 matches the current signatures: `update_games` (`games.py:36`), `update_teams` (`teams.py:64`), `update_team` (`team.py:180`), `update_player` (`player.py:137`), `update_goalies` (`goalies.py:41`), `update_skaters` (`skaters.py:80`) and `elites.layout(season=None)` (`elites.py:122`).
- I ran the current code in a scratch copy with `DATA_DIR` set to an empty dir. `update_games` returned `P('No games found in this range.')`, and `update_team` returned a Div without the not-ready text, so the Task 9 tests go red for the stated reason. The Task 11 layout walker finds exactly one `filter-season` with labels `['2025']`, so that test goes red today.
- `Format().nully("—")` is valid in Dash 4 (it serializes `{'nully': '—'}`). `str(html.Div([...]))` contains the goalie message text verbatim, so the `in str(section)` assertion works.
- Joining an empty `bursts_for` frame (object index) onto an int64 `playerId` index gives NaN burst columns, not an error.
- `season_date_range` with a scored-games-free table: `MIN(gameDate)` comes back as `None`. The old `is None` check and the new `pd.isna` check both take the fallback, so the Task 7 test goes red only on the dates, as the spec's Testing table says.
- The plan's Task 12 script, run verbatim with the Task 8 verifier edits applied, passes all four Task 12 tests (scratch run: `4 passed`).
- The Task 8 tests are consistent: 18 of 20 gives `90.0%`, the `""` birth date counts as missing, and `main` returns 1 when only the `birthDate` check fails.
- The Task 6 tests go red for the stated reasons: `usecols=keep` drops `birthDate` (`build_league_db.py:69-74`), and the recovered dict lacks it (`:102-111`). Adding `birthDate` to `_setup_recovery_db` doesn't break the two existing recovery tests.
- `players.csv` has a `birthDate` column (column 10) for 2024, 2025 and 2026.
- Tasks 1, 2 and 3 have correct test arithmetic: `season_label("2099") == "2099-00"`, the Sept 15 boundary ages come out 25 and 26, `normalize_season(2026)` returns the default, and monkeypatching `runtime_paths.data_root` redirects `league_db` in local-dev mode.
- The Task 5 monkeypatch target works: `burst_data` imports `player_bursts_csv` into its own namespace (`burst_data.py:17`), and `_VALID_ROW` has `speed_max_mph` 24.6 for id 8478402.
- The Task 9 and 10 grep expectations match what's in the repo today: every `"2025"` literal sits in the lines the plan rewrites (`games.py:37`, `teams.py:65`, `team.py:181`, `player.py:105,138`, `goalies.py:42`, `elites.py:123`, `skaters.py:22,35,81`, `filters.py:9,97`, `db.py:31,46`, `burst_data.py:24`). `home.py`'s `"/game/2025020871"` doesn't match the pattern.
- `git check-ignore -v v2/browser/runtime_data/2026/league.db` is a meaningful check: today no `.gitignore` rule covers that path (`.gitignore:10-13` lists only 2024 and 2025).
- The Task 11 CSS matches DESIGN.md: `--text`, `--text-3` and `--navy` exist in `style.css:7-14`. DESIGN.md:108 says "Radio/checkbox accent: navy", DESIGN.md:175-180 give the `< 640px` breakpoint and the 40px rows, and `.filter-bar` already sets `display: flex` (`style.css:86-92`), so `toggle_season_bar` returning `{}` shows the bar correctly.
- The player page has no Age column (`grep -n 'birth_date\|age' pages/player.py` finds only `_load_bursts`), so the spec's Age criterion applies only to skaters, and the plan's "no change" to `player._load_bursts` is right.
- Review Focus 1 (`sync_season("2019")`), 2 (the `/elites` junk values) and 3 (`""`/`None`/NaN birth dates in `age_in_season`) are each pinned by a test that goes red before the change.
