---
lens: verification
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/plans/2026-09-29-season-toggle-plan.md
---

# verification review

## Verdict

not ready

## Findings

### F-1 [blocker] The early-season build fix the plan calls "already shipped" exists only as uncommitted working-tree changes

- Where: Global Constraints ("The early-season `build_league_db.py` fix ... already shipped on 2026-09-29. Don't redo it."); Task 6 Step 4 ("PASS (all, including the two early-season tests already there)"); Task 13 Step 1.
- Evidence: `git status` shows `M v2/browser/build_league_db.py` and `M v2/browser/tests/test_player_metrics.py`. `git diff v2/browser/build_league_db.py` shows `_write_empty_player_metrics` and `PLAYER_METRICS_COLUMNS` as additions. `git show HEAD:v2/browser/tests/test_player_metrics.py | grep -c no_one_eligible` printed `0`. The plan's header recommends subagent-driven execution, and its Git constraint describes a feature branch, so the work starts from HEAD.
- Problem: On any branch or worktree cut from HEAD, the fix and its two tests aren't there. Task 6 Step 4's expected output is false, and a build on the branch still fails with `no such table: player_metrics` early in the season. Task 6 edits the same two files, so merging back to master collides with oiler's uncommitted edits, and Task 13 runs in that main checkout after the merge.
- Fix: Add a Step 0 before Task 1: "Precondition: the early-season fix is committed on master. Run `git show HEAD:v2/browser/tests/test_player_metrics.py | grep -c no_one_eligible`. Expected: `2`. If it prints `0`, stop and ask oiler to commit `build_league_db.py` and `test_player_metrics.py` first." Reword the Global Constraint from "already shipped" to "committed on master before this plan starts (checked in Step 0)".

### F-2 [major] The 2026-27 skaters page will raise on an early-season database, and no check catches it before merge

- Where: Task 10 (skaters page); the plan has no task for spec "Early-season database" bullet 3 ("Every other table builder must also complete on a season's first games. The test in the 'Testing' section runs the full build to prove it") or for spec Testing row 1 (full build in `main()` order).
- Evidence: In a scratch copy I built synthetic early-season rows (2 skaters, 2 games, competition columns copied from `data/2025/generated/competition/2025020001.csv`) and ran the builders in `main()` order. Output: `elite_forwards: 0 rows (no qualifying forwards)`, `pct_vs_elite_fwd: skipped (no elite forwards)`, `pct_vs_elite_def: skipped (no elite defensemen)`, then `competition cols tail: ['weighted_team_heaviness', 'line_number', 'deployment_score']` and `SELECT c.pct_any_elite_fwd, c.pct_any_elite_def FROM competition c` → `OperationalError no such column: c.pct_any_elite_fwd`. The competition CSVs don't carry `pct_any_elite_*`. Only `recompute_pct_vs_elite_fwd`/`_def` add them (`build_league_db.py:559-563`, `:753-757`), after an early `return` when no elites exist. `skaters.py:41` selects both columns. Elite D need GP ≥ 20, so the column stays missing for weeks. A second run with no `points_5v5` table (no 5v5 goals yet) showed `build_elite_forwards_table` raising `no such table: points_5v5`. `main()` has no try/except, so the build aborts. The only skaters test in the plan (`test_skaters_not_ready`) returns at the not-ready guard before any query. `test_skaters_has_no_import_time_2025_bursts` checks that attributes are absent, so it restates the code: an implementation that renames `_BURSTS_DF` and still joins 2025 bursts passes it.
- Problem: Spec success criteria "every season-aware page shows the selected season's data", "`build_league_db.py` completes for a season where no skater has 5 games", "Age displays for every skater with a `birthDate`", and "A season without Edge bursts shows an em dash ... never another season's values" have no automated check. The first signal is Task 13 Step 4's manual "no page errors", after the merge, with no task to fix what it finds. The `_COMP_SQL` `p.birthDate` edit, the groupby `birthDate=` line, the `bursts_for(season)` join, and the `age_in_season` apply all run untested: a missing groupby line raises `KeyError` only in the running app.
- Fix: Add a task before Task 10: (a) a test that builds a synthetic early-season tree (competition CSVs with < 5 GP per skater, `players.csv`, `boxscores.csv`, empty flatplays and timelines dirs), monkeypatches `SEASON_DIR`/`COMPETITION_DIR`/`PLAYERS_CSV`/`FLATBOXSCORES_CSV`/`FLATPLAYS_DIR`, and runs the builders in `main()` order. It asserts that `points_5v5`, `player_metrics`, and `constants` exist and that `competition` has `pct_any_elite_fwd` and `pct_any_elite_def`. (b) The build change that makes it pass: move each "ensure column exists" block above `if not elite_rows: return`, and have `build_points_5v5_table` write an empty table when it finds no 5v5 goals. (c) In Task 10, replace `test_skaters_has_no_import_time_2025_bursts` with a behavior test: local dev, synthetic 2025 and 2026 `league.db` files (built by the fixture from (a), plus a `birthDate` on one player), a 2025 burst CSV only. Call `update_skaters(..., "2026")` and assert the rendered rows have `bursts_per_60` and `speed_max_mph` null and `age` computed from `birthDate` with the 2026 cutoff.

