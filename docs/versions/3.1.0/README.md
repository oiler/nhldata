# v3.1.0: Season toggle

The first milestone in `ROADMAP.md`. It lets the browser switch between 2025-26 and 2026-27, shows "not available yet" for a season without verified data, and keeps the deploy guard strict for the default season only.

v3.1.0 also carries the work merged to `master` since v3.0.0: the goalie 5v5 situation cut, 5v5 goalie time on ice, the fix for the 2026-07-29 production outage, the switch of the daily pipeline to 2026-27, and the daily run's catch-up on missed games. `CHANGELOG.md` section "Unreleased" lists them.

The release isn't built yet. Task 0 of the season-toggle plan is done.

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

Not run yet.

## Close-out

- [ ] Every file in this folder listed under "This folder", and the human test recorded under "Results"
- [ ] The version added to `CHANGELOG.md`
- [ ] The milestone's row and log entry added to `docs/history.md`
- [ ] The milestone removed from `ROADMAP.md`, so the next milestone is first in its list
- [ ] The release commit tagged: the commit that adds the version to `CHANGELOG.md`

oiler runs the git steps. `AGENTS.md` section "Project rules" says so.
