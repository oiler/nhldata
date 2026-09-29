---
lens: operations
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/plans/2026-09-29-season-toggle-plan.md
---

# operations review

## Verdict

not ready

## Findings

### F-1 [blocker] The early-season build fix is uncommitted on master, so a feature branch won't have it and the merge back will abort

- Where: Global Constraints ("The early-season `build_league_db.py` fix ... already shipped on 2026-09-29. Don't redo it."); Task 6 Step 4 ("PASS (all, including the two early-season tests already there)"); Task 13 intro ("runs from the main checkout after oiler merges").
- Evidence: `git status --short` on master at `78ce20f` shows `M v2/browser/build_league_db.py`, `M v2/browser/tests/test_player_metrics.py`, `M v2/orchestrator/config.py`, and `M v2/orchestrator/com.nhl.orchestrator.plist`. `git diff v2/browser/build_league_db.py` shows `_write_empty_player_metrics` and the empty `constants` table exist only in the working tree. `git diff v2/browser/tests/test_player_metrics.py` shows `test_player_metrics_empty_table_when_no_one_eligible` and `test_constants_empty_table_when_no_one_eligible` exist only in the working tree. `git diff v2/orchestrator/config.py` shows `NHL_SEASON` default `"2025"` changed to `"2026"`, also uncommitted.
- Problem: The plan runs under subagent-driven development on a feature branch, and Task 13 assumes a worktree ("a worktree has none"). A branch cut from `78ce20f` doesn't contain the fix or its two tests, so Task 6 Step 4's expected output can't happen, and an implementer told "don't redo it" either hits failures it can't explain or re-implements it. Task 6 edits the same two files, so `git merge` into master aborts with "Your local changes to the following files would be overwritten by merge". Stashing to get past that also reverts the orchestrator's `NHL_SEASON=2026` default in `config.py` for the 08:00 run.
- Fix: Add a "Task 0 — before branching (oiler)" step: commit the early-season fix (`v2/browser/build_league_db.py`, `v2/browser/tests/test_player_metrics.py`) and the orchestrator season switch (`v2/orchestrator/config.py`, `v2/orchestrator/com.nhl.orchestrator.plist`) to master, then cut the feature branch from that commit. Reword the Global Constraint to "committed to master in Task 0; don't redo it." Add "Don't `git stash` to merge; the orchestrator runs from this working tree" to Task 13.

### F-2 [major] Every checkpoint expects "all pass" from the full suite, but `requires_data` tests fail in a worktree

- Where: Step 5 "Checkpoint" of Tasks 1–12 (`python -m pytest v2/ -q` → "Expected: all pass").
- Evidence: `v2/browser/tests/test_smoke.py:39-44` is `@pytest.mark.requires_data` and asserts `data/2025/generated/browser/league.db` exists. `grep -rln requires_data v2/` also lists `test_build_goalies_db.py`, `v2/competition/tests/test_compute_competition.py`, and `v2/goalies/tests/test_toi_5v5.py`. `.github/workflows/tests.yml:39` runs `python -m pytest v2/ -q -m "not requires_data"`. The runbook (`docs/fly-deploy-runbook.md:21`) says 3 of the 298 tests need `data/`. `data/` is gitignored (`.gitignore:3`), so a worktree has none. Task 13 says so itself.
- Problem: In the worktree, every checkpoint shows failures that the plan says won't happen. A subagent then either stops or tries to "fix" tests that are correct.
- Fix: In Tasks 1–12, change the checkpoint to `python -m pytest v2/ -q -m "not requires_data"` (the CI command) with "Expected: all pass (data-dependent tests deselected; Task 13 runs them)." Keep the unfiltered `python -m pytest v2/ -v` only in Task 13 Step 5, from the main checkout.

### F-3 [major] Nothing at image build or boot enforces the new `players.birthDate` column, so a deploy without a fresh sync breaks the skaters page in production

