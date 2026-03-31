# Elite Forwards v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the per-team ranked elite forward model with a league-wide threshold model (~5% of forwards) using 2-of-3 deployment qualification and 80/20 blending.

**Architecture:** Rewrite `build_elite_forwards_table(conn)` in `v2/browser/build_league_db.py` (lines 214–304), update helper functions to remove carry-over schema references, and update the elites browser page to display new columns.

**Tech Stack:** Python, sqlite3, pandas

---

## Files Modified

| File | Change |
|------|--------|
| `v2/browser/tests/test_player_metrics.py` | Update `_make_comp_row`, delete 6 old elite_forwards tests, add 4 new tests, update changelog test fixtures |
| `v2/browser/build_league_db.py` | Rewrite `build_elite_forwards_table`, update `_log_elite_changes` and `_read_old_elites` |
| `v2/browser/pages/elites.py` | Update `_FWD_SQL`, remove `_collapse_traded`, rewrite `_build_fwd_table` |

---

## Task 1: Update test helpers and write failing tests

**Files:**
- Modify: `v2/browser/tests/test_player_metrics.py`

### Step 1: Update `_make_comp_row` to include `line_number`

The helper at line 245 is missing `line_number`. Add it as a keyword arg with default `None`:

```python
def _make_comp_row(pid, team, game, position, toi, total_toi, line_number=None):
    """Build a full competition row with zeros for non-essential columns."""
    return {
        "gameId": game, "playerId": pid, "team": team, "position": position,
        "toi_seconds": toi, "total_toi_seconds": total_toi,
        "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
        "comp_fwd": 0, "comp_def": 0,
        "height_in": 72, "weight_lbs": 198,
        "heaviness": 0, "weighted_forward_heaviness": 0,
        "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0,
        "line_number": line_number,
    }
```

### Step 2: Delete `_setup_elite_db` and the 6 old elite_forwards tests

Delete lines 258–384 entirely. This removes:
- `_setup_elite_db()` function
- `test_elite_forwards_table_created`
- `test_elite_forwards_correct_players_selected`
- `test_elite_forwards_specialist_excluded`
- `test_elite_forwards_p60_threshold`
- `test_elite_forwards_rank_by_p60`
- `test_elite_trade_carryover`

The `_make_comp_row` helper is still used by `test_recompute_pct_vs_elite_fwd` further down, so keep it.

### Step 3: Insert 4 new elite_forwards tests in place of the deleted block

Insert after line 255 (after `_make_comp_row`, before `test_recompute_pct_vs_elite_fwd`):

