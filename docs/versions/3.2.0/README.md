# v3.2.0: Restructure the code into browser, pipeline, and research

**Created:** 2026-11-18 19:26

The current milestone in `ROADMAP.md`. It replaces `v1/`, `v2/`, and `tools/` with three top-level folders, `browser/`, `pipeline/`, and `research/`, installed as one editable package. Nothing a user of the browser or the pipeline sees changes: the same pages, the same data files in the same places, and the same 08:00 run.

Rulings: Decision Queue D43 to D45 (folders, package, `metrics.py`, goalies), D50 (trunk-based on `master`), and D53 (the restructure goes before the Edge refresh).

**Status:** design for discussion. No code has moved. The open questions are D54 to D56 in the Decision Queue, and each section that depends on one says so.

## What the release changes

Filled in as the work lands. The design's file map is in the section "Where each file goes."

## Design

### What the survey found

The coupling section of `docs/context/2026-09-05-project-scaffold-ai-migration-recommendation.md` is the starting checklist. A survey of `master` at `5c6308c` on 2026-11-18 confirms it and finds more than it lists:

- **`v2.` imports.** 64 files use `from v2.…`, not the 14 the report counts. The orchestrator (`runner.py`, `agent.py`, `sync_season.py`, `log_writer.py`, `tools/*.py`, and nine test files), the Edge code, the players tests, and the goalies package all use it.
- **Cross-part imports.** Only two exist, and both are already decided: `build_league_db.py` imports `metrics.py` from the browser, and `build_goalies_db.py` imports `v2.goalies.cut`. Nothing in the pipeline imports from research, and nothing in the browser app imports from the pipeline.
- **`sys.path.insert` calls.** 37 sites. 18 are browser tests that put `v2/browser/` on the path; 15 are goalies modules; the rest are `runner.py`, `sync_season.py`, `build_league_db.py`, `build_goalies_db.py`, `v2/browser/test_rate_metrics.py`, and the competition test.
- **Working-directory-relative `data/` paths.** 13 modules, not 7. The report's list, plus `v1/nhlgame.py` (3 sites), `v2/orchestrator/sync_season.py`, and `tools/flatten_boxscore.py`, `tools/flatten_plays.py`, and `tools/discover_test_games.py`. The orchestrator runs every step as a subprocess with no `cwd` argument, so each one works only because `run.sh` changes to the repository root first.
- **File-relative roots.** 26 modules walk up from `__file__`: 21 goalies modules, `runtime_paths.py`, `build_goalies_db.py`, `orchestrator/config.py`, and four `tools/` scripts. Two browser tests use `parents[3]`, and `test_sync_runtime_data.py` does too.
- **Browser imports.** The app imports its own modules flat (`from db import …`), because the `Dockerfile` copies `v2/browser/` to `/app/` and gunicorn runs `app:server` from there. Dash 4.0.0 names page modules from the app's `__name__`, so a change to package imports changes page module names too. D54 covers this.
- **Missing `__init__.py`.** `v2/`, `v2/browser/`, `v2/players/`, `v2/players/tests/`, and `v2/timelines/` have none and import as namespace packages.
- **Deploy and CI paths.** As the report lists: the `Dockerfile`, `.dockerignore`, `tools/sync-runtime-data.sh`, and both workflows. Also `.gitignore` (the `runtime_data/` lines) and the `requires_data` marker text in `pyproject.toml`.
- **The launchd job.** `~/Library/LaunchAgents/com.nhl.orchestrator.plist` is a copy of the repository's plist, not a link. It names `v2/orchestrator/run.sh`, so Claude reinstalls and reloads it in the same sitting as the move.
- **Stray files.** `v2/browser/league.db` is a tracked, empty file from v1.27.0. `v2/browser/test_rate_metrics.py` is a test outside `tests/`. `tools/test_offwing_splits.py` is a test that CI never runs, because CI runs only `v2/`.
- **Not affected.** The repository itself doesn't move, so the Claude Code memory directory keyed to its path stays valid.

### Where each file goes

- **`browser/`** is the Dash app and everything the Docker image ships.
  - `v2/browser/` moves here whole, except for the three `build_*_db.py` scripts, which move with their tests.
  - `v2/browser/test_rate_metrics.py` moves into `browser/tests/`.
  - `v2/browser/league.db` (empty, tracked) goes.
  - `tools/sync-runtime-data.sh` moves here, next to `verify_runtime_data.py` and their two tests, because it builds `browser/runtime_data/` for the image. D56 covers this.
  - `metrics.py` stays here, and the pipeline imports it (D44).
