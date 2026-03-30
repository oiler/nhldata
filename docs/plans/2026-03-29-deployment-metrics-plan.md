# Deployment Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add forward line detection and defenseman deployment scoring to the competition pipeline, then surface `deployment_rate` (normalized) in the browser pages.

**Architecture:** Two new pure functions in `compute_competition.py` (one per loop: line detection, D scoring) write `line_number` and `deployment_score` columns to each game's competition CSV. `build_league_db.py` picks them up automatically (no code change needed — `pd.to_sql` derives schema from DataFrame). `compute_deployment_metrics()` in `filters.py` is extended to compute `deployment_rate` from the filtered `comp_df`. Browser pages get one new column each: F tables show "Line", D tables show "Dep Score" (game page) or "D-Rate" (team/skaters).

**Tech Stack:** Python, pandas, itertools.combinations, SQLite (via existing infrastructure)

---

## File Map

| File | Change |
|------|--------|
| `v2/competition/compute_competition.py` | Add `assign_forward_lines()`, `compute_deployment_scores()`, wire into `run_game()` + `write_output()` |
| `v2/competition/tests/test_compute_competition.py` | 4 new tests for the two new functions |
| `v2/browser/filters.py` | Extend `compute_deployment_metrics()` to compute and return `deployment_rate` |
| `v2/browser/tests/test_deployment_metrics.py` | 2 new tests + update `test_output_columns` |
| `v2/browser/pages/game.py` | Add `line_number` to F table, `deployment_score` to D table |
| `v2/browser/pages/team.py` | Add `c.deployment_score` to SQL; add `deployment_rate` to D table only |
| `v2/browser/pages/skaters.py` | Add `c.deployment_score` to SQL; add `deployment_rate` column |

`build_league_db.py` — **no change needed.** `build_competition_table` uses `pd.read_csv` + `to_sql(if_exists="replace")`, so new CSV columns propagate automatically.

---

### Task 1: Write failing tests for `assign_forward_lines()`

**Files:**
- Modify: `v2/competition/tests/test_compute_competition.py`

- [ ] **Step 1: Add two tests at the bottom of the file**

