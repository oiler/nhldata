# PPI Metrics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the `heaviness` metric with 4 PPI metrics (PPI, PPI+, wPPI, wPPI+) per `resources/heaviness_calculations.md`, and update all browser pages to display them.

**Architecture:** A new `player_metrics` table in `league.db` stores all 4 computed season-level metrics per eligible player (GP ≥ 5, positions F/D). Browser pages join to this table via `c.playerId = pm.playerId`. Game pages show team-level PPI and wPPI aggregates in a summary table; skaters and team pages show individual player metrics.

**Tech Stack:** Python, pandas, SQLite, Plotly Dash, `dash.dash_table.Format`

---

## Metric Definitions

All metrics are season-level, eligible pool = skaters with position IN ('F', 'D') AND GP ≥ 5.

```
PPI_i       = weight_lbs_i / height_in_i

mean_PPI    = mean(PPI across eligible players)
PPI+_i      = 100 × (PPI_i / mean_PPI)

TOI_i,t     = sum of toi_seconds for player i on team t (5v5 only)
TOI_team,t  = sum of toi_seconds for all ELIGIBLE skaters on team t
share_i,t   = TOI_i,t / TOI_team,t
wPPI_i      = Σ_t (PPI_i × share_i,t)   [sum across all team stints]

mean_wPPI   = mean(wPPI across eligible players)
wPPI+_i     = 100 × (wPPI_i / mean_wPPI)
```

Physical data source: `height_in` and `weight_lbs` columns already in the `competition` table (use `MAX()` per player to get a single value).

---

## Files to Modify

| File | Change |
|------|--------|
| `v2/browser/build_league_db.py` | Add `build_player_metrics_table(conn)`, call in `main()` |
| `v2/browser/tests/test_smoke.py` | Add `player_metrics` to expected tables check |
| `v2/browser/tests/test_player_metrics.py` | New — unit tests for metric computation |
| `v2/browser/pages/game.py` | Rename 3 heaviness cols → PPI; add 3 wPPI cols |
| `v2/browser/pages/skaters.py` | Replace `heaviness` with all 4 metrics |
| `v2/browser/pages/team.py` | Replace `heaviness` with all 4 metrics |

---

## Task 1: Compute PPI Metrics in build_league_db.py

**Files:**
- Modify: `v2/browser/build_league_db.py`
- Modify: `v2/browser/tests/test_smoke.py`
- Create: `v2/browser/tests/test_player_metrics.py`

---

### Step 1: Add player_metrics to the smoke test table check

In `test_smoke.py`, find `test_league_db_exists`. Add one assertion:

```python
assert "player_metrics" in tables
```

The full updated assertion block:
```python
assert "competition" in tables
assert "players" in tables
assert "games" in tables
assert "player_metrics" in tables
```

**Run:** `cd v2/browser && python -m pytest tests/test_smoke.py::test_league_db_exists -v`
**Expected:** FAIL — `player_metrics` table doesn't exist yet.

---

### Step 2: Write unit tests in test_player_metrics.py

