# AGENTS.md

NHL game data analytics: a data pipeline that turns public NHL API data into second-by-second timelines and 5v5 metrics, a Dash browser app that serves them, and research built on the same data. `PROJECT.md` says why the project exists.

## Files

- `README.md`: what the project does and how to deploy it. Links to `PROJECT.md`.
- `AGENTS.md`: a map of the project's files and the project's own rules.
- `CLAUDE.md`: imports `AGENTS.md`.
- `PROJECT.md`: why the product exists and what guides its tradeoffs. Evergreen.
- `DESIGN.md`: the browser's visual design system. Evergreen.
- `ROADMAP.md`: planned work, in order. The controlling document.
- `BACKLOG.md`: everything not promised yet. Not promised.
- `CHANGELOG.md`: what shipped, for someone who uses it.
- `GLOSSARY.md`: definitions of the project's stats and terms.
- `PATHWAYS.md`: files to add as the project grows.
- `docs/history.md`: finished milestones, and a dated log. Artifact.
- `docs/versions/`: one folder per release, with its record, specs, plans, and reviews. Its `README.md` explains the layout and the close-out. A release that needs a separate spec or plan puts it in `docs/versions/<version>/specs/` or `docs/versions/<version>/plans/`. The project doesn't use superpowers. Artifacts.
- `docs/context/`: background, such as the kickoff note, analysis write-ups, idea notes, and session logs. Artifacts.
- `docs/plans/`: specs and plans from January to June 2026 that predate release folders. An archive; don't add to it. Artifacts.
- `research/<study>/docs/`: a study's design, plans, pre-registration, and reports. `research/goalies/docs/` and `research/shooters/docs/` exist today. New research documents go here, not in `docs/versions/`. Artifacts.
- `docs/commands.md`, `docs/data-limitations.md`, `docs/elite-classification-model.md`, `docs/team-deployment-analysis.md`, `docs/2024-season-support-status.md`: standing reference documents.
- `resources/`: reference material, including `Rules Coincidental Penalties.md` (NHL Rule 19 and Table 13), `NHL API Documentation.md`, and `SITUATIONCODE_REFERENCE.md`.
- `v1/nhlgame.py`: the raw-data fetcher the daily pipeline runs. The rest of `v1/` is the first version of the scripts.
- `v2/timelines/`, `v2/competition/`, `v2/players/`, `v2/edge/`: pipeline steps that turn raw data into derived data.
- `v2/orchestrator/`: the daily pipeline runner, scheduled by launchd at 08:00.
- `v2/browser/`: the Dash app, and the `build_*_db.py` scripts that build its databases.
- `v2/goalies/`: the goalie research models.
- `tools/`: utility scripts, including `sync-runtime-data.sh`, which copies built data into the image before a deploy.
- `data/`: raw and generated data, one folder per season. Gitignored.
- `Dockerfile`, `fly.toml`, `.github/`: deployment to Fly.io and the test workflow.

`ROADMAP.md` schedules a restructure of `v1/`, `v2/`, and `tools/` into `browser/`, `pipeline/`, and `research/`. Until then `research/` holds only documents, and the research code is in `v2/goalies/` and `tools/`. Update this map in the same change.

## Commands

- **Tests:** `python -m pytest v2/ -v`. Run it before finishing any change. CI runs `python -m pytest v2/ -q -m "not requires_data"`, because `data/` is gitignored.
- **Daily pipeline by hand:** `python v2/orchestrator/runner.py`. `NHL_SEASON` selects the season.
- **Rebuild a season from raw files:** `python v2/orchestrator/sync_season.py <season>`.
- **Deploy:** `./tools/sync-runtime-data.sh`, then `fly deploy`. Claude deploys only after oiler approves that deploy. Deploy locally only, never from CI.
- `docs/commands.md` lists the rest.

## Technical stack

- `nhl-api-py`: NHL API wrapper.
- `pandas`: data processing.
- `requests` and `BeautifulSoup`: HTML scraping when the API returns nothing.
- Plotly Dash: the browser app. SQLite: its databases.
- Outputs are JSON for programs and CSV for analysis.

## Project rules

- In project documents, write items that carry details as list items with sublists. Use a table only when it fits better, such as rows that compare a few short attributes.
- **Discuss before implementing.** Talk through the solution and its edge cases, explain the reasoning and tradeoffs, and wait for an explicit instruction before writing code. Cite the specific NHL rule or official source a decision rests on.
- **Validate against official sources.** Outputs must match official NHL statistics exactly: ESPN box scores for game summaries, NHL.com for time on ice, and established scrapers (Hockey-Scraper patterns) as a cross-check.
- **Python, not R.** Use Python tools and libraries for everything.
- **Git.** Trunk-based development (D50, 2026-11-17). Work one change at a time on `master`. Claude commits each change once the tests pass, and pushes it to `hub`. Each commit leaves `master` working, because the 08:00 pipeline runs from this checkout: don't leave a change half-done across 08:00.
- **Deploys.** Pause for oiler's approval before every Fly deploy. A push doesn't deploy: `fly-deploy.yml` runs only by hand.
- **Releases.** A release's close-out uses the document steps in `docs/versions/README.md`. Claude tags each release with an annotated tag and publishes a GitHub Release whose notes are the version's `CHANGELOG.md` section (oiler, 2026-11-18).
- Never capitalize "oiler".

### Situation timelines

- The situation code format is `[Away Goalie][Away Skaters][Home Skaters][Home Goalie]`. `1551` is both goalies in at 5v5. `1441` is 4v4.
- 5v5 means `1551` only. `1441` is excluded from every 5v5 stat.
- Coincidental penalties (Rule 19.1): when exactly one minor penalty per team occurs at the same time with no other penalties in effect, the teams play 4v4. Penalties cancel by total count, not by type. `resources/Rules Coincidental Penalties.md` has the rule and the Table 13 examples.
- Other cases the timeline handles: several simultaneous penalties that need cancellation, and captain's choice in penalty assessment.

### On-ice shifts

- When shifts overlap at one timestamp, the departing player has priority. The incoming player starts at `startTime + 1`.
- Process one period at a time, 0 to 1200 seconds, so shifts don't overlap a period boundary.
- The raw API has no position data. Detect goaltenders from period starters and total ice time.
- The NHL shifts API often returns empty responses for 2024-25 and later. That's missing data, not an error. The fetcher scrapes the HTML Time-on-Ice reports instead. `resources/NHL API Documentation.md`, section "API Access Patterns," has the details.

### Testing

- Test computations, not callbacks. For each new feature, add a targeted test for the pandas or math logic it touches. Full Dash callback tests aren't needed.
- Use synthetic data. Build small DataFrames in tests instead of reading real data files. `test_player_metrics.py` and `test_deployment_metrics.py` show the pattern.
- Shared metric logic lives in `v2/browser/metrics.py`. Both `build_league_db.py` and `filters.py` use the wPPI, wPPI+, and `avg_toi_share` calculation there. Change `metrics.py`; never duplicate metric logic.

## External references

- NHL API reference: https://github.com/Zmalski/NHL-API-Reference
- nhl-api-py: https://github.com/coreyjs/nhl-api-py
- Hockey-Scraper (archived; the reference for the HTML fallback): https://github.com/HarryShomer/Hockey-Scraper
- TopDownHockey tutorials: https://github.com/TopDownHockey/TopDownHockey_Scraper