```python
from compute_competition import assign_forward_lines


def test_greedy_line_detection_standard():
    """12 forwards, 4 clean lines — greedy assigns lines 1–4 in TOI order."""
    fwd_ids = set(range(1, 13))
    # Only the 3 fwds on ice each row are in fwd_ids; pids 20–34 are D or opposing team
    rows = (
        [{"situationCode": "1551", "awaySkaters": "1|2|3|20|21",    "homeSkaters": "30|31|32|33|34"}] * 300
      + [{"situationCode": "1551", "awaySkaters": "4|5|6|20|21",    "homeSkaters": "30|31|32|33|34"}] * 200
      + [{"situationCode": "1551", "awaySkaters": "7|8|9|20|21",    "homeSkaters": "30|31|32|33|34"}] * 100
      + [{"situationCode": "1551", "awaySkaters": "10|11|12|20|21", "homeSkaters": "30|31|32|33|34"}] * 50
    )
    result = assign_forward_lines(rows, fwd_ids)
    assert result[1] == 1 and result[2] == 1 and result[3] == 1
    assert result[4] == 2 and result[5] == 2 and result[6] == 2
    assert result[7] == 3 and result[8] == 3 and result[9] == 3
    assert result[10] == 4 and result[11] == 4 and result[12] == 4


def test_greedy_line_detection_11_forwards():
    """11 forwards — lines 1–3 assigned to 9 players, remaining 2 get line 4."""
    fwd_ids = set(range(1, 12))  # 11 forwards
    rows = (
        [{"situationCode": "1551", "awaySkaters": "1|2|3|20|21",  "homeSkaters": "30|31|32|33|34"}] * 300
      + [{"situationCode": "1551", "awaySkaters": "4|5|6|20|21",  "homeSkaters": "30|31|32|33|34"}] * 200
      + [{"situationCode": "1551", "awaySkaters": "7|8|9|20|21",  "homeSkaters": "30|31|32|33|34"}] * 100
      + [{"situationCode": "1551", "awaySkaters": "10|11|20|21|22", "homeSkaters": "30|31|32|33|34"}] * 50
        # players 10 and 11 appear together but never form a 3-man combo → both fall to line 4
    )
    result = assign_forward_lines(rows, fwd_ids)
    assert result[1] == 1 and result[2] == 1 and result[3] == 1
    assert result[4] == 2 and result[5] == 2 and result[6] == 2
    assert result[7] == 3 and result[8] == 3 and result[9] == 3
    assert result[10] == 4 and result[11] == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run from project root: `python -m pytest v2/competition/tests/test_compute_competition.py -k "line_detection" -v`

Expected: `ImportError: cannot import name 'assign_forward_lines'`

---

### Task 2: Implement `assign_forward_lines()`

**Files:**
- Modify: `v2/competition/compute_competition.py`

- [ ] **Step 1: Add import at the top of the file (after existing imports)**

```python
from itertools import combinations as _combinations
```

- [ ] **Step 2: Add `assign_forward_lines()` before `run_game()`**

```python
def assign_forward_lines(
    rows: List[dict],
    team_fwd_ids: set,
) -> Dict[int, int]:
    """Greedy forward line detection for one team.

    Args:
        rows: all timeline row dicts for the game
        team_fwd_ids: set of INTEGER player IDs who are forwards for this team

    Returns:
        {player_id: line_number}  line_number is 1–4; every ID in team_fwd_ids is present.
    """
    combo_seconds: Dict[tuple, int] = {}
    for row in rows:
        if row.get("situationCode") != "1551":
            continue
        on_ice: set = set()
        for col in ("awaySkaters", "homeSkaters"):
            raw = row.get(col, "")
            if raw:
                for pid_str in raw.split("|"):
                    pid = int(pid_str)
                    if pid in team_fwd_ids:
                        on_ice.add(pid)
        if len(on_ice) < 3:
            continue
        for combo in _combinations(sorted(on_ice), 3):
            combo_seconds[combo] = combo_seconds.get(combo, 0) + 1

    # Greedy: assign lines 1–4 to the top non-overlapping combos
    sorted_combos = sorted(combo_seconds.items(), key=lambda x: x[1], reverse=True)
    assigned: Dict[int, int] = {}
    used: set = set()
    line = 1
    for combo, _ in sorted_combos:
        if line > 4:
            break
        if any(p in used for p in combo):
            continue
        for p in combo:
            assigned[p] = line
            used.add(p)
        line += 1

    # Any forward not assigned by greedy → line 4
    for pid in team_fwd_ids:
        if pid not in assigned:
            assigned[pid] = 4

    return assigned
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m pytest v2/competition/tests/test_compute_competition.py -k "line_detection" -v`

Expected: 2 PASSED

---

### Task 3: Write failing tests for `compute_deployment_scores()`

**Files:**
- Modify: `v2/competition/tests/test_compute_competition.py`

- [ ] **Step 1: Add two tests at the bottom of the file**

```python
from compute_competition import compute_deployment_scores


def test_deployment_score_pure_line1():
    """D facing pure line 1 for 100 seconds → score = 100 × 9 = 900."""
    positions = {
        1: "F", 2: "F", 3: "F",    # HOME line 1
        10: "D", 11: "D",           # HOME D (being measured)
        20: "F", 21: "F", 22: "F",  # AWAY line 1
        23: "D", 24: "D",           # AWAY D
    }
    teams = {
        1: "HOME", 2: "HOME", 3: "HOME", 10: "HOME", 11: "HOME",
        20: "AWAY", 21: "AWAY", 22: "AWAY", 23: "AWAY", 24: "AWAY",
    }
    line_assignments = {
        "HOME": {1: 1, 2: 1, 3: 1},
        "AWAY": {20: 1, 21: 1, 22: 1},
    }
    rows = [
        {"situationCode": "1551", "homeSkaters": "1|2|3|10|11", "awaySkaters": "20|21|22|23|24"}
    ] * 100

    scores = compute_deployment_scores(rows, positions, teams, line_assignments)

    # HOME D face AWAY L1: sum=3, pts=9; 100s → 900
    assert scores.get(10) == 900
    assert scores.get(11) == 900
    # Forwards not in result (or 0)
    assert scores.get(1, 0) == 0


