# Roadmap

Planned work, in order. When a milestone finishes, it moves to `docs/history.md`.

The project is past its first release: `docs/history.md` lists the releases through v3.0.0. This file holds only the work that's planned next.

- **Current milestone:** Season toggle (v3.1.0).
- **Order:** set by oiler on 2026-11-17 (Decision Queue D37 and D40). The season toggle ships on the current code layout, the code restructure follows as its own release, and the daily pipeline moves machines after that. The Dependabot fix, added at high priority on 2026-11-17, was folded into v3.1.0 the same day.

## Milestones

### Season toggle (v3.1.0)

Let the browser switch between 2025-26 and 2026-27, show "not available yet" for a season without verified data, and keep the deploy guard strict for the default season only. The deployed browser shows no 2026-27 data until this ships, because `tools/sync-runtime-data.sh` copies only 2024 and 2025.

v3.1.0 also carries the fix for 14 Dependabot alerts (2026-11-17) and what's merged since v3.0.0: the goalie 5v5 situation cut, 5v5 goalie time on ice, the fix for the 2026-07-29 production outage, and the switch of the daily pipeline to 2026-27. `CHANGELOG.md` section "Unreleased" lists them.

- **Release folder:** `docs/versions/3.1.0/`
- **Spec:** `docs/versions/3.1.0/specs/2026-09-29-season-toggle-design.md`
- **Plan:** `docs/versions/3.1.0/plans/2026-09-29-season-toggle-plan.md`. Task 0 is done.
- **Depends on:** nothing.

### Restructure the code into browser, pipeline, and research

Replace `v1/`, `v2/`, and `tools/` with three top-level folders that match the project's three parts. No behavior changes.

- **Decided (D43 to D45, 2026-11-17):**
  - Top-level folders `browser/`, `pipeline/`, and `research/`, installed as an editable package, with the `v2.` import prefix dropped. Of `v1/`, only `nhlgame.py` moves, into `pipeline/`.
  - `metrics.py` stays in `browser/`, and the pipeline imports it.
  - `v2/goalies/` moves whole to `research/goalies/`, and the pipeline's `build_goalies_db` imports from it.
- **Work:**
  - Move the three `build_*_db.py` scripts from the browser folder to the pipeline.
  - Replace the working-directory-relative `data/` paths and the `parents[N]` root lookups with one helper. `docs/context/2026-09-05-project-scaffold-ai-migration-recommendation.md`, section "Coupling that blocks a move," lists each site.
  - Update the launchd job, `run.sh`, the `Dockerfile`, `.dockerignore`, `tools/sync-runtime-data.sh`, and the GitHub workflows for the new paths.
  - Confirm the other `v1/` scripts are unused before removing them.
  - Verify with the full test suite, one full daily pipeline run, a sync, and a Docker build compared against the current image.
- **Version:** not chosen yet.
- **Depends on:** the season toggle, because its plan was reviewed against the current paths.

### Move the daily pipeline to an always-on Linux machine

The 08:00 launchd job runs on a laptop that is often asleep. Fifteen runs between 2026-10-03 and 2026-11-15 failed with `Agent error: Connection error.` The daily run now catches up on games an earlier run missed, so a failed morning no longer loses games, but the data arrives a day or more late.

- **Decided (D36, 2026-11-17):** move the scheduled run to an always-on Linux machine, instead of adding retries or changing the time on the laptop.
- **Work:**
  - Replace `com.nhl.orchestrator.plist` and the hard-coded paths in `v2/orchestrator/run.sh` with a cron job or systemd timer that takes the repository path from its environment.
  - Decide where `data/` lives on that machine, and how the laptop reads it for local deploys.
  - Replace `send_notification`, which is a macOS desktop notification.
- **Depends on:** the code restructure.

### Keep the deployed browser current during the season

**Added:** 2026-09-29