### F-3 [major] `player_meta`'s fallback to an older season is unpinned

- Where: Task 4 Step 1 (`test_player_meta_prefers_newest_season`, `test_player_meta_unknown_player`).
- Evidence: Player 1 and player 2 both appear in 2026, and the unknown-player test has no 2026 DB, so `league_query` returns an empty frame for 2026. An implementation that queries only `seasons[-1]` returns VAN, CGY, and `None`, and passes all three assertions.
- Problem: The behavior the spec needs is "looks up `_META_SQL` in each season, newest first, and returns the first match". Its most common case isn't tested: a 2025 player with no 2026 row while the 2026 DB exists. A regression shows `Player {id}` for most of the league.
- Fix: In `test_player_meta_prefers_newest_season`, add `_row(3, "EDM")` to the 2025 DB only, then assert `player_meta(3)["currentTeamAbbrev"] == "EDM"`.

### F-4 [minor] Two tests pass before their change, and Step 2 says every test fails

- Where: Task 9 Step 2 (`test_team_goalie_section_team_absent_is_omitted`); Task 12 Step 2 (`test_required_season_failure_is_fatal`).
- Evidence: I ran the plan's Task 9 test file against current code in a scratch copy: `4 failed, 1 passed`, and the pass was `test_team_goalie_section_team_absent_is_omitted`. I ran the plan's Task 12 test file against the current `tools/sync-runtime-data.sh` in a scratch checkout with no `data/` (what a worktree has): `3 failed, 1 passed`. `test_required_season_failure_is_fatal` passes because the old script exits 1 on its first `cp` (`data/2024/generated/browser/league.db: No such file or directory`). In the main checkout, the old script ignores `SYNC_SRC`/`SYNC_DST` and copies real `data/` into the real `v2/browser/runtime_data/`. Step 2's advice to "rerun `./tools/sync-runtime-data.sh` afterward to restore it" restores nothing: the directory is gitignored, and no earlier copy exists to put back.
- Problem: Both tests are regression guards, and their red state is never observed. Step 2's expected outputs are wrong for them. CLAUDE.md: "Testing existing code with no test ... prove the test can fail by temporarily breaking the code it covers." Task 12 Step 2 also risks overwriting the real runtime data with the old script.
- Fix: Task 9 Step 2: state that `test_team_goalie_section_team_absent_is_omitted` passes at this step, and after Step 3 prove it with a mutation: return the message whenever `env.empty`, run it, see it go red, then restore. Task 12 Step 2: run the red step only from a scratch copy of the repo (or a worktree without `data/`), never the main checkout. State that `test_required_season_failure_is_fatal` passes there, and prove it after Step 3 by temporarily adding `|| true` to the required-season burst-CSV `cp` and to the `-s` guard loop. Delete the "rerun to restore" sentence.

### F-5 [minor] Sync-script tests leave spec cases and a Review Focus path unexercised