```python
# ---------------------------------------------------------------------------
# Elite Forwards v2
# ---------------------------------------------------------------------------

def _ef_comp_rows(pid, team, games, toi, total_toi, line_number, filler_d_toi):
    """Return competition rows for one target forward + one filler defenseman.

    filler_d_toi is set so that team_total = toi + filler_d_toi, giving a
    deterministic tTOI% = 5 * toi / (toi + filler_d_toi) * 100.
    """
    rows = []
    for game in games:
        rows.append({
            "gameId": game, "playerId": pid, "team": team, "position": "F",
            "toi_seconds": toi, "total_toi_seconds": total_toi,
            "line_number": line_number,
            "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
            "comp_fwd": 0, "comp_def": 0, "height_in": 72, "weight_lbs": 198,
            "heaviness": 0, "weighted_forward_heaviness": 0,
            "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0,
        })
        rows.append({
            "gameId": game, "playerId": pid + 1000, "team": team, "position": "D",
            "toi_seconds": filler_d_toi, "total_toi_seconds": filler_d_toi,
            "line_number": None,
            "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
            "comp_fwd": 0, "comp_def": 0, "height_in": 72, "weight_lbs": 198,
            "heaviness": 0, "weighted_forward_heaviness": 0,
            "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0,
        })
    return rows


def _ef_pts_rows(pid, game_ids, total_pts):
    """Distribute total_pts evenly across game_ids for player pid."""
    rows = []
    for i, gid in enumerate(game_ids):
        if i < total_pts:
            rows.append({"gameId": gid, "playerId": pid, "goals": 1, "assists": 0, "points": 1})
    return rows


def test_ef_phase1_no_elite_under_10_gp():
    """Phase 1: player with 8 GP never gets elite status regardless of stats."""
    conn = sqlite3.connect(":memory:")
    # toi=900, filler_d=9100 → team_total=10000, tTOI%=5*900/10000*100=45% ≥28%
    # iTOI%=900/1200*100=75% <83%
    # DPL=1.0 ≤2.5
    # P/60=10*3600/7200=5.0 ≥2.3 — great stats but too few games
    games = list(range(1, 9))
    rows = _ef_comp_rows(pid=1, team="EDM", games=games, toi=900, total_toi=1200,
                         line_number=1.0, filler_d_toi=9100)
    pd.DataFrame(rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(_ef_pts_rows(1, games, total_pts=10)).to_sql(
        "points_5v5", conn, index=False, if_exists="replace")

    build_elite_forwards_table(conn)

    rows_out = conn.execute("SELECT * FROM elite_forwards").fetchall()
    assert rows_out == [], f"Expected empty, got {rows_out}"


def test_ef_phase2_full_season_only_no_blend():
    """Phase 2: 15 GP uses full-season values; l20_* columns are NULL."""
    conn = sqlite3.connect(":memory:")
    # tTOI%=5*900/10000*100=45%, iTOI%=75%, DPL=1.0 → all 3 deployment signals pass
    # P/60=10*3600/13500=2.67 ≥2.3
    games = list(range(1, 16))
    rows = _ef_comp_rows(pid=1, team="EDM", games=games, toi=900, total_toi=1200,
                         line_number=1.0, filler_d_toi=9100)
    pd.DataFrame(rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(_ef_pts_rows(1, games, total_pts=10)).to_sql(
        "points_5v5", conn, index=False, if_exists="replace")

    build_elite_forwards_table(conn)

    row = conn.execute("SELECT * FROM elite_forwards WHERE playerId = 1").fetchone()
    assert row is not None, "Player with 15 GP and qualifying stats should be elite"

    cols = [d[0] for d in conn.execute("SELECT * FROM elite_forwards LIMIT 1").description]
    data = dict(zip(cols, row))
    assert data["l20_p60"] is None, "l20_p60 should be NULL for GP < 20"
    assert data["l20_dpl"] is None
    assert data["l20_ttoi_pct"] is None
    assert data["l20_itoi_pct"] is None
    # Full-season P/60 = 10 pts * 3600 / (15 * 900s) = 2.667
    assert abs(data["weighted_p60"] - 10 * 3600 / 13500) < 0.01


def test_ef_phase3_blend_applied():
    """Phase 3: 80/20 blend applied to P/60 and DPL."""
    conn = sqlite3.connect(":memory:")
    # 30 games total: games 1-10 use line_number=3, games 11-30 use line_number=1
    # All games: toi=900, total_toi=1200, filler_d=9100 → team_total=10000
    games_early = list(range(1, 11))   # 10 games, line 3
    games_late  = list(range(11, 31))  # 20 games, line 1
    rows = (
        _ef_comp_rows(pid=1, team="EDM", games=games_early, toi=900, total_toi=1200,
                      line_number=3.0, filler_d_toi=9100)
        + _ef_comp_rows(pid=1, team="EDM", games=games_late, toi=900, total_toi=1200,
                        line_number=1.0, filler_d_toi=9100)
    )
    pd.DataFrame(rows).to_sql("competition", conn, index=False, if_exists="replace")

    # Points: 12 in first 10 games, 9 in last 20 → total=21
    # fs_p60 = 21 * 3600 / (30*900) = 21*3600/27000 = 2.8
    # l20_p60 = 9 * 3600 / (20*900) = 9*3600/18000 = 1.8
    # weighted_p60 = 2.8*0.8 + 1.8*0.2 = 2.6
    pts_rows = _ef_pts_rows(1, games_early, total_pts=12) + _ef_pts_rows(1, games_late, total_pts=9)
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_forwards_table(conn)

    row = conn.execute("SELECT * FROM elite_forwards WHERE playerId = 1").fetchone()
    assert row is not None, "Player should be elite (weighted_p60=2.6 ≥ 2.3)"

    cols = [d[0] for d in conn.execute("SELECT * FROM elite_forwards LIMIT 1").description]
    data = dict(zip(cols, row))

    # P/60 blend
    assert abs(data["fs_p60"] - 2.8) < 0.01, f"fs_p60={data['fs_p60']}"
    assert abs(data["l20_p60"] - 1.8) < 0.01, f"l20_p60={data['l20_p60']}"
    assert abs(data["weighted_p60"] - 2.6) < 0.01, f"weighted_p60={data['weighted_p60']}"

    # DPL blend: fs_dpl=(10*3+20*1)/30=1.6667, l20_dpl=1.0, weighted=1.6667*0.8+1.0*0.2=1.5333
    assert abs(data["fs_dpl"] - 5/3) < 0.01, f"fs_dpl={data['fs_dpl']}"
    assert abs(data["l20_dpl"] - 1.0) < 0.01, f"l20_dpl={data['l20_dpl']}"
    assert abs(data["weighted_dpl"] - (5/3 * 0.8 + 1.0 * 0.2)) < 0.01


def test_ef_two_of_three_deployment():
    """2-of-3 deployment: players with exactly 2 signals pass; 0 or 1 signal fails.

    All players have GP=20, P/60 ≥ 2.3.
    Team total per game = 10000s (target_toi + filler_d_toi = 10000).

    Player  team  toi  filler_d  total_toi  tTOI%   iTOI%   DPL   signals
    1       T1    700  9300      700        35%     100%    1.0   DPL+tTOI  → IN
    2       T2    500  9500      700        25%     71.4%   1.0   DPL+iTOI  → IN
    3       T3    700  9300      900        35%     77.8%   3.0   tTOI+iTOI → IN
    4       T4    500  9500      500        25%     100%    3.0   none      → OUT
    5       T5    500  9500      500        25%     100%    1.0   DPL only  → OUT
    """
    conn = sqlite3.connect(":memory:")
    games = list(range(1, 21))  # 20 games each

    # Each player on their own team to avoid interaction
    setup = [
        (1, "T1", 700, 9300, 700,  1.0),  # DPL + tTOI pass
        (2, "T2", 500, 9500, 700,  1.0),  # DPL + iTOI pass
        (3, "T3", 700, 9300, 900,  3.0),  # tTOI + iTOI pass
        (4, "T4", 500, 9500, 500,  3.0),  # none pass
        (5, "T5", 500, 9500, 500,  1.0),  # DPL only (1-of-3)
    ]
    comp_rows = []
    pts_rows = []
    for pid, team, toi, filler_d_toi, total_toi, line_number in setup:
        comp_rows.extend(_ef_comp_rows(pid, team, games, toi, total_toi,
                                       line_number, filler_d_toi))
        # 10 pts over 20 games: P/60 = 10 * 3600 / (20 * toi)
        # For toi=700: 10*3600/14000 = 2.57 ≥ 2.3 ✓
        # For toi=500: 10*3600/10000 = 3.6 ≥ 2.3 ✓
        pts_rows.extend(_ef_pts_rows(pid, games, total_pts=10))

    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")

    build_elite_forwards_table(conn)

    elite_pids = {r[0] for r in conn.execute("SELECT playerId FROM elite_forwards").fetchall()}
    assert 1 in elite_pids, "pid 1 (DPL + tTOI) should be elite"
    assert 2 in elite_pids, "pid 2 (DPL + iTOI) should be elite"
    assert 3 in elite_pids, "pid 3 (tTOI + iTOI) should be elite"
    assert 4 not in elite_pids, "pid 4 (no signals) should not be elite"
    assert 5 not in elite_pids, "pid 5 (DPL only, 1-of-3) should not be elite"
```