```python
# v2/browser/tests/test_player_metrics.py
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_league_db import build_player_metrics_table


def _setup_db():
    """
    In-memory DB with 4 players:
      Player 1: FLA F, 6 games, 198 lbs / 72 in → PPI = 2.7500
      Player 2: FLA D, 6 games, 220 lbs / 74 in → PPI = 2.9730
      Player 3: EDM→VAN (3+3 games), 180 lbs / 70 in → PPI = 2.5714
      Player 4: EDM F, 3 games only → INELIGIBLE
    Games 1-6 used by players 1 & 2 (FLA).
    Games 11-16 used by player 3 (11-13 = EDM, 14-16 = VAN).
    Games 1-3 used by player 4 (EDM) — different team but same gameIds as FLA; OK for test.
    """
    conn = sqlite3.connect(":memory:")
    rows = []
    for game in range(1, 7):
        rows.append({"playerId": 1, "team": "FLA", "gameId": game,      "position": "F", "toi_seconds": 900,  "height_in": 72, "weight_lbs": 198})
        rows.append({"playerId": 2, "team": "FLA", "gameId": game,      "position": "D", "toi_seconds": 1000, "height_in": 74, "weight_lbs": 220})
    for game in range(11, 17):
        team = "EDM" if game <= 13 else "VAN"
        rows.append({"playerId": 3, "team": team,  "gameId": game,      "position": "F", "toi_seconds": 600,  "height_in": 70, "weight_lbs": 180})
    for game in range(1, 4):
        rows.append({"playerId": 4, "team": "EDM", "gameId": game + 20, "position": "F", "toi_seconds": 400,  "height_in": 68, "weight_lbs": 175})
    df = pd.DataFrame(rows)
    df.to_sql("competition", conn, index=False, if_exists="replace")
    return conn


def test_player_metrics_table_created():
    conn = _setup_db()
    build_player_metrics_table(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "player_metrics" in tables


def test_ppi_calculation():
    conn = _setup_db()
    build_player_metrics_table(conn)
    row = conn.execute("SELECT ppi FROM player_metrics WHERE playerId = 1").fetchone()
    assert row is not None
    assert abs(row[0] - 198 / 72) < 0.001


def test_ineligible_player_excluded():
    conn = _setup_db()
    build_player_metrics_table(conn)
    row = conn.execute("SELECT * FROM player_metrics WHERE playerId = 4").fetchone()
    assert row is None


def test_ppi_plus_mean_is_100():
    conn = _setup_db()
    build_player_metrics_table(conn)
    rows = conn.execute("SELECT ppi_plus FROM player_metrics").fetchall()
    values = [r[0] for r in rows]
    assert len(values) == 3
    assert abs(sum(values) / len(values) - 100.0) < 0.001


def test_wppi_traded_player():
    """
    Player 3 is the only eligible player on EDM and VAN, so their TOI share
    on each team is 1.0. wPPI = PPI × (1.0 + 1.0).
    """
    conn = _setup_db()
    build_player_metrics_table(conn)
    row = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 3").fetchone()
    assert row is not None
    expected = (180 / 70) * (1800 / 1800 + 1800 / 1800)
    assert abs(row[0] - expected) < 0.001


def test_wppi_plus_mean_is_100():
    conn = _setup_db()
    build_player_metrics_table(conn)
    rows = conn.execute("SELECT wppi_plus FROM player_metrics").fetchall()
    values = [r[0] for r in rows]
    assert len(values) == 3
    assert abs(sum(values) / len(values) - 100.0) < 0.001
```

**Run:** `cd v2/browser && python -m pytest tests/test_player_metrics.py -v`
**Expected:** FAIL — `build_player_metrics_table` doesn't exist yet.

---

### Step 3: Implement build_player_metrics_table in build_league_db.py

Add this function (before `main()`):

```python
def build_player_metrics_table(conn):
    """Compute PPI, PPI+, wPPI, wPPI+ for eligible skaters and write to player_metrics."""
    comp = pd.read_sql_query(
        "SELECT playerId, team, gameId, position, toi_seconds, height_in, weight_lbs"
        " FROM competition WHERE position IN ('F', 'D')",
        conn,
    )
    if comp.empty:
        print("  player_metrics: 0 rows (no competition data)")
        return

    # Games played per player
    gp = comp.groupby("playerId")["gameId"].nunique().rename("games_played")

    # Physical data per player (all rows for a player have the same height/weight)
    phys = comp.groupby("playerId")[["height_in", "weight_lbs"]].max()
    phys["ppi"] = phys["weight_lbs"] / phys["height_in"]

    # Eligible: GP >= 5, non-null PPI
    player_df = gp.to_frame().join(phys[["ppi"]])
    eligible = player_df[(player_df["games_played"] >= 5) & player_df["ppi"].notna()].copy()

    if eligible.empty:
        print("  player_metrics: 0 rows (no eligible players)")
        return

    # PPI+
    mean_ppi = eligible["ppi"].mean()
    eligible["ppi_plus"] = 100.0 * eligible["ppi"] / mean_ppi

    # wPPI: PPI × TOI share per team-stint, summed across stints
    eligible_comp = comp[comp["playerId"].isin(eligible.index)]
    team_total_toi = eligible_comp.groupby("team")["toi_seconds"].sum()
    player_team_toi = eligible_comp.groupby(["playerId", "team"])["toi_seconds"].sum()

    wppi_map: dict = {}
    for (pid, team), toi in player_team_toi.items():
        total = team_total_toi.get(team, 0)
        if total == 0:
            continue
        share = toi / total
        wppi_map[pid] = wppi_map.get(pid, 0.0) + eligible.loc[pid, "ppi"] * share

    eligible["wppi"] = pd.Series(wppi_map)
    eligible = eligible[eligible["wppi"].notna()]

    # wPPI+
    mean_wppi = eligible["wppi"].mean()
    eligible["wppi_plus"] = 100.0 * eligible["wppi"] / mean_wppi

    out = eligible[["ppi", "ppi_plus", "wppi", "wppi_plus"]].reset_index()
    out.to_sql("player_metrics", conn, if_exists="replace", index=False)
    print(f"  player_metrics: {len(out)} rows")
```

