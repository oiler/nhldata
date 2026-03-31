# Elite Defensemen v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-team production/deployment/full-elite defenseman model with a league-wide threshold model using full-season stats only (no blend).

**Architecture:** Unlike the Elite Forwards v2 model, defensemen use full-season stats only — points streaks are not reliable for D. A single GP gate (≥ 20) applies; all three signals are required (no 2-of-3). DPS+ is computed inside `build_elite_defensemen_table` by normalizing raw per-game deployment scores against the league average for all qualifying D. The schema is intentionally simple — no `fs_*`/`l20_*`/`weighted_*` columns.

**Tech Stack:** Python, pandas, SQLite, Plotly Dash

---

## Model Summary

| Signal | Threshold | Role |
|--------|-----------|------|
| GP | ≥ 20 | Minimum sample (required) |
| P/60 | > 1.2 | Production (required) |
| tTOI% | > 35% | Top-pair usage (required) |
| DPS+ | > 120 | Deployment difficulty (required) |

All three metric gates are required. No 2-of-3 logic.

**DPS+ normalization:**
```
avg_deploy_per_game = total deployment_score / gp   (for each D with GP ≥ 20)
league_avg          = mean(avg_deploy_per_game)     (across all qualifying D)
dps_plus            = avg_deploy_per_game / league_avg * 100
```

**New `elite_defensemen` schema:**
```
playerId, team, gp, toi_min_gp, p60, ttoi_pct, dps_plus
```

No `is_production`, `is_deployment`, `is_full_elite`, `rank`, `is_carryover`, or `fs_*`/`l20_*`/`weighted_*` columns.

---

## File Map

| File | Action |
|------|--------|
| `v2/browser/tests/test_player_metrics.py` | Delete `_setup_elite_def_db` + 7 old tests; add `deployment_score` param to `_make_comp_row`; add 3 new tests; update 5 changelog fixtures; repurpose type-change test |
| `v2/browser/build_league_db.py` | Replace `build_elite_defensemen_table`; update `_read_old_elites`, `_log_elite_changes`, `recompute_pct_vs_elite_def`; delete `backfill_vs_elite_def_to_forwards`; update `main()` |
| `v2/browser/pages/elites.py` | Update `_DEF_SQL`; remove `_DPS_SQL`; rewrite `_build_def_table`; simplify `layout()` |

---

## Task 1: Write failing tests

**Files:**
- Modify: `v2/browser/tests/test_player_metrics.py`

- [ ] **Step 1: Update `_make_comp_row` to accept `deployment_score`**

Add `deployment_score=None` parameter and include it in the returned dict:

```python
def _make_comp_row(pid, team, game, position, toi, total_toi, line_number=None, deployment_score=None):
    return {
        "gameId": game, "playerId": pid, "team": team, "position": position,
        "toi_seconds": toi, "total_toi_seconds": total_toi,
        "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
        "comp_fwd": 0, "comp_def": 0,
        "height_in": 72, "weight_lbs": 198,
        "heaviness": 0, "weighted_forward_heaviness": 0,
        "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0,
        "line_number": line_number,
        "deployment_score": deployment_score,
    }
```

- [ ] **Step 2: Remove `backfill_vs_elite_def_to_forwards` from imports**

```python
from build_league_db import (
    build_player_metrics_table, _recover_missing_players,
    build_elite_forwards_table, recompute_pct_vs_elite_fwd,
    build_elite_defensemen_table, recompute_pct_vs_elite_def,
    _read_old_elites, _log_elite_changes,
)
```

- [ ] **Step 3: Delete `_setup_elite_def_db` and 7 old tests**

Delete the following in their entirety:
- `_setup_elite_def_db` (lines ~523–600)
- `test_elite_defensemen_table_created`
- `test_elite_def_production_selected`
- `test_elite_def_deployment_selected`
- `test_elite_def_full_elite`
- `test_elite_def_gap_too_large`
- `test_elite_def_no_production`
- `test_elite_def_itoi_filter`