def test_deployment_score_mixed():
    """D faces L1 for 100s (9 pts/s) then L2 for 100s (6 pts/s) → score = 1500."""
    positions = {
        1: "F", 2: "F", 3: "F",    # HOME line 1
        10: "D", 11: "D",           # HOME D
        20: "F", 21: "F", 22: "F",  # AWAY line 1
        23: "F", 24: "F", 25: "F",  # AWAY line 2
        30: "D", 31: "D",           # AWAY D
    }
    teams = {
        1: "HOME", 2: "HOME", 3: "HOME", 10: "HOME", 11: "HOME",
        20: "AWAY", 21: "AWAY", 22: "AWAY",
        23: "AWAY", 24: "AWAY", 25: "AWAY",
        30: "AWAY", 31: "AWAY",
    }
    line_assignments = {
        "HOME": {1: 1, 2: 1, 3: 1},
        "AWAY": {20: 1, 21: 1, 22: 1, 23: 2, 24: 2, 25: 2},
    }
    # 100s vs AWAY L1 (sum=3, pts=9)
    rows_l1 = [
        {"situationCode": "1551", "homeSkaters": "1|2|3|10|11", "awaySkaters": "20|21|22|30|31"}
    ] * 100
    # 100s vs AWAY L2 (sum=6, pts=6)
    rows_l2 = [
        {"situationCode": "1551", "homeSkaters": "1|2|3|10|11", "awaySkaters": "23|24|25|30|31"}
    ] * 100

    scores = compute_deployment_scores(rows_l1 + rows_l2, positions, teams, line_assignments)

    assert scores.get(10) == 1500  # 900 + 600
    assert scores.get(11) == 1500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest v2/competition/tests/test_compute_competition.py -k "deployment_score" -v`

Expected: `ImportError: cannot import name 'compute_deployment_scores'`

---

### Task 4: Implement `compute_deployment_scores()`

**Files:**
- Modify: `v2/competition/compute_competition.py`

- [ ] **Step 1: Add `compute_deployment_scores()` immediately after `assign_forward_lines()`**

```python
def compute_deployment_scores(
    rows: List[dict],
    positions: Dict[int, str],
    teams: Dict[int, str],
    line_assignments: Dict[str, Dict[int, int]],
) -> Dict[int, int]:
    """Compute raw deployment score per defenseman for one game.

    For each 5v5 second a D is on ice:
        points = 12 − (lineA + lineB + lineC)  [opposing 3 forwards]
    TOI is embedded — more seconds on ice accumulates more points.

    Args:
        rows: all timeline row dicts for the game
        positions: {player_id: "F"/"D"/"G"}
        teams: {player_id: team_abbrev}
        line_assignments: {team_abbrev: {player_id: line_number}}

    Returns:
        {player_id: deployment_score}  only for D players with > 0 points
    """
    scores: Dict[int, int] = {}

    for row in rows:
        if row.get("situationCode") != "1551":
            continue

        away = [int(p) for p in row["awaySkaters"].split("|")] if row.get("awaySkaters") else []
        home = [int(p) for p in row["homeSkaters"].split("|")] if row.get("homeSkaters") else []

        for player_id, opponents in (
            [(p, home) for p in away] +
            [(p, away) for p in home]
        ):
            if positions.get(player_id) != "D":
                continue

            opp_team = teams.get(opponents[0], "") if opponents else ""
            if not opp_team:
                continue

            opp_fwds = [p for p in opponents if positions.get(p, "F") == "F"]
            if len(opp_fwds) != 3:
                continue  # strict 5v5 only — skip malformed rows

            opp_lines = line_assignments.get(opp_team, {})
            line_sum = sum(opp_lines.get(f, 4) for f in opp_fwds)
            scores[player_id] = scores.get(player_id, 0) + (12 - line_sum)

    return scores
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest v2/competition/tests/test_compute_competition.py -k "deployment_score" -v`

Expected: 2 PASSED

---

### Task 5: Wire into `run_game()` and `write_output()`

**Files:**
- Modify: `v2/competition/compute_competition.py`
- Modify: `v2/competition/tests/test_compute_competition.py`

- [ ] **Step 1: Update `write_output()` to accept and write `line_numbers` and `deployment_scores`**

Replace the `write_output` signature and the rows-building loop. The full updated function:

```python
def write_output(game_id: str, season: str, scores: Dict[int, dict],
                 toi: Dict[int, int], total_toi: Dict[int, int],
                 positions: Dict[int, str],
                 teams: Dict[int, str],
                 line_numbers: Dict[int, int] = None,
                 deployment_scores: Dict[int, int] = None) -> Path:
    """Write per-player competition scores to CSV."""
    if line_numbers is None:
        line_numbers = {}
    if deployment_scores is None:
        deployment_scores = {}

    out_dir = DATA_DIR / season / "generated" / "competition"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{game_id}.csv"

    rows = []
    for pid, data in scores.items():
        pos = positions.get(pid, "F")
        rows.append({
            "gameId":           game_id,
            "playerId":         pid,
            "team":             teams.get(pid, ""),
            "position":         pos,
            "toi_seconds":      toi.get(pid, 0),
            "total_toi_seconds": total_toi.get(pid, 0),
            "comp_fwd":         round(data["comp_fwd"], 2),
            "comp_def":         round(data["comp_def"], 2),
            "pct_vs_top_fwd":   round(data.get("pct_vs_top_fwd", 0.0), 4),
            "pct_vs_top_def":   round(data.get("pct_vs_top_def", 0.0), 4),
            "height_in":                  data.get("height_in", 0),
            "weight_lbs":                 data.get("weight_lbs", 0),
            "heaviness":                  round(data.get("heaviness", 0.0), 4),
            "weighted_forward_heaviness": round(data.get("weighted_forward_heaviness", 0.0), 4),
            "weighted_defense_heaviness": round(data.get("weighted_defense_heaviness", 0.0), 4),
            "weighted_team_heaviness":    round(data.get("weighted_team_heaviness", 0.0), 4),
            "line_number":      line_numbers.get(pid) if pos == "F" else None,
            "deployment_score": deployment_scores.get(pid) if pos == "D" else None,
        })

    rows.sort(key=lambda r: r["toi_seconds"], reverse=True)

    fieldnames = [
        "gameId", "playerId", "team", "position", "toi_seconds", "total_toi_seconds",
        "comp_fwd", "comp_def", "pct_vs_top_fwd", "pct_vs_top_def",
        "height_in", "weight_lbs", "heaviness",
        "weighted_forward_heaviness", "weighted_defense_heaviness", "weighted_team_heaviness",
        "line_number", "deployment_score",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return out_path
```

- [ ] **Step 2: Update `run_game()` to call the two new functions**

Replace the entire `run_game()` function:

```python
def run_game(game_number: int, season: str) -> Path:
    """Full pipeline for a single game. Returns path to output CSV."""
    game_id = f"{season}{GAME_TYPE}{game_number:04d}"

    plays_data = load_plays(season, game_id)
    positions, teams = build_lookups(plays_data)

    timeline_rows = load_timeline(season, game_id)
    toi = compute_game_toi(timeline_rows)
    total_toi = compute_total_toi(timeline_rows)

    scores = score_game(timeline_rows, toi, positions)
    top_comp = build_top_competition(toi, positions, teams)
    pct_scores = score_game_pct(timeline_rows, positions, teams, top_comp)

    for pid in scores:
        if pid in pct_scores:
            scores[pid].update(pct_scores[pid])

    physicals      = load_player_physicals(list(toi.keys()), season)
    team_heaviness = compute_team_heaviness(toi, positions, teams, physicals)

    for pid in scores:
        ph    = physicals.get(pid, {})
        h_in  = ph.get("height_in", 0)
        w_lbs = ph.get("weight_lbs", 0)
        team  = teams.get(pid, "")
        th = team_heaviness.get(team, {"fwd": 0.0, "def": 0.0, "all": 0.0})
        scores[pid]["height_in"]                 = h_in
        scores[pid]["weight_lbs"]                = w_lbs
        scores[pid]["heaviness"]                 = compute_heaviness(h_in, w_lbs)
        scores[pid]["weighted_forward_heaviness"] = th["fwd"]
        scores[pid]["weighted_defense_heaviness"] = th["def"]
        scores[pid]["weighted_team_heaviness"]    = th["all"]

    # Loop 1 — forward line detection (per team)
    team_to_fwds: Dict[str, set] = {}
    for pid, team in teams.items():
        if positions.get(pid) == "F":
            team_to_fwds.setdefault(team, set()).add(pid)

    line_assignments: Dict[str, Dict[int, int]] = {}
    for team, fwd_ids in team_to_fwds.items():
        line_assignments[team] = assign_forward_lines(timeline_rows, fwd_ids)

    # Flatten line_numbers: {pid: line_number} for all forwards
    line_numbers: Dict[int, int] = {}
    for team_lines in line_assignments.values():
        line_numbers.update(team_lines)

    # Loop 2 — deployment scoring for D
    deployment_scores = compute_deployment_scores(
        timeline_rows, positions, teams, line_assignments
    )

    return write_output(
        game_id, season, scores, toi, total_toi, positions, teams,
        line_numbers=line_numbers,
        deployment_scores=deployment_scores,
    )
```

- [ ] **Step 3: Update the integration test to check new columns**

In `test_run_game_produces_output`, update the `required` set:

```python
required = {"gameId", "playerId", "team", "position", "toi_seconds", "total_toi_seconds",
            "comp_fwd", "comp_def", "pct_vs_top_fwd", "pct_vs_top_def",
            "height_in", "weight_lbs", "heaviness",
            "weighted_forward_heaviness", "weighted_defense_heaviness", "weighted_team_heaviness",
            "line_number", "deployment_score"}
```

Also add checks after the existing assertions:

```python
# Forwards have line_number 1–4; D have empty line_number
fwds = [r for r in rows if r["position"] == "F"]
defs = [r for r in rows if r["position"] == "D"]

assert all(r["line_number"] in {"1", "2", "3", "4"} for r in fwds), \
    "All forwards should have line_number 1-4"
assert all(r["line_number"] == "" for r in defs), \
    "All D should have empty line_number"

# D have deployment_score >= 0; forwards have empty deployment_score
assert all(int(r["deployment_score"]) >= 0 for r in defs if r["deployment_score"]), \
    "D deployment_score must be non-negative"
assert all(r["deployment_score"] == "" for r in fwds), \
    "Forwards should have empty deployment_score"
```

- [ ] **Step 4: Run full competition test suite**

Run from project root: `python -m pytest v2/competition/tests/ -v`

Expected: All tests pass (existing + 4 new)

---

### Task 6: Write failing tests for `deployment_rate` in browser

**Files:**
- Modify: `v2/browser/tests/test_deployment_metrics.py`

- [ ] **Step 1: Update `test_output_columns` to include `deployment_rate`**

Find this assertion and update it:

```python
def test_output_columns():
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    assert list(result.columns) == ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]
```

- [ ] **Step 2: Add two new tests at the bottom of the file**

```python
# ---------------------------------------------------------------------------
# Deployment Rate
# ---------------------------------------------------------------------------