- Where: Task 10 Step 3 item 3 (`_COMP_SQL` selects `p.birthDate`); Task 12 Dockerfile ("The file list in the guard doesn't change"); spec line 112 ("The deploy guard catches a stale database in production").
- Evidence: `Dockerfile:42-57` checks only that each file exists and is non-empty (`[ ! -s ... ]`). `.dockerignore:37` excludes `verify_runtime_data.py` from the image. `shasum` shows `v2/browser/runtime_data/2025/league.db` == `data/2025/generated/browser/league.db` (`cf72ac9d…`), and `build_players_table`'s `keep` list at `build_league_db.py:69-72` has no `birthDate`. The runtime copy that exists today therefore has no `birthDate` column. The runbook's Deploy section (`docs/fly-deploy-runbook.md:26`) lists a bare `fly deploy --remote-only` as its own step, and its line 19 says "`fly deploy` ships the working tree". The current sync also copies into `runtime_data/` before verifying (`tools/sync-runtime-data.sh:19-23` then `:48`), and the plan's rewrite keeps that order for the required tier (plan lines 1334-1338 before 1363).
- Problem: After merge, `runtime_data/2025/league.db` still has the old schema. Any of three paths reaches production with that schema, and each makes the skaters callback raise `no such column: p.birthDate`: deploying without re-syncing, deploying after a sync that failed the new birthDate check (the failed sync has already overwritten `runtime_data/2025/league.db`), or rolling forward from an old local `runtime_data/`. The spec relies on "the deploy guard" to catch this, but the only guard that checks the schema is the sync script, and it is optional in the runbook's flow.
- Fix: (a) In Task 12, extend the Dockerfile `RUN` guard with an inline check that each shipped `league.db` has the column, for example `python -c "import sqlite3,sys; c={r[1] for r in sqlite3.connect(sys.argv[1]).execute('PRAGMA table_info(players)')}; sys.exit('ERROR: players.birthDate missing in '+sys.argv[1] if 'birthDate' not in c else 0)" /app/runtime_data/2025/league.db`, and repeat it for `runtime_data/2026/league.db` when that file exists. (b) Change the required tier to stage into a temp directory and move files into `runtime_data/` only after every check passes, as the optional tier already does, so a failed sync never overwrites the last good copy. (c) State in Task 13 that after merge, every deploy is refused until Step 1's `build_league_db.py 2025` has run.

### F-4 [major] The optional-tier checks pass a partially built 2026 `league.db`, which then ships and breaks every 2026-27 page

- Where: Task 8 (`verify_birthdates`), Task 12 (`sync_optional_season`), and Task 3 (`season_ready` = files exist).
- Evidence: `build_league_db.py:1013-1016` deletes `league.db` and then builds it in place, with `build_competition_table` and `build_players_table` running first (`:1019-1021`). `v2/orchestrator/tools/build.py:13` runs the build with `timeout=300`, so a slow build is killed mid-write. `verify_burst_csv` reads only `competition` (`verify_runtime_data.py:47-49`), and the plan's `verify_birthdates` reads only `competition` and `players`. The pages read `games`, `player_metrics`, `constants`, `points_5v5`, `events_5v5`, `onice_5v5`, `elite_forwards`, and `elite_defensemen` (grep of `FROM|JOIN` across `v2/browser/pages` and `filters.py`). The spec itself says a failed build leaves "a partial `league.db`" (spec line 16).
- Problem: If a 2026 build dies after the first two builders (from the timeout, an exception, or a sync that runs during the 08:00 rebuild), it leaves a file that passes non-empty, burst coverage, and birthDate coverage. The sync ships it, `season_ready("2026")` returns true, and 2026-27 pages raise `no such table` in production. In local dev the same partial file makes `season_ready` true during every daily rebuild. That breaks the spec's promise that an optional season "ships only when its files pass the same checks".
- Fix: Add `verify_tables(db_path)` to `verify_runtime_data.py` and run it from `main()`. It fails when any of `competition, players, games, player_metrics, constants, points_5v5, events_5v5, onice_5v5, elite_forwards, elite_defensemen` is missing from `sqlite_master`. Pin it with a red test that drops one table. Better still, also have `build_league_db.main()` write to `league.db.tmp` and `os.replace` it onto `league.db` only on success. That closes the local-dev window and the race with the sync too. If that goes out of scope, name it in the plan as a known gap.

### F-5 [major] The plan drops the spec's full-build test, and `points_5v5` still isn't created when a season has no 5v5 goals