- Where: Task 12 Step 1; spec "Testing" sync cases 3 and 4; plan Review Focus 5.
- Evidence: `_league_db(..., birth=True)` has a `birth` parameter that no test passes as `False`. No test uses a header-only 2026 CSV (spec case 3 names it). `test_optional_season_failing_coverage_is_removed_not_fatal` doesn't pre-create `dst/2026`, so "a previously synced copy is removed on failure" is pinned only on the missing-file branch. A mutation that moves `rm -rf "${DST:?}/$season"` into that branch survives. Spec case 4 says "a 2025 file missing or failing a check", and only "missing" is tested. I ran three extra probes against the plan's script and Task 8 verifier in scratch: 2026 without `birthDate` → exit 0 with `WARNING: 2026 not synced` and `birthDate` in stderr; header-only 2026 CSV → `empty burst CSV` and the WARNING; 2025 without `birthDate` → non-zero. All 3 passed, so the script is right and only the tests are missing.
- Fix: Add three tests: an optional season with `birth=False` (WARNING, `"birthDate"` in stderr, no `dst/2026`); an optional season with a header-only CSV (`"empty burst CSV"` in stderr); and a required season with `birth=False` (`returncode != 0`). In the coverage-failure test, pre-create `dst/2026/league.db` the way case 2 does.

### F-6 [minor] `season_ready`'s production test doesn't pin that both files are required

- Where: Task 3 Step 1 (`test_season_ready_production_needs_both_files`).
- Evidence: The test covers three states: neither file, `league.db` only, and both. An implementation that returns `player_bursts_csv(season).exists()` alone gives False, False, True and passes.
- Problem: The spec's production rule "both `league_db(season)` and `player_bursts_csv(season)` exist" is only half pinned.
- Fix: Add a case with the CSV present and `league.db` missing, asserting False. For example, write the CSV first, assert False, then add `league.db` and assert True.

### F-7 [minor] The runtime-mode burst preload in `skaters.py` has no check

- Where: Task 10 Step 3 item 2 (the `if is_runtime_mode(): for _s in SEASONS: if season_ready(_s): bursts_for(_s)` block); spec "Edge bursts per season" bullet 3.
- Evidence: None of the Task 10 tests import `pages.skaters` with `DATA_DIR` set. Deleting the block leaves every test in the plan passing. The spec says this preload is what keeps "a present-but-empty CSV in production still fails boot", and the rewritten `burst_data.py` docstring and Dockerfile comment (Tasks 5 and 12) state it as fact.
- Problem: The deploy-safety fact the spec relies on has no verification step.
- Fix: Move the loop into `burst_data.preload_ready_seasons(seasons)` (no Dash import), call it from `skaters.py`, and test it: with `DATA_DIR` set, a ready 2026 with a header-only CSV raises `RuntimeError`, and a season missing `league.db` is skipped without raising.

### F-8 [minor] Task 13's preconditions and manual checklist don't match the spec

- Where: Task 13 Steps 1 and 4.
- Evidence: `ls data/2026/generated` shows only `players`, with no `competition/` or `flatboxscores/`. With no competition CSVs, `build_competition_table` prints `competition: 0 rows (no CSVs found)` and creates no table. Then `_recover_missing_players` runs `SELECT ... FROM competition c` and raises, so "both end with `Done.`" fails. The spec's manual list says the filter "matches DESIGN.md at desktop and phone widths". Task 13 Step 4 checks only under `640px`. Nothing checks that the "Season" and "Situations" group labels keep the eyebrow style after `.filter-bar label` becomes `.filter-bar .filter-bar-label`.
- Fix: Step 1: add "Precondition: `ls data/2026/generated/competition/*.csv` lists at least one game (the daily run has processed a 2026 game)". Step 4: add "At desktop width, the Season and Situations labels are 0.75rem uppercase tertiary eyebrows, and the options are sentence case in `--text` with navy radios."

### F-9 [nit] Several expected outputs say FAIL where pytest reports a collection ERROR