def test_deployment_rate_normalization():
    """D with higher avg deployment_score gets rate > 100; mean = 100."""
    comp_rows = (
        [{"playerId": 1, "team": "EDM", "gameId": g, "position": "D",
          "toi_seconds": 1000, "deployment_score": 5000} for g in range(1, 11)]
      + [{"playerId": 2, "team": "EDM", "gameId": g, "position": "D",
          "toi_seconds": 900,  "deployment_score": 3000} for g in range(1, 11)]
    )
    # League avg = (5000+3000)/2 = 4000
    # Player 1 rate = 5000/4000 * 100 = 125
    # Player 2 rate = 3000/4000 * 100 = 75
    ppi_rows = [
        {"playerId": 1, "ppi": 3.0, "ppi_plus": 100.0},
        {"playerId": 2, "ppi": 2.9, "ppi_plus": 98.0},
    ]
    result = compute_deployment_metrics(pd.DataFrame(comp_rows), pd.DataFrame(ppi_rows))

    assert result.loc[1, "deployment_rate"] > 100
    assert result.loc[2, "deployment_rate"] < 100
    assert abs(result["deployment_rate"].mean() - 100.0) < 0.001


def test_deployment_rate_forwards_null():
    """Forward players receive NaN for deployment_rate; D receives a value."""
    comp_rows = (
        [{"playerId": 1, "team": "EDM", "gameId": g, "position": "F",
          "toi_seconds": 900, "deployment_score": None} for g in range(1, 11)]
      + [{"playerId": 2, "team": "EDM", "gameId": g, "position": "D",
          "toi_seconds": 1000, "deployment_score": 5000} for g in range(1, 11)]
    )
    ppi_rows = [
        {"playerId": 1, "ppi": 3.0, "ppi_plus": 100.0},
        {"playerId": 2, "ppi": 3.0, "ppi_plus": 100.0},
    ]
    result = compute_deployment_metrics(pd.DataFrame(comp_rows), pd.DataFrame(ppi_rows))

    assert pd.isna(result.loc[1, "deployment_rate"])       # forward → NaN
    assert not pd.isna(result.loc[2, "deployment_rate"])   # D → has value
