# Elite Forwards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add elite forward classification to `build_league_db.py` and replace `pct_vs_top_fwd` with elite-model-based values computed from timeline CSVs.

**Architecture:** Two new functions in `build_league_db.py`: (1) `build_elite_forwards_table` computes the elite roster from competition + points_5v5 data using per-(player, team) stats with threshold filters and per-team caps, then detects trade carry-overs; (2) `recompute_pct_vs_elite_fwd` re-reads all timeline CSVs and UPDATEs `competition.pct_vs_top_fwd` with the fraction of opposing forwards who are elite. No changes to `compute_competition.py` or browser pages.

**Tech Stack:** Python, SQLite, pandas, csv (stdlib)

**Design doc:** `docs/plans/2026-03-21-elite-forwards-design.md`

**Key reference files:**
- `v2/browser/build_league_db.py` — main file to modify
- `v2/browser/tests/test_player_metrics.py` — test file to extend
- `v2/competition/compute_competition.py:23` — `SCORED_SITUATIONS = {"1551", "0651", "1560"}` (must match in new code)
- Timeline CSVs: `data/<season>/generated/timelines/csv/<gameId>.csv` — columns: `period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,awayGoalie,awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters`

**Git:** Do not commit. oiler handles all git operations manually.

---

### Task 1: Elite forwards table — write failing tests

**Files:**
- Modify: `v2/browser/tests/test_player_metrics.py`

**Step 1: Add import for `build_elite_forwards_table`**

At line 13, extend the import:

```python
from build_league_db import build_player_metrics_table, _recover_missing_players, build_elite_forwards_table
```

**Step 2: Add `_setup_elite_db()` helper**

Add after the `_setup_recovery_db` function (after line 191). This builds a realistic synthetic dataset with 2 teams, 18 skaters per game (12F + 6D), 25 games each, plus a points_5v5 table.

