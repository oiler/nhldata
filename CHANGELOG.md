# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]
### Added
- Glossary entries for G/A/P, P/60, 5v5 TOI, Line/Pair, Dep Score, and a
  "Teams and games" section: P%, RW, 5v5 GF/GA/GD, team PPI and wPPI,
  heaviness, and Game wPPI+.

### Fixed
- The SB/a60 glossary entry gives typical ranges from 2025-26 data, and the
  DPS+ and DPL entries cover both forwards and defensemen.

## [3.1.1] - 2026-11-18
### Changed
- The browser opens on 2026-27. The deploy now requires 2026-27 and treats
  2025-26 as optional, so a failing 2025-26 check leaves it out of the image
  with a warning instead of blocking the deploy.

### Fixed
- A failing optional season no longer deletes the other files in its
  `runtime_data/` folder, such as `2025/edm.db`.

## [3.1.0] - 2026-11-18
### Security
- Closed 14 Dependabot alerts (2 critical, 6 high, 6 moderate) in `certifi`,
  `anyio`, `urllib3`, and `soupsieve`. `uv.lock` now resolves the patched
  versions, the image's `requirements.txt` raises the `urllib3` floor to 2.8.0
  and adds `certifi>=2026.10.18`, and `pyproject.toml` requires Python 3.11.5+,
  which the patched `soupsieve` needs.

### Changed
- The daily pipeline fetches and builds 2026-27 (since 2026-09-29).

### Fixed
- A season's first weeks no longer break pages: the build creates every table
  and column the pages read before any 5v5 goal or elite exists, and the game
  page shows em dashes while season metrics are empty.
- `league.db` builds before any skater reaches 5 games played. Early in a
  season the build stopped with `no such table: player_metrics`.
- Missing goalie time on ice shows as an em dash instead of a wrong per-60.
- Production 502 on 2026-07-29. The `Deploy to Fly` Action deployed on every push
  to master, but builds from a bare `git checkout` — which lacks the gitignored
  `v2/browser/runtime_data/{2024,2025}/`. `pages/skaters.py` loads the burst CSV at
  import, so the dataless image crash-looped gunicorn past Fly's restart cap.
  - `Dockerfile` now fails the **build** when any of the five runtime files is
    missing or empty, so a dataless image never reaches the registry.
  - `fly-deploy.yml` is `workflow_dispatch`-only; deploys are local-only.

### Added
- A season filter on the games, teams, team, skaters, player, and goalies
  pages, with 2025-26 and 2026-27. It opens on 2025-26 and keeps the selected
  season across page loads in the same tab. A season without verified data
  says "<season> data isn't available yet."
- 2026-27 Edge speed bursts (SB/a60 and Max MPH) on the skaters page, from a
  manual Edge run on 2026-11-17. Each season shows its own bursts.
- Age comes from each player's birth date, so it shows with or without Edge
  data. Missing numbers show as an em dash and still sort numerically.
- The deploy sync ships 2025-26 as required and 2026-27 as optional: a failing
  2026-27 is left out with a warning instead of blocking the deploy. A failing
  required file now leaves `runtime_data/` unchanged.
- Goalie pages have a situation dropdown: all situations or strict 5v5. The
  goalies list, the goalie page, the team goalie section, and the glossary
  follow it. Deployed 2026-07-21.
- GSAx/60 and xGA/60 on the goalie pages in both situations, using 5v5 goalie
  time on ice built from the per-second timelines.
- A notes page, with a goalie note and a goalie glossary.
- `Tests` workflow — runs `pytest v2/` on push to master and on PRs. Tests that
  read the gitignored `data/` tree are marked `requires_data` (registered in
  `pyproject.toml`) and deselected in CI; 295 of 298 run there.

## [3.0.0] - 2026-07-19
### Added
- Goalies in the browser, built from the goalie evaluation models:
  - `/goalies`: a goalie index for each season.
  - `/goalie/<id>`: season cards, a per-game ledger, and a freeze-value line
    stated relative to the median goalie.
  - A goalie environment section on each team page.
- `goalies.db`, a cross-season database the browser reads beside `league.db`.
  `tools/sync-runtime-data.sh` copies and checks it before a deploy.

### Notes
- This entry was written on 2026-11-17 from the commit history. The `v3.0.0`
  tag was created without one.

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