- **`pipeline/`** is everything the daily run and a season rebuild run.
  - `v1/nhlgame.py` becomes `pipeline/nhlgame.py` (D43).
  - `v2/timelines/`, `v2/competition/`, `v2/players/`, `v2/edge/`, and `v2/orchestrator/` move under `pipeline/` with their names.
  - `tools/flatten_boxscore.py`, `tools/flatten_plays.py`, and `tools/gamecheck.py` move to `pipeline/`, because the orchestrator runs them.
  - The three `build_*_db.py` scripts move to `pipeline/build_dbs/`, with `test_player_metrics.py`, `test_build_goalies_db.py`, and `test_build_opening_night.py`.
  - A new `pipeline/paths.py` is the one place that knows where `data/` is. D55 covers this.
- **`research/`** is the studies. Each study's code sits next to its existing `docs/` folder.
  - `v2/goalies/` becomes `research/goalies/` (D45). Its 26 modules and tests sit beside `research/goalies/docs/`.
  - `tools/offwing_splits.py`, `tools/forwards_offwing_map.py`, `tools/plotting_bias_probe.py`, and `tools/test_offwing_splits.py` move to `research/shooters/`, beside `research/shooters/docs/`. Their test starts running in CI.
  - `tools/discover_test_games.py`, which picks candidate games for the timeline test set, moves to `pipeline/` with the timeline tooling.
- **Removed.**
  - The rest of `v1/`: `onice/`, `plays/`, `timelines/`, `pyproject.toml`, `README.md`, and `PROJECT_STRUCTURE.md`. A search finds no import, script, or schedule that runs them; `tools/gamecheck.py` prints `v1/nhlgame.py` in a hint, which becomes the new path. Before deleting them, Claude compares each Markdown file in `v1/timelines/` with `resources/` and moves any rule text that `resources/` lacks. Git history keeps the rest.
  - `tools/`, once empty.

### The package

- `pyproject.toml` gains a `[build-system]` (setuptools) and a package list of `browser`, `pipeline`, and `research`, with `namespaces = false`. Every package directory gets an `__init__.py`, including `research/`, `research/goalies/`, `research/shooters/`, and the folders that lack one today.
- Pipeline and research code imports by package: `from pipeline.orchestrator.config import …`, `from research.goalies.cut import …`, `from browser.metrics import …`. Every `sys.path.insert` outside the browser goes.
- `pyproject.toml` sets `testpaths = ["browser", "pipeline", "research"]`, so `python -m pytest` with no path runs everything.
- The editable install goes into all three environments that run code, because each has its own site-packages:
  - pyenv 3.11.6, which the 08:00 job runs: `~/.pyenv/versions/3.11.6/bin/python -m pip install -e . --no-deps`.
  - The `uv` environment: `uv sync`.
  - CI: `pip install -e . --no-deps` after `requirements.txt`.
  - The Docker image doesn't need it: gunicorn runs from `/app` with the app on the path, as it does today.
- `--no-deps` keeps the install from changing package versions in the pyenv environment the pipeline depends on.

### Browser imports (D54)

Two ways to treat the browser's own imports:

- **Package imports** (recommended). `from browser.db import …` everywhere, the 18 test `sys.path` inserts go, the image copies `browser/` to `/app/browser/`, and gunicorn runs `browser.app:server`. Dash then names pages `browser.pages.skaters` and so on. The risk is a page imported under two names, for example `pages.notes` and `browser.pages.notes`, which registers its callbacks twice and fails at startup; a test that imports the app and checks the page registry catches it.
- **Flat imports, unchanged.** The browser keeps `from db import …` and its test path inserts, and the image layout stays as it is. The pipeline still imports `browser.metrics` by package, so one test session can hold `metrics` and `browser.metrics` as two module objects. That's harmless for `metrics.py`, which is pure functions, but it leaves the path hack the restructure exists to remove.

### Data paths (D55)

- `pipeline/paths.py` provides `repo_root()`, `data_dir()`, and `season_dir(season)`, as functions, not module constants, so tests can redirect them.
- `data_dir()` returns `$NHL_DATA_DIR` when it's set, and `repo_root() / "data"` otherwise. `repo_root()` is the one remaining `parents[N]` lookup, and a test asserts that it finds `pyproject.toml`. `NHL_DATA_DIR` is the hook the Linux move needs to put `data/` somewhere else. It's a new name because the browser already uses `DATA_DIR` for the image's flat layout.
- Every working-directory-relative path and every `__file__` root in pipeline and research code calls the helper instead. This is the one behavior change in the release: a script started from outside the repository root now finds `data/` instead of writing a new `data/` wherever it was started.
- `browser/runtime_paths.py` keeps its two modes. In local mode it imports `pipeline.paths` inside the function that needs it, never at module level, so the image, which has no `pipeline/`, never runs that import. A test imports `browser.runtime_paths` with `DATA_DIR` set and `pipeline` blocked, to prove it.
- The competition test that depends on the working directory (`test_compute_competition.py`, near line 173) redirects `data_dir()` to a temporary folder instead.

