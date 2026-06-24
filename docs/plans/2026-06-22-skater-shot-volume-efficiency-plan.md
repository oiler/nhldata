# Skater Shot Volume & Efficiency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two individual 5v5 stats to the player page — `iSA/60` (individual shot attempts per 60) and `P/100iSA` (5v5 points per 100 individual shot attempts) — each with a league rank.

**Architecture:** Add an `ishots` column to the existing `events_5v5` table (individual Corsi attempts by the shooter). Extend `events_per60` to emit `ishots_per60`; add a `points_per100_shots` helper. Wire two new cells into the player-page season-summary strip, reusing the established pool/rank pattern; the P/100iSA rank is gated to players with ≥ 50 attempts in the window.

**Tech Stack:** Python 3.12+, pandas, sqlite3, Dash, pytest.

## Global Constraints

- 5v5 is strict `situationCode == "1551"` (existing `FIVE_V_FIVE = {"1551"}` in `build_league_db.py`).
- Individual shot attempts (iSA) = Corsi, blocked attempts included: `shot-on-goal` + `missed-shot` + `blocked-shot` (shooter via `details.shootingPlayerId`) + `goal` (via `details.scoringPlayerId`).
- A `blocked-shot` event credits BOTH the blocker's `blocks` (existing) AND the shooter's `ishots` (new) — independent stats.
- `iSA/60` denominator = `competition.toi_seconds` (5v5 TOI), full filtered-game denominator.
- `P/100iSA` = `Σ(5v5 points) · 100 / Σ ishots`; NaN when `Σ ishots == 0`.
- P/100iSA rank requires `total_ishots >= 50` in the window (value still displays for all); floor is one named constant `ISA_RANK_MIN = 50`. iSA/60 has no floor (GP ≥ 5 pool gate only).
- Labels exactly: `iSA/60` and `P/100iSA`.
- Shared metric logic lives in `v2/browser/metrics.py` — never duplicated in player.py.
- DB tables full-replace (`if_exists="replace"`).
- Tests use synthetic DataFrames, never real data files.
- Do NOT run `git commit` directly in subagents — the controller commits per task (local commits on the feature branch are authorized for this build; never push, never touch master).
- Run `python -m pytest v2/ -v` green before declaring any task done.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `v2/browser/build_league_db.py` | DB build | `count_5v5_events` counts `ishots`; `events_5v5` gains the column; both column lists updated |
| `v2/browser/metrics.py` | Shared math | `events_per60` emits `ishots_per60`; new `points_per100_shots` |
| `v2/browser/pages/player.py` | Player page render | `_EVENTS_SQL` selects `ishots`; two new cells (`iSA/60`, `P/100iSA`) with ranks; `ISA_RANK_MIN` constant |
| `v2/browser/test_rate_metrics.py` | Tests | new `ishots` count test; extend `events_per60` test; new `points_per100_shots` test |

---

# PHASE 1 — Individual shot attempts (`ishots` + `iSA/60`)

### Task 1: `ishots` in the builder + `events_per60`

**Files:**
- Modify: `v2/browser/build_league_db.py` (`count_5v5_events`, `build_events_5v5_table` empty-frame columns)
- Modify: `v2/browser/metrics.py` (`events_per60`)
- Modify: `v2/browser/pages/player.py` (`_EVENTS_SQL`)
- Modify: `v2/browser/test_rate_metrics.py`

**Interfaces:**
- Produces: `events_5v5` table gains column `ishots`; `count_5v5_events(df, game_id)` returns columns `gameId, playerId, hits, blocks, takeaways, giveaways, ishots`.
- Produces: `events_per60(events_df, toi_df)` returns an additional column `ishots_per60` (existing `hits_per60`/`blocks_per60`/`tk_per60`/`gv_per60` unchanged).

- [ ] **Step 1: Write the failing test for `ishots` counting**

Append to `v2/browser/test_rate_metrics.py`:

```python
def test_count_5v5_events_counts_individual_shot_attempts():
    df = pd.DataFrame([
        {"typeDescKey": "shot-on-goal", "situationCode": "1551", "details.shootingPlayerId": 50, "details.scoringPlayerId": None, "details.blockingPlayerId": None},
        {"typeDescKey": "missed-shot",  "situationCode": "1551", "details.shootingPlayerId": 50, "details.scoringPlayerId": None, "details.blockingPlayerId": None},
        {"typeDescKey": "blocked-shot", "situationCode": "1551", "details.shootingPlayerId": 50, "details.scoringPlayerId": None, "details.blockingPlayerId": 60},
        {"typeDescKey": "goal",         "situationCode": "1551", "details.shootingPlayerId": None, "details.scoringPlayerId": 50, "details.blockingPlayerId": None},
        {"typeDescKey": "shot-on-goal", "situationCode": "1441", "details.shootingPlayerId": 50, "details.scoringPlayerId": None, "details.blockingPlayerId": None},  # not 5v5
    ])
    out = count_5v5_events(df, game_id=2025020001).set_index("playerId")
    assert out.loc[50, "ishots"] == 4         # SOG + missed + blocked(as shooter) + goal; 1441 excluded
    assert out.loc[60, "blocks"] == 1         # blocker still credited a block
    assert out.loc[60, "ishots"] == 0         # blocker did not attempt the shot
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/test_rate_metrics.py::test_count_5v5_events_counts_individual_shot_attempts -v`
Expected: FAIL — `KeyError: 50` or `ishots` missing (column not produced yet).

- [ ] **Step 3: Implement `ishots` in `count_5v5_events`**

In `v2/browser/build_league_db.py`, update `count_5v5_events`. Change the `_bump` default dict to include `ishots`, add the Corsi branches, and add `ishots` to the returned columns:

```python
def count_5v5_events(df, game_id):
    """Count per-player 5v5 hits/blocks/takeaways/giveaways and individual shot attempts."""
    five_v_five = df[df["situationCode"].astype(str).isin(FIVE_V_FIVE)]
    counts = {}  # playerId -> dict

    def _bump(pid_val, key):
        if pd.notna(pid_val):
            pid = int(pid_val)
            row = counts.setdefault(pid, {"hits": 0, "blocks": 0, "takeaways": 0, "giveaways": 0, "ishots": 0})
            row[key] += 1

    for _, r in five_v_five.iterrows():
        t = r["typeDescKey"]
        if t == "hit":
            _bump(r.get("details.hittingPlayerId"), "hits")
        elif t == "blocked-shot":
            _bump(r.get("details.blockingPlayerId"), "blocks")
            _bump(r.get("details.shootingPlayerId"), "ishots")
        elif t == "takeaway":
            _bump(r.get("details.playerId"), "takeaways")
        elif t == "giveaway":
            _bump(r.get("details.playerId"), "giveaways")
        elif t in ("shot-on-goal", "missed-shot"):
            _bump(r.get("details.shootingPlayerId"), "ishots")
        elif t == "goal":
            _bump(r.get("details.scoringPlayerId"), "ishots")

    records = [{"gameId": game_id, "playerId": pid, **vals} for pid, vals in counts.items()]
    return pd.DataFrame(records, columns=["gameId", "playerId", "hits", "blocks", "takeaways", "giveaways", "ishots"])
```

Also update the empty-frame write in `build_events_5v5_table` to include `ishots`:

```python
        pd.DataFrame(columns=["gameId", "playerId", "hits", "blocks", "takeaways", "giveaways", "ishots"]).to_sql(
            "events_5v5", conn, if_exists="replace", index=False
        )
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `python -m pytest v2/browser/test_rate_metrics.py::test_count_5v5_events_counts_individual_shot_attempts -v`
Expected: PASS. Also run the existing `test_count_5v5_events_credits_correct_fields_and_filters_strength` — it must still PASS (its synthetic rows lack `shootingPlayerId`/`scoringPlayerId` columns, so `ishots` stays 0 there and no assertion changes).

- [ ] **Step 5: Extend `events_per60` to emit `ishots_per60`**

In `v2/browser/metrics.py`, update `events_per60` — add `ishots` to the summed columns and the output, and update the docstring return line:

```python
def events_per60(events_df: pd.DataFrame, toi_df: pd.DataFrame) -> pd.DataFrame:
    """Per-60 individual-event rates over all of a player's 5v5 TOI.

    Args:
        events_df: per-(gameId, playerId) with hits, blocks, takeaways, giveaways, ishots.
        toi_df:    per-(gameId, playerId) with toi_seconds (denominator = all filtered games).

    Returns:
        Indexed by playerId: hits_per60, blocks_per60, tk_per60, gv_per60, ishots_per60.
    """
    toi = toi_df.groupby("playerId")["toi_seconds"].sum()
    sums = events_df.groupby("playerId")[["hits", "blocks", "takeaways", "giveaways", "ishots"]].sum()
    out = sums.reindex(toi.index).fillna(0).join(toi.rename("toi"))
    denom = out["toi"].where(out["toi"] > 0)
    return pd.DataFrame({
        "hits_per60":   out["hits"]   * 3600 / denom,
        "blocks_per60": out["blocks"] * 3600 / denom,
        "tk_per60":     out["takeaways"] * 3600 / denom,
        "gv_per60":     out["giveaways"] * 3600 / denom,
        "ishots_per60": out["ishots"] * 3600 / denom,
    })
```

- [ ] **Step 6: Update the existing `events_per60` test (adds the `ishots` column it now requires)**

In `v2/browser/test_rate_metrics.py`, edit `test_events_per60_uses_full_toi_denominator`: add `"ishots": 4` to the single events row and add one assertion. The groupby now requires the `ishots` column, so without this the test errors.

```python
def test_events_per60_uses_full_toi_denominator():
    events = pd.DataFrame([
        {"gameId": 1, "playerId": 7, "hits": 3, "blocks": 1, "takeaways": 0, "giveaways": 2, "ishots": 4},
    ])
    # player 7 played two games at 5v5: 1200s total -> 3 hits over 1200s = 9.0/60min
    toi = pd.DataFrame([
        {"gameId": 1, "playerId": 7, "toi_seconds": 600},
        {"gameId": 2, "playerId": 7, "toi_seconds": 600},
    ])
    out = events_per60(events, toi)
    assert round(out.loc[7, "hits_per60"], 2) == 9.0       # 3 * 3600 / 1200
    assert round(out.loc[7, "gv_per60"], 2) == 6.0         # 2 * 3600 / 1200
    assert out.loc[7, "blocks_per60"] > 0
    assert round(out.loc[7, "ishots_per60"], 2) == 12.0    # 4 * 3600 / 1200
```

- [ ] **Step 7: Add `ishots` to `_EVENTS_SQL`**

In `v2/browser/pages/player.py`:

```python
_EVENTS_SQL = "SELECT gameId, playerId, hits, blocks, takeaways, giveaways, ishots FROM events_5v5"
```

- [ ] **Step 8: Run full suite, then rebuild and validate the DB**

Run: `python -m pytest v2/ -v` — all PASS.
Then: `python v2/browser/build_league_db.py 2025`
Then verify the column populated:

```bash
python3 -c "import sqlite3; c=sqlite3.connect('data/2025/generated/browser/league.db'); print(c.execute('select count(*), sum(ishots) from events_5v5').fetchone())"
```

Expected: nonzero rows and `sum(ishots)` > 0 (a full season of 5v5 shot attempts — tens of thousands). Report the number.

- [ ] **Step 9: Commit** (controller commits; subagent runs `git add` only)

```bash
git add v2/browser/build_league_db.py v2/browser/metrics.py v2/browser/pages/player.py v2/browser/test_rate_metrics.py
```

### Task 2: Wire `iSA/60` into the player page

**Files:**
- Modify: `v2/browser/pages/player.py`

**Interfaces:**
- Consumes: `events_per60`'s `ishots_per60` (Task 1), already joined into `lg` via the existing `lg = lg.join(events_per60(pool_events, pool_games))` call.

- [ ] **Step 1: Initialize the value local**

In `v2/browser/pages/player.py`, find the line initializing the event/Corsi value locals before the `if not league_comp_df.empty:` block:

```python
        hits60 = blocks60 = tk60 = gv60 = cf60 = ca60 = cf_pct_val = None