```python
def _setup_elite_db():
    """
    In-memory DB with 2 teams (EDM, COL), 25 games each.
    Each team has 12 forwards + 6 defensemen per game.

    EDM forwards:
      F1 (pid=1):  toi=900, total=1200 → iTOI=75.0%, points=15 → P/60=2.40  ELITE rank 1
      F2 (pid=2):  toi=850, total=1100 → iTOI=77.3%, points=12 → P/60=2.03  ELITE rank 2
      F3 (pid=3):  toi=800, total=1000 → iTOI=80.0%, points=8  → P/60=1.44  ELITE rank 3
      F4 (pid=4):  toi=820, total=820  → iTOI=100%  FAILS iTOI (5v5 specialist)
      F5-F12 (pid=5-12): toi=500, total=600 → tTOI < 28% (bottom-six)
    EDM defense: D1-D6 (pid=13-18): toi=1000, total=1300

    team_total per game = 900+850+800+820+(8×500)+(6×1000) = 13370
    tTOI% for F1 = 5×900/13370 = 33.7%   (passes 28%)
    tTOI% for F5 = 5×500/13370 = 18.7%   (fails 28%)

    COL forwards — same structure but with a 4th-slot candidate:
      F21 (pid=21): toi=900, total=1200 → P/60=2.40  ELITE rank 1
      F22 (pid=22): toi=850, total=1100 → P/60=2.03  ELITE rank 2
      F23 (pid=23): toi=800, total=1000 → P/60=1.44  ELITE rank 3
      F24 (pid=24): toi=830, total=1050 → iTOI=79.0%, points=11 → P/60=1.91  ELITE rank 4 (P/60 ≥ 1.7)
      F25 (pid=25): toi=810, total=1020 → iTOI=79.4%, points=6  → P/60=1.07  rank 5 (P/60 < 1.7, no 4th slot)
      F26-F32 (pid=26-32): toi=500, total=600
    COL defense: D21-D26 (pid=33-38): toi=1000, total=1300

    COL team_total = 900+850+800+830+810+(7×500)+(6×1000) = 13390
    """
    conn = sqlite3.connect(":memory:")
    comp_rows = []
    pts_rows = []

    # --- EDM: 25 games (gameId 1-25) ---
    edm_fwds = [
        (1, 900, 1200, 15),   # elite
        (2, 850, 1100, 12),   # elite
        (3, 800, 1000, 8),    # elite
        (4, 820, 820,  10),   # fails iTOI (100%)
    ]
    for game in range(1, 26):
        for pid, toi, total, _ in edm_fwds:
            comp_rows.append({"playerId": pid, "team": "EDM", "gameId": game,
                              "position": "F", "toi_seconds": toi,
                              "total_toi_seconds": total, "pct_vs_top_fwd": 0.0,
                              "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                              "height_in": 72, "weight_lbs": 198,
                              "heaviness": 0, "weighted_forward_heaviness": 0,
                              "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
        for pid in range(5, 13):  # 8 bottom-six
            comp_rows.append({"playerId": pid, "team": "EDM", "gameId": game,
                              "position": "F", "toi_seconds": 500,
                              "total_toi_seconds": 600, "pct_vs_top_fwd": 0.0,
                              "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                              "height_in": 72, "weight_lbs": 198,
                              "heaviness": 0, "weighted_forward_heaviness": 0,
                              "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
        for pid in range(13, 19):  # 6 defensemen
            comp_rows.append({"playerId": pid, "team": "EDM", "gameId": game,
                              "position": "D", "toi_seconds": 1000,
                              "total_toi_seconds": 1300, "pct_vs_top_fwd": 0.0,
                              "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                              "height_in": 74, "weight_lbs": 220,
                              "heaviness": 0, "weighted_forward_heaviness": 0,
                              "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})

    # EDM points — distribute across games
    for pid, _, _, total_pts in edm_fwds:
        for i in range(total_pts):
            game = (i % 25) + 1
            pts_rows.append({"gameId": game, "playerId": pid, "goals": 1, "assists": 0, "points": 1})

    # --- COL: 25 games (gameId 101-125) ---
    col_fwds = [
        (21, 900, 1200, 15),  # elite rank 1
        (22, 850, 1100, 12),  # elite rank 2
        (23, 800, 1000, 8),   # elite rank 3
        (24, 830, 1050, 11),  # elite rank 4 (P/60 = 1.91 ≥ 1.7)
        (25, 810, 1020, 6),   # rank 5 (P/60 = 1.07, < 1.7 — NOT 4th slot)
    ]
    for game in range(101, 126):
        for pid, toi, total, _ in col_fwds:
            comp_rows.append({"playerId": pid, "team": "COL", "gameId": game,
                              "position": "F", "toi_seconds": toi,
                              "total_toi_seconds": total, "pct_vs_top_fwd": 0.0,
                              "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                              "height_in": 72, "weight_lbs": 198,
                              "heaviness": 0, "weighted_forward_heaviness": 0,
                              "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
        for pid in range(26, 33):  # 7 bottom-six
            comp_rows.append({"playerId": pid, "team": "COL", "gameId": game,
                              "position": "F", "toi_seconds": 500,
                              "total_toi_seconds": 600, "pct_vs_top_fwd": 0.0,
                              "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                              "height_in": 72, "weight_lbs": 198,
                              "heaviness": 0, "weighted_forward_heaviness": 0,
                              "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
        for pid in range(33, 39):  # 6 defensemen
            comp_rows.append({"playerId": pid, "team": "COL", "gameId": game,
                              "position": "D", "toi_seconds": 1000,
                              "total_toi_seconds": 1300, "pct_vs_top_fwd": 0.0,
                              "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                              "height_in": 74, "weight_lbs": 220,
                              "heaviness": 0, "weighted_forward_heaviness": 0,
                              "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})

    for pid, _, _, total_pts in col_fwds:
        for i in range(total_pts):
            game = (i % 25) + 101
            pts_rows.append({"gameId": game, "playerId": pid, "goals": 1, "assists": 0, "points": 1})

    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")
    return conn
```

**Step 3: Add core classification tests**

```python
def test_elite_forwards_table_created():
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "elite_forwards" in tables


def test_elite_forwards_correct_players_selected():
    """EDM should have 3 elite forwards (pid 1,2,3). pid 4 fails iTOI. pid 5-12 fail tTOI."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    edm = conn.execute(
        "SELECT playerId FROM elite_forwards WHERE team = 'EDM' ORDER BY playerId"
    ).fetchall()
    assert [r[0] for r in edm] == [1, 2, 3]


def test_elite_forwards_specialist_excluded():
    """pid 4 has tTOI > 28% and P/60 > 1.0 but iTOI = 100% — excluded."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    row = conn.execute("SELECT * FROM elite_forwards WHERE playerId = 4").fetchone()
    assert row is None


def test_elite_forwards_fourth_slot():
    """COL pid 24 gets 4th slot (P/60 = 1.91 ≥ 1.7). pid 25 does not (P/60 = 1.07 < 1.7)."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    col = conn.execute(
        "SELECT playerId FROM elite_forwards WHERE team = 'COL' ORDER BY playerId"
    ).fetchall()
    pids = [r[0] for r in col]
    assert 24 in pids, "pid 24 (P/60 1.91) should get 4th slot"
    assert 25 not in pids, "pid 25 (P/60 1.07) should NOT get 4th slot"


def test_elite_forwards_rank_by_p60():
    """Within EDM, rank 1 = highest P/60 (pid 1), rank 3 = lowest (pid 3)."""
    conn = _setup_elite_db()
    build_elite_forwards_table(conn)
    rows = conn.execute(
        "SELECT playerId, rank FROM elite_forwards WHERE team = 'EDM' ORDER BY rank"
    ).fetchall()
    assert rows[0] == (1, 1)  # P/60 = 2.40
    assert rows[1] == (2, 2)  # P/60 = 2.03
    assert rows[2] == (3, 3)  # P/60 = 1.44
```

