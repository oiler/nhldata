# Player Page Stat Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add carry-over leaderboard stats (`SB/a60`, `Max MPH`, `DPL`, `DPS+`) plus new 5v5 per-60 rate stats (Hits/Blocks/TK/GV per 60, CF/60, CA/60, CF%) to the individual player page, each with a league rank.

**Architecture:** Two new per-`(gameId, playerId)` tables in `league.db` (`events_5v5` from flatplays, `onice_5v5` from flatplays Corsi events joined to per-second timelines). Pure aggregation helpers in `metrics.py` turn per-game rows into per-60 rates. `pages/player.py` renders new stat cells in the existing season-summary strip, with ranks from the existing `lg` league pool.

**Tech Stack:** Python 3.12+, pandas, sqlite3, csv (stdlib), Dash, pytest.

## Global Constraints

- 5v5 is strict `situationCode == "1551"` (the existing `FIVE_V_FIVE = {"1551"}` set in `build_league_db.py`). Never include `1441`/`0651`/`1560` in these stats.
- All new DB tables are built full-replace (`if_exists="replace"`), same as every existing builder.
- Per-60 denominator is `competition.toi_seconds` (already 5v5 TOI).
- Corsi side is determined by which timeline skater list contains the shooter, never `eventOwnerTeamId`.
- Missing timeline files are skipped gracefully with a logged count; no crash. Rebuild picks them up automatically.
- Shared metric logic lives in `v2/browser/metrics.py` — never duplicate it into `player.py` or `build_league_db.py`.
- Tests use synthetic DataFrames, never real data files (pattern: `test_player_metrics.py`, `test_deployment_metrics.py`).
- Do NOT run git commits — oiler commits manually. The "Commit" steps below describe the staged change; run `git add` only, and report. (Overrides the skill's commit default per project CLAUDE.md.)
- Run `python -m pytest v2/ -v` green before declaring any phase done.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `v2/browser/build_league_db.py` | DB build | Add `count_5v5_events`, `build_events_5v5_table`, `corsi_for_game`, `build_onice_5v5_table`; wire both builders into `main()` |
| `v2/browser/metrics.py` | Shared metric math | Add `carryover_per_player`, `events_per60`, `corsi_per60` |
| `v2/browser/pages/player.py` | Player page render | Add `line_number` to `_ALL_COMP_SQL`; load bursts; extend `lg` pool + selected-player summary + stat cells/ranks across 3 phases |
| `v2/browser/test_rate_metrics.py` | New tests | Unit tests for the three `metrics.py` helpers + the two builder pure functions |

---

# PHASE 1 — Carry-over stats (display only, no new tables)

Adds `SB/a60`, `Max MPH`, `DPL`, `DPS+` to the player page. Data already exists: bursts CSV (`runtime_paths.player_bursts_csv`), `competition.line_number`, and `compute_deployment_metrics`.

### Task 1: `carryover_per_player` helper + wire into player page

**Files:**
- Modify: `v2/browser/metrics.py` (append function)
- Create: `v2/browser/test_rate_metrics.py`
- Modify: `v2/browser/pages/player.py` (`_ALL_COMP_SQL` ~line 64-72; `lg` pool ~line 206-270; summary cells ~line 289-311)

**Interfaces:**
- Produces: `carryover_per_player(comp_df: pd.DataFrame, bursts_df: pd.DataFrame) -> pd.DataFrame`
  - `comp_df` columns used: `playerId`, `line_number`
  - `bursts_df` indexed by `playerId` with columns `bursts_per_60`, `speed_max_mph`
  - Returns DataFrame indexed by `playerId` with columns: `avg_line`, `bursts_per_60`, `speed_max_mph`

- [ ] **Step 1: Write the failing test**

In `v2/browser/test_rate_metrics.py`:

```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from metrics import carryover_per_player


def test_carryover_per_player_aggregates_line_and_joins_bursts():
    comp = pd.DataFrame({
        "playerId": [1, 1, 2],
        "line_number": [1, 3, 2],
    })
    bursts = pd.DataFrame(
        {"bursts_per_60": [4.5, 1.2], "speed_max_mph": [22.1, 20.0]},
        index=pd.Index([1, 2], name="playerId"),
    )
    out = carryover_per_player(comp, bursts)
    assert out.loc[1, "avg_line"] == 2.0          # mean(1, 3)
    assert out.loc[1, "bursts_per_60"] == 4.5
    assert out.loc[2, "speed_max_mph"] == 20.0


def test_carryover_per_player_missing_bursts_is_nan():
    comp = pd.DataFrame({"playerId": [9], "line_number": [2]})
    bursts = pd.DataFrame(columns=["bursts_per_60", "speed_max_mph"])
    bursts.index.name = "playerId"
    out = carryover_per_player(comp, bursts)
    assert out.loc[9, "avg_line"] == 2.0
    assert pd.isna(out.loc[9, "bursts_per_60"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/test_rate_metrics.py -v`
Expected: FAIL with `ImportError: cannot import name 'carryover_per_player'`

- [ ] **Step 3: Write minimal implementation**

Append to `v2/browser/metrics.py`:

```python
def carryover_per_player(comp_df: pd.DataFrame, bursts_df: pd.DataFrame) -> pd.DataFrame:
    """Per-player carry-over stats: mean line number joined with skating bursts.

    Args:
        comp_df:   competition rows with columns playerId, line_number.
        bursts_df: indexed by playerId with bursts_per_60, speed_max_mph.

    Returns:
        DataFrame indexed by playerId with avg_line, bursts_per_60, speed_max_mph.
        bursts columns are NaN for players absent from bursts_df.
    """
    out = (
        comp_df.groupby("playerId")["line_number"]
        .mean()
        .rename("avg_line")
        .to_frame()
    )
    return out.join(bursts_df[["bursts_per_60", "speed_max_mph"]])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/test_rate_metrics.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Add `line_number` to the league pool query**

In `v2/browser/pages/player.py`, `_ALL_COMP_SQL` (lines 64-72), add `c.line_number` to the SELECT list:

```python
_ALL_COMP_SQL = """
SELECT c.playerId, c.position, c.team, c.gameId, c.toi_seconds, c.total_toi_seconds,
       c.pct_vs_top_fwd, c.pct_vs_top_def, c.comp_fwd, c.comp_def, c.line_number,
       c.deployment_score,
       g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
JOIN games g ON c.gameId = g.gameId
WHERE c.position IN ('F', 'D')
  AND g.gameDate BETWEEN ? AND ?
"""
```

(`deployment_score` is added too — `compute_deployment_metrics` needs it for `DPS+` ranks.)

- [ ] **Step 6: Load bursts and extend the `lg` pool**

In `v2/browser/pages/player.py`, add near the top imports:

```python
from runtime_paths import player_bursts_csv
from metrics import carryover_per_player
```

Add a module-level bursts loader (mirror `pages/skaters.py:36-42`):

```python
def _load_bursts(season: str) -> pd.DataFrame:
    path = player_bursts_csv(season)
    if not path.exists():
        return pd.DataFrame(columns=["bursts_per_60", "speed_max_mph"]).set_index(
            pd.Index([], name="playerId")
        )
    df = pd.read_csv(path)[["playerId", "bursts_per_60", "speed_max_mph"]]
    return df.set_index("playerId")
```

(`import pandas as pd` is already present? It is not — add `import pandas as pd` to the imports.)

Inside `update_player`, after `lg_metrics` is joined into `lg` (~line 243), add carry-over columns to the pool and DPS+:

```python
        bursts_df = _load_bursts(season)
        carry = carryover_per_player(league_comp_df, bursts_df)
        lg = lg.join(carry)
        if not lg_metrics.empty:
            rate_col = "fwd_deployment_rate" if position == "F" else "deployment_rate"
            if rate_col in lg_metrics.columns:
                lg["dps_plus"] = lg_metrics[rate_col]
```

- [ ] **Step 7: Add ranks and selected-player values, then stat cells**

In the `ranks = { ... }` dict (lines 257-270), add:

```python
                "SB/a60":   _rank("bursts_per_60"),
                "Max MPH":  _rank("speed_max_mph"),
                "DPL":      _rank("avg_line", ascending=True),   # line 1 = best, rank ascending
                "DPS+":     _rank("dps_plus"),
```

Compute the selected player's values from the same pool so value and rank never drift. After the `ranks` dict, add:

```python
        def _pool_val(col):
            if pid in lg.index and col in lg.columns:
                v = lg.loc[pid, col]
                return None if pd.isna(v) else float(v)
            return None

        sb_a60   = _pool_val("bursts_per_60")
        max_mph  = _pool_val("speed_max_mph")
        dpl_val  = _pool_val("avg_line")
        dps_val  = _pool_val("dps_plus")
```

In the `summary_section` cell list (lines 292-304), append after the `wPPI+` cell:

```python
                stat_cell("SB/a60", _fmt(sb_a60), ranks.get("SB/a60")),
                stat_cell("Max MPH", _fmt(max_mph), ranks.get("Max MPH")),
                stat_cell("DPL", _fmt(dpl_val), ranks.get("DPL")),
                stat_cell("DPS+", _fmt(dps_val, 1), ranks.get("DPS+")),
```

- [ ] **Step 8: Manually verify against the leaderboard**

Run the app and open a known player (e.g. a regular top-line forward). Confirm `SB/a60`, `Max MPH`, `DPL`, `DPS+` appear in the summary strip and match that player's row on `/skaters` for the full-season date range.

Run: `python -m pytest v2/ -v`
Expected: all tests PASS.

- [ ] **Step 9: Stage Phase 1**

```bash
git add v2/browser/metrics.py v2/browser/test_rate_metrics.py v2/browser/pages/player.py
```

Report staged diff to oiler (do not commit).

---

# PHASE 2 — Individual events (`events_5v5` table + per-60 display)

### Task 2: `count_5v5_events` + `build_events_5v5_table`

**Files:**
- Modify: `v2/browser/build_league_db.py` (add functions; wire into `main()` after `build_points_5v5_table`, ~line 871)
- Modify: `v2/browser/test_rate_metrics.py`

**Interfaces:**
- Produces: `count_5v5_events(df: pd.DataFrame, game_id: int) -> pd.DataFrame`
  - `df`: one game's flatplays rows (columns include `typeDescKey`, `situationCode`, `details.hittingPlayerId`, `details.blockingPlayerId`, `details.playerId`)
  - Returns per-player rows: columns `gameId`, `playerId`, `hits`, `blocks`, `takeaways`, `giveaways`
- Produces: `build_events_5v5_table(conn)` writing table `events_5v5(gameId, playerId, hits, blocks, takeaways, giveaways)`

- [ ] **Step 1: Write the failing test**

In `v2/browser/test_rate_metrics.py`:

```python
from build_league_db import count_5v5_events


def test_count_5v5_events_credits_correct_fields_and_filters_strength():
    df = pd.DataFrame([
        {"typeDescKey": "hit",          "situationCode": "1551", "details.hittingPlayerId": 10, "details.blockingPlayerId": None, "details.playerId": None},
        {"typeDescKey": "hit",          "situationCode": "1441", "details.hittingPlayerId": 10, "details.blockingPlayerId": None, "details.playerId": None},  # not 5v5
        {"typeDescKey": "blocked-shot", "situationCode": "1551", "details.hittingPlayerId": None, "details.blockingPlayerId": 20, "details.playerId": None},
        {"typeDescKey": "takeaway",     "situationCode": "1551", "details.hittingPlayerId": None, "details.blockingPlayerId": None, "details.playerId": 30},
        {"typeDescKey": "giveaway",     "situationCode": "1551", "details.hittingPlayerId": None, "details.blockingPlayerId": None, "details.playerId": 30},
    ])
    out = count_5v5_events(df, game_id=2025020001).set_index("playerId")
    assert out.loc[10, "hits"] == 1          # 1441 hit excluded
    assert out.loc[20, "blocks"] == 1
    assert out.loc[30, "takeaways"] == 1
    assert out.loc[30, "giveaways"] == 1
    assert (out["gameId"] == 2025020001).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/test_rate_metrics.py::test_count_5v5_events_credits_correct_fields_and_filters_strength -v`
Expected: FAIL with `ImportError: cannot import name 'count_5v5_events'`

- [ ] **Step 3: Write minimal implementation**

In `v2/browser/build_league_db.py`, add after `build_points_5v5_table`:

```python
def count_5v5_events(df, game_id):
    """Count per-player 5v5 hits/blocks/takeaways/giveaways for one game's flatplays."""
    five_v_five = df[df["situationCode"].astype(str).isin(FIVE_V_FIVE)]
    counts = {}  # playerId -> dict

    def _bump(pid_val, key):
        if pd.notna(pid_val):
            pid = int(pid_val)
            row = counts.setdefault(pid, {"hits": 0, "blocks": 0, "takeaways": 0, "giveaways": 0})
            row[key] += 1

    for _, r in five_v_five.iterrows():
        t = r["typeDescKey"]
        if t == "hit":
            _bump(r.get("details.hittingPlayerId"), "hits")
        elif t == "blocked-shot":
            _bump(r.get("details.blockingPlayerId"), "blocks")
        elif t == "takeaway":
            _bump(r.get("details.playerId"), "takeaways")
        elif t == "giveaway":
            _bump(r.get("details.playerId"), "giveaways")

    records = [{"gameId": game_id, "playerId": pid, **vals} for pid, vals in counts.items()]
    return pd.DataFrame(records, columns=["gameId", "playerId", "hits", "blocks", "takeaways", "giveaways"])


def build_events_5v5_table(conn):
    """Per-game 5v5 individual event counts from flattened plays."""
    frames = []
    for path in sorted(glob.glob(os.path.join(FLATPLAYS_DIR, "*.csv"))):
        game_id = int(os.path.basename(path).replace(".csv", ""))
        df = pd.read_csv(path, low_memory=False)
        game_df = count_5v5_events(df, game_id)
        if not game_df.empty:
            frames.append(game_df)
    if not frames:
        pd.DataFrame(columns=["gameId", "playerId", "hits", "blocks", "takeaways", "giveaways"]).to_sql(
            "events_5v5", conn, if_exists="replace", index=False
        )
        print("  events_5v5: 0 rows (no flatplays found)")
        return
    out = pd.concat(frames, ignore_index=True)
    out.to_sql("events_5v5", conn, if_exists="replace", index=False)
    print(f"  events_5v5: {len(out)} rows from {len(frames)} games")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/test_rate_metrics.py -v`
Expected: PASS

- [ ] **Step 5: Wire builder into `main()`**

In `v2/browser/build_league_db.py` `main()`, add after `build_points_5v5_table(conn)` (line 871):

```python
        build_events_5v5_table(conn)
```

- [ ] **Step 6: Rebuild the DB and sanity-check**

Run: `python v2/browser/build_league_db.py 2025`
Then verify:

```bash
python3 -c "import sqlite3; c=sqlite3.connect('data/2025/generated/browser/league.db'); print(c.execute('select count(*), sum(hits), sum(blocks) from events_5v5').fetchone())"
```

Expected: nonzero rows and plausible totals (hits and blocks both > 0).

- [ ] **Step 7: Stage**

```bash
git add v2/browser/build_league_db.py v2/browser/test_rate_metrics.py
```

Report to oiler.

### Task 3: `events_per60` helper

**Files:**
- Modify: `v2/browser/metrics.py`
- Modify: `v2/browser/test_rate_metrics.py`

**Interfaces:**
- Produces: `events_per60(events_df: pd.DataFrame, toi_df: pd.DataFrame) -> pd.DataFrame`
  - `events_df`: columns `gameId`, `playerId`, `hits`, `blocks`, `takeaways`, `giveaways`
  - `toi_df`: per-`(gameId, playerId)` with `toi_seconds` (all filtered games — the denominator)
  - Returns indexed by `playerId`: `hits_per60`, `blocks_per60`, `tk_per60`, `gv_per60`

- [ ] **Step 1: Write the failing test**

```python
from metrics import events_per60


def test_events_per60_uses_full_toi_denominator():
    events = pd.DataFrame([
        {"gameId": 1, "playerId": 7, "hits": 3, "blocks": 1, "takeaways": 0, "giveaways": 2},
    ])
    # player 7 played two games at 5v5: 1200s total -> 3 hits over 1200s = 9.0/60min
    toi = pd.DataFrame([
        {"gameId": 1, "playerId": 7, "toi_seconds": 600},
        {"gameId": 2, "playerId": 7, "toi_seconds": 600},
    ])
    out = events_per60(events, toi)
    assert round(out.loc[7, "hits_per60"], 2) == 9.0      # 3 * 3600 / 1200
    assert round(out.loc[7, "gv_per60"], 2) == 6.0        # 2 * 3600 / 1200
    assert out.loc[7, "blocks_per60"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/test_rate_metrics.py::test_events_per60_uses_full_toi_denominator -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write minimal implementation**

Append to `v2/browser/metrics.py`:

```python
def events_per60(events_df: pd.DataFrame, toi_df: pd.DataFrame) -> pd.DataFrame:
    """Per-60 individual-event rates over all of a player's 5v5 TOI.

    Args:
        events_df: per-(gameId, playerId) with hits, blocks, takeaways, giveaways.
        toi_df:    per-(gameId, playerId) with toi_seconds (denominator = all filtered games).

    Returns:
        Indexed by playerId: hits_per60, blocks_per60, tk_per60, gv_per60.
    """
    toi = toi_df.groupby("playerId")["toi_seconds"].sum()
    sums = events_df.groupby("playerId")[["hits", "blocks", "takeaways", "giveaways"]].sum()
    out = sums.reindex(toi.index).fillna(0).join(toi.rename("toi"))
    denom = out["toi"].where(out["toi"] > 0)
    return pd.DataFrame({
        "hits_per60":   out["hits"]   * 3600 / denom,
        "blocks_per60": out["blocks"] * 3600 / denom,
        "tk_per60":     out["takeaways"] * 3600 / denom,
        "gv_per60":     out["giveaways"] * 3600 / denom,
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/test_rate_metrics.py -v`
Expected: PASS

- [ ] **Step 5: Stage**

```bash
git add v2/browser/metrics.py v2/browser/test_rate_metrics.py
```

### Task 4: Wire events per-60 into the player page

**Files:**
- Modify: `v2/browser/pages/player.py` (`update_player`: pool + selected-player + cells)

**Interfaces:**
- Consumes: `events_per60` (Task 3); `events_5v5` table (Task 2)

- [ ] **Step 1: Query events for the filtered window**

In `v2/browser/pages/player.py`, add a module constant near the other SQL:

```python
_EVENTS_SQL = "SELECT gameId, playerId, hits, blocks, takeaways, giveaways FROM events_5v5"
```

Inside `update_player`, after `all_comp_df` is loaded (~line 175), load events and restrict to the games already in the pool:

```python
        events_df = league_query(_EVENTS_SQL, season=season)
```

- [ ] **Step 2: Extend the `lg` pool and selected-player values**

After the carry-over join from Phase 1 (~after `lg = lg.join(carry)`), add:

```python
        from metrics import events_per60
        pool_games = league_comp_df[["gameId", "playerId", "toi_seconds"]]
        if not events_df.empty:
            pool_events = events_df.merge(
                league_comp_df[["gameId", "playerId"]].drop_duplicates(),
                on=["gameId", "playerId"], how="inner",
            )
            lg = lg.join(events_per60(pool_events, pool_games))
```

(Move the `from metrics import events_per60` to the top-of-file imports instead of inline — shown here for locality.)

- [ ] **Step 3: Add ranks and cells**

In the `ranks` dict add:

```python
                "Hits/60":   _rank("hits_per60"),
                "Blocks/60": _rank("blocks_per60"),
                "TK/60":     _rank("tk_per60"),
                "GV/60":     _rank("gv_per60"),
```

Add selected-player values via the existing `_pool_val` helper and cells in `summary_section`:

```python
                stat_cell("Hits/60", _fmt(_pool_val("hits_per60")), ranks.get("Hits/60")),
                stat_cell("Blocks/60", _fmt(_pool_val("blocks_per60")), ranks.get("Blocks/60")),
                stat_cell("TK/60", _fmt(_pool_val("tk_per60")), ranks.get("TK/60")),
                stat_cell("GV/60", _fmt(_pool_val("gv_per60")), ranks.get("GV/60")),
```

- [ ] **Step 4: Verify**

Run: `python -m pytest v2/ -v` (PASS), then open a player and confirm the four event-rate cells render with ranks and plausible values (a checking forward shows higher Hits/60, a shutdown D higher Blocks/60).

- [ ] **Step 5: Stage**

```bash
git add v2/browser/pages/player.py
```

---

# PHASE 3 — On-ice Corsi (`onice_5v5` table + CF/60, CA/60, CF%)

### Task 5: `corsi_for_game` + `build_onice_5v5_table`

**Files:**
- Modify: `v2/browser/build_league_db.py`
- Modify: `v2/browser/test_rate_metrics.py`

**Interfaces:**
- Produces: `corsi_for_game(flat_df: pd.DataFrame, timeline_rows: list[dict], game_id: int) -> pd.DataFrame`
  - `flat_df`: one game's flatplays (columns `typeDescKey`, `situationCode`, `timeInPeriod`, `periodDescriptor.number`, `details.shootingPlayerId`, `details.scoringPlayerId`)
  - `timeline_rows`: list of dicts from `csv.DictReader` of the timeline CSV (keys `period`, `secondsIntoPeriod`, `awaySkaters`, `homeSkaters`, `situationCode`)
  - Returns per-player rows: `gameId`, `playerId`, `cf`, `ca`. **Empty DataFrame if `timeline_rows` is empty** (graceful missing-timeline path).
- Produces: `build_onice_5v5_table(conn)` writing `onice_5v5(gameId, playerId, cf, ca)`, skipping + counting games with no timeline.

- [ ] **Step 1: Write the failing test**

```python
from build_league_db import corsi_for_game

_CORSI_COLS = {
    "typeDescKey": None, "situationCode": None, "timeInPeriod": None,
    "periodDescriptor.number": None, "details.shootingPlayerId": None,
    "details.scoringPlayerId": None,
}


def _ev(**kw):
    row = dict(_CORSI_COLS)
    row.update(kw)
    return row


def test_corsi_for_game_credits_shooter_side_from_timeline():
    # Home shooter 100 vs away on-ice {200,201,202,203,204}; home {100,101,102,103,104}
    timeline = [{
        "period": "1", "secondsIntoPeriod": "22", "situationCode": "1551",
        "awaySkaters": "200|201|202|203|204",
        "homeSkaters": "100|101|102|103|104",
    }]
    flat = pd.DataFrame([
        # a blocked shot BY home player 100 (blocker is away 200) -> still CF for home
        _ev(typeDescKey="blocked-shot", situationCode="1551", timeInPeriod="00:22",
            **{"periodDescriptor.number": 1, "details.shootingPlayerId": 100}),
    ])
    out = corsi_for_game(flat, timeline, game_id=99).set_index("playerId")
    assert out.loc[100, "cf"] == 1 and out.loc[100, "ca"] == 0   # shooter side = home
    assert out.loc[200, "ca"] == 1 and out.loc[200, "cf"] == 0   # away side against


def test_corsi_for_game_empty_timeline_returns_empty():
    flat = pd.DataFrame([
        _ev(typeDescKey="shot-on-goal", situationCode="1551", timeInPeriod="00:10",
            **{"periodDescriptor.number": 1, "details.shootingPlayerId": 100}),
    ])
    assert corsi_for_game(flat, [], game_id=99).empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/test_rate_metrics.py -k corsi -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write minimal implementation**

In `v2/browser/build_league_db.py`:

```python
_CORSI_TYPES = {"shot-on-goal", "missed-shot", "blocked-shot", "goal"}


def _mmss_to_secs(value):
    mm, ss = str(value).split(":")
    return int(mm) * 60 + int(ss)


def corsi_for_game(flat_df, timeline_rows, game_id):
    """Per-player on-ice 5v5 Corsi for/against for one game.

    Shooter side is determined by which timeline skater list (home/away) contains the
    shooter at the event's second. Returns empty if the timeline is missing.
    """
    if not timeline_rows:
        return pd.DataFrame(columns=["gameId", "playerId", "cf", "ca"])

    # (period, secondsIntoPeriod) -> (away_set, home_set)
    onice = {}
    for row in timeline_rows:
        key = (int(row["period"]), int(row["secondsIntoPeriod"]))
        away = [int(p) for p in row["awaySkaters"].split("|")] if row.get("awaySkaters") else []
        home = [int(p) for p in row["homeSkaters"].split("|")] if row.get("homeSkaters") else []
        onice[key] = (away, home)

    counts = {}  # playerId -> {"cf": int, "ca": int}

    def _bump(pid, key):
        counts.setdefault(pid, {"cf": 0, "ca": 0})[key] += 1

    corsi = flat_df[
        flat_df["typeDescKey"].isin(_CORSI_TYPES)
        & flat_df["situationCode"].astype(str).isin(FIVE_V_FIVE)
    ]
    for _, e in corsi.iterrows():
        shooter = e.get("details.shootingPlayerId")
        if pd.isna(shooter):
            shooter = e.get("details.scoringPlayerId")
        if pd.isna(shooter):
            continue
        shooter = int(shooter)
        key = (int(e["periodDescriptor.number"]), _mmss_to_secs(e["timeInPeriod"]))
        if key not in onice:
            continue
        away, home = onice[key]
        if shooter in home:
            for_side, against_side = home, away
        elif shooter in away:
            for_side, against_side = away, home
        else:
            continue  # shooter not on ice at that second; skip
        for p in for_side:
            _bump(p, "cf")
        for p in against_side:
            _bump(p, "ca")

    records = [{"gameId": game_id, "playerId": pid, **v} for pid, v in counts.items()]
    return pd.DataFrame(records, columns=["gameId", "playerId", "cf", "ca"])


def build_onice_5v5_table(conn):
    """Per-game on-ice 5v5 Corsi from flatplays joined to per-second timelines."""
    timelines_dir = os.path.join(SEASON_DIR, "generated", "timelines", "csv")
    frames = []
    skipped = 0
    for path in sorted(glob.glob(os.path.join(FLATPLAYS_DIR, "*.csv"))):
        game_id = int(os.path.basename(path).replace(".csv", ""))
        timeline_path = os.path.join(timelines_dir, f"{game_id}.csv")
        if not os.path.exists(timeline_path):
            skipped += 1
            continue
        with open(timeline_path, newline="") as f:
            timeline_rows = list(csv.DictReader(f))
        flat_df = pd.read_csv(path, low_memory=False)
        game_df = corsi_for_game(flat_df, timeline_rows, game_id)
        if not game_df.empty:
            frames.append(game_df)
    if not frames:
        pd.DataFrame(columns=["gameId", "playerId", "cf", "ca"]).to_sql(
            "onice_5v5", conn, if_exists="replace", index=False
        )
        print(f"  onice_5v5: 0 rows ({skipped} games skipped, no timeline)")
        return
    out = pd.concat(frames, ignore_index=True)
    out.to_sql("onice_5v5", conn, if_exists="replace", index=False)
    print(f"  onice_5v5: {len(out)} rows from {len(frames)} games ({skipped} skipped, no timeline)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/test_rate_metrics.py -k corsi -v`
Expected: PASS (both corsi tests)

- [ ] **Step 5: Wire builder into `main()`**

In `main()`, add after `build_events_5v5_table(conn)`:

```python
        build_onice_5v5_table(conn)
```

- [ ] **Step 6: Rebuild and validate**

Run: `python v2/browser/build_league_db.py 2025`

Validation — for one game, total CF across all players ÷ 5 should equal the count of 5v5 Corsi events:

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('data/2025/generated/browser/league.db')
cf = c.execute('select sum(cf) from onice_5v5 where gameId=2025020001').fetchone()[0]
print('sum(cf)/5 =', (cf or 0)/5)
"
```

Compare against the count of 5v5 `shot-on-goal`+`missed-shot`+`blocked-shot`+`goal` events in `data/2025/generated/flatplays/2025020001.csv` — they should match (each attempt credits exactly 5 skaters with CF).

- [ ] **Step 7: Stage**

```bash
git add v2/browser/build_league_db.py v2/browser/test_rate_metrics.py
```

### Task 6: `corsi_per60` helper

**Files:**
- Modify: `v2/browser/metrics.py`
- Modify: `v2/browser/test_rate_metrics.py`

**Interfaces:**
- Produces: `corsi_per60(onice_df: pd.DataFrame, toi_df: pd.DataFrame) -> pd.DataFrame`
  - `onice_df`: per-`(gameId, playerId)` with `cf`, `ca`
  - `toi_df`: per-`(gameId, playerId)` with `toi_seconds` (full filtered window)
  - **Denominator restricted to `(gameId, playerId)` present in `onice_df`.**
  - Returns indexed by `playerId`: `cf_per60`, `ca_per60`, `cf_pct`

- [ ] **Step 1: Write the failing test**

```python
from metrics import corsi_per60


def test_corsi_per60_restricts_denominator_to_covered_games():
    onice = pd.DataFrame([
        {"gameId": 1, "playerId": 5, "cf": 10, "ca": 5},
    ])
    # game 2 has no onice row (missing timeline) -> its TOI must NOT dilute the rate
    toi = pd.DataFrame([
        {"gameId": 1, "playerId": 5, "toi_seconds": 600},
        {"gameId": 2, "playerId": 5, "toi_seconds": 600},
    ])
    out = corsi_per60(onice, toi)
    assert round(out.loc[5, "cf_per60"], 1) == 60.0   # 10 * 3600 / 600 (game 1 only)
    assert round(out.loc[5, "ca_per60"], 1) == 30.0   # 5  * 3600 / 600
    assert round(out.loc[5, "cf_pct"], 3) == 0.667    # 10 / 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/test_rate_metrics.py -k corsi_per60 -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write minimal implementation**

Append to `v2/browser/metrics.py`:

```python
def corsi_per60(onice_df: pd.DataFrame, toi_df: pd.DataFrame) -> pd.DataFrame:
    """Per-60 on-ice Corsi, with the TOI denominator restricted to games that have
    on-ice rows (so missing-timeline games do not dilute the rate).

    Args:
        onice_df: per-(gameId, playerId) with cf, ca.
        toi_df:   per-(gameId, playerId) with toi_seconds.

    Returns:
        Indexed by playerId: cf_per60, ca_per60, cf_pct.
    """
    if onice_df.empty:
        return pd.DataFrame(columns=["cf_per60", "ca_per60", "cf_pct"])
    covered = onice_df[["gameId", "playerId"]].drop_duplicates()
    toi_cov = toi_df.merge(covered, on=["gameId", "playerId"], how="inner")
    toi = toi_cov.groupby("playerId")["toi_seconds"].sum()
    sums = onice_df.groupby("playerId")[["cf", "ca"]].sum()
    out = sums.join(toi.rename("toi"))
    denom = out["toi"].where(out["toi"] > 0)
    total = (out["cf"] + out["ca"]).where((out["cf"] + out["ca"]) > 0)
    return pd.DataFrame({
        "cf_per60": out["cf"] * 3600 / denom,
        "ca_per60": out["ca"] * 3600 / denom,
        "cf_pct":   out["cf"] / total,
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/test_rate_metrics.py -v`
Expected: PASS

- [ ] **Step 5: Stage**

```bash
git add v2/browser/metrics.py v2/browser/test_rate_metrics.py
```

### Task 7: Wire Corsi into the player page

**Files:**
- Modify: `v2/browser/pages/player.py`

**Interfaces:**
- Consumes: `corsi_per60` (Task 6); `onice_5v5` table (Task 5)

- [ ] **Step 1: Query onice for the window**

Add module SQL:

```python
_ONICE_SQL = "SELECT gameId, playerId, cf, ca FROM onice_5v5"
```

In `update_player`, load it:

```python
        onice_df = league_query(_ONICE_SQL, season=season)
```

- [ ] **Step 2: Extend pool + selected-player values**

After the events join (Phase 2), add (with `from metrics import corsi_per60` hoisted to top imports):

```python
        if not onice_df.empty:
            pool_onice = onice_df.merge(
                league_comp_df[["gameId", "playerId"]].drop_duplicates(),
                on=["gameId", "playerId"], how="inner",
            )
            lg = lg.join(corsi_per60(pool_onice, pool_games))
```

- [ ] **Step 3: Ranks + cells**

In `ranks`:

```python
                "CF/60":  _rank("cf_per60"),
                "CA/60":  _rank("ca_per60", ascending=True),   # fewer attempts against = better
                "CF%":    _rank("cf_pct"),
```

Cells in `summary_section`:

```python
                stat_cell("CF/60", _fmt(_pool_val("cf_per60"), 1), ranks.get("CF/60")),
                stat_cell("CA/60", _fmt(_pool_val("ca_per60"), 1), ranks.get("CA/60")),
                stat_cell("CF%", _fmt((_pool_val("cf_pct") or 0) * 100, 1) + "%" if _pool_val("cf_pct") is not None else "—", ranks.get("CF%")),
```

- [ ] **Step 4: Verify**

Run: `python -m pytest v2/ -v` (PASS). Open a player; confirm `CF/60`, `CA/60`, `CF%` render with ranks. Spot-check a strong possession player shows `CF% > 50%`.

- [ ] **Step 5: Stage**

```bash
git add v2/browser/pages/player.py
```

---

## Self-Review

**Spec coverage:**
- Carry-over `SB/a60`, `Max MPH`, `DPL`, `DPS+` → Task 1. ✓
- `events_5v5` table + Hits/Blocks/TK/GV per 60 → Tasks 2-4. ✓
- `onice_5v5` table + CF/60, CA/60, CF% → Tasks 5-7. ✓
- Per-60 denominator = `competition.toi_seconds` → `events_per60`, `corsi_per60`. ✓
- Blocked-shot dual role → `count_5v5_events` credits blocker; `corsi_for_game` credits shooter side. ✓
- Shooter side from timeline, not `eventOwnerTeamId` → `corsi_for_game`. ✓
- Missing timeline graceful + self-healing → `corsi_for_game` empty path, `build_onice_5v5_table` skip+log, full-replace build. ✓
- CF/60 denominator restricted to covered games → `corsi_per60`. ✓
- Ranks for every new stat → Tasks 1, 4, 7. ✓
- Shared logic in `metrics.py` → all three helpers there. ✓
- Synthetic-data tests → `test_rate_metrics.py`. ✓
- Phased + independently shippable → Phases 1/2/3 each end staged & tested. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `carryover_per_player` → `avg_line`/`bursts_per_60`/`speed_max_mph`; `events_per60` → `hits_per60`/`blocks_per60`/`tk_per60`/`gv_per60`; `corsi_per60` → `cf_per60`/`ca_per60`/`cf_pct`; `corsi_for_game`/`count_5v5_events` return `gameId,playerId,...`. Pool column names match the `_rank()`/`_pool_val()` lookups in player.py. ✓

## Notes for the implementer

- `_rank("avg_line", ascending=True)` and `_rank("ca_per60", ascending=True)`: for these, *lower is better* (line 1, fewer shots against), so rank ascends. All other new stats rank descending (default).
- Hoist the `from metrics import ...` lines to the top of `player.py` rather than importing inside the callback — they're shown inline only for locality.
- `_pool_val` reads the selected player's value from the same `lg` pool used for ranks, guaranteeing value/rank consistency. It returns `None` when the player is outside the pool (GP < 5), and `_fmt(None)` renders `—`.