```

Change it to also initialize `isa60`:

```python
        hits60 = blocks60 = tk60 = gv60 = cf60 = ca60 = cf_pct_val = isa60 = None
```

- [ ] **Step 2: Read the selected-player value inside the guard**

Find the block where the locals are assigned via `_pool_val` (e.g. `cf_pct_val  = _pool_val("cf_pct")`). Add, alongside them:

```python
            isa60 = _pool_val("ishots_per60")
```

- [ ] **Step 3: Add the rank**

In the `ranks = { ... }` dict, add (next to the other per-60 event ranks):

```python
                "iSA/60":    _rank("ishots_per60"),
```

- [ ] **Step 4: Add the stat cell**

In the `summary_section` cells list, add a cell next to the event cells (after the `GV/60` cell):

```python
                stat_cell("iSA/60", _fmt(isa60, 1), ranks.get("iSA/60")),
```

- [ ] **Step 5: Verify**

Run: `python -m pytest v2/ -v` — all PASS (no new test; display wiring of already-tested logic).
Then sanity-check the callback renders the cell with a value and rank:

```bash
cd v2/browser && python3 - <<'PY'
import sys; sys.path.insert(0,'.')
import app
from pages import player
from dash import html
out = player.update_player("2025-10-07","2026-04-16","all",8484984,"F","2025")
cells=[]
def walk(n):
    if isinstance(n,(list,tuple)):
        for c in n: walk(c)
        return
    ch=getattr(n,"children",None)
    if isinstance(n,html.Div) and isinstance(ch,list) and ch and isinstance(ch[0],html.Div):
        t=[c.children for c in ch if isinstance(c,html.Div)]
        if len(t)>=2 and isinstance(t[0],str): cells.append(t)
    if ch is not None: walk(ch)
walk(out)
for t in cells:
    if t[0]=="iSA/60": print("iSA/60", t[1], t[2] if len(t)>2 else "")
PY
```

Expected: a line like `iSA/60 <value> <rank>/...` with a real number.

- [ ] **Step 6: Commit** (controller commits; subagent runs `git add` only)

```bash
git add v2/browser/pages/player.py
```

---

# PHASE 2 — Shot efficiency (`P/100iSA`)

### Task 3: `points_per100_shots` helper

**Files:**
- Modify: `v2/browser/metrics.py`
- Modify: `v2/browser/test_rate_metrics.py`

**Interfaces:**
- Produces: `points_per100_shots(points_df, ishots_df, min_attempts=50) -> pd.DataFrame`
  - `points_df`: per-(gameId, playerId) with a `points` column.
  - `ishots_df`: per-(gameId, playerId) with an `ishots` column.
  - Returns indexed by `playerId`: `total_ishots`, `p_per100`, `p_per100_ranked`.

- [ ] **Step 1: Write the failing test**

Append to `v2/browser/test_rate_metrics.py`:

```python
from metrics import points_per100_shots


def test_points_per100_shots_ratio_and_floor():
    points = pd.DataFrame([
        {"gameId": 1, "playerId": 1, "points": 10},
        {"gameId": 1, "playerId": 2, "points": 3},
        {"gameId": 1, "playerId": 3, "points": 2},
    ])
    ishots = pd.DataFrame([
        {"gameId": 1, "playerId": 1, "ishots": 50},
        {"gameId": 1, "playerId": 2, "ishots": 20},
        {"gameId": 1, "playerId": 3, "ishots": 0},
    ])
    out = points_per100_shots(points, ishots, min_attempts=50)
    assert round(out.loc[1, "p_per100"], 1) == 20.0          # 10 * 100 / 50
    assert out.loc[1, "p_per100_ranked"] == 20.0             # 50 >= floor -> ranked
    assert round(out.loc[2, "p_per100"], 1) == 15.0          # 3 * 100 / 20
    assert pd.isna(out.loc[2, "p_per100_ranked"])            # 20 < 50 -> unranked
    assert pd.isna(out.loc[3, "p_per100"])                   # 0 attempts -> NaN value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/test_rate_metrics.py::test_points_per100_shots_ratio_and_floor -v`
