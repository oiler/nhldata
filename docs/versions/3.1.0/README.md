# v3.1.0: Season toggle

The first milestone in `ROADMAP.md`. It lets the browser switch between 2025-26 and 2026-27, shows "not available yet" for a season without verified data, and keeps the deploy guard strict for the default season only.

v3.1.0 also carries the work merged to `master` since v3.0.0: the goalie 5v5 situation cut, 5v5 goalie time on ice, the fix for the 2026-07-29 production outage, the switch of the daily pipeline to 2026-27, and the daily run's catch-up on missed games. `CHANGELOG.md` section "Unreleased" lists them.

Tasks 0 to 12 of the season-toggle plan are built and on `master`. Task 13's machine-led steps and oiler's hand checks passed on 2026-11-17. The runbook update (Step 7) and the deploy are open. On 2026-11-17 the plan was updated to build without superpowers, on `master` by trunk-based development (D50), and to add a 2026-27 Edge run before the sync (D51).

## This folder

The files dated before 2026-11-17 were moved here on that date from `docs/plans/` and `docs/superpowers/`, by `git mv` and a literal replacement of the old paths. Files inside each orko-review run folder are left as recorded, so the paths they cite predate the move.

| Path | What it is |
|---|---|
| `specs/2026-09-29-season-toggle-design.md` | The season-toggle spec, approved 2026-09-29 |
| `plans/2026-09-29-season-toggle-plan.md` | The season-toggle plan |
| `reviews/2026-09-29-season-toggle-design/` | orko-review run on the spec |
| `reviews/2026-09-29-season-toggle-plan/` | orko-review run on the plan |
| `specs/2026-07-21-goalie-5v5-parallel-design.md` | The design for the 5v5 goalie pipeline and the situation dropdown, merged and deployed 2026-07-21 |
| `plans/2026-07-21-goalie-5v5-parallel-plan.md` | Its implementation plan |
| `specs/2026-07-30-goalie-5v5-toi-design.md` | The design for 5v5 goalie time on ice, merged 2026-08-11 |
| `plans/2026-07-30-goalie-5v5-toi-plan.md` | Its implementation plan |

The daily run's catch-up on missed games (2026-11-17) was built without a plan. `docs/history.md` records it.

## What the release changes

The season-toggle plan lists the files each task changes. The two goalie plans list theirs.

## Design

- Season toggle: the spec and the plan above.
- Goalie 5v5 situation cut and 5v5 time on ice: the two goalie specs and plans above. Both are already merged.

## Human test

Task 13 of the season-toggle plan, "Rebuild and verify in the running app." Steps 1 to 5 rebuild both seasons, check the databases, run the sync, and boot the app in production mode. Step 6 is the list of checks oiler makes by hand in local dev. Record the outcome of each step under "Results."

## Results

### Machine-led tests, 2026-11-17

- **Run by:** Claude, in the main checkout on `master`.
- **Result:** Passed. The full suite, including the `requires_data` tests, gave 401 passed.
- **Found:**
  - Both seasons rebuilt with `players.birthDate`. Every player in 2025 (1,017) and 2026 (871) has one, and the 2025 values match the Edge CSV's `birth_date` for all 940 skaters.
  - The 2026-27 Edge fetch got data for 775 of 776 skaters. `verify_runtime_data.py` passed for both seasons, with 100% burst and `birthDate` coverage.
  - The real sync exited 0 and ended `Seasons in image: 2025 (required), 2026 (optional)`.
  - In production mode against `runtime_data/`, the app preloaded both seasons' bursts. Skaters, games, team, and player pages rendered for both seasons, Age had no gaps, and 2026-27 SB/a60 was blank for the one skater without Edge data.
- **Changed:** Independent reviews of Tasks 6, 8, and 12 found no bugs. The Task 8 review led to tests for each check's condition. The Task 12 review led the sync to stage every required file before replacing any. The plan's Task 12 section records the difference.

### Human test, Step 6, 2026-11-17

- **Run by:** oiler, in local dev.
- **Result:** Passed. oiler confirmed the season toggle works locally.
- **Found:** Nothing reported.
- **Changed:** Nothing.

## Close-out

- [ ] Every file in this folder listed under "This folder", and the human test recorded under "Results"
- [ ] The version added to `CHANGELOG.md`
- [ ] The milestone's row and log entry added to `docs/history.md`
- [ ] The milestone removed from `ROADMAP.md`, so the next milestone is first in its list
- [ ] The release commit tagged by oiler: the commit that adds the version to `CHANGELOG.md`
