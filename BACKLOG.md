# Backlog

Committed work not yet scheduled. Research ideas live in `docs/opportunities.md`.

---

## Keep the deployed browser current during the season

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

## Extend the goalie pipeline to 2026-27

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

## Scheduled and on-demand Edge refresh

**Added:** 2026-09-29

**Problem:** The Edge burst data (`data/<season>/generated/edge/player_bursts.csv`) behind SB/a60 and Max MPH is built by hand: `NHL_SEASON=<season> python v2/edge/fetch_skater_detail.py`, then `compute_burst_rates.py`. During the season the numbers go stale between manual runs.

**Want:**

- One command that refreshes Edge data for the active season, runnable on demand (for example, `python v2/orchestrator/runner.py "refresh edge"` or a standalone script).
- A monthly schedule (launchd, like the daily orchestrator), kept out of the daily run so about 800 Edge requests don't add a failure mode every morning.
- The same season guards as the daily run: read `NHL_SEASON`, require the season's `league.db` to exist (the skater list comes from it), and write a log to `data/<season>/logs/`.

**Depends on:** the season-toggle work (per-season burst loading in the browser).