Expected: FAIL — `ImportError: cannot import name 'points_per100_shots'`.

- [ ] **Step 3: Implement the helper**

Append to `v2/browser/metrics.py`:

```python
def points_per100_shots(points_df: pd.DataFrame, ishots_df: pd.DataFrame, min_attempts: int = 50) -> pd.DataFrame:
    """5v5 points per 100 individual shot attempts, with a min-attempts rank floor.

    Args:
        points_df: per-(gameId, playerId) with a points column (from points_5v5).
        ishots_df: per-(gameId, playerId) with an ishots column (from events_5v5).
        min_attempts: total-attempt floor below which p_per100_ranked is NaN.

    Returns:
        Indexed by playerId:
          total_ishots    — summed individual shot attempts.
          p_per100        — points * 100 / total_ishots (NaN when total_ishots == 0). Display value.
          p_per100_ranked — p_per100 where total_ishots >= min_attempts, else NaN. Rank column.
    """
    pts = (points_df.groupby("playerId")["points"].sum()
           if not points_df.empty else pd.Series(dtype=float))
    ish = (ishots_df.groupby("playerId")["ishots"].sum()
           if not ishots_df.empty else pd.Series(dtype=float))
    out = pd.DataFrame({"total_ishots": ish, "points": pts})
    out["total_ishots"] = out["total_ishots"].fillna(0)
    out["points"] = out["points"].fillna(0)
    denom = out["total_ishots"].where(out["total_ishots"] > 0)
    out["p_per100"] = out["points"] * 100 / denom
    out["p_per100_ranked"] = out["p_per100"].where(out["total_ishots"] >= min_attempts)
    return out[["total_ishots", "p_per100", "p_per100_ranked"]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/test_rate_metrics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** (controller commits; subagent runs `git add` only)

```bash
git add v2/browser/metrics.py v2/browser/test_rate_metrics.py
```

### Task 4: Wire `P/100iSA` into the player page (floor-gated rank)

**Files:**
- Modify: `v2/browser/pages/player.py`

**Interfaces:**
- Consumes: `points_per100_shots` (Task 3); `events_5v5.ishots` via `pool_events` (Task 1); `points_5v5` via `pts_df` (existing `_POINTS_SQL`).

- [ ] **Step 1: Add the floor constant and import**

In `v2/browser/pages/player.py`, add the import to the existing metrics import line:

```python
from metrics import carryover_per_player, events_per60, corsi_per60, points_per100_shots
```

Add a module-level constant near the other module constants (e.g. under `_ONICE_SQL`):

```python
ISA_RANK_MIN = 50  # min 5v5 individual shot attempts in window to qualify for the P/100iSA rank
```

- [ ] **Step 2: Initialize the value local**

Extend the value-local initialization line to include `p100`:

```python
        hits60 = blocks60 = tk60 = gv60 = cf60 = ca60 = cf_pct_val = isa60 = p100 = None
```

(If Task 2 has not run, the line will not yet contain `isa60`; add both `isa60` and `p100` so the line ends `... = cf_pct_val = isa60 = p100 = None`.)

- [ ] **Step 3: Join P/100iSA into the pool**

In `update_player`, inside the `if not events_df.empty:` block, right after the existing `lg = lg.join(events_per60(pool_events, pool_games))` line, add:

```python
                pool_points = (
                    pts_df.merge(
                        league_comp_df[["gameId", "playerId"]].drop_duplicates(),
                        on=["gameId", "playerId"], how="inner",
                    )
                    if not pts_df.empty else pd.DataFrame(columns=["gameId", "playerId", "points"])
                )
                lg = lg.join(points_per100_shots(pool_points, pool_events, min_attempts=ISA_RANK_MIN))