- [ ] **Step 4: Add helper `_ed_comp_rows`**

```python
def _ed_comp_rows(pid, team, game_ids, toi, total_toi, deploy_score=None):
    """Return one competition row per game for a D player."""
    return [
        _make_comp_row(pid, team, gid, "D", toi, total_toi,
                       deployment_score=deploy_score)
        for gid in game_ids
    ]
```

- [ ] **Step 5: Add `test_ed_gp_gate`**

```python
def test_ed_gp_gate():
    """D with < 20 GP never designated elite regardless of stats.

    Player 1: 15 GP, P/60 = 6.0, tTOI% ≈ 71%, DPS+ would be 100 → excluded by GP gate.
    Player 2: 20 GP, same stats per game → included.

    Setup per game: 4 filler F (500s each) + 4 filler D (450s each)
    team_total = 4*500 + 600 + 4*450 = 4400s
    ttoi_frac = 5.0 * 600 / 4400 = 0.6818  → tTOI% = 68.2% (> 35% ✓)
    P/60 = 1 pt/game * 3600 / 600 = 6.0 (> 1.2 ✓)
    deploy_score = 100 for both → DPS+ = 100 (fails > 120 ✗ — only one player so avg=100)

    To pass DPS+: need two players with different deploy_score so normalization works.
    Give player 2 deploy=200, add a filler D3 (pid=3) with deploy=100 for 20 games.
    league_avg = (200 + 100) / 2 = 150
    Player 2 DPS+ = 200/150*100 = 133 ✓
    Player 3 DPS+ = 100/150*100 = 67 ✗ (only 20 GP, deploy=100 — used for normalization only)

    Player 1 (15 GP) must not appear even though same stats as player 2.
    """
    conn = sqlite3.connect(":memory:")
    game_ids_15 = list(range(1, 16))
    game_ids_20 = list(range(1, 21))

    filler_rows = []
    for gid in game_ids_20:
        for fid in range(1001, 1005):
            filler_rows.append(_make_comp_row(fid, "TMA", gid, "F", 500, 600))
        for did in range(1005, 1009):
            filler_rows.append(_make_comp_row(did, "TMA", gid, "D", 450, 600))

    comp_rows = (
        _ed_comp_rows(1, "TMA", game_ids_15, toi=600, total_toi=800, deploy_score=200)
        + _ed_comp_rows(2, "TMA", game_ids_20, toi=600, total_toi=800, deploy_score=200)
        + _ed_comp_rows(3, "TMA", game_ids_20, toi=600, total_toi=800, deploy_score=100)
    )
    pts_rows = (
        [{"gameId": gid, "playerId": 1, "goals": 1, "assists": 0, "points": 1} for gid in game_ids_15]
        + [{"gameId": gid, "playerId": 2, "goals": 1, "assists": 0, "points": 1} for gid in game_ids_20]
        + [{"gameId": gid, "playerId": 3, "goals": 1, "assists": 0, "points": 1} for gid in game_ids_20]
    )

    pd.DataFrame(filler_rows + comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_defensemen_table(conn)

    pids = {r[0] for r in conn.execute("SELECT playerId FROM elite_defensemen").fetchall()}
    assert 1 not in pids, "Player 1 (15 GP) must not qualify"
    assert 2 in pids, "Player 2 (20 GP, DPS+ 133) must qualify"
```

- [ ] **Step 6: Add `test_ed_all_three_gates_required`**