**Step 4: Run tests to verify they fail**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -k elite -v`

Expected: FAIL — `build_elite_forwards_table` doesn't exist yet (ImportError).

---

### Task 2: Elite forwards table — implement

**Files:**
- Modify: `v2/browser/build_league_db.py`

**Step 1: Add `import csv` and `SCORED_SITUATIONS` constant**

Add `import csv` after `import json` (line 16). Add after the `FIVE_V_FIVE` line (line 35):

```python
SCORED_SITUATIONS = {"1551", "0651", "1560"}  # 5v5 + empty-net pulls (matches compute_competition.py)
```

**Step 2: Add `build_elite_forwards_table()` function**

Add after `build_points_5v5_table()` (after the current line 201):

```python
def build_elite_forwards_table(conn):
    """Identify elite forwards per team using tTOI%, iTOI%, P/60 thresholds."""
    stats = pd.read_sql_query("""
        WITH team_totals AS (
            SELECT gameId, team, SUM(toi_seconds) as team_total
            FROM competition WHERE position IN ('F','D')
            GROUP BY gameId, team
        ),
        player_points AS (
            SELECT playerId, SUM(points) as total_pts
            FROM points_5v5 GROUP BY playerId
        )
        SELECT
            c.playerId, c.team,
            COUNT(DISTINCT c.gameId) as gp,
            ROUND(SUM(c.toi_seconds) * 1.0 / COUNT(DISTINCT c.gameId) / 60, 2) as toi_min_gp,
            AVG(5.0 * c.toi_seconds / tt.team_total) * 100 as ttoi_pct,
            SUM(c.toi_seconds) * 100.0 / SUM(c.total_toi_seconds) as itoi_pct,
            COALESCE(pp.total_pts, 0) * 3600.0 / SUM(c.toi_seconds) as p60
        FROM competition c
        JOIN team_totals tt ON tt.gameId = c.gameId AND tt.team = c.team
        LEFT JOIN player_points pp ON pp.playerId = c.playerId
        WHERE c.position = 'F'
        GROUP BY c.playerId, c.team
        HAVING gp >= 20
    """, conn)

    if stats.empty:
        print("  elite_forwards: 0 rows (no qualifying forwards)")
        return

    # Apply thresholds
    qualified = stats[
        (stats["ttoi_pct"] >= 28.0)
        & (stats["itoi_pct"] < 83.0)
        & (stats["p60"] >= 1.0)
    ].copy()

    if qualified.empty:
        print("  elite_forwards: 0 rows (no forwards pass thresholds)")
        return

    # Rank by P/60 within team — top 3 always, 4th only if P/60 >= 1.7
    qualified["rank"] = (
        qualified.groupby("team")["p60"]
        .rank(ascending=False, method="first")
        .astype(int)
    )
    selected = qualified[
        (qualified["rank"] <= 3)
        | ((qualified["rank"] == 4) & (qualified["p60"] >= 1.7))
    ].copy()
    selected["is_carryover"] = 0

    # Trade carry-over: elite on old team → also elite on new team
    elite_pids = set(selected["playerId"])
    all_stints = pd.read_sql_query(
        "SELECT DISTINCT playerId, team FROM competition WHERE position = 'F'",
        conn,
    )
    carryovers = []
    for pid in elite_pids:
        elite_teams = set(selected.loc[selected["playerId"] == pid, "team"])
        all_teams = set(all_stints.loc[all_stints["playerId"] == pid, "team"])
        for new_team in all_teams - elite_teams:
            src = selected[selected["playerId"] == pid].iloc[0]
            carryovers.append({
                "playerId": pid, "team": new_team,
                "gp": src["gp"], "toi_min_gp": src["toi_min_gp"],
                "ttoi_pct": src["ttoi_pct"], "itoi_pct": src["itoi_pct"],
                "p60": src["p60"], "rank": 0, "is_carryover": 1,
            })
    if carryovers:
        selected = pd.concat([selected, pd.DataFrame(carryovers)], ignore_index=True)

    out_cols = ["playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
                "p60", "rank", "is_carryover"]
    selected[out_cols].to_sql("elite_forwards", conn, if_exists="replace", index=False)

    n_carry = len(carryovers)
    n_orig = len(selected) - n_carry
    carry_msg = f" + {n_carry} carry-overs" if n_carry else ""
    print(f"  elite_forwards: {n_orig} players{carry_msg}")