### Step 4: Run tests to verify they fail

```
python -m pytest v2/browser/tests/test_player_metrics.py -k "test_ef_" -v
```

Expected: 4 FAILED with `AssertionError` or column errors (function still has old logic).

---

## Task 2: Rewrite `build_elite_forwards_table`

**Files:**
- Modify: `v2/browser/build_league_db.py` lines 214–304

### Step 1: Replace the entire `build_elite_forwards_table` function

Replace lines 214–304 with:

```python
def build_elite_forwards_table(conn):
    """League-wide elite forwards: production gate + 2-of-3 deployment, 80/20 blend.

    Production gate (required):
      - weighted P/60 ≥ 2.3

    Deployment qualification (2-of-3 required):
      - DPL    ≤ 2.5  (avg line assignment — lower is better)
      - tTOI%  ≥ 28%  (share of team 5v5 ice time)
      - iTOI%  < 83%  (fraction of total TOI at 5v5 — plays special teams)

    Three-phase logic based on GP with current team:
      Phase 1 (GP < 10):   no designation
      Phase 2 (10–19 GP):  full-season values only, l20_* stored as NULL
      Phase 3 (≥ 20 GP):   80/20 blend: metric = fs_metric * 0.8 + l20_metric * 0.2

    "Last 20 games" is player-specific (their last 20 games played, across all teams).
    """
    # ---- Load per-game forward data with per-game team totals ----
    comp = pd.read_sql_query(
        """
        WITH tt AS (
            SELECT gameId, team, SUM(toi_seconds) AS team_total
            FROM competition WHERE position IN ('F', 'D')
            GROUP BY gameId, team
        )
        SELECT c.playerId, c.team, c.gameId,
               c.toi_seconds, c.total_toi_seconds, c.line_number,
               5.0 * c.toi_seconds / tt.team_total AS ttoi_frac
        FROM competition c
        JOIN tt ON tt.gameId = c.gameId AND tt.team = c.team
        WHERE c.position = 'F'
        """,
        conn,
    )
    if comp.empty:
        print("  elite_forwards: 0 rows (no forward competition data)")
        return

    pts = pd.read_sql_query("SELECT playerId, gameId, points FROM points_5v5", conn)

    # Merge points into per-game data (one row per player per game per team)
    gd = comp.merge(pts, on=["playerId", "gameId"], how="left")
    gd["points"] = gd["points"].fillna(0)
    gd = gd.sort_values(["playerId", "gameId"]).reset_index(drop=True)

    # Pre-index player's full game sequence for last-20 slicing
    player_games = (
        gd.groupby("playerId")["gameId"]
        .apply(lambda s: sorted(s.unique()))
        .to_dict()
    )

    records = []
    for (pid, team), grp in gd.groupby(["playerId", "team"]):
        gp = grp["gameId"].nunique()
        if gp < 10:  # Phase 1
            continue

        # Full-season metrics for this (player, team)
        fs_toi     = grp["toi_seconds"].sum()
        fs_all_toi = grp["total_toi_seconds"].sum()
        fs_pts     = grp["points"].sum()
        fs_p60        = fs_pts * 3600.0 / fs_toi if fs_toi > 0 else 0.0
        fs_ttoi_pct   = float(grp["ttoi_frac"].mean()) * 100.0
        fs_itoi_pct   = fs_toi * 100.0 / fs_all_toi if fs_all_toi > 0 else 0.0
        fs_dpl_raw    = grp["line_number"].dropna()
        fs_dpl        = float(fs_dpl_raw.mean()) if not fs_dpl_raw.empty else None

        toi_min_gp = fs_toi / gp / 60.0

        # Last-20-games metrics (player-specific across all teams)
        all_player_game_ids = player_games.get(pid, [])
        total_player_gp = len(all_player_game_ids)

        l20_p60 = l20_ttoi_pct = l20_itoi_pct = l20_dpl = None

        if total_player_gp >= 20:
            last20 = set(all_player_game_ids[-20:])
            l20_rows = gd[(gd["playerId"] == pid) & (gd["gameId"].isin(last20))]
            l20_toi     = l20_rows["toi_seconds"].sum()
            l20_all_toi = l20_rows["total_toi_seconds"].sum()
            l20_pts     = l20_rows["points"].sum()
            l20_p60       = l20_pts * 3600.0 / l20_toi if l20_toi > 0 else 0.0
            l20_ttoi_pct  = float(l20_rows["ttoi_frac"].mean()) * 100.0
            l20_itoi_pct  = l20_toi * 100.0 / l20_all_toi if l20_all_toi > 0 else 0.0
            l20_dpl_raw   = l20_rows["line_number"].dropna()
            l20_dpl       = float(l20_dpl_raw.mean()) if not l20_dpl_raw.empty else None

        # Weighted metrics
        if total_player_gp >= 20:
            weighted_p60      = fs_p60 * 0.8 + l20_p60 * 0.2
            weighted_ttoi_pct = fs_ttoi_pct * 0.8 + l20_ttoi_pct * 0.2
            weighted_itoi_pct = fs_itoi_pct * 0.8 + l20_itoi_pct * 0.2
            if fs_dpl is not None and l20_dpl is not None:
                weighted_dpl = fs_dpl * 0.8 + l20_dpl * 0.2
            else:
                weighted_dpl = fs_dpl  # fall back to full-season if l20 unavailable
        else:
            # Phase 2: full-season only
            weighted_p60      = fs_p60
            weighted_ttoi_pct = fs_ttoi_pct
            weighted_itoi_pct = fs_itoi_pct
            weighted_dpl      = fs_dpl

        # Production gate
        if weighted_p60 < 2.3:
            continue

        # 2-of-3 deployment
        dpl_ok   = weighted_dpl is not None and weighted_dpl <= 2.5
        ttoi_ok  = weighted_ttoi_pct >= 28.0
        itoi_ok  = weighted_itoi_pct < 83.0

        if sum([dpl_ok, ttoi_ok, itoi_ok]) < 2:
            continue

        records.append({
            "playerId":          pid,
            "team":              team,
            "gp":                gp,
            "toi_min_gp":        round(toi_min_gp, 2),
            "fs_p60":            round(fs_p60, 4),
            "l20_p60":           round(l20_p60, 4) if l20_p60 is not None else None,
            "weighted_p60":      round(weighted_p60, 4),
            "fs_dpl":            round(fs_dpl, 4) if fs_dpl is not None else None,
            "l20_dpl":           round(l20_dpl, 4) if l20_dpl is not None else None,
            "weighted_dpl":      round(weighted_dpl, 4) if weighted_dpl is not None else None,
            "fs_ttoi_pct":       round(fs_ttoi_pct, 4),
            "l20_ttoi_pct":      round(l20_ttoi_pct, 4) if l20_ttoi_pct is not None else None,
            "weighted_ttoi_pct": round(weighted_ttoi_pct, 4),
            "fs_itoi_pct":       round(fs_itoi_pct, 4),
            "l20_itoi_pct":      round(l20_itoi_pct, 4) if l20_itoi_pct is not None else None,
            "weighted_itoi_pct": round(weighted_itoi_pct, 4),
        })

    if not records:
        print("  elite_forwards: 0 rows (no qualifying forwards)")
        return

    out = pd.DataFrame(records)
    out.to_sql("elite_forwards", conn, if_exists="replace", index=False)
    print(f"  elite_forwards: {len(out)} rows")
```