```python
def test_ed_all_three_gates_required():
    """All three signals required: P/60 > 1.2, tTOI% > 35%, DPS+ > 120.

    4 players, all 20 GP, each missing exactly one gate:
      Player 1: P/60 fails (0.5), tTOI% ✓, DPS+ ✓ → excluded
      Player 2: P/60 ✓ (2.0), tTOI% fails (30%), DPS+ ✓ → excluded
      Player 3: P/60 ✓ (2.0), tTOI% ✓, DPS+ fails (80) → excluded
      Player 4: P/60 ✓ (2.0), tTOI% ✓, DPS+ ✓ → included

    Setup: 4 filler F (500s each) per game.
    team_total for tTOI% calc varies by player toi.

    For tTOI% > 35%: need 5 * toi / team_total > 0.35
    team_total = 4*500 + 300+300+300+300 = 3200 per game (all 4 D at 300s)
      tTOI% = 5*300/3200*100 = 46.9% ✓ for all at same toi

    Players 1,3,4: toi=300s/game → tTOI% = 46.9% ✓
    Player 2 (tTOI% fails): toi=180s/game → team_total = 4*500+180+300+300+300=3080
      tTOI% = 5*180/3080*100 = 29.2% ✗

    iTOI%: total_toi=400s for all → not used in gate

    P/60:
      Player 1 (P/60 fails): 0 pts → 0.0 ✗
      Players 2,3,4: 2 pts/game * 3600 / (300*20) = 7200/6000 = 1.2 ... need > 1.2
      Use 3 pts/game: 3*3600/(300*20) = 10800/6000 = 1.8 ✓

    deploy_score per game:
      Players 1,2,4: deploy=200
      Player 3: deploy=50
      league_avg of qualifying GP≥20 players = (200+200+200+50)/4 = 162.5
      P1 DPS+ = 200/162.5*100 = 123.1 ✓ (but fails P/60)
      P2 DPS+ = 200/162.5*100 = 123.1 ✓ (but fails tTOI%)
      P3 DPS+ = 50/162.5*100  = 30.8 ✗
      P4 DPS+ = 200/162.5*100 = 123.1 ✓
    """
    conn = sqlite3.connect(":memory:")
    game_ids = list(range(1, 21))

    filler_rows = []
    for gid in game_ids:
        for fid in range(1001, 1005):
            filler_rows.append(_make_comp_row(fid, "TMA", gid, "F", 500, 600))

    comp_rows = (
        _ed_comp_rows(1, "TMA", game_ids, toi=300, total_toi=400, deploy_score=200)  # P/60 fails
        + _ed_comp_rows(2, "TMA", game_ids, toi=180, total_toi=400, deploy_score=200)  # tTOI% fails
        + _ed_comp_rows(3, "TMA", game_ids, toi=300, total_toi=400, deploy_score=50)   # DPS+ fails
        + _ed_comp_rows(4, "TMA", game_ids, toi=300, total_toi=400, deploy_score=200)  # all pass
    )
    pts_rows = []
    for gid in game_ids:
        # Player 1: 0 pts (P/60 fails)
        for pid in [2, 3, 4]:
            pts_rows.append({"gameId": gid, "playerId": pid, "goals": 3, "assists": 0, "points": 3})

    pd.DataFrame(filler_rows + comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_defensemen_table(conn)

    pids = {r[0] for r in conn.execute("SELECT playerId FROM elite_defensemen").fetchall()}
    assert 4 in pids,     "Player 4 (all gates pass) must be elite"
    assert 1 not in pids, "Player 1 (P/60 fails) must be excluded"
    assert 2 not in pids, "Player 2 (tTOI% fails) must be excluded"
    assert 3 not in pids, "Player 3 (DPS+ fails) must be excluded"
```

- [ ] **Step 7: Add `test_ed_dps_plus_normalization`**