```

**Step 3: Run tests to verify they pass**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -k elite -v`

Expected: All 5 elite tests PASS.

---

### Task 3: Trade carry-over — write failing test + verify

**Files:**
- Modify: `v2/browser/tests/test_player_metrics.py`

**Step 1: Add trade carry-over test**

Add a modified setup that gives EDM's pid=1 a 3-game stint on COL, then test:

```python
def test_elite_trade_carryover():
    """Player elite on EDM (25 GP) who also played 3 games on COL
    should appear as a carry-over on COL."""
    conn = _setup_elite_db()
    # Add 3 COL games for EDM's pid=1 (simulates a trade)
    trade_rows = []
    for game in range(201, 204):
        trade_rows.append({"playerId": 1, "team": "COL", "gameId": game,
                           "position": "F", "toi_seconds": 900,
                           "total_toi_seconds": 1200, "pct_vs_top_fwd": 0.0,
                           "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                           "height_in": 72, "weight_lbs": 198,
                           "heaviness": 0, "weighted_forward_heaviness": 0,
                           "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(trade_rows).to_sql("competition", conn, if_exists="append", index=False)

    build_elite_forwards_table(conn)

    # pid=1 should be elite on EDM (earned) AND COL (carry-over)
    edm_row = conn.execute(
        "SELECT is_carryover FROM elite_forwards WHERE playerId = 1 AND team = 'EDM'"
    ).fetchone()
    assert edm_row is not None
    assert edm_row[0] == 0  # earned, not carry-over

    col_row = conn.execute(
        "SELECT is_carryover FROM elite_forwards WHERE playerId = 1 AND team = 'COL'"
    ).fetchone()
    assert col_row is not None
    assert col_row[0] == 1  # carry-over
```