- Where: Step 2 in Tasks 2, 3, 4, 5, 7, 8.
- Evidence: Each of these steps adds an import of a name that doesn't exist yet to the test module's top-level import line (or appends one at module level). pytest reports `ERROR collecting ... ImportError`, and the file's existing tests error too.
- Problem: An implementer comparing output to "FAIL with ImportError" sees ERROR and a larger failing count.
- Fix: Reword to "ERROR at collection: `ImportError: cannot import name '<x>'` (the file's existing tests also error until Step 3)".

### F-10 [nit] `test_season_aware_pages_say_not_ready` bundles four behaviors in one test

- Where: Task 9 Step 1.
- Evidence: In my scratch red run, only the games assertion (line 24, `'No games fou...n this range.' == '2026-27 data...vailable yet.'`) was reported. The teams, team, and player assertions never ran.
- Problem: The red state for three pages isn't observed. Neighbor tests use one test per behavior (for example `test_burst_data.py`).
- Fix: Split it into four tests, or `pytest.mark.parametrize` over the four callables.

## Checked and sound

- Dash 4.0.0 `@callback`-decorated functions are directly callable and return the component (scratch: `f("1").children == "x1"`), so the Global Constraint "Dash callbacks are directly callable in tests" holds.
- `Format(precision=2, scheme=Scheme.fixed).nully("—")` serializes to `{'nully': '—', 'specifier': '.2f'}`, and `Format().nully("—")` to `specifier: ''`. The em-dash approach keeps the columns numeric.
- Task 9's red claims hold: in a scratch run, games returns "No games found in this range.", goalies returns "No goalie data for this season.", the season-absent team section is `None`, and elites queries `{'../x', '2024', '2025'}`.
- The plan's new `tools/sync-runtime-data.sh` plus the Task 8 `verify_runtime_data.py` changes pass all 4 of the plan's sync tests in a scratch checkout (`4 passed`). `REPO = parents[3]` resolves to the repo root.
- The Task 11 layout walker finds exactly one `filter-season` in the current `app.app.layout`, with labels `['2025']` and `persistence` `None`, so the test goes red for the stated reason and turns green once labels and persistence change.
- `birthDate` exists as ISO text in `data/2025/generated/players/csv/players.csv`, in `data/2026/generated/players/csv/players.csv` (778 rows, 0 null), and in player JSON (`data/2025/players/8470613.json` → `1985-03-09`). The spec facts behind Task 6 and the 95% gate hold.
- Task 6's red states are right: without `birthDate` in `keep`, `SELECT birthDate` raises `no such column`, and the recovered row appends with a NULL `birthDate` once the fixture has the column.
- Task 2's boundary values give 25 and 26 at the Sept 15 cutoff, and `""`, `None`, and NaN return `None` (Review Focus 3 pinned).
- Task 7's no-scored-games fixture yields `MIN(gameDate)` of `None`. The old code returns `("2025-10-01", "2026-06-30")`, so both fallback tests go red for the stated reason.
- Task 8's low-coverage fixture gives 18/20 = `90.0%`, which matches the asserted message. No existing `main()` test needs the fixture change mentioned in Step 4, because the file has none today.
- The Task 9 and 10 grep expectations match the current `"2025"` occurrences. `home.py`'s `"/game/2025020871"` doesn't match the quoted pattern.
- `git check-ignore` on `runtime_data/2026/league.db` matches nothing today (`data/` matches only directories named `data`), so the Task 12 Step 5 check turns green only after the `.gitignore` change.
- CSS tokens `--text`, `--text-3`, and `--navy` exist in `assets/style.css:7-15`, and `max-width: 639px` matches DESIGN.md's `< 640px` breakpoint.
- Review Focus 1 (`sync_season("2019")`), 2 (elites `"../x"`, `"2024"`, `None`), and 5 (case 2 with a pre-existing `runtime_data/2026/`) are pinned by the tests the plan names.
- Test counts in the expected outputs are right: Task 1 "PASS (5 tests)" and Task 12 "PASS (4 tests)".
- Task 13 Step 1's expected line `player_metrics: 0 rows (no eligible players)` matches `_write_empty_player_metrics`'s print format, once F-1's precondition holds.