```python
def test_ed_dps_plus_normalization():
    """DPS+ is normalized to 100 = league average of qualifying D.

    Two players, 20 GP each:
      Player 1: deploy_score=200/game → avg=200
      Player 2: deploy_score=100/game → avg=100
      league_avg = (200+100)/2 = 150
      P1 DPS+ = 200/150*100 = 133.3
      P2 DPS+ = 100/150*100 = 66.7

    Both pass P/60 and tTOI%. Only P1 passes DPS+ > 120.
    """
    conn = sqlite3.connect(":memory:")
    game_ids = list(range(1, 21))

    filler_rows = []
    for gid in game_ids:
        for fid in range(1001, 1005):
            filler_rows.append(_make_comp_row(fid, "TMA", gid, "F", 500, 600))

    comp_rows = (
        _ed_comp_rows(1, "TMA", game_ids, toi=300, total_toi=400, deploy_score=200)
        + _ed_comp_rows(2, "TMA", game_ids, toi=300, total_toi=400, deploy_score=100)
    )
    pts_rows = [
        {"gameId": gid, "playerId": pid, "goals": 2, "assists": 0, "points": 2}
        for gid in game_ids for pid in [1, 2]
    ]

    pd.DataFrame(filler_rows + comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_defensemen_table(conn)

    col_names = [d[0] for d in conn.execute("SELECT * FROM elite_defensemen").description]
    rows = {r[0]: dict(zip(col_names, r))
            for r in conn.execute("SELECT * FROM elite_defensemen").fetchall()}

    assert 1 in rows, "Player 1 (DPS+ 133) must be elite"
    assert 2 not in rows, "Player 2 (DPS+ 67) must not be elite"
    assert abs(rows[1]["dps_plus"] - 133.3) < 0.5
```

- [ ] **Step 8: Update 5 changelog tests to use new defensemen schema**

In all five tests below, replace the old `elite_defensemen` creation:
```python
pd.DataFrame(columns=[
    "playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
    "p60", "vs_ef_pct", "is_production", "is_deployment", "is_full_elite",
    "rank", "is_carryover",
]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
```

With the new v2 schema:
```python
pd.DataFrame(columns=[
    "playerId", "team", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus",
]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
```

Apply to: `test_elite_changelog_addition`, `test_elite_changelog_removal`, `test_elite_changelog_no_changes`, `test_elite_changelog_appends`.

- [ ] **Step 9: Repurpose `test_elite_changelog_def_type_change`**

Replace the test body — v2 defensemen have no type designations:

```python
def test_elite_changelog_def_no_type_changes(tmp_path):
    """No type-change entries for defensemen in v2 (no type designations exist)."""
    csv_path = tmp_path / "elite_changelog.csv"
    old_def = pd.DataFrame([
        {"playerId": 10, "playerName": "Evan Bouchard", "team": "EDM", "type": "Elite"},
    ])
    old_fwd = pd.DataFrame(columns=["playerId", "playerName", "team"])

    conn = sqlite3.connect(":memory:")
    pd.DataFrame(columns=[
        "playerId", "team", "gp", "toi_min_gp",
        "weighted_p60", "weighted_dpl", "weighted_ttoi_pct", "weighted_itoi_pct",
        "fs_p60", "fs_dpl", "fs_ttoi_pct", "fs_itoi_pct",
        "l20_p60", "l20_dpl", "l20_ttoi_pct", "l20_itoi_pct",
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 10, "team": "EDM", "gp": 25, "toi_min_gp": 22.0,
         "p60": 1.6, "ttoi_pct": 40.0, "dps_plus": 130.0},
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")
    pd.DataFrame([
        {"playerId": 10, "firstName": "Evan", "lastName": "Bouchard",
         "currentTeamAbbrev": "EDM", "position": "D", "shootsCatches": "R",
         "heightInInches": 74, "weightInPounds": 197},
    ]).to_sql("players", conn, index=False, if_exists="replace")

    _log_elite_changes(old_fwd, old_def, conn, str(csv_path))
    conn.close()

    assert not csv_path.exists(), "No changelog entry when elite D unchanged"
```

- [ ] **Step 10: Run tests and confirm failures**

```bash
python -m pytest v2/browser/tests/test_player_metrics.py -v -k "ed_gp or ed_all_three or ed_dps" 2>&1 | tail -15
```

Expected: 3 new tests FAIL (function not yet implemented).

---

## Task 2: Implement new `build_elite_defensemen_table`