**Problem:** The deployed app (`app.nhldata.org`) reads data baked into the Docker image at build time, and there's no Fly volume. The daily 08:00 orchestrator run updates local data only, so the live site shows the in-progress season (2026-27) only as of the last manual `./tools/sync-runtime-data.sh` + `fly deploy`.

**Constraints:**

- Deploy locally only. A CI deploy built from a bare checkout with no data took production down on 2026-07-29, and `.github/workflows/fly-deploy.yml` is now `workflow_dispatch`-only.
- The sync script and the Dockerfile `RUN` guard name each season's runtime files explicitly. Any new approach has to keep the guarantee that a dataless or partial image can't ship.
- The daily pipeline doesn't build the files the browser needs beyond `league.db`: Edge bursts (`player_bursts.csv`), `edm.db`, and `goalies.db` are manual today.
- `build_league_db.py` deletes `league.db` and then rebuilds it table by table, so a sync or a page read during the 08:00 build (or after a failed one) sees a partial database. Any automated sync needs the build to write to a temporary file and `os.replace()` it into place. Source: orko-review finding `data/F-5` on the season-toggle spec.

**Options:**

1. **Daily local deploy.** After the 08:00 run, a local job rebuilds the manual artifacts, syncs, and runs `fly deploy`. Smallest change, but it depends on this Mac being awake and building an image every day.
2. **Manual cadence with an "as of" date.** Deploy when convenient (for example, weekly), and show the data date in the app header.
3. **Move data off the image.** A Fly volume or object storage that the pipeline pushes to, so data refreshes without a deploy. Most robust, but it changes the deploy model and the runtime-data guards.

**Depends on:** the season-toggle work (2025-26 + 2026-27 in the browser).

---

### Extend the goalie pipeline to 2026-27

**Added:** 2026-09-29

**Problem:** The goalie pipeline covers 2021-22 through 2025-26 only. `SEASONS = ("2021", ..., "2025")` is hard-coded in 10 modules under `v2/goalies/` and in `v2/browser/build_goalies_db.py`. Until it's extended, the browser shows "not yet available" for 2026-27 on `/goalies` and in the team page's goalie section.

**Decision needed first:** how to score an in-progress season against models fit on 2021–2025. The GSAx baseline, game difficulty, arena adjustments, and freeze pricing were all fit on the five completed seasons.

- **Score against the frozen baseline.** Keep the 2021–2025 fits fixed and apply them to 2026-27 games. Stable and comparable across the season, but the baseline drifts out of date as the league changes.
- **Refit including 2026-27.** Adds the new season to the pooled fits. Moves every historical number on each rebuild, and early-season samples are thin.

**Other work:**

- Replace the per-module `SEASONS` tuples with one shared definition so the next season is a one-line change.
- Decide whether goalies.db rebuilds join the daily orchestrator run or stay manual.
- Check the research honesty guardrails on `/goalie/<id>` against small in-season samples (for example, the freeze-percentile eligibility of `MIN_SAVES_FOR_PCT = 500` saves).

**Depends on:** the season-toggle work.

---

### Scheduled and on-demand Edge refresh

**Added:** 2026-09-29

**Problem:** The Edge burst data (`data/<season>/generated/edge/player_bursts.csv`) behind SB/a60 and Max MPH is built by hand: `NHL_SEASON=<season> python v2/edge/fetch_skater_detail.py`, then `compute_burst_rates.py`. During the season the numbers go stale between manual runs.

**Want:**

- One command that refreshes Edge data for the active season, runnable on demand (for example, `python v2/orchestrator/runner.py "refresh edge"` or a standalone script).
- A monthly schedule (launchd, like the daily orchestrator), kept out of the daily run so about 800 Edge requests don't add a failure mode every morning.
- The same season guards as the daily run: read `NHL_SEASON`, require the season's `league.db` to exist (the skater list comes from it), and write a log to `data/<season>/logs/`.

**Depends on:** the season-toggle work (per-season burst loading in the browser).
