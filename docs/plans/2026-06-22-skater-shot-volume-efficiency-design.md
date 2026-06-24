# Skater Shot Volume & Efficiency — Design

**Date:** 2026-06-22
**Status:** Approved, ready for implementation plan
**Scope:** `v2/browser/build_league_db.py`, `v2/browser/metrics.py`, `v2/browser/pages/player.py`, tests

## Goal

Add two individual 5v5 stats to the individual player page (`/player/<player_id>`,
`pages/player.py`), each with a league rank:

1. **iSA/60** — individual shot attempts per 60 minutes of 5v5 ice time. Measures how
   much shot volume a skater generates himself (not an on-ice total).
2. **P/100iSA** — 5v5 points (G+A) per 100 individual shot attempts. Measures how
   productive each of his attempts is; a playmaker scores high.

These extend the v2.2.0 player-page stat work. Player page only for now (not the
`/skaters` leaderboard).

## Definitions & decisions

- **Individual shot attempts (iSA) = Corsi, blocked attempts included.** Count of
  `shot-on-goal` + `missed-shot` + `blocked-shot` + `goal` events at
  `situationCode == "1551"` where the player is the shooter. This keeps iSA on the
  same scale as the on-ice `CF/CA` already on the page (which also include blocked).
  Shooter attribution: `details.shootingPlayerId` for shot-on-goal/missed-shot/
  blocked-shot; `details.scoringPlayerId` for goal. (For a blocked shot,
  `shootingPlayerId` is the shooter whose attempt was blocked — correct for iSA.)
- **iSA/60 denominator** = `competition.toi_seconds` (5v5 TOI), full filtered-game
  denominator — same as the other per-60 event rates.
- **P/100iSA** = `Σ(5v5 points) · 100 / Σ ishots`. NaN when `Σ ishots == 0`.
- **Small-sample guard (P/100iSA rank only):** the *value* displays for every player,
  but the *rank* requires **≥ 50 total 5v5 individual shot attempts in the window**.
  Players below the floor display their value with rank `—` (unqualified), and the
  rank denominator is the qualified-pool count. The floor is one named, tunable
  constant. iSA/60 has no such floor — it is a rate over TOI and the existing GP ≥ 5
  pool gate suffices.
- **Labels:** `iSA/60` and `P/100iSA` (unambiguous against the on-ice `CF/60`).

## Non-goals

- No `/skaters` leaderboard columns (player page only for now).
- No new DB table — `events_5v5` already has the right grain and source.
- No change to the 5v5 definition (`situationCode == "1551"`).
- No Fenwick/unblocked variant.

## Context: what already exists

- `events_5v5(gameId, playerId, hits, blocks, takeaways, giveaways)` is built by
  `count_5v5_events` + `build_events_5v5_table` in `build_league_db.py` from
  `data/<season>/generated/flatplays/*.csv`, filtering `situationCode` via
  `FIVE_V_FIVE = {"1551"}`.
- `points_5v5(gameId, playerId, goals, assists, points)` already holds 5v5 points.
- `metrics.py` has `events_per60(events_df, toi_df)` (per-60 over full filtered-game
  TOI) and `corsi_per60(...)`.
- `pages/player.py` renders the season-summary strip; each cell's value comes from
  `_pool_val(col)` and its rank from `_rank(col, ascending=...)`, both reading the
  same `lg` league pool (same position, GP ≥ 5). `_rank` drops NaN before ranking.

## Data model

Add one column to `events_5v5`:

```
events_5v5(gameId, playerId, hits, blocks, takeaways, giveaways, ishots)
```

`ishots` is counted inside the existing `count_5v5_events` per-game loop: for each
5v5 Corsi event type, increment the shooter's `ishots`. No new file, no new pass —
`build_events_5v5_table` already reads every flatplays CSV once.

## Metrics (`metrics.py`)

1. **iSA/60** — extend `events_per60` to also emit `ishots_per60`
   (`= Σ ishots · 3600 / Σ toi_seconds`). Same denominator regime as the other
   event rates (all of the player's filtered-game 5v5 TOI).

2. **P/100iSA** — new helper:
   ```
   points_per100_shots(points_df, ishots_df, min_attempts=50) -> DataFrame
   ```
   - `points_df`: per-(gameId, playerId) with a `points` column (from `points_5v5`).
   - `ishots_df`: per-(gameId, playerId) with an `ishots` column (from `events_5v5`).
   - Returns indexed by `playerId`:
     - `total_ishots` = `Σ ishots`
     - `p_per100` = `Σ points · 100 / total_ishots` (NaN when `total_ishots == 0`)
     - `p_per100_ranked` = `p_per100` where `total_ishots >= min_attempts`, else NaN
   - The page uses `p_per100` for the displayed value and `p_per100_ranked` for the
     rank, so the 50-attempt floor is enforced purely by `_rank`'s existing
     drop-NaN behavior.

## Display (`pages/player.py`)

Two new cells appended to the season-summary strip, mirroring the v2.2.0 pattern
(value from the `lg` pool, rank from the same pool):

- **`iSA/60`** — `_rank("ishots_per60")` descending (more volume → rank 1);
  value via `_pool_val("ishots_per60")`. Pool gate is the existing GP ≥ 5.
- **`P/100iSA`** — value via `_pool_val("p_per100")` (shown for all qualifying-GP
  players); **rank via `_rank("p_per100_ranked")`** so only players with
  `total_ishots >= 50` are ranked. A selected player below the floor shows his value
  with rank `—` (because `_rank` returns None when the player is absent from the
  dropna'd series), and the rank denominator reflects only qualified players.

Both the selected-player value and the `lg` pool columns are computed from the same
sources (extend `lg` with `ishots_per60`, `p_per100`, `p_per100_ranked`), so value
and rank never drift.

The 50-attempt floor lives as a single module constant in `player.py` (passed as
`min_attempts` to `points_per100_shots`).

## Testing (red/green TDD, synthetic DataFrames)

- `count_5v5_events`: `ishots` counts the shooter across all four Corsi event types
  (`shootingPlayerId` for shot-on-goal/missed-shot/blocked-shot, `scoringPlayerId`
  for goal); non-5v5 events excluded; existing hits/blocks/tk/gv assertions unchanged.
- `events_per60`: `ishots_per60` computed over the full TOI denominator.
- `points_per100_shots`: the ratio; `total_ishots == 0` → `p_per100` NaN;
  `p_per100_ranked` is NaN below `min_attempts` and equals `p_per100` at/above it.
- Display wiring (cells/ranks) is regression-green only (no new callback test),
  matching the v2.2.0 approach.
- Full suite green: `python -m pytest v2/ -v`.

## Phasing (each independently shippable)

| Phase | Deliverable | Touches |
|-------|-------------|---------|
| 1 | `ishots` column + `iSA/60` cell with rank | `build_league_db.py` (`count_5v5_events`, table), `metrics.py` (`events_per60`), `player.py`, tests |
| 2 | `P/100iSA` helper + cell with floor-gated rank | `metrics.py` (`points_per100_shots`), `player.py`, tests |

Each phase: build → test → rebuild `league.db` → verify against a known player.

## Open follow-ups (out of scope here)

- Surfacing iSA/60 and P/100iSA as sortable `/skaters` leaderboard columns.
- Revisiting the 50-attempt floor after seeing real distributions.
