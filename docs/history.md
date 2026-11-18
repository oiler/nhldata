# History

Finished milestones, and a dated log of what happened along the way. `ROADMAP.md` holds the planned work. When a milestone finishes, add its row to "Finished milestones" and an entry to "Log."

## Finished milestones

| Milestone | Version | Done | Release folder |
|---|---|---|---|
| Player page stat expansion | 2.2.0 | 2026-06-18 | `docs/versions/2.2.0/` |
| Skater shot stats (iSA/60 and P/100iSA) | 2.3.0 | 2026-06-22 | `docs/versions/2.3.0/` |
| Goalies in the browser | 3.0.0 | 2026-07-19 | `docs/versions/3.0.0/` |
| Season toggle | 3.1.0 | 2026-11-18 | `docs/versions/3.1.0/` |
| Default to 2026-27 | 3.1.1 | 2026-11-18 | `docs/versions/3.1.1/` |

Work from January to June 2026 predates version tags: the timeline generator, the fetcher, the competition score, the browser app, the orchestrator, the elite models, deployment metrics, Edge bursts, the Fly.io deploy, and the frontend redesign. Its designs and plans are in `docs/plans/`, named by date.

The goalie evaluation research (phases P0 to P6, the freeze-value study, and the 5v5 re-check) ran from June to July 2026. Its design, plans, pre-registration, and report are in `research/goalies/docs/`. Research documents live in `research/<study>/docs/`, beside where the study's code moves in the code restructure (Decision Queue D46).

## Log

- 2026-01-30: Project created, with the v1 scripts and the plan for v2. `docs/context/kickoff.md` is the kickoff note.
- 2026-06-10: Frontend redesign. `docs/context/session-logs/2026-06-10-frontend-redesign.md`
- 2026-06-18: v2.2.0, player page stat expansion. `docs/context/session-logs/2026-06-18-player-page-stat-expansion-v2.2.0.md`
- 2026-06-18: Security upgrades and a skater burst fix. `docs/context/session-logs/2026-06-18-security-upgrades-and-skater-burst-fix.md`
- 2026-06-22: v2.3.0, skater shot stats.
- 2026-06-24: Backfilled Edge and off-wing data for 2024-25. `docs/context/session-logs/2026-06-24-2024-25-edge-offwing-backfill.md`
- 2026-07-19: v3.0.0, goalies in the browser.
- 2026-07-21: Goalie 5v5 re-check finished, and the goalie situation dropdown deployed.
- 2026-07-29: Production returned 502 after a CI deploy built an image with no data. Deploys became local-only, and the Docker build now fails without the runtime files.
- 2026-07-30: Goalie evaluation phases P4 through post-P6. `docs/context/session-logs/2026-07-30-goalie-eval-p4-through-postp6.md`
- 2026-08-11: 5v5 goalie time on ice merged.
- 2026-09-29: The daily pipeline switched to 2026-27. The season-toggle spec and plan were written and reviewed.
- 2026-11-13 to 2026-11-15: Fifteen failed daily runs since 2026-10-03 had left 130 of 325 games of 2026-27 missing. They were fetched by hand and the season was rebuilt from raw files.
- 2026-11-17: The daily run now fetches every finished game that isn't on disk, not only yesterday's, and one game without shift reports no longer stops a fetch range (Decision Queue D35).
- 2026-11-17: Project documents moved to the project-scaffold-ai layout. `AGENTS.md`, `PROJECT.md`, `ROADMAP.md`, this file, `docs/context/`, and `docs/versions/` were added, and existing specs, plans, and reviews moved by `git mv` (D37 to D42). Research documents moved to `research/goalies/docs/` and `research/shooters/docs/` (D46).
- 2026-11-18: v3.1.0, the season toggle. The browser switches between 2025-26 and 2026-27, the deploy sync ships seasons in required and optional tiers, and 14 Dependabot alerts were closed. Built on `master` without superpowers, by trunk-based development (D50). Deployed as Fly release v28.
- 2026-11-18: v3.1.1, the browser opens on 2026-27, and 2026-27 became the required deploy season. Deployed as Fly release v29. Claude took over release tagging.
