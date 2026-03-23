# Elite Defensemen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add elite defenseman classification to `build_league_db.py` with two distinct designations (production and deployment), replace `pct_vs_top_def` with elite-model-based values, and backfill a competition quality metric onto the elite forwards table.

**Architecture:** Three new functions in `build_league_db.py`: (1) `build_elite_defensemen_table` classifies defensemen using separate production (talent-driven: P/60 + tTOI% + iTOI%) and deployment (coaching-driven: highest vs-elite-forward rate) designations, then promotes production elites to full elite when they demonstrably play as a pair with the deployment elite; (2) `recompute_pct_vs_elite_def` re-reads all timeline CSVs and replaces `competition.pct_vs_top_def` with the fraction of opposing deployment-elite defensemen, plus a binary `pct_any_elite_def` column; (3) `backfill_vs_elite_def_to_forwards` averages `pct_any_elite_def` per elite forward and stores it in `elite_forwards.vs_ed_pct`. No changes to `compute_competition.py`.

**Tech Stack:** Python, SQLite, pandas, csv (stdlib)

**Design doc:** `docs/elite-classification-model.md`

**Key reference files:**
- `v2/browser/build_league_db.py` — main file to modify
- `v2/browser/tests/test_player_metrics.py` — test file to extend
- `data/<season>/generated/timelines/csv/<gameId>.csv` — columns: `period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,awayGoalie,awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters`

**Git:** Do not commit. oiler handles all git operations manually.

---

## File Map

| File | Change |
|------|--------|
| `v2/browser/build_league_db.py` | Add `build_elite_defensemen_table`, `recompute_pct_vs_elite_def`, `backfill_vs_elite_def_to_forwards`; update `main()` |
| `v2/browser/tests/test_player_metrics.py` | Extend import; add `_setup_elite_def_db()` helper + 10 tests |

**Note:** A separate elite changelog plan (`2026-03-23-elite-changelog-plan.md`) adds `_read_old_elites` and `_log_elite_changes` to this file and extends `main()` further. That plan should be executed after this one. The import and `main()` blocks in this plan reflect the state after the defensemen feature only.

---

## Background: The Two Designations

Defensemen have two elite archetypes that don't always overlap:

- **Production elite** — talent-driven. Best offensive D by P/60, max one per team. Criteria: GP ≥ 20, tTOI% ≥ 33, iTOI% < 83, P/60 ≥ 1.25. Rank by P/60, keep rank 1 only.
- **Deployment elite** — coaching-driven. The D who faces the most elite forwards, exactly one per team. Criteria: GP ≥ 20, tTOI% ≥ 33, iTOI% < 90, highest avg `pct_any_elite_fwd`.
- **Full elite** — production D who is also the deployment D, OR whose vs-elite-forward rate is within 1.5 percentage points of the deployment D (indicating they play as a pair and absorb the same matchups).

The `recompute_pct_vs_elite_def` step uses deployment-elite (not full-elite) as the "elite" set — because deployment designation directly answers "who faces the hardest matchups."

---

### Task 1: Write failing tests — `build_elite_defensemen_table`

**Files:**
- Modify: `v2/browser/tests/test_player_metrics.py`

- [ ] **Step 1: Extend imports**

Add the three new functions to the import at the top of the test file. The full import after this step:

```python
from build_league_db import (
    build_player_metrics_table, _recover_missing_players,
    build_elite_forwards_table, recompute_pct_vs_elite_fwd,
    build_elite_defensemen_table, recompute_pct_vs_elite_def,
    backfill_vs_elite_def_to_forwards,
)
```