### Step 2: Run the new tests

```
python -m pytest v2/browser/tests/test_player_metrics.py -k "test_ef_" -v
```

Expected: 4 PASSED.

### Step 3: Run full test suite to check for regressions

```
python -m pytest v2/ -v
```

Expected: all passing except possibly changelog tests (handled in Task 3).

---

## Task 3: Update changelog helpers and fix test fixtures

**Problem:** `_log_elite_changes` and `_read_old_elites` both reference `is_carryover` in SQL queries. The new `elite_forwards` table has no `is_carryover` column, so these queries will fail on the new DB.

**Files:**
- Modify: `v2/browser/build_league_db.py` — two functions
- Modify: `v2/browser/tests/test_player_metrics.py` — changelog test fixtures

### Step 1: Update `_log_elite_changes` — remove `is_carryover` filter

The new `elite_forwards` table has no carry-over rows, so the filter is unnecessary.

In `_log_elite_changes`, find the two SQL strings that read `elite_forwards` and remove `WHERE e.is_carryover = 0`:

```python
# Old:
new_fwd = pd.read_sql_query(
    "SELECT e.playerId, "
    "  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
    "  e.team "
    "FROM elite_forwards e "
    "LEFT JOIN players p ON e.playerId = p.playerId "
    "WHERE e.is_carryover = 0",
    conn,
)

# New:
new_fwd = pd.read_sql_query(
    "SELECT e.playerId, "
    "  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
    "  e.team "
    "FROM elite_forwards e "
    "LEFT JOIN players p ON e.playerId = p.playerId",
    conn,
)
```