Add to `main()` after `build_players_table(conn)`:
```python
build_player_metrics_table(conn)
```

---

### Step 4: Run unit tests

**Run:** `cd v2/browser && python -m pytest tests/test_player_metrics.py -v`
**Expected:** All 6 tests pass.

---

### Step 5: Rebuild league.db

**Run:** `python v2/browser/build_league_db.py`
**Expected output** includes a line like: `player_metrics: NNN rows`

---

### Step 6: Run full test suite

**Run:** `cd v2/browser && python -m pytest tests/ -v`
**Expected:** All tests pass (including updated `test_league_db_exists`).

---

### Step 7: Commit

```bash
git add v2/browser/build_league_db.py \
        v2/browser/tests/test_player_metrics.py \
        v2/browser/tests/test_smoke.py
git commit -m "feat: add player_metrics table with PPI, PPI+, wPPI, wPPI+ to league.db"
```

---

## Task 2: Update game.py — rename to PPI, add wPPI columns

**Files:**
- Modify: `v2/browser/pages/game.py`

The game page summary table currently shows 3 team-level columns per team:
- Fwd Heaviness → **FWD PPI** (rename; value unchanged, comes from `weighted_forward_heaviness`)
- Def Heaviness → **DEF PPI** (rename; value unchanged)
- Team Heaviness → **Team PPI** (rename; value unchanged)

Add 3 new columns computed via JOIN to `player_metrics`:
- **FWD wPPI** = TOI-weighted average of each forward's season `wppi` in this game
- **DEF wPPI** = same for defensemen
- **Team wPPI** = same for all skaters

---

### Step 1: Update _HEAVINESS_SQL

Replace the current `_HEAVINESS_SQL` with:

```python
_HEAVINESS_SQL = """
SELECT c.team,
       MAX(c.weighted_forward_heaviness)                                        AS fwd_ppi,
       MAX(c.weighted_defense_heaviness)                                        AS def_ppi,
       MAX(c.weighted_team_heaviness)                                           AS team_ppi,
       SUM(CASE WHEN c.position = 'F' THEN pm.wppi * c.toi_seconds ELSE 0 END)
           / NULLIF(SUM(CASE WHEN c.position = 'F' THEN c.toi_seconds ELSE 0 END), 0) AS fwd_wppi,
       SUM(CASE WHEN c.position = 'D' THEN pm.wppi * c.toi_seconds ELSE 0 END)
           / NULLIF(SUM(CASE WHEN c.position = 'D' THEN c.toi_seconds ELSE 0 END), 0) AS def_wppi,
       SUM(pm.wppi * c.toi_seconds)
           / NULLIF(SUM(c.toi_seconds), 0)                                     AS team_wppi
FROM competition c
LEFT JOIN player_metrics pm ON c.playerId = pm.playerId
WHERE c.gameId = ? AND c.position IN ('F', 'D')
GROUP BY c.team
"""
```

---

### Step 2: Update heaviness_table HTML

The `_h()` helper function is unchanged (it already handles None → "—").

Replace the `heaviness_table` definition with updated column headers and 3 new cells per row:

```python
heaviness_table = html.Table([
    html.Thead(html.Tr([
        html.Th("Team",      style=th_style),
        html.Th("FWD PPI",   style=th_style),
        html.Th("DEF PPI",   style=th_style),
        html.Th("Team PPI",  style=th_style),
        html.Th("FWD wPPI",  style=th_style),
        html.Th("DEF wPPI",  style=th_style),
        html.Th("Team wPPI", style=th_style),
    ])),
    html.Tbody([
        html.Tr([
            html.Td(away, style=td_style),
            html.Td(_h(away, "fwd_ppi"),   style=td_style),
            html.Td(_h(away, "def_ppi"),   style=td_style),
            html.Td(_h(away, "team_ppi"),  style=td_style),
            html.Td(_h(away, "fwd_wppi"),  style=td_style),
            html.Td(_h(away, "def_wppi"),  style=td_style),
            html.Td(_h(away, "team_wppi"), style=td_style),
        ]),
        html.Tr([
            html.Td(home, style=td_style),
            html.Td(_h(home, "fwd_ppi"),   style=td_style),
            html.Td(_h(home, "def_ppi"),   style=td_style),
            html.Td(_h(home, "team_ppi"),  style=td_style),
            html.Td(_h(home, "fwd_wppi"),  style=td_style),
            html.Td(_h(home, "def_wppi"),  style=td_style),
            html.Td(_h(home, "team_wppi"), style=td_style),
        ]),
    ]),
], style={"borderCollapse": "collapse", "marginBottom": "1.5rem"})
```

---

### Step 3: Run test suite

**Run:** `cd v2/browser && python -m pytest tests/ -v`
**Expected:** All tests pass.

---

### Step 4: Commit

```bash
git add v2/browser/pages/game.py
git commit -m "feat: rename game page heaviness → PPI, add FWD/DEF/Team wPPI columns"
```

---

## Task 3: Update skaters.py — replace heaviness with 4 metrics

**Files:**
- Modify: `v2/browser/pages/skaters.py`

---

### Step 1: Update _SQL

Add `LEFT JOIN player_metrics pm ON c.playerId = pm.playerId`.
Replace `MAX(c.heaviness) AS heaviness` with:

```sql
    MAX(pm.ppi)                                                          AS ppi,
    MAX(pm.ppi_plus)                                                     AS ppi_plus,
    MAX(pm.wppi)                                                         AS wppi,
    MAX(pm.wppi_plus)                                                    AS wppi_plus,
```

Full updated SQL:
```python
_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    GROUP_CONCAT(DISTINCT c.team)                                        AS teams_raw,
    c.position,
    COUNT(DISTINCT c.gameId)                                             AS games_played,
    CAST(SUM(c.toi_seconds) AS REAL)
        / NULLIF(COUNT(DISTINCT c.gameId), 0)                           AS toi_per_game,
    MAX(pm.ppi)                                                          AS ppi,
    MAX(pm.ppi_plus)                                                     AS ppi_plus,
    MAX(pm.wppi)                                                         AS wppi,
    MAX(pm.wppi_plus)                                                    AS wppi_plus,
    CAST(SUM(c.pct_vs_top_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_fwd,
    CAST(SUM(c.pct_vs_top_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_def,
    CAST(SUM(c.comp_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_fwd,
    CAST(SUM(c.comp_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_def
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
LEFT JOIN player_metrics pm ON c.playerId = pm.playerId
WHERE c.position IN ('F', 'D')
GROUP BY c.playerId
ORDER BY toi_per_game DESC
"""
```

---

### Step 2: Update layout() — remove heaviness.round(), update imports

Add import at the top of the file:
```python
from dash.dash_table.Format import Format, Scheme
```

In `layout()`, remove this line:
```python
df["heaviness"] = df["heaviness"].round(4)
```
(The pm columns come pre-computed from the DB; no Python-side rounding needed.)

---

### Step 3: Update columns and display_cols

Replace:
```python
{"name": "Heaviness",    "id": "heaviness",          "type": "numeric"},
```

With 4 columns after `"5v5 TOI/GP"`:
```python
{"name": "PPI",   "id": "ppi",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
{"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
{"name": "wPPI",  "id": "wppi",      "type": "numeric", "format": Format(precision=4, scheme=Scheme.fixed)},
{"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
```