**Files:**
- Modify: `v2/browser/build_league_db.py:458–613`

- [ ] **Step 1: Replace `build_elite_defensemen_table` entirely**

```python
def build_elite_defensemen_table(conn):
    """Identify elite defensemen using a league-wide threshold model.

    Gate (all required, GP >= 20):
      P/60   > 1.2   — production
      tTOI%  > 35%   — top-pair usage
      DPS+   > 120   — deployment difficulty (100 = league avg)

    Full-season stats only — no last-20 blend (points streaks unreliable for D).

    DPS+ normalization:
      avg_deploy = SUM(deployment_score) / gp   per player
      league_avg = mean(avg_deploy) across all D with GP >= 20
      dps_plus   = avg_deploy / league_avg * 100

    Output columns: playerId, team, gp, toi_min_gp, p60, ttoi_pct, dps_plus
    """
    _COLS = ["playerId", "team", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus"]

    comp = pd.read_sql_query("""
        WITH tt AS (
            SELECT gameId, team, SUM(toi_seconds) AS team_total
            FROM competition WHERE position IN ('F', 'D')
            GROUP BY gameId, team
        )
        SELECT c.playerId, c.team, c.gameId,
               c.toi_seconds,
               COALESCE(c.deployment_score, 0) AS deployment_score,
               5.0 * c.toi_seconds / tt.team_total AS ttoi_frac
        FROM competition c
        JOIN tt ON tt.gameId = c.gameId AND tt.team = c.team
        WHERE c.position = 'D'
    """, conn)

    pts = pd.read_sql_query(
        "SELECT playerId, gameId, SUM(points) AS points FROM points_5v5 GROUP BY playerId, gameId",
        conn,
    )

    def _empty():
        pd.DataFrame(columns=_COLS).to_sql(
            "elite_defensemen", conn, if_exists="replace", index=False
        )

    if comp.empty:
        _empty()
        print("  elite_defensemen: 0 rows (no competition data)")
        return

    gd = comp.merge(pts, on=["playerId", "gameId"], how="left")
    gd["points"] = gd["points"].fillna(0)

    rows = []
    for (pid, team), grp in gd.groupby(["playerId", "team"]):
        gp = grp["gameId"].nunique()
        if gp < 20:
            continue

        total_toi = grp["toi_seconds"].sum()
        total_pts = grp["points"].sum()

        p60      = total_pts * 3600.0 / total_toi if total_toi > 0 else 0.0
        ttoi_pct = grp["ttoi_frac"].mean() * 100
        avg_deploy = grp["deployment_score"].mean()

        rows.append({
            "playerId": pid, "team": team, "gp": gp,
            "toi_min_gp": round(total_toi / gp / 60, 2),
            "p60": p60, "ttoi_pct": ttoi_pct, "avg_deploy": avg_deploy,
        })

    if not rows:
        _empty()
        print("  elite_defensemen: 0 rows (no qualifying defensemen)")
        return

    df = pd.DataFrame(rows)

    # Normalize deployment scores → DPS+ (100 = league average)
    league_avg = df["avg_deploy"].mean()
    if league_avg and league_avg > 0:
        df["dps_plus"] = df["avg_deploy"] / league_avg * 100
    else:
        df["dps_plus"] = 100.0

    # Apply gates (all three required)
    elite = df[
        (df["p60"] > 1.2) &
        (df["ttoi_pct"] > 35.0) &
        (df["dps_plus"] > 120.0)
    ].copy()

    if elite.empty:
        _empty()
        print("  elite_defensemen: 0 rows (no defensemen pass gates)")
        return

    elite[_COLS].to_sql("elite_defensemen", conn, if_exists="replace", index=False)
    print(f"  elite_defensemen: {len(elite)} rows")
```

- [ ] **Step 2: Run the 3 new tests**

```bash
python -m pytest v2/browser/tests/test_player_metrics.py -v -k "ed_gp or ed_all_three or ed_dps" 2>&1 | tail -15
```