```

- [ ] **Step 3: Run tests to verify they fail**

Run from `v2/browser/`: `python -m pytest tests/test_deployment_metrics.py -k "deployment_rate or output_columns" -v`

Expected: 3 FAIL (`test_output_columns` now fails too because `deployment_rate` missing from columns)

---

### Task 7: Extend `compute_deployment_metrics()` in `filters.py`

**Files:**
- Modify: `v2/browser/filters.py`

- [ ] **Step 1: Replace the body of `compute_deployment_metrics()`**

The full updated function (replace lines 138–167):

```python
def compute_deployment_metrics(comp_df: pd.DataFrame, ppi_df: pd.DataFrame) -> pd.DataFrame:
    """Compute wPPI, wPPI+, avg_toi_share, and deployment_rate from filtered competition data.

    Args:
        comp_df: Filtered competition rows with columns:
                 playerId, team, gameId, toi_seconds, position
                 (deployment_score column optional — if absent, deployment_rate = NaN)
        ppi_df:  Player metrics with columns: playerId, ppi, ppi_plus

    Returns:
        DataFrame indexed by playerId with columns:
        ppi, ppi_plus, wppi, wppi_plus, avg_toi_share, deployment_rate
    """
    if comp_df.empty or ppi_df.empty:
        return pd.DataFrame()

    ppi = ppi_df.set_index("playerId")[["ppi", "ppi_plus"]]

    gp = comp_df.groupby("playerId")["gameId"].nunique().rename("games_played")
    eligible = ppi.join(gp, how="inner")
    eligible = eligible[eligible["games_played"] >= 5].copy()
    if eligible.empty:
        return pd.DataFrame()

    eligible = compute_wppi_and_toi_share(eligible, comp_df)
    if eligible.empty:
        return pd.DataFrame()

    # Deployment rate — D only, requires deployment_score column in comp_df
    if "deployment_score" in comp_df.columns:
        d_comp = comp_df[comp_df["position"] == "D"].copy()
        if not d_comp.empty:
            d_comp["deployment_score"] = pd.to_numeric(d_comp["deployment_score"], errors="coerce")
            d_agg = d_comp.groupby("playerId").agg(
                total_score=("deployment_score", "sum"),
                d_gp=("gameId", "nunique"),
            )
            d_agg["avg_score"] = d_agg["total_score"] / d_agg["d_gp"]
            league_avg = d_agg["avg_score"].mean()
            if league_avg and league_avg > 0:
                d_agg["deployment_rate"] = d_agg["avg_score"] / league_avg * 100
            else:
                d_agg["deployment_rate"] = None
            eligible = eligible.join(d_agg[["deployment_rate"]])
        else:
            eligible["deployment_rate"] = None
    else:
        eligible["deployment_rate"] = None

    return eligible[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]]