**Step 2: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py::test_elite_trade_carryover -v`

Expected: PASS (implementation from Task 2 already handles carry-overs).

---

### Task 4: Recompute pct_vs_elite_fwd — write failing test

**Files:**
- Modify: `v2/browser/tests/test_player_metrics.py`

**Step 1: Add import for `recompute_pct_vs_elite_fwd`**

Update the import line:

```python
from build_league_db import (
    build_player_metrics_table, _recover_missing_players,
    build_elite_forwards_table, recompute_pct_vs_elite_fwd,
)
```

**Step 2: Add recompute test**

This test creates a minimal timeline CSV and verifies the fraction is computed correctly.

```python
def test_recompute_pct_vs_elite_fwd(tmp_path, monkeypatch):
    """
    Game 1001: EDM (away) vs COL (home).
    Away skaters: pid 1 (F, elite), pid 2 (F, elite), pid 4 (F, NOT elite), pid 13 (D), pid 14 (D)
    Home skaters: pid 21 (F, elite), pid 22 (F, elite), pid 26 (F, NOT elite), pid 33 (D), pid 34 (D)

    For away player pid=1: opposing forwards are 21 (elite), 22 (elite), 26 (not elite).
    Fraction = 2/3 per second. All seconds the same → pct_vs_top_fwd = 2/3 ≈ 0.6667.

    For home player pid=21: opposing forwards are 1 (elite), 2 (elite), 4 (not elite).
    Fraction = 2/3 per second → pct_vs_top_fwd = 2/3 ≈ 0.6667.
    """
    import build_league_db

    conn = sqlite3.connect(":memory:")

    # competition table — one game, 10 skaters
    comp_rows = []
    for pid, team, pos in [
        (1, "EDM", "F"), (2, "EDM", "F"), (4, "EDM", "F"), (13, "EDM", "D"), (14, "EDM", "D"),
        (21, "COL", "F"), (22, "COL", "F"), (26, "COL", "F"), (33, "COL", "D"), (34, "COL", "D"),
    ]:
        comp_rows.append({"playerId": pid, "team": team, "gameId": 1001,
                          "position": pos, "toi_seconds": 100,
                          "total_toi_seconds": 120, "pct_vs_top_fwd": 0.0,
                          "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                          "height_in": 72, "weight_lbs": 198,
                          "heaviness": 0, "weighted_forward_heaviness": 0,
                          "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")

    # elite_forwards table — pids 1, 2, 21, 22 are elite
    pd.DataFrame([
        {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1, "is_carryover": 0},
        {"playerId": 2, "team": "EDM", "gp": 25, "toi_min_gp": 14.0,
         "ttoi_pct": 31.0, "itoi_pct": 77.0, "p60": 2.0, "rank": 2, "is_carryover": 0},
        {"playerId": 21, "team": "COL", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1, "is_carryover": 0},
        {"playerId": 22, "team": "COL", "gp": 25, "toi_min_gp": 14.0,
         "ttoi_pct": 31.0, "itoi_pct": 77.0, "p60": 2.0, "rank": 2, "is_carryover": 0},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")

    # Write a minimal timeline CSV — 3 seconds of 5v5 with identical lineups
    timelines_dir = tmp_path / "generated" / "timelines" / "csv"
    timelines_dir.mkdir(parents=True)
    timeline = timelines_dir / "1001.csv"
    timeline.write_text(
        "period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,"
        "awayGoalie,awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters\n"
        "1,0,0,1551,5v5,99,5,1|2|4|13|14,5,98,21|22|26|33|34\n"
        "1,1,1,1551,5v5,99,5,1|2|4|13|14,5,98,21|22|26|33|34\n"
        "1,2,2,1551,5v5,99,5,1|2|4|13|14,5,98,21|22|26|33|34\n"
    )

    monkeypatch.setattr(build_league_db, "SEASON_DIR", str(tmp_path))
    recompute_pct_vs_elite_fwd(conn)

    # Away forward pid=1: opponents are F21 (elite), F22 (elite), F26 (not) → 2/3
    row1 = conn.execute(
        "SELECT pct_vs_top_fwd FROM competition WHERE playerId = 1"
    ).fetchone()
    assert abs(row1[0] - 2/3) < 0.001, f"Expected 0.667, got {row1[0]}"

    # Home forward pid=21: opponents are F1 (elite), F2 (elite), F4 (not) → 2/3
    row21 = conn.execute(
        "SELECT pct_vs_top_fwd FROM competition WHERE playerId = 21"
    ).fetchone()
    assert abs(row21[0] - 2/3) < 0.001, f"Expected 0.667, got {row21[0]}"

    # Defenseman pid=13: same opposing forwards → also 2/3
    row13 = conn.execute(
        "SELECT pct_vs_top_fwd FROM competition WHERE playerId = 13"
    ).fetchone()
    assert abs(row13[0] - 2/3) < 0.001, f"Expected 0.667, got {row13[0]}"
```

**Step 3: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py::test_recompute_pct_vs_elite_fwd -v`

Expected: FAIL — `recompute_pct_vs_elite_fwd` doesn't exist yet (ImportError).

---

### Task 5: Recompute pct_vs_elite_fwd — implement

**Files:**
- Modify: `v2/browser/build_league_db.py`

**Step 1: Add `recompute_pct_vs_elite_fwd()` function**

Add after `build_elite_forwards_table()`:

```python
def recompute_pct_vs_elite_fwd(conn):
    """Replace pct_vs_top_fwd with fraction of opposing forwards who are elite."""
    elite_rows = conn.execute("SELECT playerId FROM elite_forwards").fetchall()
    if not elite_rows:
        print("  pct_vs_elite_fwd: skipped (no elite forwards)")
        return
    elite_set = {r[0] for r in elite_rows}

    # Build per-game lookups from competition table
    pos_rows = conn.execute(
        "SELECT gameId, playerId, position FROM competition"
    ).fetchall()
    game_positions = {}
    game_ids = set()
    for gid, pid, pos in pos_rows:
        game_ids.add(gid)
        game_positions.setdefault(gid, {})[pid] = pos

    timelines_dir = os.path.join(SEASON_DIR, "generated", "timelines", "csv")
    updates = []

    for game_id in sorted(game_ids):
        timeline_path = os.path.join(timelines_dir, f"{game_id}.csv")
        if not os.path.exists(timeline_path):
            continue

        positions = game_positions.get(game_id, {})
        accum = {}  # playerId → [fraction, fraction, ...]

        with open(timeline_path, newline="") as f:
            for row in csv.DictReader(f):
                if row["situationCode"] not in SCORED_SITUATIONS:
                    continue

                away = [int(p) for p in row["awaySkaters"].split("|")] if row.get("awaySkaters") else []
                home = [int(p) for p in row["homeSkaters"].split("|")] if row.get("homeSkaters") else []

                for player_id, opponents in (
                    [(p, home) for p in away] + [(p, away) for p in home]
                ):
                    if positions.get(player_id) == "G":
                        continue

                    opp_fwds = [p for p in opponents if positions.get(p) == "F"]
                    if not opp_fwds:
                        continue

                    elite_count = sum(1 for p in opp_fwds if p in elite_set)
                    accum.setdefault(player_id, []).append(elite_count / len(opp_fwds))

        for pid, fracs in accum.items():
            updates.append((round(sum(fracs) / len(fracs), 4), game_id, pid))

    if updates:
        conn.executemany(
            "UPDATE competition SET pct_vs_top_fwd = ? WHERE gameId = ? AND playerId = ?",
            updates,
        )
        conn.commit()

    print(f"  pct_vs_elite_fwd: updated {len(updates)} rows across {len(game_ids)} games")
```

**Step 2: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py::test_recompute_pct_vs_elite_fwd -v`

Expected: PASS.

---

### Task 6: Wire into main() and run full suite

**Files:**
- Modify: `v2/browser/build_league_db.py`

**Step 1: Update module docstring**

Replace the docstring (lines 1-13) to mention the new tables:

```python
"""
Build a league-wide SQLite database for the NHL Data Browser.

Creates 6 tables:
  - competition:      all rows from data/<season>/generated/competition/*.csv
  - players:          from data/<season>/generated/players/csv/players.csv
  - games:            from data/<season>/generated/flatboxscores/boxscores.csv
  - points_5v5:       5v5 goals/assists from flatplays CSVs
  - elite_forwards:   per-team elite forward classification (tTOI%, iTOI%, P/60 model)
  - player_metrics:   PPI, PPI+, wPPI, wPPI+, avg_toi_share per eligible skater (GP >= 5)

After building elite_forwards, pct_vs_top_fwd in the competition table is
overwritten with the fraction of opposing forwards who are in the elite set.

Usage:
    python v2/browser/build_league_db.py          # defaults to 2025
    python v2/browser/build_league_db.py 2024      # builds 2024 database
"""
```

**Step 2: Update `main()` — add new function calls**

In `main()`, add the two new calls between `build_points_5v5_table` and `build_player_metrics_table`:

```python
def main():
    os.makedirs(os.path.dirname(OUTPUT_DB), exist_ok=True)
    if os.path.exists(OUTPUT_DB):
        os.remove(OUTPUT_DB)
        print(f"Removed existing {OUTPUT_DB}")
    conn = sqlite3.connect(OUTPUT_DB)
    try:
        print(f"Building {OUTPUT_DB} ...\n")
        build_competition_table(conn)
        build_players_table(conn)
        _recover_missing_players(conn)
        build_games_table(conn)
        build_points_5v5_table(conn)
        build_elite_forwards_table(conn)
        recompute_pct_vs_elite_fwd(conn)
        build_player_metrics_table(conn)
    finally:
        conn.close()
    size_mb = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print(f"\nDone. Database: {OUTPUT_DB} ({size_mb:.1f} MB)")
```

**Step 3: Run full test suite**

Run: `python -m pytest v2/ -v`

Expected: All tests pass (86 existing + 7 new = 93 total).

**Step 4: Run full DB build**

Run: `python v2/browser/build_league_db.py 2025`

Expected output includes lines like:
```
  elite_forwards: 88 players + 3 carry-overs
  pct_vs_elite_fwd: updated ~39058 rows across 1085 games
```

**Step 5: Spot-check results**

Run:
```bash
sqlite3 data/2025/generated/browser/league.db "SELECT playerId, team, p60, rank, is_carryover FROM elite_forwards ORDER BY team, rank"
```

Verify McDavid/Draisaitl/Hyman on EDM, Kucherov/Point/Hagel/Guentzel on TBL, Panarin carry-over on LAK.

Run:
```bash
sqlite3 data/2025/generated/browser/league.db "SELECT AVG(pct_vs_top_fwd) FROM competition WHERE position = 'F'"
```

The average should be noticeably lower than the old value (since we went from top-6 → ~3 elite per team, the fraction of time against "top" players drops).
