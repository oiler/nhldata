# Skater Leaderboard — Shot Volume & Efficiency Columns — Design

**Date:** 2026-06-22
**Status:** Approved, ready for implementation plan
**Scope:** `v2/browser/pages/skaters.py`, `v2/browser/app.py` (glossary)

## Goal

Add the two new individual 5v5 stats to the `/skaters` leaderboard table, and remove
the `PPI` column from that table to make room:

1. **iSA/60** — individual shot attempts (Corsi, blocked included) per 60 of 5v5 TOI.
2. **P/100iSA** — 5v5 points per 100 individual shot attempts.

These already exist on the player page (`/player/<id>`). This surfaces them as
sortable leaderboard columns. No new data, tables, or helpers.

## Decisions

- **Reuse existing helpers** — `events_per60` (for `ishots_per60`) and
  `points_per100_shots` (for `p_per100_ranked`), both in `metrics.py`. No new logic.
- **P/100iSA respects the 50-attempt floor on the table:** the leaderboard displays
  the `p_per100_ranked` column (NaN below `min_attempts=50`), so sub-floor players
  render **blank** and do not pollute the native sort. On a sortable table, sorting
  the column *is* the ranking, so the floor must apply to the displayed value here
  (unlike the player page, where the floor gated only the rank and the value still
  showed). User-confirmed.
- **iSA/60 has no floor** — a rate over TOI, shown for all, like the existing `P/60`.
- **Placement:** both columns immediately after `P/60`, forming a
  scoring → shot-volume → efficiency cluster: `… P, P/60, iSA/60, P/100iSA, 5v5 TOI/GP …`.
- **Remove the `PPI` column from the skaters table only** (keep `PPI+` and `wPPI+`).
- **Keep the PPI glossary entry.** The glossary (`app.py`) is a global footer shown on
  every page, and PPI is still displayed on the player page; removing its definition
  would orphan a visible stat and break the `PPI+` definition that references it.
- **Add glossary entries** for `iSA/60` and `P/100iSA`.
- **Labels** match the player page exactly: `iSA/60`, `P/100iSA`.

## Non-goals

- No change to the player page (it already has both stats).
- No new DB tables or columns (`events_5v5.ishots` already exists).
- No change to the 50-attempt floor value or to `points_per100_shots` / `events_per60`.
- No removal of PPI anywhere except the skaters table column.

## Context: what already exists

- `pages/skaters.py` builds a sortable/filterable `dash_table.DataTable`. It queries
  `competition` (`comp_df`), `player_metrics` (`ppi_df`), and `points_5v5` (`pts_df`),
  aggregates per player into `grouped`, then defines `columns` and `display_cols`.
  It restricts points to the filtered games via a `valid_games` inner-merge on
  `(playerId, gameId)`.
- `comp_df` carries per-(gameId, playerId) `toi_seconds` (5v5 TOI) — the per-60
  denominator.
- `events_5v5(gameId, playerId, hits, blocks, takeaways, giveaways, ishots)` exists.
- `metrics.events_per60(events_df, toi_df)` returns `ishots_per60` (among others).
- `metrics.points_per100_shots(points_df, ishots_df, min_attempts=50)` returns
  `total_ishots`, `p_per100`, `p_per100_ranked`.
- The glossary is global `html.Dt`/`html.Dd` pairs in `app.py` (~lines 122-164);
  `PPI` is defined there and referenced by the `PPI+` definition.

## Data flow (`pages/skaters.py`)

1. Add a module SQL constant: `SELECT gameId, playerId, hits, blocks, takeaways, giveaways, ishots FROM events_5v5`.
2. In the callback, query it and restrict to the filtered games — inner-merge on the
   same `(playerId, gameId)` set already derived for points (`valid_games`).
3. Build a per-(gameId, playerId) TOI frame from `comp_df` (`gameId, playerId, toi_seconds`).
4. `events_per60(restricted_events, toi_frame)` → join `ishots_per60` into `grouped`.
5. `points_per100_shots(restricted_points, restricted_events, min_attempts=50)` →
   join `p_per100_ranked` into `grouped` (the displayed efficiency column).
   - `restricted_points` = the same points rows already restricted to filtered games.
   - `restricted_events` = the events rows restricted to filtered games (has `ishots`).

## Display (`pages/skaters.py`)

- Remove the `{"name": "PPI", "id": "ppi", ...}` column dict and `"ppi"` from
  `display_cols`. Leave `PPI+` and `wPPI+` untouched.
- Add two column dicts (both `type: "numeric"` for native sort):
  - `{"name": "iSA/60", "id": "ishots_per60", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)}`
  - `{"name": "P/100iSA", "id": "p_per100_ranked", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)}`
- Insert both `id`s into `display_cols` immediately after `p_per_60`.
- Ensure the two new numeric columns are coerced to numeric in the existing rounding
  loop (or join already yields floats); NaN renders blank in the DataTable, which is
  the intended sub-floor / no-data display for `p_per100_ranked` and any player with
  zero 5v5 TOI for `ishots_per60`.

## Glossary (`app.py`)

- Add `html.Dt("iSA/60")` + `html.Dd(...)` — "Individual shot attempts (shots on goal,
  missed, and blocked attempts the player took, plus goals) per 60 minutes of 5v5 ice
  time. Measures how much shot volume a skater generates himself."
- Add `html.Dt("P/100iSA")` + `html.Dd(...)` — "5v5 points (goals + assists) per 100
  individual shot attempts. Measures how productive each attempt is; playmakers score
  high. On the leaderboard, shown only for skaters with at least 50 attempts in the
  window so small samples don't distort the sort."
- Keep the existing `PPI` entry.

## Testing

- No new pure logic — both stats are wiring over already-tested helpers
  (`events_per60`, `points_per100_shots` have unit tests in `test_rate_metrics.py`).
- Bar: full suite green (`python -m pytest v2/ -v`) + a callback smoke confirming the
  skaters table renders `iSA/60` and `P/100iSA`, that `PPI` is gone, and that a
  sub-50-attempt skater shows blank `P/100iSA` while a high-volume skater shows a value.
- This matches how the player-page display wiring was verified (regression-green +
  callback smoke, no new callback unit test).

## Phasing

Single phase, one task: query + restrict events, join the two metrics, swap the
columns (remove PPI, add iSA/60 + P/100iSA after P/60), update the glossary, smoke-test.

## Open follow-ups (out of scope)

- Revisiting the 50-attempt floor after seeing real distributions (shared constant).
- Any min-GP/min-attempts user-facing filter control on the leaderboard.
