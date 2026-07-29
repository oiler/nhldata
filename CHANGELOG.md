# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]
### Fixed
- Production 502 on 2026-07-29. The `Deploy to Fly` Action deployed on every push
  to master, but builds from a bare `git checkout` — which lacks the gitignored
  `v2/browser/runtime_data/{2024,2025}/`. `pages/skaters.py` loads the burst CSV at
  import, so the dataless image crash-looped gunicorn past Fly's restart cap.
  - `Dockerfile` now fails the **build** when any of the five runtime files is
    missing or empty, so a dataless image never reaches the registry.
  - `fly-deploy.yml` is `workflow_dispatch`-only; deploys are local-only.

### Added
- `Tests` workflow — runs `pytest v2/` on push to master and on PRs. Tests that
  read the gitignored `data/` tree are marked `requires_data` (registered in
  `pyproject.toml`) and deselected in CI; 295 of 298 run there.

## [2.3.0] - 2026-06-22
### Added
- Two individual 5v5 shot stats on the player page (`/player/<id>`, each with a
  league rank) and the `/skaters` leaderboard (sortable columns):
  - **iSA/60** — individual shot attempts (Corsi, blocked attempts included) per 60
    minutes of 5v5 ice time. Measures the shot volume a skater generates himself.
  - **P/100iSA** — 5v5 points (G+A) per 100 individual shot attempts. Measures shot
    efficiency; playmakers score high. Ranked/displayed only for skaters with ≥ 50
    attempts in the window so small samples don't distort the leaderboard sort.
- New `events_5v5.ishots` column (individual 5v5 shot attempts, credited to the
  shooter; a blocked shot still credits the blocker's `blocks`). New
  `points_per100_shots` helper and `events_per60` now emits `ishots_per60`.

### Removed
- `PPI` column from the `/skaters` leaderboard (its `PPI+`/`wPPI+` companions and the
  player-page PPI cell remain).

## [2.2.0] - 2026-06-18
### Added
- Individual player page (`/player/<id>`) now shows, each with a league rank:
  - Carry-over leaderboard stats: `SB/a60`, `Max MPH`, `DPL`, `DPS+`.
  - 5v5 per-60 individual events: `Hits/60`, `Blocks/60`, `TK/60`, `GV/60`.
  - 5v5 on-ice possession: `CF/60`, `CA/60`, `CF%`.
- New `league.db` tables: `events_5v5` (per-game 5v5 hits/blocks/takeaways/giveaways)
  and `onice_5v5` (per-game on-ice 5v5 Corsi for/against, built by joining
  play-by-play to the per-second on-ice timelines).
- Shared per-60 helpers in `v2/browser/metrics.py`: `carryover_per_player`,
  `events_per60`, `corsi_per60`. New tests in `v2/browser/test_rate_metrics.py`.

### Removed
- Raw `wPPI` cell on the player page (the normalized `wPPI+` remains).

### Notes
- On-ice Corsi uses the timeline-derived shooter side (not `eventOwnerTeamId`,
  which is the blocking team on blocked shots). Games missing a timeline are
  skipped gracefully and picked up automatically on the next DB rebuild; their
  TOI is excluded from the `CF/60` denominator so the rate is not diluted.