```

- [ ] **Step 2: Run browser deployment tests**

Run from `v2/browser/`: `python -m pytest tests/test_deployment_metrics.py -v`

Expected: All 15 tests pass (13 original + 2 new)

---

### Task 8: Update `team.py` and `skaters.py`

**Files:**
- Modify: `v2/browser/pages/team.py`
- Modify: `v2/browser/pages/skaters.py`

#### `team.py`

- [ ] **Step 1: Add `c.deployment_score` to `_COMP_SQL`**

```python
_COMP_SQL = """
SELECT c.playerId,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
       c.position, c.team, c.gameId, c.toi_seconds, c.total_toi_seconds,
       c.pct_any_elite_fwd, c.pct_any_elite_def,
       c.comp_fwd, c.comp_def, c.deployment_score,
       g.gameDate, g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
JOIN games g ON c.gameId = g.gameId
WHERE c.position IN ('F', 'D') AND c.team = ?
  AND g.gameDate BETWEEN ? AND ?
"""
```

- [ ] **Step 2: Update `grouped` aggregation to include `deployment_score`**

In the `grouped = comp_df.groupby("playerId").agg(...)` block, add `deployment_score` to the aggregation and add `deployment_rate` to the join. Find this line:

```python
        metrics = compute_deployment_metrics(comp_df, ppi_df)
        if not metrics.empty:
            grouped = grouped.join(metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]])
        else:
            for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]:
                grouped[col] = None
```

Replace with:

```python
        metrics = compute_deployment_metrics(comp_df, ppi_df)
        if not metrics.empty:
            grouped = grouped.join(
                metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]]
            )
        else:
            for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]:
                grouped[col] = None
