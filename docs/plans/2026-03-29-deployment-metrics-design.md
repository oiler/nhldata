# Deployment Metrics Design
**Date:** 2026-03-29
**Status:** Approved

## Overview

Introduces a deployment-based competition measurement for forwards and defensemen. This is the first of two phases — deployment now, production elite later. The core idea: for each game, identify which forward line (1–4) each player skated on using actual 5v5 ice time, then use those line numbers to measure how hard each defenseman's deployment was.

This is a pure 5v5 measurement. Line numbers are assigned per-game based on that game's actual usage, not season-long status.

## Data Model

Two new columns added to the `competition` table. No existing columns removed. No changes to `player_metrics`.

| Column | Type | Who | Description |
|--------|------|-----|-------------|
| `line_number` | INTEGER | Forwards only | Which line (1–4) this forward played most on in this game. NULL for defensemen. |
| `deployment_score` | INTEGER | D only | Raw difficulty points for the game: `Σ (12 − (lineA + lineB + lineC))` per 5v5 second. NULL for forwards. |

`deployment_rate` is **not stored** — it is computed dynamically in the browser so it respects date filters.

## Forward Line Detection Algorithm

For each game, run once per team:

1. Enumerate all unique 3-man forward combinations with their total 5v5 seconds from the timeline CSV.
2. **Greedy assignment:**
   - Sort combinations descending by seconds
   - Take the top combination → line 1, mark those 3 players as assigned
   - Take the next combination with no already-assigned players → line 2
   - Repeat for lines 3 and 4
3. Any forward who played in the game but is not assigned by the greedy pass → line 4 (handles 11-forward games and injured/benched players)
4. If a player's position is unknown (not yet in the players table), treat as forward for line detection purposes.

**Validated against full 2025-26 season data:** With proper forward filtering, zero instances of a forward appearing in two different top-4 combinations across 1,153 games. The greedy algorithm resolves the rare 11-forward edge cases cleanly.

## Defenseman Deployment Score

For each 5v5 second a defenseman is on the ice:

```
points_this_second = 12 − (line_number_fwdA + line_number_fwdB + line_number_fwdC)
```

| Opposing line | Line sum | Points |
|---------------|----------|--------|
| Pure line 1 (1+1+1) | 3 | 9 |
| Mixed line 1+2 (1+1+2) | 4 | 8 |
| Mixed line 1+2 (1+2+2) | 5 | 7 |
| Pure line 2 (2+2+2) | 6 | 6 |
| Mixed line 2+3 (2+2+3) | 7 | 5 |
| Pure line 3 (3+3+3) | 9 | 3 |
| Pure line 4 (4+4+4) | 12 | 0 |

```
deployment_score = Σ points_this_second  (all 5v5 seconds in the game)
```

TOI is fully embedded in this count — more seconds on ice accumulates more points. A D who plays 20 min against pure line 1 earns twice the score of one who plays 10 min against pure line 1.

## `compute_competition` Changes

The existing step reads each game's timeline CSV and outputs a per-player competition CSV. Extended with:

**One disk read per game, two in-memory loops:**
1. Read full timeline CSV into memory once
2. **Loop 1** — forward line detection: enumerate 3-man forward combos with second counts, run greedy assignment for both teams
3. **Loop 2** — scoring: for each 5v5 second with 5 skaters per side:
   - Each forward: record their `line_number` for this game
   - Each D: accumulate `deployment_score += (12 − opp_line_sum)`
4. Write `line_number` and `deployment_score` as new columns in the per-game competition CSV

## `build_league_db.py` Changes

When building the `competition` table from CSVs, add the two new columns to the schema:

```sql
line_number      INTEGER,   -- NULL for D
deployment_score INTEGER    -- NULL for forwards
```

No changes to `player_metrics` table. No changes to elite tables.

## Browser Changes

### `filters.py` — `compute_deployment_metrics()`

Add `deployment_rate` computation alongside the existing wPPI/toi_share logic:

```python
# For each D in the filtered competition rows:
avg_deployment_score = sum(deployment_score) / games_played

# League average across all D in the same filtered window:
league_avg = mean(avg_deployment_score for all D)

# Normalized rate:
deployment_rate = (avg_deployment_score / league_avg) * 100
```

Forwards receive `deployment_rate = None` (their `deployment_score` is NULL).

The normalization is always relative to the current filter window — if the user filters to Jan 1 onward, the 100-baseline reflects that period only.

### `pages/team.py` and `pages/skaters.py`

Add `deployment_rate` as a new column in the D section of each page. Display format: `Format(precision=1, scheme=Scheme.fixed)` (same as wPPI+). Column label: **"D-Rate"**.

Existing `vs Elite Fwd %` and `vs Elite Def %` columns remain. They will be reconciled when the production elite work is done.

### `pages/game.py`

Add `deployment_score` as a new column in the D table on single-game pages. Display as a raw integer. Column label: **"Dep Score"**. Add `line_number` to the forward table. Column label: **"Line"**.

## Testing

Following the pattern in `test_deployment_metrics.py` and `test_player_metrics.py` — synthetic DataFrames, no real data dependencies.

New tests:
1. **`test_greedy_line_detection_standard`** — 12 forwards, verifies top 4 combos are assigned lines 1–4 with no overlaps
2. **`test_greedy_line_detection_11_forwards`** — 11 forwards, verifies the 2 remaining players are assigned line 4
3. **`test_deployment_score_pure_line1`** — D facing pure line 1 all game, verifies score = TOI × 9
4. **`test_deployment_score_mixed`** — D facing mixed lines, verifies correct accumulation
5. **`test_deployment_rate_normalization`** — two D with different scores, verifies one scores >100 and one <100 and league avg = 100
6. **`test_deployment_rate_forwards_null`** — forwards receive None for deployment_rate

## Out of Scope

- **Production elite metrics** — the existing `pct_any_elite_fwd`, `pct_any_elite_def`, `elite_forwards`, and `elite_defensemen` tables are unchanged. Reconciling the elite system with the new deployment data is a separate phase.
- **Rolling averages** — deferred. Season-to-date (or filtered window) is the initial implementation.
- **Forward season-level deployment** — `line_number` is stored per game. How to express a forward's season deployment (e.g., "% of games on line 1") is deferred until we have the per-game data to work with.
