# Player Page Stat Expansion — Design

**Date:** 2026-06-18
**Status:** Approved, ready for implementation plan
**Scope:** `v2/browser/pages/player.py`, `v2/browser/build_league_db.py`, shared metric helpers, tests

## Goal

Expand the individual player page (`/player/<player_id>`, `pages/player.py`) so its
season-summary strip carries the stats already on the `/skaters` leaderboard plus new
5v5 per-60 rate stats. Everything is league-wide, 5v5 only, and (where it is a count)
normalized per 60 minutes of 5v5 ice time. Every new stat shows a league rank
(`X / pool`) like the existing summary cells.

This is **not** about the `/skaters` leaderboard table — that page already has the
carry-over stats. "Individual skaters page" means the per-player detail page.

### Stats being added

| Group | Stats | Per-60? |
|-------|-------|---------|
| Carry-over (already on leaderboard) | `SB/a60`, `Max MPH`, `DPL`, `DPS+` | already rates/maxes — shown as-is |
| Individual events | `Hits/60`, `Blocks/60`, `TK/60`, `GV/60` | yes, ÷ 5v5 TOI |
| On-ice possession | `CF/60`, `CA/60`, `CF%` | yes (CF%, derived) |

## Non-goals

- No changes to the situation-code model; 5v5 stays strict `situationCode == "1551"`.
- No special teams (PP/PK), no faceoffs, no xG.
- **Fixing missing-timeline data is out of scope** — that root cause is a separate
  effort. This work only handles missing timelines *gracefully* and picks them up
  automatically on the next rebuild once they exist.
- No visual/layout polish beyond letting the new cells wrap in the existing
  flex-wrap strip. Visual grouping is explicit follow-up work.

## Context: what already exists

- `pages/player.py` renders a **Season Summary** flex-wrap strip of stat cells
  (GP, Record, G, A, P, P/60, 5v5 TOI/GP, tTOI%, iTOI%, PPI, PPI+, wPPI, wPPI+),
  each with a league rank, plus a **Game Log** table. The page already builds a
  league pool `lg` (grouped by `playerId`, same position, GP ≥ 5) to compute ranks.
- `build_league_db.py` builds `league.db` tables, full-replace each run
  (`if_exists="replace"`). Two existing builders are direct templates:
  - `build_points_5v5_table` reads `data/<season>/generated/flatplays/*.csv`,
    filters `situationCode`, writes per-game player counts.
  - `recompute_pct_vs_elite_fwd` reads `data/<season>/generated/timelines/csv/<gameId>.csv`,
    parsing per-second on-ice skater lists.
- `flatplays` CSVs already carry every attribution field needed:
  `details.hittingPlayerId`, `details.blockingPlayerId`, `details.shootingPlayerId`,
  `details.playerId`, `details.scoringPlayerId`, `details.eventOwnerTeamId`,
  plus `situationCode` and `typeDescKey`.
- `competition.toi_seconds` is 5v5 TOI per `(gameId, playerId)` — the denominator
  the page already uses for `P/60`.
- Carry-over sources: `SB/a60` + `Max MPH` from `generated/edge/player_bursts.csv`
  (`bursts_per_60`, `speed_max_mph`); `DPL` from mean `competition.line_number`;
  `DPS+` from deployment metrics (`fwd_deployment_rate` for F, `deployment_rate` for D),
  exactly as `pages/skaters.py` derives them.

## Data model — two new per-game tables in `league.db`

Both keyed per `(gameId, playerId)` so the page's date-range and home/away filters
work unchanged. Both built full-replace each rebuild.

### `events_5v5`

```
gameId, playerId, hits, blocks, takeaways, giveaways
```

Counts of events where `situationCode == "1551"`, credited as:

| Column | Attribution field | Meaning |
|--------|-------------------|---------|
| `hits` | `details.hittingPlayerId` | hits thrown by the player |
| `blocks` | `details.blockingPlayerId` | shots blocked by the player (defensive — player without the puck) |
| `takeaways` | `details.playerId` (on `takeaway`) | takeaways |
| `giveaways` | `details.playerId` (on `giveaway`) | giveaways |

Template: `build_points_5v5_table`. Reads flatplays only.

### `onice_5v5`

```
gameId, playerId, cf, ca
```

On-ice 5v5 Corsi. A Corsi attempt is any `shot-on-goal`, `missed-shot`,
`blocked-shot`, or `goal` with `situationCode == "1551"`.

For each such event:
1. Map `period` + `timeInPeriod` → `secondsElapsedGame` using the **same convention
   the timeline builder uses**, so events and timeline rows align exactly.
2. Look up the timeline row for that second → the home and away on-ice skater lists.
3. **Determine the shooter's side by which list contains `shootingPlayerId`**
   (`scoringPlayerId` for goals). The shooter's 5 skaters each get `+1 cf`; the
   opposing 5 each get `+1 ca`.

