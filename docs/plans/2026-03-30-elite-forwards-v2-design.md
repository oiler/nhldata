# Elite Forwards v2 Design

**Goal:** Replace the per-team ranked elite forward model with a league-wide threshold model that identifies the top ~5% of forwards by requiring high 5v5 production plus deployment qualification across multiple signals.

**Architecture:** Rewrite `build_elite_forwards_table(conn)` in `build_league_db.py`. All changes are confined to that function plus minor updates to the elites browser page. Downstream consumer `recompute_pct_vs_elite_fwd(conn)` requires no changes.

**Tech Stack:** Python, sqlite3, pandas

---

## Model

### Production Gate (required)

| Metric | Threshold |
|--------|-----------|
| Weighted P/60 | ≥ 2.3 |

P/60 is the primary qualifier. A player must clear this floor before deployment is evaluated.

### Deployment Qualification (2 of 3 required)

| Signal | Threshold | What it measures |
|--------|-----------|-----------------|
| DPL | ≤ 2.5 | Average line assignment — top-two-line deployment |
| tTOI% | ≥ 28% | Share of team's 5v5 ice time — heavy usage |
| iTOI% | < 83% | Fraction of total TOI at 5v5 — plays special teams |

A player qualifies on deployment by meeting any 2 of the 3 signals. This allows different deployment profiles:
- A PP specialist (lower tTOI%) can qualify via DPL + iTOI%
- A player on a deep team (diluted tTOI%) can qualify via DPL + iTOI%
- A high-usage player with elevated iTOI% can qualify via DPL + tTOI%

### Three-Phase Logic (based on GP with current team)

| Phase | GP | Behaviour |
|-------|----|-----------|
| 1 | < 10 | No designation — insufficient sample |
| 2 | 10–19 | Full-season values only, all thresholds applied as-is |
| 3 | ≥ 20 | 80/20 blend applied to all four metrics |

### Blending Formula (Phase 3)

```
weighted_metric = full_season_metric * 0.8 + last_20_games_metric * 0.2
```

Applied identically to P/60, DPL, tTOI%, and iTOI%. "Last 20 games" means the player's last 20 games played — player-specific, not team-specific. Injured players' last 20 naturally reflect pre-injury form.

### Expected Output

~24 elite forwards league-wide (~5% of qualifying forwards). Count floats with actual quality — no floor, no ceiling.

### Future Extension

Once the elite defensemen model is rebuilt (producing reliable DPS+ values), a fourth deployment signal — `pct_any_elite_def` (fraction of 5v5 time against elite defensemen) — can be added, making this a 2-of-4 model. This will further distinguish truly challenged forwards from sheltered high producers.

---

## What is Removed vs v1

- Per-team cap (3–4 elites per team)
- Trade carry-over logic and `is_carryover` column
- `rank` column
- Single iTOI% gate replaced by 2-of-3 deployment model
- Minimum GP of 20 (lowered to 10 for phase 2)

---

## Output Table Schema

`elite_forwards` table columns:

| Column | Type | Description |
|--------|------|-------------|
| `playerId` | int | Player identifier |
| `team` | text | Team abbreviation |
| `gp` | int | Games played with this team |
| `toi_min_gp` | float | Average 5v5 TOI per game (minutes) |
| `fs_p60` | float | Full-season P/60 |
| `l20_p60` | float | Last-20-games P/60 (NULL if GP < 20) |
| `weighted_p60` | float | Blended P/60 used for threshold |
| `fs_dpl` | float | Full-season avg line assignment |
| `l20_dpl` | float | Last-20-games avg line assignment (NULL if GP < 20) |
| `weighted_dpl` | float | Blended DPL used for threshold |
| `fs_ttoi_pct` | float | Full-season tTOI% |
| `l20_ttoi_pct` | float | Last-20-games tTOI% (NULL if GP < 20) |
| `weighted_ttoi_pct` | float | Blended tTOI% used for threshold |
| `fs_itoi_pct` | float | Full-season iTOI% |
| `l20_itoi_pct` | float | Last-20-games iTOI% (NULL if GP < 20) |
| `weighted_itoi_pct` | float | Blended iTOI% used for threshold |

Storing both full-season and weighted values enables the elites browser page to show the split, and future analysis of form drift.

---

## Implementation Notes

### Computing tTOI%

Per game: `toi_seconds * 5.0 / team_total_5v5_toi`. Team total computed as `SUM(toi_seconds)` for all F and D on the same team in the same game. Average across games to get per-player tTOI%.

### Computing last-20-games stats

Use Python/pandas. Sort each player's games by `gameDate`, take the last 20 `gameId` values, aggregate separately. Keeps logic readable and testable.

### Downstream changes

- `recompute_pct_vs_elite_fwd(conn)`: reads `SELECT playerId FROM elite_forwards` — no change needed
- `elites.py` browser page: update `_FWD_SQL` and `_build_fwd_table` to display new columns (`weighted_p60`, `weighted_dpl`, `weighted_ttoi_pct`, `weighted_itoi_pct`) and remove old ones (`vs_ed_pct`, `rank`, `is_carryover`). Show full-season vs weighted split where useful.

---

## Tests

All tests in `v2/browser/tests/test_player_metrics.py` using synthetic DataFrames.

### Test 1: Phase gate — GP < 10 produces no elite rows

Player with 8 GP and stats that would qualify under all thresholds. Assert `elite_forwards` table is empty.

### Test 2: Phase 2 — full-season values, no blend (GP 10–19)

Player with 15 GP whose full-season P/60 ≥ 2.3 and passes 2-of-3 deployment. Assert player appears in `elite_forwards`. Verify `l20_*` columns are NULL.

### Test 3: Phase 3 — 80/20 blend applied to all metrics

Player with 30 GP. Set full-season P/60 = 2.8, last-20 P/60 = 1.8. Assert `weighted_p60 = 2.8 * 0.8 + 1.8 * 0.2 = 2.6`. Verify same math applied to DPL, tTOI%, iTOI%.

### Test 4: 2-of-3 deployment logic

Four players all with weighted P/60 ≥ 2.3, GP ≥ 20:
- Passes DPL + tTOI% (fails iTOI%) → in
- Passes DPL + iTOI% (fails tTOI%) → in
- Passes tTOI% + iTOI% (fails DPL) → in
- Fails all three deployment signals → out
- Passes only 1 deployment signal → out