```

(`pool_events` already exists in this block and carries `ishots` after Task 1.)

- [ ] **Step 4: Read the selected-player value inside the guard**

Alongside `isa60 = _pool_val("ishots_per60")`, add:

```python
            p100 = _pool_val("p_per100")
```

- [ ] **Step 5: Add the rank (ranks the floor-gated column)**

In the `ranks = { ... }` dict, add:

```python
                "P/100iSA":  _rank("p_per100_ranked"),
```

- [ ] **Step 6: Add the stat cell**

In the `summary_section` cells list, add after the `iSA/60` cell:

```python
                stat_cell("P/100iSA", _fmt(p100), ranks.get("P/100iSA")),
```

- [ ] **Step 7: Verify**

Run: `python -m pytest v2/ -v` — all PASS.
Then sanity-check the callback for a high-volume player (value present, rank qualifies) and confirm a low-attempt player shows a value but rank `—`:

```bash
cd v2/browser && python3 - <<'PY'
import sys; sys.path.insert(0,'.')
import app
from pages import player
from dash import html
def cells_for(pid, pos):
    out = player.update_player("2025-10-07","2026-04-16","all",pid,pos,"2025")
    found={}
    def walk(n):
        if isinstance(n,(list,tuple)):
            for c in n: walk(c)
            return
        ch=getattr(n,"children",None)
        if isinstance(n,html.Div) and isinstance(ch,list) and ch and isinstance(ch[0],html.Div):
            t=[c.children for c in ch if isinstance(c,html.Div)]
            if len(t)>=2 and isinstance(t[0],str): found[t[0]]=(t[1], t[2] if len(t)>2 else "")
        if ch is not None: walk(ch)
    walk(out)
    return {k:found[k] for k in ("iSA/60","P/100iSA") if k in found}
print("Demidov:", cells_for(8484984,"F"))
PY
```

Expected: `iSA/60` and `P/100iSA` both present with values; `P/100iSA` carries a rank for a qualifying player.

- [ ] **Step 8: Commit** (controller commits; subagent runs `git add` only)

```bash
git add v2/browser/pages/player.py
```

---

## Self-Review

**Spec coverage:**
- `ishots` column (Corsi, blocked included; blocker also keeps `blocks`) → Task 1. ✓
- `iSA/60` denominator = 5v5 TOI, full filtered-game → `events_per60` (Task 1) + cell (Task 2). ✓
- `P/100iSA` = Σpoints·100/Σishots, NaN at 0 attempts → `points_per100_shots` (Task 3). ✓
- 50-attempt rank floor, value shown for all → `p_per100_ranked` + `_rank` (Tasks 3, 4); `ISA_RANK_MIN` constant. ✓
- Player page only; labels `iSA/60`, `P/100iSA` → Tasks 2, 4. ✓
- Shared math in metrics.py → Tasks 1, 3. ✓
- Value/rank from same `lg` pool → `_pool_val`/`_rank` both read `lg` (Tasks 2, 4). ✓

**Placeholder scan:** none — every code step shows full code. ✓

**Type consistency:** `count_5v5_events` returns `...,ishots`; `events_per60` emits `ishots_per60`; `points_per100_shots` returns `total_ishots`/`p_per100`/`p_per100_ranked`. Pool columns (`ishots_per60`, `p_per100`, `p_per100_ranked`) match the `_rank`/`_pool_val` lookups in player.py. ✓

## Notes for the implementer

- `P/100iSA` ranks **descending** (default) — higher points-per-attempt = rank 1.
- The P/100iSA rank uses `p_per100_ranked` (NaN below the floor), so `_rank`'s existing drop-NaN behavior excludes sub-floor players automatically and a sub-floor selected player gets rank `—` from `_fmt`/`ranks.get`.
- Hoist the `from metrics import ...` change to the existing import line, not inside the callback.
- The new pool joins live inside the existing `if not events_df.empty:` block (P/100iSA needs `ishots`, which needs events data); when events are absent the cells degrade to `—`.
