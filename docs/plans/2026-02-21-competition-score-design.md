# Competition Score — Per-Game Design

## Goal

For every skater in a game, produce two values that measure the quality of the opposing players they shared the ice with at 5v5:

- **`comp_fwd`** — mean game 5v5 TOI of opposing forwards while the player was on ice
- **`comp_def`** — mean game 5v5 TOI of opposing defensemen while the player was on ice

These are raw per-game values. Season-level aggregation and normalization to a 100-centered scale are deferred to a future phase.

---

## Situation Codes in Scope

Only rows with these `situationCode` values are used. All others are ignored.

| situationCode | Meaning |
|---|---|
| `1551` | 5v5, both goalies in net |
| `0651` | 6v5, away goalie pulled |
| `1560` | 6v5, home goalie pulled |

---

## Inputs

| Input | Source |
|---|---|
| Timeline CSV | `data/{season}/generated/timelines/csv/{gameId}.csv` |
| Position lookup | `data/{season}/generated/players/csv/players.csv` (primary) |
| Position fallback | `rosterSpots` array in `data/{season}/plays/{gameId}.json` |

**Position mapping:** `C`, `L`, `R` → Forward. `D` → Defense. `G` → Goalie (excluded from scoring). Any skater beyond the standard 5 in an extra-attacker situation is treated as a Forward.

---

## Algorithm

### Step 1 — Filter timeline

Load the game's timeline CSV. Keep only rows where `situationCode` is `1551`, `0651`, or `1560`.

### Step 2 — Compute game 5v5 TOI per player

For each row in the filtered timeline, add 1 second to each player ID found in `awaySkaters` and `homeSkaters` (pipe-delimited). Goalies (`awayGoalie`, `homeGoalie`) are counted separately and excluded from competition scoring.

Result: a dict `toi[playerId] = seconds` for every skater in the game.

### Step 3 — Score each second

For each row in the filtered timeline:

For each player ID in `awaySkaters`:
- Opposing skaters = `homeSkaters` (pipe-split)
- Classify each opposing skater as F or D using position lookup
- `comp_fwd_this_second` = mean of `toi[p]` for all opposing Forwards
- `comp_def_this_second` = mean of `toi[p]` for all opposing Defensemen
- Append both values to that player's accumulator lists

Repeat symmetrically for each player in `homeSkaters` (opposing = `awaySkaters`).

### Step 4 — Aggregate per player

For each skater:
- `comp_fwd` = mean of all accumulated `comp_fwd` second-values
- `comp_def` = mean of all accumulated `comp_def` second-values

Values are in **seconds** (same unit as `toi_seconds`). Convert to minutes at display time if needed.

---

## Output

One CSV per game: `data/{season}/generated/competition/{gameId}.csv`

| Column | Type | Description |
|---|---|---|
| `gameId` | str | Full game ID (e.g. `2025020001`) |
| `playerId` | int | NHL player ID |
| `team` | str | Team abbreviation |
| `position` | str | `F` or `D` |
| `toi_seconds` | int | Player's total 5v5 ice time this game (seconds) |
| `comp_fwd` | float | Mean game 5v5 TOI of opposing forwards (seconds) |
| `comp_def` | float | Mean game 5v5 TOI of opposing defensemen (seconds) |

---

## Edge Cases

| Situation | Handling |
|---|---|
| Extra attacker (6th skater) | Treated as a Forward regardless of actual position |
| Player in timeline but not in position lookup | Fall back to `rosterSpots` in the plays JSON; skip with a warning if still not found |
| Player on ice for only a few seconds | Included — no minimum TOI threshold at this stage |
| Goalie pulled mid-shift | The timeline already handles this second-by-second; no special logic needed |

---

## Future Phase (Season Aggregation)

Not in scope now. When added:

1. Weighted average of per-game `comp_fwd` and `comp_def` scores across all games, weighted by `toi_seconds`
2. Normalize to 100-centered scale: `(player_season_avg / league_season_avg) × 100`
3. Separate league averages computed for forwards and defensemen independently
