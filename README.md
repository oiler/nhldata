# NHL Data

- https://app.nhldata.org/

## What This Project Does

This project processes NHL API data into a set of analytics tools focused entirely on 5v5 play. The core idea is that 5v5 data is the most meaningful. It tells us how different teams and coaches use their players — who produces in the hardest environments, and who is producing against easier competition.

## What We Track — and What We Don't

The focus is 5v5 only. Power plays, penalty kills, and 4v4 situations are excluded from all metrics. Special teams inflate individual production numbers and make cross-player comparisons unreliable. Every stat in this project is 5v5.

## How the Data Gets Built

The pipeline starts with the NHL API. Each night:
- Raw game data is fetched for any new games — play-by-play, shifts, boxscores
- Second-by-second timelines are generated from the shift data, tracking exactly who was on the ice for each second of 5v5 play
- Competition scores are computed from those timelines — who each player shared the ice with, and who they faced
- The browser database is rebuilt from everything above

A Claude-powered orchestrator runs this nightly on a schedule, validates each step, and reports what was processed.

## In The Browser

A multi-page Dash app serves all of the data. Everything is filterable by date range, which means you can look at the last 20 games, a specific road trip, or the full season. Pages include:
- Games — every game with final score and team competition quality
- Teams — points percentage, goal differential, deployment metrics by team
- Skaters — 5v5 stats for every player in the league: P/60, TOI, competition quality, deployment
- Player — per-player season view with game-by-game breakdown
- Elites — the top forwards and defensemen by production and deployment

## New Stat Models

- **Second-by-Second Timelines**

  The foundation everything else is built on. For each game, we process the shift data into a snapshot for every second of play — which players were on the ice, and what the game situation was. Every second is tagged with a situation code that describes the ice exactly: both goalies in, skater counts for each team, whether it's 5v5, 5v4, or anything else.

  The NHL API frequently returns empty shift data for recent seasons, so we scrape the official HTML time-on-ice reports as a fallback. That second-by-second record is what makes it possible to calculate anything that follows.

- **PPI and wPPI+ (Player Physical Index and Weighted PPI Plus)**

  Tall, skinny players can be "smaller" than shorter, stockier players. PPI is an attempt to create a single value that measures a player's physical heaviness by using a physical density ratio.

  With wPPI+, that PPI ratio is then scaled by 5v5 ice time share: a big player with heavy minutes sees his wPPI+ amplified, while a big player who doesn't play much sees it reduced. The result is a single number that measures how much physical presence a player actually brings to the game. 100 is league average.

- **DPL (Deployment Line)**

  The average line or pair number a player draws from his coach. A forward with a DPL of 1.2 is consistently deployed on the first line. A defenseman with a DPL of 1.8 plays second-pair minutes. This measures deployment, not production.

- **DPS+ (Deployment Score Plus)**

  Measures the quality and quantity of deployment against top opponents. For forwards, it captures how often a coach sends them out against top defensive pairs. For defensemen, it captures how often they face top opposing forwards. 100 is league average. Higher means tougher assignments.

- **Elite Classification**

  Elite status identifies the top forwards and defensemen by 5v5 production and deployment. Forwards clear thresholds on P/60, team ice time share, and multi-situational usage. Defensemen qualify through production, deployment against top forwards, or both.

  Once classified, elite players feed into the competition metrics — every second of 5v5 play is scored against whether the opponents on the ice were elite. That gives every skater in the league a competition quality measure that the box score never could.

- **tTOI% and iTOI%**

  Seperating 5v5 TOI percentages into these two values tells us how much a player skates relative to their team's 5v5 ice time (tTOI%) and how much of a player's individual ice time is at 5v5 vs other situations (iTOI%). For the latter, a lower iTOI% value means the player is called upon in other situations (4v4, 3v3, PP, or SH) so a lower iTOI% is usually better. For tTOI%, a higher value is usually better because it means this player plays a lot at 5v5. But this data reveals that some players, like Matt Boldy or Tim Stützle, can have an average tTOI% and an extremely low iTOI% and still be a top point producer at 5v5

## Deployment

The `v2/browser/` app deploys to Fly.io. See `resources/vps-setup-guide-fly.md`
for the platform-level setup and `docs/plans/2026-05-07-fly-deploy.md` for the
implementation plan.

### Refresh production data

```bash
# 1. Rebuild source DBs locally
python v2/browser/build_league_db.py 2024
python v2/browser/build_league_db.py 2025
python v2/browser/build_edm_db.py

# 2. Sync to runtime_data/
./tools/sync-runtime-data.sh

# 3. Deploy
fly deploy --remote-only
```

### Local dev

`runtime_paths.py` falls back to the legacy `data/<season>/generated/...` layout
when `DATA_DIR` is unset, so `cd v2/browser && python app.py` Just Works without
any env vars.

### First-time setup on a fresh clone

`v2/browser/runtime_data/` is gitignored, so a fresh clone won't have the DB
files baked in. Before the first `fly deploy`, run:

```bash
./tools/sync-runtime-data.sh
```

This copies the four runtime files (`league.db` for 2024 and 2025, `edm.db`,
`player_bursts.csv`) from `data/<season>/generated/...` into `runtime_data/`.