```

- [ ] **Step 3: Add `deployment_rate` to `_make_position_table()` for D only**

Replace the existing `_make_position_table(df)` function signature and column list with a `pos`-aware version:

```python
def _make_position_table(df, pos="F"):
    """Build a single sortable DataTable for one position group."""
    df = df.copy()
    df["player_link"]      = df.apply(lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1)
    df["toi_display"]      = df["toi_per_game"].apply(seconds_to_mmss)
    df["comp_fwd_display"] = df["avg_comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"] = df["avg_comp_def"].apply(seconds_to_mmss)
    columns = [
        {"name": "Player",       "id": "player_link",        "presentation": "markdown"},
        {"name": "GP",           "id": "games_played",       "type": "numeric"},
        {"name": "G",     "id": "total_goals",   "type": "numeric"},
        {"name": "A",     "id": "total_assists",  "type": "numeric"},
        {"name": "P",     "id": "total_points",   "type": "numeric"},
        {"name": "P/60",  "id": "p_per_60",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "5v5 TOI/GP",   "id": "toi_display"},
        {"name": "tTOI%",        "id": "avg_toi_share", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "iTOI%",        "id": "avg_itoi_pct", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "vs Elite Fwd %", "id": "avg_pct_any_elite_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Elite Def %", "id": "avg_pct_any_elite_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "OPP F TOI",    "id": "comp_fwd_display"},
        {"name": "OPP D TOI",    "id": "comp_def_display"},
        {"name": "PPI",   "id": "ppi",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "wPPI",  "id": "wppi",      "type": "numeric", "format": Format(precision=4, scheme=Scheme.fixed)},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "games_played",
        "total_goals", "total_assists", "total_points", "p_per_60",
        "toi_display", "avg_toi_share", "avg_itoi_pct",
        "avg_pct_any_elite_fwd", "avg_pct_any_elite_def",
        "comp_fwd_display", "comp_def_display",
        "ppi", "ppi_plus", "wppi", "wppi_plus",
    ]
    if pos == "D":
        columns.append({"name": "D-Rate", "id": "deployment_rate", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)})
        display_cols.append("deployment_rate")

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        markdown_options={"link_target": "_self"},
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8f9fa", "fontWeight": "bold",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_cell={
            "textAlign": "left", "padding": "8px 12px",
            "border": "1px solid #dee2e6", "fontSize": "14px",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    )
```

- [ ] **Step 4: Update the `_make_player_tables()` call to pass `pos`**

```python
def _make_player_tables(df):
    sections = []
    for pos, label in [("F", "Forwards"), ("D", "Defensemen")]:
        pos_df = df[df["position"] == pos]
        if pos_df.empty:
            continue
        sections.append(html.H4(label, style={"marginTop": "1.5rem", "marginBottom": "0.25rem"}))
        sections.append(_make_position_table(pos_df, pos=pos))
    return html.Div(sections) if sections else html.Div("No player data.")
```

- [ ] **Step 5: Round `deployment_rate` alongside the other numeric columns**

Find this loop in `update_team`:
```python
        for col, dec in [("ppi", 2), ("ppi_plus", 1), ("wppi", 4), ("wppi_plus", 1)]:
            player_df[col] = pd.to_numeric(player_df[col], errors="coerce").round(dec)
```

Replace with:
```python
        for col, dec in [("ppi", 2), ("ppi_plus", 1), ("wppi", 4), ("wppi_plus", 1), ("deployment_rate", 1)]:
            player_df[col] = pd.to_numeric(player_df[col], errors="coerce").round(dec)
```

#### `skaters.py`

- [ ] **Step 6: Add `c.deployment_score` to `_COMP_SQL`**

```python
_COMP_SQL = """
SELECT c.playerId,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
       c.position, p.shootsCatches, c.team, c.gameId, c.toi_seconds, c.total_toi_seconds,
       c.pct_any_elite_fwd, c.pct_any_elite_def,
       c.comp_fwd, c.comp_def, c.deployment_score,
       g.gameDate, g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
JOIN games g ON c.gameId = g.gameId
WHERE c.position IN ('F', 'D')
  AND g.gameDate BETWEEN ? AND ?
"""
```

- [ ] **Step 7: Update `compute_deployment_metrics` join and fallback in `update_skaters`**

Find:
```python
    metrics = compute_deployment_metrics(comp_df, ppi_df)
    if not metrics.empty:
        grouped = grouped.join(metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]])
    else:
        for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]:
            grouped[col] = None
```

Replace with:
```python
    metrics = compute_deployment_metrics(comp_df, ppi_df)
    if not metrics.empty:
        grouped = grouped.join(
            metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]]
        )
    else:
        for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]:
            grouped[col] = None
```

- [ ] **Step 8: Add `deployment_rate` column and rounding in `update_skaters`**

Find the rounding loop:
```python
    for col, decimals in [("ppi", 2), ("ppi_plus", 1), ("wppi", 4), ("wppi_plus", 1)]:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(decimals)
```

Replace with:
```python
    for col, decimals in [("ppi", 2), ("ppi_plus", 1), ("wppi", 4), ("wppi_plus", 1), ("deployment_rate", 1)]:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(decimals)
