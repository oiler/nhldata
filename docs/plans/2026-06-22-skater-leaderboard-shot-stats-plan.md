# Skater Leaderboard Shot Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `iSA/60` and `P/100iSA` columns to the `/skaters` leaderboard (after `P/60`), remove the `PPI` column from that table, and add glossary entries — reusing the existing `events_per60` and `points_per100_shots` helpers.

**Architecture:** `pages/skaters.py` queries `events_5v5` (the `ishots` column), restricts it to the filtered games, and joins `ishots_per60` (from `events_per60`) and `p_per100_ranked` (from `points_per100_shots`, floor-applied) into the per-player `grouped` frame. The two stats become sortable numeric columns; `PPI` is dropped from the column/display lists. The global glossary in `app.py` gains two entries.

**Tech Stack:** Python 3.12+, pandas, Dash DataTable.

## Global Constraints

- Reuse `metrics.events_per60` (→ `ishots_per60`) and `metrics.points_per100_shots(points_df, ishots_df, min_attempts=50)` (→ `p_per100_ranked`). No new metric logic.
- `P/100iSA` on the leaderboard displays `p_per100_ranked` (NaN below 50 attempts → renders blank), so small samples don't distort the native sort.
- `iSA/60` has no floor (rate over TOI, shown for all).
- Both new columns placed immediately after `P/60`; labels exactly `iSA/60` and `P/100iSA`.
- Remove `PPI` from the skaters table only (keep `PPI+`, `wPPI+`). KEEP the PPI glossary entry (PPI still shows on the player page).
- `ISA_RANK_MIN = 50` as a named constant in `skaters.py`.
- No new unit test (wiring over already-tested helpers); full suite stays green + a callback smoke.
- Do NOT run git commit in subagents — the controller commits per task (local commits on the feature branch; never push, never touch master).
- Run `python -m pytest v2/ -v` green before declaring the task done.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `v2/browser/pages/skaters.py` | Skaters leaderboard | Query + restrict `events_5v5`, join `ishots_per60` + `p_per100_ranked`, add two columns after `P/60`, remove `PPI` column, add `ISA_RANK_MIN` + import |
| `v2/browser/app.py` | Global glossary | Add `iSA/60` and `P/100iSA` `Dt`/`Dd` entries (keep `PPI`) |

---

### Task 1: Add iSA/60 + P/100iSA to the skaters leaderboard, remove PPI column, update glossary

**Files:**
- Modify: `v2/browser/pages/skaters.py`
- Modify: `v2/browser/app.py`

**Interfaces:**
- Consumes: `events_per60(events_df, toi_df) -> DataFrame` with `ishots_per60`; `points_per100_shots(points_df, ishots_df, min_attempts=50) -> DataFrame` with `p_per100_ranked`. Both in `v2/browser/metrics.py` (already implemented + tested).

- [ ] **Step 1: Add the metrics import**

In `v2/browser/pages/skaters.py`, add to the imports (after the `from filters import ...` line):

```python
from metrics import events_per60, points_per100_shots
```

- [ ] **Step 2: Add the events SQL and the floor constant**

In `v2/browser/pages/skaters.py`, near `_POINTS_SQL` (currently `_POINTS_SQL = "SELECT playerId, gameId, goals, assists, points FROM points_5v5"`), add:

```python
_EVENTS_SQL = "SELECT gameId, playerId, hits, blocks, takeaways, giveaways, ishots FROM events_5v5"
ISA_RANK_MIN = 50  # min 5v5 individual shot attempts in window to show P/100iSA on the leaderboard
```

- [ ] **Step 3: Query, restrict, and join the two stats**

In `update_skaters`, immediately AFTER the line `grouped["p_per_60"] = grouped["total_points"] * 3600 / grouped["total_toi"].where(grouped["total_toi"] > 0)` and BEFORE `grouped = grouped.join(_BURSTS_DF)`, insert:

```python
    # Individual shot attempts (iSA/60) and shot efficiency (P/100iSA), 5v5
    events_df = league_query(_EVENTS_SQL, season=season)
    valid_games = comp_df[["playerId", "gameId"]].drop_duplicates()
    toi_frame = comp_df[["gameId", "playerId", "toi_seconds"]]
    if not events_df.empty:
        ev = events_df.merge(valid_games, on=["playerId", "gameId"], how="inner")
        grouped = grouped.join(events_per60(ev, toi_frame)[["ishots_per60"]])
        pts_for_eff = (
            pts_df.merge(valid_games, on=["playerId", "gameId"], how="inner")
            if not pts_df.empty else pd.DataFrame(columns=["gameId", "playerId", "points"])
        )
        grouped = grouped.join(
            points_per100_shots(pts_for_eff, ev, min_attempts=ISA_RANK_MIN)[["p_per100_ranked"]]
        )
    for col in ["ishots_per60", "p_per100_ranked"]:
        if col not in grouped.columns:
            grouped[col] = None
```

Note: `pts_df` is already loaded earlier in the callback (the `# 5v5 points` block). `comp_df` and `grouped` are in scope. `events_per60`'s denominator sums `toi_frame` (all the player's filtered-game 5v5 TOI); `ev` provides the numerator over the same game set.

- [ ] **Step 4: Add the two columns after P/60 and remove the PPI column**

In `v2/browser/pages/skaters.py`, in the `columns = [ ... ]` list, insert the two new column dicts immediately after the `P/60` dict, and DELETE the `PPI` dict. The affected region becomes:

```python
        {"name": "P/60",  "id": "p_per_60",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "iSA/60", "id": "ishots_per60", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "P/100iSA", "id": "p_per100_ranked", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "5v5 TOI/GP",   "id": "toi_display",        "filter_options": _ci},
        {"name": "tTOI%",        "id": "avg_toi_share", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "iTOI%",        "id": "avg_itoi_pct", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
```

(The line `{"name": "PPI",   "id": "ppi",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},` is removed; `PPI+` and `wPPI+` remain.)

- [ ] **Step 5: Update `display_cols` (add the two ids after p_per_60, remove "ppi")**

Replace the `display_cols` list with:

```python
    display_cols = [
        "player_link", "team", "shoots", "position", "age", "games_played",
        "total_goals", "total_assists", "total_points", "p_per_60", "ishots_per60", "p_per100_ranked",
        "toi_display",
        "avg_toi_share", "avg_itoi_pct",
        "ppi_plus", "wppi_plus", "bursts_per_60", "speed_max_mph", "avg_line", "dps_plus",
    ]
```

(`"ppi"` removed; `"ishots_per60"`, `"p_per100_ranked"` added after `"p_per_60"`.)

- [ ] **Step 6: Add glossary entries in `app.py`**

In `v2/browser/app.py`, inside the glossary `html.Dl([ ... ])`, insert after the `Max MPH` `html.Dd(...)` block (the one ending `"...McDavid leads at 24.6."`) and before `html.Dt("tTOI%")`:

```python
            html.Dt("iSA/60"),
            html.Dd(
                "Individual shot attempts per 60 minutes of 5v5 ice time — shots on goal, "
                "missed shots, and the player's own attempts that were blocked, plus goals. "
                "Measures how much shot volume a skater generates himself."
            ),
            html.Dt("P/100iSA"),
            html.Dd(
                "5v5 points (goals + assists) per 100 individual shot attempts. Measures how "
                "productive each attempt is; playmakers score high. On the leaderboard, shown "
                "only for skaters with at least 50 attempts in the window so small samples "
                "don't distort the sort."
            ),
```

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest v2/ -v`
Expected: all PASS (164). No new test — this is wiring over already-tested helpers.

- [ ] **Step 8: Callback smoke — columns present, PPI gone, floor blanks sub-50**

Run:

```bash
cd v2/browser && python3 - <<'PY'
import sys; sys.path.insert(0,'.')
import pandas as pd
import app
from pages import skaters
from dash import dash_table

out = skaters.update_skaters("2025-10-07", "2026-04-16", "all", "2025")

def find_dt(n):
    if isinstance(n,(list,tuple)):
        for c in n:
            r=find_dt(c)
            if r: return r
        return None
    if isinstance(n, dash_table.DataTable): return n
    ch=getattr(n,"children",None)
    return find_dt(ch) if ch is not None else None

dt=find_dt(out)
names=[c["name"] for c in dt.columns]
print("iSA/60 col:", "iSA/60" in names, "| P/100iSA col:", "P/100iSA" in names,
      "| PPI removed:", "PPI" not in names, "| PPI+ kept:", "PPI+" in names)
data=pd.DataFrame(dt.data)
print("rows:", len(data),
      "| ishots_per60 non-null:", data["ishots_per60"].notna().sum(),
      "| p_per100_ranked non-null (qualified):", data["p_per100_ranked"].notna().sum(),
      "| p_per100_ranked blank (sub-floor/no-data):", data["p_per100_ranked"].isna().sum())
PY
```

Expected: `iSA/60 col: True | P/100iSA col: True | PPI removed: True | PPI+ kept: True`; nonzero rows; `ishots_per60` populated for most; `p_per100_ranked` has BOTH some non-null (qualified ≥50) AND some blank (sub-floor) — confirming the floor renders blank on the table.

- [ ] **Step 9: Commit** (controller commits; subagent runs `git add` only)

```bash
git add v2/browser/pages/skaters.py v2/browser/app.py
```

---

## Self-Review

**Spec coverage:**
- iSA/60 via `events_per60`'s `ishots_per60` → Steps 3, 4, 5. ✓
- P/100iSA via `points_per100_shots`'s `p_per100_ranked` (floor applied, blank sub-50) → Steps 3, 4, 5. ✓
- Placement after `P/60` → Steps 4, 5. ✓
- Remove `PPI` column only, keep `PPI+`/`wPPI+` → Steps 4, 5. ✓
- Keep PPI glossary, add iSA/60 + P/100iSA glossary → Step 6. ✓
- Reuse helpers, no new logic → Step 3. ✓
- Regression-green + smoke → Steps 7, 8. ✓

**Placeholder scan:** none — every step shows full code. ✓

**Type consistency:** joined columns `ishots_per60` and `p_per100_ranked` match the column `id`s and `display_cols` entries exactly. `ISA_RANK_MIN` passed as `min_attempts`. ✓

## Notes for the implementer

- NaN in a numeric DataTable column renders as blank — this is the intended display for `p_per100_ranked` below the floor and for any player with zero 5v5 TOI in `ishots_per60`.
- Do not touch the player page — it already has both stats.
- The existing rounding loop (`for col, decimals in [("ppi", 2), ...]`) still references `"ppi"`; leave that loop as-is (the `ppi` column still exists in `grouped`, it's just no longer displayed). Removing it from the loop is optional cleanup, not required, and out of scope.