### Step 2: Update `_read_old_elites` — handle both old and new schemas

`_read_old_elites` reads the OLD database (before deletion). During the transition, the old DB may have the v1 schema (with `is_carryover`). After the first rebuild, the old DB will have the v2 schema (without it). Handle both:

```python
def _read_old_elites(db_path):
    """Read current elite sets from an existing league.db before it is deleted.

    Returns (fwd_df, def_df) — primary rows only (excludes carry-overs if schema has them).
    Each DataFrame has columns: playerId, playerName, team.
    def_df also has a 'type' column: Full Elite / Production / Deployment.
    Returns empty DataFrames if the DB doesn't exist or tables are missing.
    """
    if not os.path.exists(db_path):
        return pd.DataFrame(columns=["playerId", "playerName", "team"]), \
               pd.DataFrame(columns=["playerId", "playerName", "team", "type"])
    try:
        old = sqlite3.connect(db_path)
        # Check if old schema has is_carryover (v1) or not (v2)
        fwd_cols = {row[1] for row in old.execute("PRAGMA table_info(elite_forwards)").fetchall()}
        carryover_filter = "WHERE e.is_carryover = 0" if "is_carryover" in fwd_cols else ""
        fwd = pd.read_sql_query(
            f"SELECT e.playerId, "
            f"  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
            f"  e.team "
            f"FROM elite_forwards e "
            f"LEFT JOIN players p ON e.playerId = p.playerId "
            f"{carryover_filter}",
            old,
        )
        def_cols = {row[1] for row in old.execute("PRAGMA table_info(elite_defensemen)").fetchall()}
        def_carryover = "WHERE e.is_carryover = 0" if "is_carryover" in def_cols else ""
        def_ = pd.read_sql_query(
            f"SELECT e.playerId, "
            f"  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
            f"  e.team, "
            f"  CASE WHEN e.is_full_elite = 1 THEN 'Full Elite' "
            f"       WHEN e.is_production = 1 THEN 'Production' "
            f"       ELSE 'Deployment' END AS type "
            f"FROM elite_defensemen e "
            f"LEFT JOIN players p ON e.playerId = p.playerId "
            f"{def_carryover}",
            old,
        )
        old.close()
        return fwd, def_
    except Exception:
        return pd.DataFrame(columns=["playerId", "playerName", "team"]), \
               pd.DataFrame(columns=["playerId", "playerName", "team", "type"])
```

