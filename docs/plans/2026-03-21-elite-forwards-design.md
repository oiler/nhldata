# Elite Forward Classification Model

## Problem

The current competition quality metric (`pct_vs_top_fwd`) uses a per-game top-6-by-TOI classification. This is too broad — it includes middle-six players with high 5v5 minutes but no special teams role or point production. The gap between "top 6" and "bottom 6" by raw 5v5 TOI is small, making the metric noisy.

## Model

Identify a team's truly elite forwards using three signals:

| Signal | Threshold | What it captures |
|--------|-----------|------------------|
| tTOI% | >= 28% | Coach trusts you with heavy 5v5 minutes |
| iTOI% | < 83% | You play special teams (PP proxy), not just a 5v5 specialist |
| P/60 | >= 1.0 | You produce at 5v5, not just a defensive deployment |
| GP | >= 20 | Sufficient sample size |

**Selection rule:** Top 3 by P/60 per team (always). A 4th is allowed if their P/60 >= 1.7.

**Trade carry-over:** If a player was elite on their previous team and gets traded mid-season, the acquiring team gets them as +1 elite forward above the normal cap. No ceiling on total per team.

### Why each signal matters

- **tTOI% >= 28%** filters for players getting heavy deployment. A 28% team share means the coach is giving them more than an equal split (20% = equal among 5 skaters at 5v5).
- **iTOI% < 83%** is the key insight. Elite forwards play PP (and often PK), so their 5v5 time is a smaller fraction of total ice time. Players with iTOI% > 85% are 5v5 specialists — high volume but not truly elite. This single filter separates star players from depth players more reliably than any TOI threshold.
- **P/60 >= 1.0** ensures the player produces at 5v5, not just logs minutes. The 1.7 floor for the 4th slot reserves it for clear stars (Guentzel 2.23, Nelson 2.17, Matthews 1.90).

### 2024-25 Results

88 elite forwards across 32 teams:
- 2 teams with 1 (CAR, STL)
- 6 teams with 2 (BUF, CBJ, CGY, NYI, VGK, WSH)
- 20 teams with 3
- 4 teams with 4 (COL, DAL, TBL, TOR)

Plus 3 trade carry-overs: Panarin (NYR to LAK), Kadri (CGY to COL), Garland (VAN to CBJ).

## Integration

### Where it lives

All computation happens in `build_league_db.py` during database build. No changes to `compute_competition.py` — the per-game CSVs retain the old top-6 values, but the DB gets overwritten with elite-model values.

### New functions

**`build_elite_forwards_table(conn)`**
- Queries competition + points_5v5 for per-(player, team) stats
- Applies thresholds, ranks, and caps
- Detects traded elites and adds carry-over rows
- Writes `elite_forwards` table: playerId, team, gp, toi_min_gp, ttoi_pct, itoi_pct, p60, rank, is_carryover

**`recompute_pct_vs_elite_fwd(conn)`**
- Loads elite player ID set from `elite_forwards`
- Loads per-game position/team lookups from competition table
- Reads all timeline CSVs (~3.99M rows, ~6s)
- For each 5v5 second, for each skater: counts opposing forwards in elite set / total opposing forwards
- UPDATEs competition.pct_vs_top_fwd with new values

### Build order

```
build_competition_table        (loads CSVs with old pct_vs_top_fwd)
build_players_table + recovery
build_games_table
build_points_5v5_table
build_elite_forwards_table     ← NEW (needs competition + points_5v5)
recompute_pct_vs_elite_fwd     ← NEW (needs elite_forwards + timeline CSVs)
build_player_metrics_table     (unchanged)
```

### What doesn't change

- `compute_competition.py` — still runs per-game, CSVs keep old values
- Browser pages — read from DB which now has new values; column name `pct_vs_top_fwd` stays, label "vs Top Fwd %" stays
- `pct_vs_top_def` — unchanged, still per-game top-4 by TOI (defense model is a future task)

## Tests

- `test_build_elite_forwards_table` — synthetic competition + points data, verify correct players selected and cap enforced
- `test_elite_trade_carryover` — player elite on team A, traded to team B, verify appears on both teams
- `test_recompute_pct_vs_elite` — small timeline + competition data, verify correct fraction

## Future work

- Elite defenseman model (two archetypes: PP-playing offensive D vs high-minutes shutdown D)
- Replace `pct_vs_top_def` with the defense model
- Consider renaming browser labels from "vs Top Fwd %" to "vs Elite Fwd %"