Replace `"heaviness"` in `display_cols` with `"ppi", "ppi_plus", "wppi", "wppi_plus"`:
```python
display_cols = [
    "player_link", "team", "position", "games_played", "toi_display",
    "ppi", "ppi_plus", "wppi", "wppi_plus",
    "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
    "comp_fwd_display", "comp_def_display",
]
```

---

### Step 4: Run test suite

**Run:** `cd v2/browser && python -m pytest tests/ -v`
**Expected:** All tests pass.

---

### Step 5: Commit

```bash
git add v2/browser/pages/skaters.py
git commit -m "feat: replace heaviness with PPI/PPI+/wPPI/wPPI+ on skaters leaderboard"
```

---

## Task 4: Update team.py — replace heaviness with 4 metrics

**Files:**
- Modify: `v2/browser/pages/team.py`

---

### Step 1: Update _PLAYER_SQL

Add `LEFT JOIN player_metrics pm ON c.playerId = pm.playerId`.
Replace `MAX(c.heaviness) AS heaviness` with:

```sql
    MAX(pm.ppi)                                                          AS ppi,
    MAX(pm.ppi_plus)                                                     AS ppi_plus,
    MAX(pm.wppi)                                                         AS wppi,
    MAX(pm.wppi_plus)                                                    AS wppi_plus,
```

Full updated SQL:
```python
_PLAYER_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    c.position,
    COUNT(DISTINCT c.gameId)                                             AS games_played,
    CAST(SUM(c.toi_seconds) AS REAL)
        / NULLIF(COUNT(DISTINCT c.gameId), 0)                           AS toi_per_game,
    MAX(pm.ppi)                                                          AS ppi,
    MAX(pm.ppi_plus)                                                     AS ppi_plus,
    MAX(pm.wppi)                                                         AS wppi,
    MAX(pm.wppi_plus)                                                    AS wppi_plus,
    CAST(SUM(c.pct_vs_top_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_fwd,
    CAST(SUM(c.pct_vs_top_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_def,
    CAST(SUM(c.comp_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_fwd,
    CAST(SUM(c.comp_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_def
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
LEFT JOIN player_metrics pm ON c.playerId = pm.playerId
WHERE c.position IN ('F', 'D') AND c.team = ?
GROUP BY c.playerId
ORDER BY toi_per_game DESC
"""
```

---

### Step 2: Update _make_position_table()

Add import at the top of the file:
```python
from dash.dash_table.Format import Format, Scheme
```

In `_make_position_table()`:

Remove:
```python
df["heaviness"] = df["heaviness"].round(4)
```

Replace the `"Heaviness"` column entry:
```python
{"name": "Heaviness",    "id": "heaviness",          "type": "numeric"},
```

With:
```python
{"name": "PPI",   "id": "ppi",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
{"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
{"name": "wPPI",  "id": "wppi",      "type": "numeric", "format": Format(precision=4, scheme=Scheme.fixed)},
{"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
```

Replace `"heaviness"` in `display_cols` with `"ppi", "ppi_plus", "wppi", "wppi_plus"`:
```python
display_cols = [
    "player_link", "games_played", "toi_display",
    "ppi", "ppi_plus", "wppi", "wppi_plus",
    "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
    "comp_fwd_display", "comp_def_display",
]
```

---

### Step 3: Run test suite

**Run:** `cd v2/browser && python -m pytest tests/ -v`
**Expected:** All tests pass.

---

### Step 4: Commit

```bash
git add v2/browser/pages/team.py
git commit -m "feat: replace heaviness with PPI/PPI+/wPPI/wPPI+ on team player tables"
```

---

## Notes

- The individual player page (`pages/player.py`) is intentionally out of scope for this plan.
- The competition CSVs are not modified — `heaviness`, `weighted_forward_heaviness`, etc. remain in the raw files. The browser renames them only in display/query aliases.
- Players ineligible for `player_metrics` (GP < 5) will show `NULL` for PPI columns on browser pages. `Format(precision=2, scheme=Scheme.fixed)` will display blank for NULL, which is acceptable.
- The `_h()` helper in `game.py` already handles None → "—" so wPPI will display cleanly even for games with no player_metrics data.