### Step 3: Update changelog test fixtures to use new elite_forwards schema

The changelog tests set up `elite_forwards` tables with old-schema columns (`rank`, `is_carryover`). Since `_log_elite_changes` no longer filters by `is_carryover`, these fixtures still work — BUT the columns are now stale. More importantly, if any future code tries to query new columns, they'll fail.

Update the `elite_forwards` fixture in all 4 changelog tests (`test_elite_changelog_addition`, `test_elite_changelog_removal`, `test_elite_changelog_no_changes`, `test_elite_changelog_appends`) to use the minimal new schema.

Example — replace old fixture rows like:
```python
# Old fixture in changelog tests:
pd.DataFrame([
    {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
     "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1,
     "is_carryover": 0, "vs_ed_pct": 0.5},
    ...
]).to_sql("elite_forwards", conn, ...)
```

With new schema (only the columns `_log_elite_changes` needs: playerId, team, and a players join):
```python
# New fixture:
pd.DataFrame([
    {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
     "weighted_p60": 2.4, "weighted_dpl": 1.5,
     "weighted_ttoi_pct": 33.0, "weighted_itoi_pct": 75.0},
    ...
]).to_sql("elite_forwards", conn, ...)
```

Apply this to all 4 changelog tests that set up an `elite_forwards` table in `conn`.

Also update `test_elite_defensemen_table_created` and related tests if they still reference the old elite_defensemen schema — check each test for `rank` and `is_carryover` column references.

### Step 4: Run full test suite

```
python -m pytest v2/ -v
```

Expected: all passing.

---

## Task 4: Update `elites.py` browser page

**Files:**
- Modify: `v2/browser/pages/elites.py`