Template: `recompute_pct_vs_elite_fwd`. Reads flatplays (for Corsi events) + timelines
(for on-ice lists).

## Computation semantics (decisions)

1. **Per-60 denominator = `competition.toi_seconds`** (5v5 TOI), same as `P/60`.
   `Hits/60 = Σ hits · 3600 / Σ(5v5 TOI)` over the filtered games. Same for
   `Blocks/60`, `TK/60`, `GV/60`.

2. **Blocked-shot has two independent roles, no conflict:**
   - In `events_5v5.blocks` it is credited to the blocker (`blockingPlayerId`) — a
     defensive stat, "shots this player blocked."
   - In `onice_5v5` the *same* event is a shot attempt by the shooting team: the
     blocker's side gets `+1 ca`, the shooter's side `+1 cf`. A shot-blocking
     defenseman correctly shows high `Blocks/60` and tends toward higher `CA/60`.

3. **Corsi side comes from the timeline shooter lookup, not `eventOwnerTeamId`.**
   `eventOwnerTeamId` on a `blocked-shot` is the *blocking* (defending) team, which
   would invert CF/CA. Using the shooter's on-ice side handles all four event types
   uniformly (every Corsi event carries a shooter ID).

4. **Missing timelines — graceful and self-healing:**
   - Build skips any game with no timeline file and logs a count
     (`onice_5v5: N games skipped, no timeline`). No crash.
   - Because the table is full-replace each rebuild, a game flows in automatically
     once its timeline exists and the DB is rebuilt — no cache to bust.
   - **CF/60 denominator is the TOI of games that have `onice_5v5` rows**, achieved
     by joining `onice_5v5 → competition` on `(gameId, playerId)`. Numerator and
     denominator move together as coverage fills in. A player's `CF/60` may cover
     fewer GP than his `Hits/60` until timelines are complete — a minor,
     self-correcting inconsistency.

5. **`CF%` = `Σ cf / (Σ cf + Σ ca)`**, derived at display time, not stored.

## Display (`pages/player.py`)

- New stat cells join the **existing** Season Summary flex-wrap strip; they wrap
  onto new rows as the strip fills. No new layout container in this work.
- Order appended after the current cells:
  `SB/a60 · Max MPH · DPL · DPS+ · Hits/60 · Blocks/60 · TK/60 · GV/60 · CF/60 · CA/60 · CF%`.
- Each cell shows a league rank `X / pool` from the page's existing `lg` pool
  (same position, GP ≥ 5).
- Both the **selected-player value** and the **`lg` pool columns** are computed from
  the same sources so a stat's value and its rank never drift.

## Shared logic

Per CLAUDE.md ("shared logic lives in `metrics.py`; never duplicate metric logic"),
the per-60 aggregation (events and Corsi → per-60, plus CF%) goes in a **shared
helper** consumed by `player.py`, so the `/skaters` leaderboard can reuse it later
without duplication. Exact module (extend `metrics.py` vs. a new sibling) is an
implementation-plan decision; the rule is: one place, no copy-paste.

## Testing (red/green TDD, synthetic DataFrames — no real data files)

Following the established pattern in `test_player_metrics.py` /
`test_deployment_metrics.py`:

- **`events_5v5` builder:** synthetic flatplays → correct per-game counts; non-5v5
  events excluded; each event type credited to the right attribution field.
- **`onice_5v5` builder:** synthetic flatplays Corsi events + synthetic timeline →
  correct `cf`/`ca`; shooter-side logic; `blocked-shot` lands as `ca` for the
  blocker's side; missing-timeline game skipped without error.
- **per-60 helper:** rates from counts + TOI; `CF%` derivation; Corsi denominator
  restricted to games present in `onice_5v5`.
- Full suite green: `python -m pytest v2/ -v`.

## Phasing (each phase independently shippable)

| Phase | Deliverable | New table | Risk |
|-------|-------------|-----------|------|
| 1 | Carry-over `SB/a60`, `Max MPH`, `DPL`, `DPS+` on player page + ranks | none | low |
| 2 | `events_5v5` builder + `Hits/60`, `Blocks/60`, `TK/60`, `GV/60` + ranks + tests | `events_5v5` | medium |
| 3 | `onice_5v5` builder + `CF/60`, `CA/60`, `CF%` + ranks + graceful skip + tests | `onice_5v5` | medium |

Each phase: build → test → verify against a known game before moving on.

## Open follow-ups (out of scope here)

- Root-cause fix for missing timeline data.
- Visual grouping/sectioning of the (now larger) summary strip.
- Optionally surfacing the new event/Corsi columns on the `/skaters` leaderboard.