- Where: The plan as a whole; no task implements the spec's Testing row "A full build on synthetic competition rows ... run in `main()` order" (spec line 163) or the rule "Every other table builder must also complete on a season's first games" (spec line 99).
- Evidence: `grep -n "full build\|main()"` on the plan finds no such test. The uncommitted early-season tests cover only `player_metrics` and `constants` (`git diff v2/browser/tests/test_player_metrics.py`: `test_player_metrics_empty_table_when_no_one_eligible`, `test_constants_empty_table_when_no_one_eligible`). `build_league_db.py:214-216` returns early (`print("  points_5v5: 0 rows (no 5v5 goals found)"); return`) without creating the table. `events_5v5` and `onice_5v5` (`:268-273`, `:355-360`) write empty tables in the same situation. `points_5v5` is read by `skaters.py:128`, `teams.py:34`, `team.py:72`, and `player.py:65`.
- Problem: For the first build of a season with no 5v5 goal yet (or any build that finds no flatplays), the daily run "completes" but leaves no `points_5v5` table. Four season-aware pages then raise for 2026-27, locally and, with F-4, in production. The spec asked for a full-build test to catch exactly this, and the plan silently omits it.
- Fix: Add a task: a synthetic full build that calls every builder in `main()` order with competition rows but no 5v5 goals, then asserts that each page-read table exists. It should go red on `points_5v5`. Then write an empty `points_5v5` (`gameId, playerId, goals, assists, points`) in that branch, matching `events_5v5`.

### F-6 [minor] New docstring and comment text claim Fly's health check stops a bad image before it takes traffic, but the project's own incident shows otherwise

- Where: Task 5 Step 3 module docstring ("so a bad file fails boot, and Fly's deploy health check catches it before the image takes traffic"); Task 10 Step 3 item 2 comment ("fails boot (Fly's health check catches it) instead of 500ing on a request").
- Evidence: `docs/fly-deploy-runbook.md:50`: "`pages/skaters.py:35` raised `RuntimeError` ... at import, gunicorn workers failed to boot, and the machine crash-looped to its 10-restart cap; the Fly proxy had no healthy instance and served 502/503. Releases v22 and v23 both failed." `fly.toml` has one machine, `min_machines_running = 0`, and no bluegreen or canary strategy. `healthz.py:12-14` always returns 200.
- Problem: The plan writes an unsafe assumption into code comments, and the import-time preload now covers every ready season. Anyone reading the comments will think a bad CSV can't take production down, but on this app it does.
- Fix: Replace both sentences with "a bad file fails boot, so the deploy fails loudly. On this single-machine app production is down until you roll back with `fly deploy --image registry.fly.io/nhl-browser:deployment-<id>`." Optionally, make the Dockerfile guard (F-3) also check that a present `runtime_data/2026/player_bursts.csv` has more than a header, so the failure moves to build time.

### F-7 [minor] No deploy, production-mode smoke test, or rollback step, and Task 13 only exercises local-dev mode

- Where: Task 13.
- Evidence: Task 13 Step 4 runs `cd v2/browser && python app.py` with `DATA_DIR` unset, so `season_ready` takes the local-dev branch (`league.db` only), and the Task 10 preload (`if is_runtime_mode()`) never runs. The runbook documents a production-mode run: `DATA_DIR=$PWD/v2/browser/runtime_data DASH_ENABLE_SECURITY_HEADERS=1 python v2/browser/app.py` (`docs/fly-deploy-runbook.md:13`). Its Verify section (`:32-35`) and Rollback section (`:45-46`) aren't referenced. `build_league_db.main()` calls `os.remove(OUTPUT_DB)` (`:1013-1015`) and `_log_elite_changes` appends to the season's elite changelog (`:1000-1004`).
- Problem: The production paths this plan adds are never run before a deploy: `season_ready` requiring both files, the boot preload for ready seasons, and the not-available message for a season left out of the image. The plan also doesn't say whether this change is meant to be deployed. Task 13 Step 1 destroys the current 2025 `league.db` without a backup. If the rebuild fails, local dev has no 2025 database and every deploy is refused until it's fixed. The changelog append can't be undone.
- Fix: Add to Task 13, after Step 3: "Step 3b: `DATA_DIR=$PWD/v2/browser/runtime_data python v2/browser/app.py`. Confirm it boots, `/skaters` on 2025-26 shows Age, and 2026-27 shows the not-available message when `runtime_data/2026/` is absent." Before Step 1: "`cp data/2025/generated/browser/league.db /tmp/league-2025-pre-birthdate.db`." Add a closing step: either "Deploy: `./tools/sync-runtime-data.sh && fly deploy --remote-only`, then run the runbook Verify list plus: the filter shows 2025-26 and 2026-27; `/skaters` Age is populated. Rollback: `fly deploy --image registry.fly.io/nhl-browser:deployment-<prev id>` (old images carry their own data)", or "Not deployed in this plan", said explicitly.

