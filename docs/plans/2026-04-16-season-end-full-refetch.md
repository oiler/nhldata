# 2025-26 Season-End Full Re-Fetch

## Overview

At the end of the 2025-26 NHL regular season, re-fetch and reprocess every
regular-season game from game ID 1. This picks up any post-game stat corrections
the NHL has applied to earlier games since they were originally downloaded, and
gives us a clean, fully-validated dataset going into the playoffs.

## When

- **Regular season ends:** final games played 2026-04-16 (Thursday night).
- **Last incremental orchestrator run:** Friday morning, 2026-04-17.
- **Full re-fetch runs:** Friday 2026-04-17, after the morning orchestrator
  finishes and we've confirmed all regular-season games are in the dataset.

## Motivation

- The NHL occasionally applies post-game stat corrections (assist reassignments,
  situation/strength re-scoring, etc.). Our incremental fetch only pulls each
  game once, so those corrections never make it into our data.
- Known symptom: 1-goal gap in LAK's 5v5 GF (113 vs NHL.com's 114). Deferred in
  `docs/opportunities.md` #1 — a full re-fetch is expected to resolve this and
  any similar drift.
- Clean baseline before playoffs start.

## Scope

- **Included:** all 2025-26 regular-season games, game IDs `2025020001`
  through `2025021312` (1,312 games total — confirm count after Friday morning
  orchestrator run).
- **Not included:** preseason, playoffs (separate game-ID series).
- **Overwrites:** all files in `data/2025/{boxscores,plays,meta,shifts}/` plus
  the regenerated files in `data/2025/generated/` and `league.db`.

## What We Have (Pre-existing Tooling)

- `v1/nhlgame.py START END` — fetches raw files for a game-ID range. Overwrites
  in place. Rate-limited to ~9s/game. No skip logic.
- `v2/orchestrator/runner.py` — Claude-agent orchestrator; accepts free-form
  natural-language prompts.
- `v2/orchestrator/sync_season.py 2025` — regenerates all derived data
  (timelines, competition, flatplays, etc.).
- `v2/browser/build_league_db.py 2025` — drops and rebuilds `league.db` from
  scratch (~2.5 min on 1,312 games).

No new code required.

## Pre-Flight Checklist (Friday Morning)

1. Confirm Friday morning orchestrator run completes cleanly.
2. Confirm `ls data/2025/boxscores | wc -l` shows the full regular-season
   count (expected: 1,312).
3. Confirm `league.db` builds and browser app loads normally.
4. Spot-check a recently-completed game (box score, timeline, skater page).

## Execution Steps

```bash
cd /Users/jrf1039/files/projects/nhl

# 1. Archive existing data (rollback safety net)
tar czf archive_2025_$(date +%Y%m%d).tar.gz data/2025/

# 2. Clear raw data directories so nothing stale lingers
rm -rf data/2025/{boxscores,plays,meta,shifts}
mkdir -p data/2025/{boxscores,plays,meta,shifts}

# 3. Re-fetch + regenerate + rebuild via the orchestrator
python v2/orchestrator/runner.py "Re-fetch all 2025-26 regular season games 1 through 1312, then run sync_season.py for 2025, then rebuild league.db"
```

Expected runtime: ~3.5–4 hours (fetch dominates at ~9s × 1,312 games ≈ 3.25 hrs;
derived-data regen and DB rebuild add ~15–30 min).

## Validation (Post-Run)

1. `ls data/2025/boxscores | wc -l` — should equal the pre-flight count.
2. `python -m pytest v2/ -v` — all 82 tests pass.
3. Spot-check LAK's 5v5 GF vs NHL.com — confirm gap is resolved.
4. Spot-check 3-5 other teams' 5v5 GF vs NHL.com.
5. Load browser app, verify home/games/skaters/teams pages render.
6. Compare a handful of player season totals vs NHL.com.

## Rollback

If anything is wrong:
```bash
rm -rf data/2025/
tar xzf archive_2025_YYYYMMDD.tar.gz
python v2/browser/build_league_db.py 2025
```

## Risks / Gaps

- **NHL API reliability:** shifts API still spotty for 2024-25+; the HTML
  scraping fallback in `nhlgame.py` handles this but is slower per game.
- **No native "full re-fetch" orchestrator mode:** we're relying on the agent
  to interpret the natural-language prompt correctly. Alternative is to call
  `nhlgame.py 1 1312`, `sync_season.py 2025`, and `build_league_db.py 2025`
  directly in sequence — lower risk, same result.
- **Unattended run:** 3.5+ hours. Run overnight or mid-day; check in
  periodically for stalls.
- **Confirm game-ID range:** 1,312 is the standard 32-team × 82-game size, but
  verify against the actual count after Friday morning's incremental run before
  kicking off.

## Open Questions

- Do we also want to archive `generated/` subfolders separately, or is the full
  `data/2025/` tarball enough?
- Do we want a dry-run on a small range (e.g., games 1-5) first to validate the
  orchestrator prompt end-to-end before committing to the full run?