### Scheduler, deploy, and CI

- `pipeline/orchestrator/config.py` builds `SCRIPTS` from the new paths.
- `run.sh` and the plist name `pipeline/orchestrator/run.sh`. The repository and pyenv paths stay hard-coded; the Linux move replaces both files.
- Claude copies the new plist over the installed one and reloads it with `launchctl bootout` and `launchctl bootstrap`, in the same sitting as the move commit.
- `Dockerfile`: the `COPY` source, the `requirements.txt` path, and (with D54's recommendation) the `/app/browser/` layout, `DATA_DIR`, and the gunicorn target. The runtime-file guard keeps every check it has.
- `.dockerignore`: `pipeline/`, `research/`, `browser/tests/`, `browser/verify_runtime_data.py`, and `browser/sync-runtime-data.sh` replace the `v1/`, `tools/`, and `v2/browser/…` lines.
- `.gitignore`: the `runtime_data/` lines move to `browser/runtime_data/`.
- `tests.yml`: the install step adds the editable install, the cache path changes, the test command changes, and the `requires_data` deselection stays.
- `fly-deploy.yml` needs only its comment updated.

### Order of work

Each step is one commit on `master`, with the full test suite passing, and each leaves the 08:00 run working. Steps 4 and 5 happen in one sitting, finished before 08:00.

1. Remove the unused `v1/` files and the empty `v2/browser/league.db`, after the `resources/` comparison.
2. Add the path helper in the current layout and convert every data-path site to it. Then run one full daily pipeline run by hand, to prove the logic change before anything moves.
3. Add the package build, install it editable in all three environments, and replace the `sys.path` inserts with `v2.`-prefixed package imports. Still no files move.
4. The move: `git mv` into the new folders, rewrite the imports to the new package names, update every path in the "Scheduler, deploy, and CI" section, reinstall the editable package in pyenv (the package names change), reinstall the plist, and update `AGENTS.md`'s file map, `README.md`, `docs/commands.md`, and the paths in `PATHWAYS.md` and `BACKLOG.md`. `AGENTS.md` asks for its map to change in the same commit as the move. Dated documents keep their old paths.
5. Verify, as the "Human test" section lists.

Separating the logic changes (steps 2 and 3) from the move (step 4) lets `git log --follow` show step 4 as renames with import edits only.

### What this release doesn't do

- No behavior, data, or page changes, apart from the working-directory fix in the section "Data paths (D55)".
- No change to the pipeline's schedule, the Edge refresh, the goalie seasons, or the shared `SEASONS` definition. Those are later milestones.
- No Fly deploy unless oiler approves one. The image changes only in layout, so the release can ship with the next data deploy.

## Human test

Claude runs steps 1 to 5. oiler runs step 6.

1. Before step 4, build the current image as `nhl-browser:pre-3.2.0` and save its file list (`find /app -type f | sort`) and the checksums of `runtime_data/`.
2. `python -m pytest -v` passes with the same test count as before the move, plus the moved shooters test. CI on the move commit passes.
3. `python pipeline/orchestrator/runner.py` completes a full daily run from the repository root, and its log in `data/2026/logs/` matches the previous day's steps. `launchctl print gui/$(id -u)/com.nhl.orchestrator` shows the new `run.sh` path.
4. `./browser/sync-runtime-data.sh` ends with the same `Seasons in image` line as v3.1.2.
5. Build the new image. Its file list matches step 1's apart from the path prefix, and the `runtime_data/` checksums match. Run it locally and check `/healthz` and one page of each type.
6. The next morning, oiler checks that the 08:00 run succeeded from launchd.

Record each result under "Results."

## Results

## Close-out

- [ ] Every file in this folder listed under "This folder", and the human test recorded under "Results"
- [ ] The version added to `CHANGELOG.md`
- [ ] The milestone's row and log entry added to `docs/history.md`
- [ ] The milestone removed from `ROADMAP.md`, so the next milestone is first in its list
- [ ] The release commit tagged, with a GitHub Release: the commit that adds the version to `CHANGELOG.md`