Expected: 3 PASS.

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest v2/ -v 2>&1 | tail -5
```

---

## Task 3: Update helper functions

**Files:**
- Modify: `v2/browser/build_league_db.py`

- [ ] **Step 1: Update `_read_old_elites` for new defensemen schema**

The current query unconditionally references `e.is_full_elite` and `e.is_production` which don't exist in the new schema. Add a PRAGMA check:

```python
def_cols = {row[1] for row in old.execute("PRAGMA table_info(elite_defensemen)").fetchall()}
def_carryover = "WHERE e.is_carryover = 0" if "is_carryover" in def_cols else ""
if "is_full_elite" in def_cols:
    type_expr = (
        "CASE WHEN e.is_full_elite = 1 THEN 'Full Elite' "
        "     WHEN e.is_production = 1 THEN 'Production' "
        "     ELSE 'Deployment' END"
    )
else:
    type_expr = "'Elite'"
def_ = pd.read_sql_query(
    f"SELECT e.playerId, "
    f"  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
    f"  e.team, "
    f"  {type_expr} AS type "
    f"FROM elite_defensemen e "
    f"LEFT JOIN players p ON e.playerId = p.playerId "
    f"{def_carryover}",
    old,
)
```

- [ ] **Step 2: Update `_log_elite_changes` defensemen block**

Replace the entire `# --- Defensemen ---` block (lines ~811–845):

```python
    # --- Defensemen ---
    # v2 schema: no is_carryover, no type designation — all rows are "Elite"
    new_def = pd.read_sql_query(
        "SELECT e.playerId, "
        "  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
        "  e.team, 'Elite' AS type "
        "FROM elite_defensemen e "
        "LEFT JOIN players p ON e.playerId = p.playerId",
        conn,
    )

    old_def_keys = set(zip(old_def["playerId"], old_def["team"])) if not old_def.empty else set()
    new_def_keys = set(zip(new_def["playerId"], new_def["team"])) if not new_def.empty else set()
    new_def_lookup = {(r["playerId"], r["team"]): (r["playerName"], r["type"]) for _, r in new_def.iterrows()} if not new_def.empty else {}
    old_def_lookup = {(r["playerId"], r["team"]): (r["playerName"], r["type"]) for _, r in old_def.iterrows()} if not old_def.empty else {}

    for pid, team in new_def_keys - old_def_keys:
        name, dtype = new_def_lookup[(pid, team)]
        changes.append({"date": today, "playerId": pid, "playerName": name,
                         "team": team, "position": "D", "type": dtype, "action": "added"})
    for pid, team in old_def_keys - new_def_keys:
        name, dtype = old_def_lookup[(pid, team)]
        changes.append({"date": today, "playerId": pid, "playerName": name,
                         "team": team, "position": "D", "type": dtype, "action": "removed"})
    # No type-change detection for defensemen in v2 (no type designations)
```

- [ ] **Step 3: Update `recompute_pct_vs_elite_def`**

Change `WHERE is_deployment = 1` to use all elite defensemen:

```python
    elite_rows = conn.execute(
        "SELECT playerId FROM elite_defensemen"
    ).fetchall()
```

- [ ] **Step 4: Delete `backfill_vs_elite_def_to_forwards` and remove from `main()`**