```

Find the `columns` list and add after the `wPPI+` entry:

```python
        {"name": "D-Rate", "id": "deployment_rate", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
```

Find the `display_cols` list and add `"deployment_rate"` after `"wppi_plus"`:

```python
    display_cols = [
        "player_link", "team", "shoots", "position", "games_played",
        "total_goals", "total_assists", "total_points", "p_per_60",
        "toi_display",
        "avg_toi_share", "avg_itoi_pct", "avg_pct_any_elite_fwd", "avg_pct_any_elite_def",
        "comp_fwd_display", "comp_def_display",
        "ppi", "ppi_plus", "wppi", "wppi_plus", "deployment_rate",
    ]
```

- [ ] **Step 9: Run full browser test suite**

Run from `v2/browser/`: `python -m pytest tests/ -v`

Expected: All tests pass

---

### Task 9: Update `game.py`

**Files:**
- Modify: `v2/browser/pages/game.py`

- [ ] **Step 1: Add `c.line_number` and `c.deployment_score` to `_PLAYERS_SQL`**

```python
_PLAYERS_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    c.team,
    c.position,
    c.toi_seconds,
    5.0 * c.toi_seconds / NULLIF(tt.team_total, 0)                      AS toi_share,
    c.total_toi_seconds,
    c.toi_seconds * 1.0 / NULLIF(c.total_toi_seconds, 0) AS itoi_pct,
    c.comp_fwd,
    c.comp_def,
    c.pct_any_elite_fwd,
    c.pct_any_elite_def,
    c.line_number,
    c.deployment_score
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
JOIN (
    SELECT gameId, team, SUM(toi_seconds) AS team_total
    FROM competition
    WHERE position IN ('F', 'D')
    GROUP BY gameId, team
) tt ON c.gameId = tt.gameId AND c.team = tt.team
WHERE c.gameId = ? AND c.position IN ('F', 'D')
ORDER BY c.toi_seconds DESC
"""
```

- [ ] **Step 2: Update `_make_position_table()` to accept a `pos` parameter**

Replace the entire `_make_position_table` function:

```python
def _make_position_table(df, pos="F"):
    """Build a single sortable DataTable for one position group."""
    df = df.copy().sort_values("toi_seconds", ascending=False)
    df["toi_display"]      = df["toi_seconds"].apply(seconds_to_mmss)
    df["comp_fwd_display"] = df["comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"] = df["comp_def"].apply(seconds_to_mmss)

    columns = [
        {"name": "Player",         "id": "playerName"},
        {"name": "5v5 TOI",        "id": "toi_display"},
        {"name": "tTOI%",          "id": "toi_share", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "iTOI%",          "id": "itoi_pct",  "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "vs Elite Fwd %", "id": "pct_any_elite_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Elite Def %", "id": "pct_any_elite_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
    ]
    display_cols = [
        "playerName", "toi_display", "toi_share", "itoi_pct",
        "pct_any_elite_fwd", "pct_any_elite_def",
    ]
    if pos == "F":
        columns.append({"name": "Line", "id": "line_number", "type": "numeric"})
        display_cols.append("line_number")
    else:  # D
        columns.append({"name": "Dep Score", "id": "deployment_score", "type": "numeric"})
        display_cols.append("deployment_score")

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8f9fa", "fontWeight": "bold",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_cell={
            "textAlign": "left", "padding": "6px 10px",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    )
```

- [ ] **Step 3: Update `_make_player_tables()` to pass `pos` to `_make_position_table()`**

```python
def _make_player_tables(df):
    """Return an html.Div with separate sortable Forwards and Defensemen tables."""
    sections = []
    for pos, label in [("F", "Forwards"), ("D", "Defensemen")]:
        pos_df = df[df["position"] == pos]
        if pos_df.empty:
            continue
        sections.append(html.H5(label, style={"marginTop": "1rem", "marginBottom": "0.25rem"}))
        sections.append(_make_position_table(pos_df, pos=pos))
    return html.Div(sections) if sections else html.Div("No player data.")
```

- [ ] **Step 4: Run full test suite**

Run from project root: `python -m pytest v2/ -v`

Expected: All tests pass

---

## Verification

After all tasks complete:

1. **Unit tests:** `python -m pytest v2/ -v` — all tests pass (82 existing + 4 competition + 2 browser = 88 total)
2. **Pipeline smoke test:** `python v2/competition/compute_competition.py 734 2025` — check the output CSV at `data/2025/generated/competition/2025020734.csv` has `line_number` and `deployment_score` columns with sensible values (forwards have line 1–4, D have non-zero deployment_score)
3. **Browser smoke test:** Rebuild the DB with `python v2/browser/build_league_db.py 2025` (after re-running compute_competition for all games to populate the new columns), then start the app and confirm the game page shows "Line" for forwards and "Dep Score" for D, and the team/skaters pages show "D-Rate" for D players