(The elite changelog plan adds `_read_old_elites, _log_elite_changes` in a subsequent step — don't add those yet.)

- [ ] **Step 2: Add `_make_comp_row` helper**

Add before the elite defensemen tests — keeps test data concise:

```python
def _make_comp_row(pid, team, game, position, toi, total_toi):
    """Build a full competition row with zeros for non-essential columns."""
    return {
        "gameId": game, "playerId": pid, "team": team, "position": position,
        "toi_seconds": toi, "total_toi_seconds": total_toi,
        "pct_vs_top_fwd": 0.0, "pct_vs_top_def": 0.0,
        "comp_fwd": 0, "comp_def": 0,
        "height_in": 72, "weight_lbs": 198,
        "heaviness": 0, "weighted_forward_heaviness": 0,
        "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0,
    }
```

- [ ] **Step 3: Add `_setup_elite_def_db()` helper**

This builds three teams with carefully controlled tTOI%, iTOI%, P/60, and `pct_any_elite_fwd` values to hit every designation path:

```python
def _setup_elite_def_db():
    """In-memory DB with 3 teams (TMA, TMB, TMC), 25 games each.

    TMA — separate production + deployment (gap > 1.5pp):
      D1 (213): toi=1100, total=1500 (iTOI=73.3%), vs_ef=0.30, 12 pts → P/60=1.57. Production elite.
      D2 (214): toi=1050, total=1200 (iTOI=87.5%), vs_ef=0.32. Deployment elite (fails prod: iTOI>=83).
      Gap = 2.0pp → too large for full elite.
      D3 (215): toi=1000, total=1200 (iTOI=83.3%), vs_ef=0.15, 10 pts. Fails iTOI for production.
      D4-D6 (216-218): toi=800, total=950 — below 33% tTOI.

    TMB — full elite via gap rule (gap < 1.5pp):
      D1 (313): toi=1100, total=1500 (iTOI=73.3%), vs_ef=0.34, 12 pts → P/60=1.57. Production elite.
      D2 (314): toi=1000, total=1200 (iTOI=83.3%), vs_ef=0.35. Deployment elite (highest vs_ef).
      Gap = 1.0pp → pair plays together → 313 promoted to full elite.
      D3-D6 (315-318): toi=900, total=1100 — below 33% tTOI.

    TMC — no production elite (deployment only):
      D1 (413): toi=1050, total=1200 (iTOI=87.5%), vs_ef=0.28. Deployment only (fails prod: iTOI>=83).
      D2 (414): toi=1000, total=1200 (iTOI=83.3%), vs_ef=0.20. Fails everything.
      D3-D6 (415-418): toi=800, total=950.
    """
    conn = sqlite3.connect(":memory:")
    comp_rows = []

    for game in range(1, 26):      # TMA
        for pid in range(201, 213):
            comp_rows.append(_make_comp_row(pid, "TMA", game, "F", 700, 850))
        comp_rows.append(_make_comp_row(213, "TMA", game, "D", 1100, 1500))
        comp_rows.append(_make_comp_row(214, "TMA", game, "D", 1050, 1200))
        comp_rows.append(_make_comp_row(215, "TMA", game, "D", 1000, 1200))  # iTOI=83.3%
        for pid in range(216, 219):
            comp_rows.append(_make_comp_row(pid, "TMA", game, "D", 800, 950))

    for game in range(101, 126):   # TMB
        for pid in range(301, 313):
            comp_rows.append(_make_comp_row(pid, "TMB", game, "F", 700, 850))
        comp_rows.append(_make_comp_row(313, "TMB", game, "D", 1100, 1500))
        comp_rows.append(_make_comp_row(314, "TMB", game, "D", 1000, 1200))
        for pid in range(315, 319):
            comp_rows.append(_make_comp_row(pid, "TMB", game, "D", 900, 1100))

    for game in range(201, 226):   # TMC
        for pid in range(401, 413):
            comp_rows.append(_make_comp_row(pid, "TMC", game, "F", 700, 850))
        comp_rows.append(_make_comp_row(413, "TMC", game, "D", 1050, 1200))
        comp_rows.append(_make_comp_row(414, "TMC", game, "D", 1000, 1200))
        for pid in range(415, 419):
            comp_rows.append(_make_comp_row(pid, "TMC", game, "D", 800, 950))

    df = pd.DataFrame(comp_rows)
    # Set pct_any_elite_fwd for deployment selection (binary metric)
    df["pct_any_elite_fwd"] = 0.0
    df.loc[df["playerId"] == 213, "pct_any_elite_fwd"] = 0.30
    df.loc[df["playerId"] == 214, "pct_any_elite_fwd"] = 0.32
    df.loc[df["playerId"] == 215, "pct_any_elite_fwd"] = 0.15
    df.loc[df["playerId"] == 313, "pct_any_elite_fwd"] = 0.34
    df.loc[df["playerId"] == 314, "pct_any_elite_fwd"] = 0.35
    df.loc[df["playerId"] == 413, "pct_any_elite_fwd"] = 0.28
    df.loc[df["playerId"] == 414, "pct_any_elite_fwd"] = 0.20
    df.to_sql("competition", conn, index=False, if_exists="replace")

    point_rows = []
    for i in range(12):   # TMA D1 (213): 12 pts → P/60=1.57
        point_rows.append({"gameId": (i % 25) + 1, "playerId": 213,
                           "goals": 1, "assists": 0, "points": 1})
    for i in range(12):   # TMB D1 (313): 12 pts
        point_rows.append({"gameId": (i % 25) + 101, "playerId": 313,
                           "goals": 1, "assists": 0, "points": 1})
    for i in range(10):   # TMA D3 (215): 10 pts — passes P/60 threshold but fails iTOI
        point_rows.append({"gameId": (i % 25) + 1, "playerId": 215,
                           "goals": 1, "assists": 0, "points": 1})
    pd.DataFrame(point_rows).to_sql("points_5v5", conn, index=False, if_exists="replace")
    return conn
```

- [ ] **Step 4: Add classification tests**

```python
def test_elite_defensemen_table_created():
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "elite_defensemen" in tables


def test_elite_def_production_selected():
    """TMA pid 213 is production elite (iTOI=73.3%, P/60=1.57). pid 214 is not (iTOI=87.5%)."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row213 = conn.execute(
        "SELECT is_production FROM elite_defensemen WHERE playerId = 213"
    ).fetchone()
    assert row213 is not None
    assert row213[0] == 1
    row214 = conn.execute(
        "SELECT is_production FROM elite_defensemen WHERE playerId = 214"
    ).fetchone()
    # 214 may or may not appear in the table, but if present, is_production must be 0
    if row214 is not None:
        assert row214[0] == 0


def test_elite_def_itoi_filter():
    """pid 214 (iTOI=87.5%) is excluded from production despite tTOI and vs_ef."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row = conn.execute(
        "SELECT is_production FROM elite_defensemen WHERE playerId = 214"
    ).fetchone()
    assert row is not None
    assert row[0] == 0


def test_elite_def_deployment_selected():
    """TMA pid 214 has highest vs_ef (0.32) → deployment elite. pid 213 is not deployment."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row214 = conn.execute(
        "SELECT is_deployment FROM elite_defensemen WHERE playerId = 214"
    ).fetchone()
    assert row214 is not None and row214[0] == 1
    row213 = conn.execute(
        "SELECT is_deployment FROM elite_defensemen WHERE playerId = 213"
    ).fetchone()
    assert row213 is not None and row213[0] == 0


def test_elite_def_full_elite():
    """TMB pid 313 is production elite; gap to deployment elite (314) is 1.0pp < 1.5pp → is_full_elite=1."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row = conn.execute(
        "SELECT is_production, is_deployment, is_full_elite FROM elite_defensemen WHERE playerId = 313"
    ).fetchone()
    assert row is not None
    assert row[0] == 1  # is_production
    assert row[1] == 0  # is_deployment (314 has higher vs_ef)
    assert row[2] == 1  # is_full_elite (gap < 1.5pp)


def test_elite_def_gap_too_large():
    """TMA pid 213 is production elite but gap to deployment elite (214) is 2.0pp → NOT full elite."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    row = conn.execute(
        "SELECT is_production, is_deployment, is_full_elite FROM elite_defensemen WHERE playerId = 213"
    ).fetchone()
    assert row is not None
    assert row[0] == 1  # is_production
    assert row[1] == 0  # is_deployment
    assert row[2] == 0  # NOT full elite


def test_elite_def_no_production():
    """TMC has 0 production elite (iTOI filter), 1 deployment elite (pid 413)."""
    conn = _setup_elite_def_db()
    build_elite_defensemen_table(conn)
    prod = conn.execute(
        "SELECT COUNT(*) FROM elite_defensemen WHERE team = 'TMC' AND is_production = 1"
    ).fetchone()[0]
    assert prod == 0
    dep_pid = conn.execute(
        "SELECT playerId FROM elite_defensemen WHERE team = 'TMC' AND is_deployment = 1"
    ).fetchone()[0]
    assert dep_pid == 413
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -k "elite_def" -v`

Expected: FAIL — `ImportError: cannot import name 'build_elite_defensemen_table'` (7 collection errors)

---

### Task 2: Implement `build_elite_defensemen_table`

**Files:**
- Modify: `v2/browser/build_league_db.py` (insert after `recompute_pct_vs_elite_fwd`)

- [ ] **Step 1: Add the function**

The function runs a single SQL query for per-(player, team) stats, then applies production and deployment selection separately, merges them, and computes the full-elite flag.

```python
def build_elite_defensemen_table(conn):
    """Identify elite defensemen per team with two designations:

    Production elite (talent-driven):
      - GP >= 20, tTOI% >= 33, iTOI% < 83, P/60 >= 1.25
      - Ranked by P/60 within team, keep only rank 1 (max 1 per team)

    Deployment elite (coaching-driven):
      - GP >= 20, tTOI% >= 33, iTOI% < 90
      - Per team, the D with the highest avg pct_vs_top_fwd (vs elite forwards)

    Full elite: production D whose vs_ef gap to the team's deployment elite
    is < 1.5 percentage points (indicating they play as a pair).
    A player who is both production and deployment elite is also full elite.
    """
    stats_sql = """
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
        COALESCE(pp.total_pts, 0) * 3600.0 / SUM(c.toi_seconds) as p60,
        AVG(c.pct_any_elite_fwd) as vs_ef_pct
    FROM competition c
    JOIN team_totals tt ON tt.gameId = c.gameId AND tt.team = c.team
    LEFT JOIN player_points pp ON pp.playerId = c.playerId
    WHERE c.position = 'D'
    GROUP BY c.playerId, c.team
    HAVING gp >= 20
    """
    df = pd.read_sql_query(stats_sql, conn)
    if df.empty:
        print("  elite_defensemen: 0 rows (no qualifying defensemen)")
        return

    # --- Production elite: rank by P/60, keep rank 1 per team ---
    prod = df[
        (df["ttoi_pct"] >= 33)
        & (df["itoi_pct"] < 83)
        & (df["p60"] >= 1.25)
    ].copy()
    if not prod.empty:
        prod["rank"] = prod.groupby("team")["p60"].rank(
            ascending=False, method="first"
        ).astype(int)
        prod = prod[prod["rank"] == 1].copy()
        prod["is_production"] = 1
    else:
        prod = pd.DataFrame()

    # --- Deployment elite: highest vs_ef per team ---
    dep = df[(df["ttoi_pct"] >= 33) & (df["itoi_pct"] < 90)].copy()
    if not dep.empty:
        dep = dep.loc[dep.groupby("team")["vs_ef_pct"].idxmax()].copy()
        dep["is_deployment"] = 1
    else:
        dep = pd.DataFrame()

    if prod.empty and dep.empty:
        print("  elite_defensemen: 0 rows (no defensemen pass filters)")
        return

    # --- Merge production + deployment ---
    key_cols = ["playerId", "team"]
    stat_cols = ["gp", "toi_min_gp", "ttoi_pct", "itoi_pct", "p60", "vs_ef_pct"]
    if not prod.empty and not dep.empty:
        combined = pd.merge(
            prod[key_cols + stat_cols + ["rank", "is_production"]],
            dep[key_cols + ["is_deployment"]],
            on=key_cols, how="outer",
        )
        # Fill stats for deployment-only rows from df
        dep_only = combined["gp"].isna()
        if dep_only.any():
            dep_pids = combined.loc[dep_only, key_cols]
            dep_stats = pd.merge(dep_pids, df, on=key_cols)
            for col in stat_cols:
                combined.loc[dep_only, col] = dep_stats[col].values
            combined.loc[dep_only, "rank"] = 0
    elif not prod.empty:
        combined = prod[key_cols + stat_cols + ["rank", "is_production"]].copy()
        combined["is_deployment"] = 0
    else:
        combined = dep[key_cols + stat_cols].copy()
        combined["is_production"] = 0
        combined["is_deployment"] = 1
        combined["rank"] = 0

    combined["is_production"] = combined.get("is_production", 0).fillna(0).astype(int)
    combined["is_deployment"] = combined.get("is_deployment", 0).fillna(0).astype(int)

    # --- Full elite: production + deployment together, or vs_ef gap < 1.5pp ---
    dep_vs_ef = (
        combined[combined["is_deployment"] == 1]
        .set_index("team")["vs_ef_pct"]
        .to_dict()
    )

    def _is_full_elite(row):
        if row["is_production"] == 1 and row["is_deployment"] == 1:
            return 1
        if row["is_production"] == 1 and row["team"] in dep_vs_ef:
            if abs(row["vs_ef_pct"] - dep_vs_ef[row["team"]]) < 0.015:
                return 1
        return 0

    combined["is_full_elite"] = combined.apply(_is_full_elite, axis=1)
    combined["rank"] = combined["rank"].fillna(0).astype(int)
    combined["is_carryover"] = 0

    # --- Trade carry-over (production elites only) ---
    prod_pids = set(combined[combined["is_production"] == 1]["playerId"].unique())
    if prod_pids:
        all_teams_for_pid = pd.read_sql_query(
            "SELECT DISTINCT playerId, team FROM competition WHERE position = 'D'",
            conn,
        )
        carryover_rows = []
        for pid in prod_pids:
            elite_teams = set(combined[combined["playerId"] == pid]["team"])
            all_teams = set(all_teams_for_pid[all_teams_for_pid["playerId"] == pid]["team"])
            for team in all_teams - elite_teams:
                src = combined[combined["playerId"] == pid].sort_values(
                    "gp", ascending=False
                ).iloc[0]
                carry = src.to_dict()
                carry["team"] = team
                carry["rank"] = 0
                carry["is_carryover"] = 1
                carryover_rows.append(carry)
        if carryover_rows:
            combined = pd.concat(
                [combined, pd.DataFrame(carryover_rows)], ignore_index=True
            )

    out_cols = [
        "playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
        "p60", "vs_ef_pct", "is_production", "is_deployment", "is_full_elite",
        "rank", "is_carryover",
    ]
    combined[out_cols].to_sql("elite_defensemen", conn, if_exists="replace", index=False)

    n_prod = int(combined["is_production"].sum())
    n_dep = int(combined["is_deployment"].sum())
    n_full = int(combined["is_full_elite"].sum())
    print(f"  elite_defensemen: {len(combined)} rows ({n_prod} production, {n_dep} deployment, {n_full} full elite)")
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -k "elite_def" -v`

Expected: All 7 classification tests PASS.

---

### Task 3: Write failing tests — `recompute_pct_vs_elite_def`

**Files:**
- Modify: `v2/browser/tests/test_player_metrics.py`

The function needs to be tested against a real timeline CSV. The key behaviors to verify: fractional metric (`pct_vs_top_def`), binary metric (`pct_any_elite_def`), and correct attribution to both away and home skaters.

- [ ] **Step 1: Add fractional + binary metric test**

```python
def test_recompute_pct_vs_elite_def(tmp_path, monkeypatch):
    """
    Game 2001: TMA (away) vs TMB (home).
    Away: 3F + D213 (deployment elite) + D214 (not elite)
    Home: 3F + D313 (deployment elite) + D314 (not elite)

    For any away skater: opposing D are 313 (elite) + 314 (not) → fraction = 1/2, binary = 1
    For any home skater: opposing D are 213 (elite) + 214 (not) → fraction = 1/2, binary = 1
    """
    import build_league_db

    conn = sqlite3.connect(":memory:")
    comp_rows = []
    for pid, team, pos in [
        (201, "TMA", "F"), (202, "TMA", "F"), (203, "TMA", "F"),
        (213, "TMA", "D"), (214, "TMA", "D"),
        (301, "TMB", "F"), (302, "TMB", "F"), (303, "TMB", "F"),
        (313, "TMB", "D"), (314, "TMB", "D"),
    ]:
        comp_rows.append({"playerId": pid, "team": team, "gameId": 2001,
                          "position": pos, "toi_seconds": 100,
                          "total_toi_seconds": 120, "pct_vs_top_fwd": 0.0,
                          "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                          "height_in": 72, "weight_lbs": 198,
                          "heaviness": 0, "weighted_forward_heaviness": 0,
                          "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")

    # 213 and 313 are deployment elite
    pd.DataFrame([
        {"playerId": 213, "team": "TMA", "gp": 25, "toi_min_gp": 18.0,
         "ttoi_pct": 40.0, "itoi_pct": 73.0, "p60": 1.5, "vs_ef_pct": 0.30,
         "is_production": 1, "is_deployment": 1, "is_full_elite": 1, "rank": 1, "is_carryover": 0},
        {"playerId": 313, "team": "TMB", "gp": 25, "toi_min_gp": 18.0,
         "ttoi_pct": 40.0, "itoi_pct": 73.0, "p60": 1.5, "vs_ef_pct": 0.35,
         "is_production": 1, "is_deployment": 1, "is_full_elite": 1, "rank": 1, "is_carryover": 0},
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")

    timelines_dir = tmp_path / "generated" / "timelines" / "csv"
    timelines_dir.mkdir(parents=True)
    (timelines_dir / "2001.csv").write_text(
        "period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,"
        "awayGoalie,awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters\n"
        "1,0,0,1551,5v5,99,5,201|202|203|213|214,5,98,301|302|303|313|314\n"
        "1,1,1,1551,5v5,99,5,201|202|203|213|214,5,98,301|302|303|313|314\n"
        "1,2,2,1551,5v5,99,5,201|202|203|213|214,5,98,301|302|303|313|314\n"
    )

    monkeypatch.setattr(build_league_db, "SEASON_DIR", str(tmp_path))
    recompute_pct_vs_elite_def(conn)

    row201 = conn.execute(
        "SELECT pct_vs_top_def FROM competition WHERE playerId = 201"
    ).fetchone()
    assert abs(row201[0] - 0.5) < 0.001, f"Expected 0.5, got {row201[0]}"

    bin201 = conn.execute(
        "SELECT pct_any_elite_def FROM competition WHERE playerId = 201"
    ).fetchone()
    assert abs(bin201[0] - 1.0) < 0.001, f"Expected 1.0, got {bin201[0]}"
```

- [ ] **Step 2: Add binary metric partial-presence test**

```python
def test_pct_any_elite_def_binary_metric(tmp_path, monkeypatch):
    """Binary metric: 2 seconds with elite D on ice, 2 without → 0.5."""
    import build_league_db

    conn = sqlite3.connect(":memory:")
    comp_rows = []
    for pid, team, pos in [
        (501, "AAA", "F"), (502, "AAA", "F"), (503, "AAA", "D"), (504, "AAA", "D"),
        (601, "BBB", "F"), (602, "BBB", "F"), (603, "BBB", "D"), (604, "BBB", "D"),
    ]:
        comp_rows.append({"playerId": pid, "team": team, "gameId": 3001,
                          "position": pos, "toi_seconds": 100,
                          "total_toi_seconds": 120, "pct_vs_top_fwd": 0.0,
                          "pct_vs_top_def": 0.0, "comp_fwd": 0, "comp_def": 0,
                          "height_in": 72, "weight_lbs": 198,
                          "heaviness": 0, "weighted_forward_heaviness": 0,
                          "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")

    pd.DataFrame([
        {"playerId": 603, "team": "BBB", "gp": 25, "toi_min_gp": 18.0,
         "ttoi_pct": 40.0, "itoi_pct": 73.0, "p60": 1.5, "vs_ef_pct": 0.30,
         "is_production": 0, "is_deployment": 1, "is_full_elite": 0, "rank": 0, "is_carryover": 0},
    ]).to_sql("elite_defensemen", conn, index=False, if_exists="replace")

    timelines_dir = tmp_path / "generated" / "timelines" / "csv"
    timelines_dir.mkdir(parents=True)
    (timelines_dir / "3001.csv").write_text(
        "period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,"
        "awayGoalie,awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters\n"
        "1,0,0,1551,5v5,99,4,501|502|503|504,4,98,601|602|603|604\n"
        "1,1,1,1551,5v5,99,4,501|502|503|504,4,98,601|602|603|604\n"
        "1,2,2,1551,5v5,99,4,501|502|503|504,4,98,601|602|604|605\n"
        "1,3,3,1551,5v5,99,4,501|502|503|504,4,98,601|602|604|605\n"
    )

    monkeypatch.setattr(build_league_db, "SEASON_DIR", str(tmp_path))
    recompute_pct_vs_elite_def(conn)

    row = conn.execute(
        "SELECT pct_any_elite_def FROM competition WHERE playerId = 501"
    ).fetchone()
    assert abs(row[0] - 0.5) < 0.001, f"Expected 0.5, got {row[0]}"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -k "pct_vs_elite_def or pct_any_elite_def" -v`

Expected: FAIL — `ImportError: cannot import name 'recompute_pct_vs_elite_def'`

---

### Task 4: Implement `recompute_pct_vs_elite_def`

**Files:**
- Modify: `v2/browser/build_league_db.py` (insert after `build_elite_defensemen_table`)

The function mirrors `recompute_pct_vs_elite_fwd` but targets the deployment-elite defensemen set. It also adds a `pct_any_elite_def` binary column (1 if any elite D is on the opposing side that second, 0 otherwise).

- [ ] **Step 1: Add the function**

```python
def recompute_pct_vs_elite_def(conn):
    """Replace pct_vs_top_def with fraction of opposing D who are deployment elite.

    Also computes pct_any_elite_def — binary: 1 if any elite D on opposing side
    each second, 0 otherwise. Averaged per game per player.
    """
    elite_rows = conn.execute(
        "SELECT playerId FROM elite_defensemen WHERE is_deployment = 1"
    ).fetchall()
    if not elite_rows:
        print("  pct_vs_elite_def: skipped (no elite defensemen)")
        return
    elite_set = {r[0] for r in elite_rows}

    # Ensure pct_any_elite_def column exists
    cols = {r[1] for r in conn.execute("PRAGMA table_info(competition)").fetchall()}
    if "pct_any_elite_def" not in cols:
        conn.execute("ALTER TABLE competition ADD COLUMN pct_any_elite_def REAL DEFAULT 0.0")
        conn.commit()

    pos_rows = conn.execute(
        "SELECT gameId, playerId, position FROM competition"
    ).fetchall()
    game_positions = {}
    game_ids = set()
    for gid, pid, pos in pos_rows:
        game_ids.add(gid)
        game_positions.setdefault(gid, {})[pid] = pos

    timelines_dir = os.path.join(SEASON_DIR, "generated", "timelines", "csv")
    frac_updates = []
    binary_updates = []

    for game_id in sorted(game_ids):
        timeline_path = os.path.join(timelines_dir, f"{game_id}.csv")
        if not os.path.exists(timeline_path):
            continue

        positions = game_positions.get(game_id, {})
        frac_accum = {}
        binary_accum = {}

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

                    opp_defs = [p for p in opponents if positions.get(p) == "D"]
                    if not opp_defs:
                        continue

                    elite_count = sum(1 for p in opp_defs if p in elite_set)
                    frac_accum.setdefault(player_id, []).append(elite_count / len(opp_defs))
                    binary_accum.setdefault(player_id, []).append(1 if elite_count > 0 else 0)

        for pid, fracs in frac_accum.items():
            frac_updates.append((round(sum(fracs) / len(fracs), 4), game_id, pid))
        for pid, bins in binary_accum.items():
            binary_updates.append((round(sum(bins) / len(bins), 4), game_id, pid))

    if frac_updates:
        conn.executemany(
            "UPDATE competition SET pct_vs_top_def = ? WHERE gameId = ? AND playerId = ?",
            frac_updates,
        )
    if binary_updates:
        conn.executemany(
            "UPDATE competition SET pct_any_elite_def = ? WHERE gameId = ? AND playerId = ?",
            binary_updates,
        )
    conn.commit()
    print(f"  pct_vs_elite_def: updated {len(frac_updates)} rows across {len(game_ids)} games")
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -k "pct_vs_elite_def or pct_any_elite_def" -v`

Expected: 2 PASS.

---

### Task 5: Write failing test + implement `backfill_vs_elite_def_to_forwards`

**Files:**
- Modify: `v2/browser/tests/test_player_metrics.py`
- Modify: `v2/browser/build_league_db.py`

This function averages `pct_any_elite_def` per elite forward (per team) and stores it in a new `vs_ed_pct` column on `elite_forwards`. It gives each elite forward a career-level number: "what fraction of your ice time was spent facing at least one elite defenseman?"

- [ ] **Step 1: Write the failing test**

```python
def test_backfill_vs_elite_def_to_forwards():
    """backfill_vs_elite_def_to_forwards adds vs_ed_pct column to elite_forwards."""
    conn = sqlite3.connect(":memory:")

    comp_rows = []
    for game in range(1, 4):
        comp_rows.append({"playerId": 1, "team": "EDM", "gameId": game,
                          "position": "F", "toi_seconds": 900,
                          "total_toi_seconds": 1200, "pct_vs_top_fwd": 0.0,
                          "pct_vs_top_def": 0.0, "pct_any_elite_def": 0.6,
                          "comp_fwd": 0, "comp_def": 0, "height_in": 72, "weight_lbs": 198,
                          "heaviness": 0, "weighted_forward_heaviness": 0,
                          "weighted_defense_heaviness": 0, "weighted_team_heaviness": 0})
    pd.DataFrame(comp_rows).to_sql("competition", conn, index=False, if_exists="replace")

    pd.DataFrame([
        {"playerId": 1, "team": "EDM", "gp": 25, "toi_min_gp": 15.0,
         "ttoi_pct": 33.0, "itoi_pct": 75.0, "p60": 2.4, "rank": 1, "is_carryover": 0},
    ]).to_sql("elite_forwards", conn, index=False, if_exists="replace")

    backfill_vs_elite_def_to_forwards(conn)

    row = conn.execute("SELECT vs_ed_pct FROM elite_forwards WHERE playerId = 1").fetchone()
    assert row is not None
    assert abs(row[0] - 0.6) < 0.001, f"Expected 0.6, got {row[0]}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py::test_backfill_vs_elite_def_to_forwards -v`

Expected: FAIL — `ImportError: cannot import name 'backfill_vs_elite_def_to_forwards'`

- [ ] **Step 3: Implement the function**

```python
def backfill_vs_elite_def_to_forwards(conn):
    """Add vs_ed_pct to elite_forwards: avg pct_any_elite_def per forward."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(elite_forwards)").fetchall()}
    if "vs_ed_pct" not in cols:
        conn.execute("ALTER TABLE elite_forwards ADD COLUMN vs_ed_pct REAL DEFAULT 0.0")
        conn.commit()

    updates = conn.execute(
        "SELECT c.playerId, c.team, AVG(c.pct_any_elite_def) "
        "FROM competition c "
        "JOIN elite_forwards e ON c.playerId = e.playerId AND c.team = e.team "
        "WHERE c.position = 'F' "
        "GROUP BY c.playerId, c.team"
    ).fetchall()

    if updates:
        conn.executemany(
            "UPDATE elite_forwards SET vs_ed_pct = ? WHERE playerId = ? AND team = ?",
            [(round(r[2], 4), r[0], r[1]) for r in updates],
        )
        conn.commit()
    print(f"  vs_elite_def → elite_forwards: backfilled {len(updates)} rows")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py::test_backfill_vs_elite_def_to_forwards -v`

Expected: PASS.

---

### Task 6: Wire into `main()` and run full suite

**Files:**
- Modify: `v2/browser/build_league_db.py`

- [ ] **Step 1: Update the module docstring**

The docstring at the top of the file lists the tables the build creates. Add `elite_defensemen` to the list and document the new build-order steps:

```python
"""
Build a league-wide SQLite database for the NHL Data Browser.

Creates 7 tables:
  - competition:      all rows from data/<season>/generated/competition/*.csv
  - players:          from data/<season>/generated/players/csv/players.csv
  - games:            from data/<season>/generated/flatboxscores/boxscores.csv
  - points_5v5:       5v5 goals/assists from flatplays CSVs
  - elite_forwards:   per-team elite forward classification (tTOI%, iTOI%, P/60 model)
  - elite_defensemen: per-team elite defensemen (production + deployment designations)
  - player_metrics:   PPI, PPI+, wPPI, wPPI+, avg_toi_share per eligible skater (GP >= 5)

After building elite_forwards, pct_vs_top_fwd in the competition table is
overwritten with the fraction of opposing forwards who are in the elite set.
After building elite_defensemen, pct_vs_top_def is similarly recomputed, and
a binary pct_any_elite_def column is added.

Usage:
    python v2/browser/build_league_db.py          # defaults to 2025
    python v2/browser/build_league_db.py 2024      # builds 2024 database
"""
```

- [ ] **Step 2: Update `main()`**

Insert the three new calls after `recompute_pct_vs_elite_fwd`. The elite changelog plan adds further calls around `main()` (snapshot + log), but that comes after this plan.

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
        build_elite_defensemen_table(conn)      # NEW
        recompute_pct_vs_elite_def(conn)        # NEW
        backfill_vs_elite_def_to_forwards(conn) # NEW
        build_player_metrics_table(conn)
    finally:
        conn.close()
    size_mb = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print(f"\nDone. Database: {OUTPUT_DB} ({size_mb:.1f} MB)")
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest v2/ -v`

Expected: All tests pass.

- [ ] **Step 4: Run full DB build**

Run: `python v2/browser/build_league_db.py 2025`

Expected output includes:
```
  elite_defensemen: 45 rows (18 production, 33 deployment, 13 full elite)
  pct_vs_elite_def: updated 39778 rows across 1105 games
  vs_elite_def → elite_forwards: backfilled 50 rows
```

- [ ] **Step 5: Spot-check results**

```bash
sqlite3 data/2025/generated/browser/league.db \
  "SELECT playerId, team, is_production, is_deployment, is_full_elite, vs_ef_pct
   FROM elite_defensemen WHERE team = 'EDM'"
```

Expect Evan Bouchard (production) and Mattias Ekholm (deployment) — both marked `is_full_elite=1` because their vs_ef gap is ~0.04pp.

```bash
sqlite3 data/2025/generated/browser/league.db \
  "SELECT playerId, team, vs_ed_pct FROM elite_forwards ORDER BY vs_ed_pct DESC LIMIT 10"
```

Expect elite forwards on teams with strong defensive pairings to show higher `vs_ed_pct`.