Delete the entire `backfill_vs_elite_def_to_forwards` function. In `main()`, remove the call:
```python
        backfill_vs_elite_def_to_forwards(conn)   # delete this line
```

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest v2/ -v 2>&1 | tail -10
```

Expected: all tests pass.

---

## Task 4: Update `elites.py` browser page

**Files:**
- Modify: `v2/browser/pages/elites.py`

- [ ] **Step 1: Replace `_DEF_SQL` and remove `_DPS_SQL`**

```python
_DEF_SQL = """
SELECT e.playerId, e.team, e.gp, e.toi_min_gp,
       e.p60, e.ttoi_pct, e.dps_plus,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName
FROM elite_defensemen e
LEFT JOIN players p ON e.playerId = p.playerId
ORDER BY e.p60 DESC
"""
```

Delete `_DPS_SQL` entirely (lines ~34–39).

- [ ] **Step 2: Rewrite `_build_def_table` as single-arg**

```python
def _build_def_table(df):
    """Build the defensemen DataTable."""
    df = df.copy()
    df["player_link"] = df.apply(
        lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1,
    )
    df["team_link"] = df["team"].apply(lambda t: f"[{t}](/team/{t})")
    df["dps_plus"] = pd.to_numeric(df["dps_plus"], errors="coerce").round(1)

    columns = [
        {"name": "Player",  "id": "player_link",  "presentation": "markdown", "filter_options": _CI},
        {"name": "Team",    "id": "team_link",     "presentation": "markdown", "filter_options": _CI},
        {"name": "GP",      "id": "gp",            "type": "numeric"},
        {"name": "TOI/GP",  "id": "toi_min_gp",    "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "P/60",    "id": "p60",           "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "tTOI%",   "id": "ttoi_pct",      "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "DPS+",    "id": "dps_plus",      "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = ["player_link", "team_link", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus"]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        markdown_options={"link_target": "_self"},
        sort_action="native",
        filter_action="native",
        css=[{"selector": ".dash-filter--case", "rule": "display: none"}],
        page_action="none",
        style_table={"overflowX": "auto"},
        style_header=_TABLE_STYLE_HEADER,
        style_cell=_TABLE_STYLE_CELL,
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    )
```

- [ ] **Step 3: Simplify `layout()`**

Remove the DPS+ computation block entirely; call `_build_def_table` with a single arg:

```python
def layout(season=None):
    season = season or "2025"
    children = []

    # --- Forwards ---
    fwd_df = league_query(_FWD_SQL, season=season)
    children.append(html.H2("Elite Forwards"))
    if fwd_df.empty:
        children.append(html.P("No elite forwards data available."))
    else:
        children.append(_build_fwd_table(fwd_df))

    # --- Defensemen ---
    children.append(html.H2("Elite Defensemen", style={"marginTop": "2rem"}))
    try:
        def_df = league_query(_DEF_SQL, season=season)
    except Exception:
        def_df = pd.DataFrame()
    if def_df.empty:
        children.append(html.P("No elite defensemen data available."))
    else:
        children.append(_build_def_table(def_df))

    return html.Div(children)
```

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest v2/ -v 2>&1 | tail -5
```

Expected: all tests pass.

---

## Self-Review

### Spec Coverage

| Requirement | Task |
|-------------|------|
| League-wide, no per-team cap | Task 2 |
| GP ≥ 20 gate | Task 2 |
| P/60 > 1.2 required | Task 2 |
| tTOI% > 35% required | Task 2 |
| DPS+ > 120 required | Task 2 |
| DPS+ normalized inside build function | Task 2 |
| Full-season only, no blend | Task 2 |
| Simple schema: p60, ttoi_pct, dps_plus | Task 2 |
| `_read_old_elites` handles new schema | Task 3 |
| `_log_elite_changes` removes is_carryover + type logic | Task 3 |
| `recompute_pct_vs_elite_def` uses all elite D | Task 3 |
| `backfill_vs_elite_def_to_forwards` removed | Task 3 |
| Browser page updated | Task 4 |
| Tests: GP gate, all-3-required, DPS+ normalization | Task 1 |
| Changelog tests updated | Task 1 |

### Type Consistency

- `dps_plus` — single float column, normalized (100 = league avg), stored directly in schema
- `avg_deploy` — intermediate raw float, NOT stored in final schema (only `dps_plus` written to DB)
- `_build_def_table` takes single `df` arg — no `dps_df` param
- `layout()` calls `_build_def_table(def_df)` — single arg, no DPS+ computation block

### No Placeholders

All code blocks are complete and runnable.