### F-8 [minor] If 2026-27 drops out of a deploy, the only record is one line in the middle of the sync output

- Where: Task 12 `sync_optional_season` (WARNING lines) and the end of the script (`echo "Synced runtime_data:"; ls -lh "$DST"/*/`).
- Evidence: The WARNING goes to stderr partway through. The script then prints a directory listing, and the documented flow chains straight into the build (`./tools/sync-runtime-data.sh && flyctl deploy`, `fly-deploy.yml:10` and runbook `:28`), so remote-builder output buries the line. At runtime, `healthz.py` returns 200 unconditionally, `app.py` configures no logging, and nothing records which seasons the image holds.
- Problem: The spec says "the sync's WARNING line says why" 2026-27 regressed to not available. In practice nobody sees that line, and after deploy the only signal is a user noticing the message.
- Fix: End the sync with a summary line after the `ls`, for example `echo "Seasons in image: 2025 (required)${shipped:+, $shipped}${skipped:+ | skipped: $skipped}"`, where `skipped` holds each optional season and its reason. In Task 10's runtime-mode preload loop, add `else: logger.warning("season %s not in image; browser shows it as not available", _s)` so it appears in `fly logs` at boot.

### F-9 [minor] Task 12 Step 2's red-phase note is wrong in both environments, and one test never goes red in the worktree

- Where: Task 12 Step 2 ("Don't let the current script write into the real `runtime_data/`: if the old script runs during this step, rerun `./tools/sync-runtime-data.sh` afterward to restore it.")
- Evidence: The test runs the script every time (`subprocess.run(["bash", str(SCRIPT)] ...)`). The old script ignores `SYNC_SRC`/`SYNC_DST` (`tools/sync-runtime-data.sh:14-15`). In a worktree there is no `data/`, so the old script runs `mkdir -p` and then fails at its first `cp` (`:19`) with a non-zero exit. `test_required_season_failure_is_fatal` asserts only `returncode != 0`, so it passes against the old code. In the main checkout, the old script overwrites the real `runtime_data/`, including `v2/browser/runtime_data/goalies.db`, which `git ls-files` shows is tracked. Rerunning the sync in a worktree just fails again.
- Problem: The instruction is conditional ("if the old script runs"), but the script always runs. It also breaks the evergreen rule that every test goes red before green (global CLAUDE.md "Testing"): in the expected execution environment, one of the four tests is green from the start.
- Fix: Replace the note with: "Run this in the worktree only. The old script creates empty `runtime_data/2024` and `2025` directories (gitignored), then fails at its first `cp`. Expected: three FAIL. `test_required_season_failure_is_fatal` passes for the wrong reason (no `data/`); make it go red by asserting the failure message: `assert 'player_bursts.csv' in r.stderr`." Or add a sentinel file check that only the new script's `SYNC_SRC` handling can satisfy.

### F-10 [nit] The Tech Stack names Python 3.11, but the image and CI run 3.12

- Where: Plan line 9, "Python 3.11".
- Evidence: `Dockerfile:3` is `FROM python:3.12-slim`, and `.github/workflows/tests.yml:26` uses `python-version: '3.12'`. The orchestrator runs 3.11.6 (`v2/orchestrator/run.sh:12`).
- Problem: This small inconsistency matters because the plan's code runs in both: the browser code on 3.12 and the build and verify scripts on 3.11.
- Fix: Change it to "Python 3.12 (browser image and CI); 3.11 (orchestrator, local builds)."