### Step 1: Update `_FWD_SQL` for new schema

The old query selected `e.ttoi_pct, e.itoi_pct, e.p60, e.vs_ed_pct, e.is_carryover`. Replace with the new columns. Also remove the `_DPL_SQL` query and join — DPL is now stored directly in `elite_forwards`.

```python
_FWD_SQL = """
SELECT e.playerId, e.team, e.gp, e.toi_min_gp,
       e.weighted_p60, e.weighted_dpl, e.weighted_ttoi_pct, e.weighted_itoi_pct,
       e.fs_p60, e.fs_dpl, e.fs_ttoi_pct, e.fs_itoi_pct,
       e.l20_p60, e.l20_dpl, e.l20_ttoi_pct, e.l20_itoi_pct,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName
FROM elite_forwards e
LEFT JOIN players p ON e.playerId = p.playerId
ORDER BY e.weighted_p60 DESC
"""
```

### Step 2: Remove `_collapse_traded` and `is_carryover` usage from `_build_fwd_table`

The old `_build_fwd_table` called `_collapse_traded(df)` which merged carry-over rows using `is_carryover`. The new model has no carry-over rows — every row is a primary row. Remove the call and the `_collapse_traded` function entirely.

Also remove the DPL join (the old code merged `dpl_df` on `playerId`); DPL is now in the table.

Remove `_DPL_SQL`, the `dpl_df = league_query(_DPL_SQL, season=season)` call in `layout()`, and the `dpl_df` parameter from `_build_fwd_table`.

Update `_build_fwd_table` signature and body:

```python
def _build_fwd_table(df):
    """Build the forwards DataTable."""
    df = df.copy()
    df["player_link"] = df.apply(
        lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1,
    )
    df["team_link"] = df["team"].apply(lambda t: f"[{t}](/team/{t})")

    columns = [
        {"name": "Player",    "id": "player_link",       "presentation": "markdown", "filter_options": _CI},
        {"name": "Team",      "id": "team_link",          "presentation": "markdown", "filter_options": _CI},
        {"name": "GP",        "id": "gp",                 "type": "numeric"},
        {"name": "TOI/GP",    "id": "toi_min_gp",         "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "P/60",      "id": "weighted_p60",       "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "DPL",       "id": "weighted_dpl",       "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "tTOI%",     "id": "weighted_ttoi_pct",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "iTOI%",     "id": "weighted_itoi_pct",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "team_link", "gp", "toi_min_gp",
        "weighted_p60", "weighted_dpl", "weighted_ttoi_pct", "weighted_itoi_pct",
    ]

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

### Step 3: Update `layout()` to remove `dpl_df` wiring

In `layout()`, remove the `dpl_df` fetch and pass-through:

```python
def layout(season=None):
    season = season or "2025"
    children = []

    # --- DPS+: normalized deployment score per defenseman ---
    dps_raw = league_query(_DPS_SQL, season=season)
    if not dps_raw.empty:
        dps_raw["avg_score"] = dps_raw["total_score"] / dps_raw["gp"]
        league_avg = dps_raw["avg_score"].mean()
        dps_raw["dps_plus"] = dps_raw["avg_score"] / league_avg * 100 if league_avg else None
    else:
        dps_raw["dps_plus"] = None

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
        children.append(_build_def_table(def_df, dps_raw))

    return html.Div(children)
```

### Step 4: Delete `_collapse_traded` function

Remove the entire `_collapse_traded` function (lines 58–71 in the current file).

### Step 5: Run full test suite

```
python -m pytest v2/ -v
```

Expected: all tests pass.

### Step 6: Do a real build and verify output

```
python v2/browser/build_league_db.py 2025
```

Check the output line for `elite_forwards` count — should be ~20–28 rows.

---

## Verification

1. `python -m pytest v2/ -v` — all tests pass
2. `python v2/browser/build_league_db.py 2025` — builds cleanly, elite_forwards shows ~24 rows
3. Load `/elites` in the browser — forwards table shows weighted P/60, DPL, tTOI%, iTOI% columns
4. Confirm no "Elite Forwards" rows with old columns (`rank`, `is_carryover`, `vs_ed_pct`) appear