### F-11 [nit] An exported `SYNC_SRC` or `SYNC_DST` silently redirects a real sync

- Where: Task 12 script (`SRC="${SYNC_SRC:-...}"`, `DST="${SYNC_DST:-...}"`).
- Evidence: Plan lines 1325-1326. The only intended callers are the tests.
- Problem: If a developer's shell still has these variables from a debugging session, the sync writes somewhere else and exits 0. The Dockerfile guard catches missing required files, but not a stale `runtime_data/2026/` left behind.
- Fix: Print the resolved paths at the start (`echo "sync: $SRC -> $DST"`), or print a warning when either override is set.

### F-12 [nit] The local deploy runbook goes stale, and the plan doesn't update it

- Where: The plan as a whole; spec "Rollover next season".
- Evidence: `docs/fly-deploy-runbook.md:21` ("all 298 ... CI only runs the 295"), `:39` ("`v2/browser/runtime_data/{2024,2025}/`"), and `:40` ("checks all five runtime files").
- Problem: After this change, the runbook's test counts and gitignored-directory list are wrong, and its Verify list has no season check. The runbook is gitignored and local-only, so no review will catch the drift.
- Fix: Add a Task 13 step: update the runbook's pre-flight count, the gitignore list (add `2026`), a Verify bullet ("season filter shows 2025-26 and 2026-27; 2026-27 shows data or the not-available message matching the sync summary"), and the rollover steps.

## Checked and sound

- `db.league_query` and `db.goalies_query` check `exists()` before `sqlite3.connect` (`db.py:36-38`, `:59-61`). A missing season never creates an empty SQLite file that would make `season_ready` true.
- `.dockerignore` doesn't exclude `v2/browser/runtime_data/`, so a synced `runtime_data/2026/` ships through the existing `COPY --chown=app:app v2/browser/ /app/` (`Dockerfile:35`) with no Dockerfile change. `seasons.py` isn't excluded either.
- The Dockerfile guard keeps listing only required files, so an image without 2026 builds, which matches the spec's two tiers.
- The sync runs every required-tier check before `sync_optional_season` touches `runtime_data/2026/`. A required failure exits before any optional-season change.
- `sync_optional_season` runs `rm -rf "${DST:?}/$season"` before staging. A previously synced 2026 can't ship beside a failed one, and `${DST:?}` guards against an empty `DST`.
- Task 12's test fixture satisfies the existing `goalies.db` two-situation check and the burst and birthDate checks. It needs only `bash`, `mktemp`, and a `python3` with pandas, all of which `tests.yml` provides. `REPO = parents[3]` resolves to the repo root from `v2/browser/tests/`.
- None of the new tests are marked `requires_data`, and all use synthetic data, so CI runs them. `test_season_pages.py` and `test_app_season.py` import `app` the same way `test_smoke.py:test_app_initializes` already does in CI.
- `players.csv` has a `birthDate` column (column 10) for 2024, 2025, and 2026 under `data/<season>/generated/players/csv/`.
- `data/2026/generated/browser/` and `data/2026/generated/edge/` don't exist yet, so Task 13 Step 3's expected `WARNING: 2026 not synced` and missing `runtime_data/2026/` are correct.
- The orchestrator passes the configured season to the build (`agent.py:206-207`, `sync_season.py:25`). The 2026 daily build runs from the main checkout's working tree via `run.sh`, which matches the plan's rollout note.
- Image rollback is clean. Each image carries its own `runtime_data/`, and old code ignores the extra `players.birthDate` column (named `SELECT`s), so a rebuilt `data/` DB is also compatible with a reverted sync.
- A session-persisted `"2026"` in a user's browser survives a deploy that drops 2026: `normalize_season` keeps it and `season_ready` returns the not-available message. A persisted value removed from `SEASONS` falls back to `DEFAULT_SEASON` (Task 11 `sync_season("2019")`).
- `git check-ignore -v v2/browser/runtime_data/2026/league.db` in Task 12 Step 5 checks the `.gitignore` edit. The current `.gitignore:11-12` pattern style matches the added line.
- Production memory impact is small. The 2025 `player_bursts.csv` is 80 KB and the preload runs once per gunicorn worker (2 workers, `Dockerfile:69`) on a 512 MB VM.
