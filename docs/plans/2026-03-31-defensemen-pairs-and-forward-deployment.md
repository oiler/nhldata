# Defensemen Pairs and Forward Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Detect defensemen pair assignments per game (analogous to forward lines), compute per-game deployment scores for forwards (opposing D pair quality), and surface season-level DPS+ (forwards) and DPL (defensemen) across game pages, the skaters page, and the elite pages.

**Architecture:** `line_number` column stores pair number (1–4) for D the same way it stores line number for F. `deployment_score` column stores per-game accumulated score for F the same way it does for D. Both columns become fully populated for all positions after this change. Season aggregation flows through `filters.py` → `skaters.py` and through `build_league_db.py` → `elites.py`.

**Tech Stack:** Python, itertools.combinations, pandas, SQLite, Plotly Dash

---

### Task 1: Add `assign_defense_pairs()` with tests

**Files:**
- Modify: `v2/competition/tests/test_compute_competition.py`
- Modify: `v2/competition/compute_competition.py`

**Step 1: Write failing tests**

Append to `v2/competition/tests/test_compute_competition.py`, after the existing `assign_forward_lines` tests (search for `from compute_competition import assign_forward_lines` and add below its tests):

```python
from compute_competition import assign_defense_pairs


def test_assign_defense_pairs_top_pair_gets_pair1():
    """D pair with most 5v5 seconds together gets pair 1."""
    # D 21+22 play together 3 seconds; D 23+24 play together 1 second
    rows = [
        {"situationCode": "1551", "awaySkaters": "21|22|1|2|3", "homeSkaters": "6|7|8|9|10"},
        {"situationCode": "1551", "awaySkaters": "21|22|1|2|3", "homeSkaters": "6|7|8|9|10"},
        {"situationCode": "1551", "awaySkaters": "21|22|1|2|3", "homeSkaters": "6|7|8|9|10"},
        {"situationCode": "1551", "awaySkaters": "23|24|1|2|3", "homeSkaters": "6|7|8|9|10"},
    ]
    team_def_ids = {21, 22, 23, 24}
    result = assign_defense_pairs(rows, team_def_ids)
    assert result[21] == 1
    assert result[22] == 1
    assert result[23] == 2
    assert result[24] == 2


def test_assign_defense_pairs_uses_5v5_only():
    """Non-5v5 rows are ignored for pair detection."""
    rows = [
        {"situationCode": "1441", "awaySkaters": "21|22|1|2", "homeSkaters": "6|7|8|9"},
        {"situationCode": "1551", "awaySkaters": "23|24|1|2|3", "homeSkaters": "6|7|8|9|10"},
    ]
    team_def_ids = {21, 22, 23, 24}
    result = assign_defense_pairs(rows, team_def_ids)
    # 23+24 in 5v5 → pair 1; 21+22 only in 1441 → default pair 4
    assert result[23] == 1
    assert result[24] == 1
    assert result[21] == 4
    assert result[22] == 4


def test_assign_defense_pairs_unassigned_gets_pair4():
    """D with no 5v5 ice time get assigned pair 4."""
    result = assign_defense_pairs([], {21, 22})
    assert result[21] == 4
    assert result[22] == 4


def test_assign_defense_pairs_requires_at_least_2_dmen():
    """Rows where fewer than 2 D from this team are on ice are skipped."""
    rows = [
        # Only D 21 on ice — no pair possible
        {"situationCode": "1551", "awaySkaters": "21|1|2|3|4", "homeSkaters": "6|7|8|9|10"},
    ]
    team_def_ids = {21, 22}
    result = assign_defense_pairs(rows, team_def_ids)
    # 21 never forms a pair → both default to 4
    assert result[21] == 4
    assert result[22] == 4
```

**Step 2: Run to verify tests fail**

Run from project root:
```
python -m pytest v2/competition/tests/test_compute_competition.py -k "assign_defense_pairs" -v
```
Expected: `ImportError: cannot import name 'assign_defense_pairs'`

**Step 3: Implement `assign_defense_pairs()`**

In `v2/competition/compute_competition.py`, insert this function immediately after `assign_forward_lines()` (around line 453):

```python
def assign_defense_pairs(
    rows: List[dict],
    team_def_ids: set,
) -> Dict[int, int]:
    """Greedy defense pair detection for one team.

    Args:
        rows: all timeline row dicts for the game
        team_def_ids: set of INTEGER player IDs who are defensemen for this team

    Returns:
        {player_id: pair_number}  pair_number is 1–4; every ID in team_def_ids is present.
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
                    if pid in team_def_ids:
                        on_ice.add(pid)
        if len(on_ice) < 2:
            continue
        for combo in _combinations(sorted(on_ice), 2):
            combo_seconds[combo] = combo_seconds.get(combo, 0) + 1

    sorted_combos = sorted(combo_seconds.items(), key=lambda x: x[1], reverse=True)
    assigned: Dict[int, int] = {}
    used: set = set()
    pair = 1
    for combo, _ in sorted_combos:
        if pair > 4:
            break
        if any(p in used for p in combo):
            continue
        for p in combo:
            assigned[p] = pair
            used.add(p)
        pair += 1

    for pid in team_def_ids:
        if pid not in assigned:
            assigned[pid] = 4

    return assigned
```

**Step 4: Run to verify tests pass**

```
python -m pytest v2/competition/tests/test_compute_competition.py -k "assign_defense_pairs" -v
```
Expected: 4 PASSED

---

### Task 2: Add `compute_forward_deployment_scores()` with tests

**Files:**
- Modify: `v2/competition/tests/test_compute_competition.py`
- Modify: `v2/competition/compute_competition.py`

**Step 1: Write failing tests**

Append to `v2/competition/tests/test_compute_competition.py`:

```python
from compute_competition import compute_forward_deployment_scores


def test_compute_forward_deployment_scores_basic():
    """Forward facing opposing D pair 1 + pair 2 scores 8-(1+2)=5 per second."""
    rows = [
        {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|8|9|10"},
    ]
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 8: "F", 9: "D", 10: "D"}
    teams = {1: "EDM", 2: "EDM", 3: "EDM", 4: "EDM", 5: "EDM",
             6: "FLA", 7: "FLA", 8: "FLA", 9: "FLA", 10: "FLA"}
    # FLA D: pair 9→1, pair 10→2  EDM D: pair 4→1, pair 5→2
    pair_assignments = {"FLA": {9: 1, 10: 2}, "EDM": {4: 1, 5: 2}}
    result = compute_forward_deployment_scores(rows, positions, teams, pair_assignments)
    # Away F 1,2,3 face FLA D 9(pair1)+10(pair2) → 8-(1+2)=5 per second
    assert result[1] == 5
    assert result[2] == 5
    assert result[3] == 5
    # Home F 6,7,8 face EDM D 4(pair1)+5(pair2) → 8-(1+2)=5 per second
    assert result[6] == 5
    assert result[7] == 5
    assert result[8] == 5
    # D should not appear in result
    assert 4 not in result
    assert 9 not in result


def test_compute_forward_deployment_scores_accumulates_across_seconds():
    """Score accumulates: 3 identical rows → 3× the single-row score."""
    row = {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|8|9|10"}
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 8: "F", 9: "D", 10: "D"}
    teams = {1: "EDM", 2: "EDM", 3: "EDM", 4: "EDM", 5: "EDM",
             6: "FLA", 7: "FLA", 8: "FLA", 9: "FLA", 10: "FLA"}
    pair_assignments = {"FLA": {9: 1, 10: 2}, "EDM": {4: 1, 5: 2}}
    result = compute_forward_deployment_scores([row, row, row], positions, teams, pair_assignments)
    assert result[1] == 15  # 5 × 3 seconds


def test_compute_forward_deployment_scores_uses_5v5_only():
    """Non-5v5 rows are skipped."""
    rows = [
        {"situationCode": "1441", "awaySkaters": "1|2|3|4", "homeSkaters": "6|7|8|9"},
        {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|8|9|10"},
    ]
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 8: "F", 9: "D", 10: "D"}
    teams = {1: "EDM", 2: "EDM", 3: "EDM", 4: "EDM", 5: "EDM",
             6: "FLA", 7: "FLA", 8: "FLA", 9: "FLA", 10: "FLA"}
    pair_assignments = {"FLA": {9: 1, 10: 2}, "EDM": {4: 1, 5: 2}}
    result = compute_forward_deployment_scores(rows, positions, teams, pair_assignments)
    # Only the 1551 row counts → 1 second, score = 5
    assert result[1] == 5


def test_compute_forward_deployment_scores_skips_not_exactly_2_defs():
    """Rows without exactly 2 opposing D are skipped."""
    rows = [
        # Only 1 D per side — malformed 5v5, should skip
        {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|8|9|10"},
    ]
    positions = {1: "F", 2: "F", 3: "F", 4: "F", 5: "D",   # EDM has 1 D
                 6: "F", 7: "F", 8: "F", 9: "F", 10: "D"}  # FLA has 1 D
    teams = {1: "EDM", 2: "EDM", 3: "EDM", 4: "EDM", 5: "EDM",
             6: "FLA", 7: "FLA", 8: "FLA", 9: "FLA", 10: "FLA"}
    pair_assignments = {"FLA": {10: 1}, "EDM": {5: 1}}
    result = compute_forward_deployment_scores(rows, positions, teams, pair_assignments)
    assert result == {}
```

**Step 2: Run to verify tests fail**

```
python -m pytest v2/competition/tests/test_compute_competition.py -k "forward_deployment_scores" -v
```
Expected: `ImportError: cannot import name 'compute_forward_deployment_scores'`

**Step 3: Implement `compute_forward_deployment_scores()`**

In `v2/competition/compute_competition.py`, insert this function immediately after `compute_deployment_scores()` (after the D deployment function, around line 505):

```python
def compute_forward_deployment_scores(
    rows: List[dict],
    positions: Dict[int, str],
    teams: Dict[int, str],
    pair_assignments: Dict[str, Dict[int, int]],
) -> Dict[int, int]:
    """Compute raw deployment score per forward for one game.

    For each 5v5 second a F is on ice:
        points = 8 − (pairA + pairB)  [opposing 2 defensemen]
    TOI is embedded — more seconds on ice accumulates more points.

    Args:
        rows: all timeline row dicts for the game
        positions: {player_id: "F"/"D"/"G"}
        teams: {player_id: team_abbrev}
        pair_assignments: {team_abbrev: {player_id: pair_number}}

    Returns:
        {player_id: deployment_score}  only for F players with > 0 seconds scored
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
            if positions.get(player_id) != "F":
                continue

            opp_team = teams.get(opponents[0], "") if opponents else ""
            if not opp_team:
                continue

            opp_defs = [p for p in opponents if positions.get(p, "F") == "D"]
            if len(opp_defs) != 2:
                continue  # strict 5v5 only — skip malformed rows

            opp_pairs = pair_assignments.get(opp_team, {})
            pair_sum = sum(opp_pairs.get(d, 4) for d in opp_defs)
            scores[player_id] = scores.get(player_id, 0) + (8 - pair_sum)

    return scores
```

**Step 4: Run to verify tests pass**

```
python -m pytest v2/competition/tests/test_compute_competition.py -k "forward_deployment_scores" -v
```
Expected: 4 PASSED

---

### Task 3: Wire into `run_game()`, update `write_output()`, update integration test

**Files:**
- Modify: `v2/competition/compute_competition.py`
- Modify: `v2/competition/tests/test_compute_competition.py`

**Step 1: Update `write_output()` to populate both columns for all positions**

In `v2/competition/compute_competition.py`, find these two lines in `write_output()` (around line 382):

```python
            "line_number":      line_numbers.get(pid) if pos == "F" else None,
            "deployment_score": deployment_scores.get(pid) if pos == "D" else None,
```

Replace with:

```python
            "line_number":      line_numbers.get(pid),
            "deployment_score": deployment_scores.get(pid),
```

**Step 2: Update `run_game()` to detect D pairs and score F deployment**

In `v2/competition/compute_competition.py`, find the section in `run_game()` that builds `line_assignments` and `deployment_scores` (around line 543). After the line `deployment_scores = compute_deployment_scores(...)` call (around line 559), add:

```python
    # Defense pair detection (per team)
    team_to_defs: Dict[str, set] = {}
    for pid, team in teams.items():
        if positions.get(pid) == "D":
            team_to_defs.setdefault(team, set()).add(pid)

    pair_assignments: Dict[str, Dict[int, int]] = {}
    for team, def_ids in team_to_defs.items():
        pair_assignments[team] = assign_defense_pairs(timeline_rows, def_ids)

    # Store D pair numbers in line_numbers (same column, both positions)
    for team_pairs in pair_assignments.values():
        line_numbers.update(team_pairs)

    # Forward deployment scoring
    fwd_deployment_scores = compute_forward_deployment_scores(
        timeline_rows, positions, teams, pair_assignments
    )
    deployment_scores.update(fwd_deployment_scores)
```

The full `run_game()` body around that section should now read:

```python
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

    # Defense pair detection (per team)
    team_to_defs: Dict[str, set] = {}
    for pid, team in teams.items():
        if positions.get(pid) == "D":
            team_to_defs.setdefault(team, set()).add(pid)

    pair_assignments: Dict[str, Dict[int, int]] = {}
    for team, def_ids in team_to_defs.items():
        pair_assignments[team] = assign_defense_pairs(timeline_rows, def_ids)

    # Store D pair numbers in line_numbers (same column, both positions)
    for team_pairs in pair_assignments.values():
        line_numbers.update(team_pairs)

    # Forward deployment scoring
    fwd_deployment_scores = compute_forward_deployment_scores(
        timeline_rows, positions, teams, pair_assignments
    )
    deployment_scores.update(fwd_deployment_scores)

    return write_output(
        game_id, season, scores, toi, total_toi, positions, teams,
        line_numbers=line_numbers,
        deployment_scores=deployment_scores,
    )
```

**Step 3: Update the integration test assertions**

In `v2/competition/tests/test_compute_competition.py`, find `test_run_game_produces_output`. Replace the D line_number and F deployment_score assertions:

Old assertions (around lines 210–219):
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

New assertions:
```python
    # Both F and D have line_number 1–4
    fwds = [r for r in rows if r["position"] == "F"]
    defs = [r for r in rows if r["position"] == "D"]

    assert all(r["line_number"] in {"1", "2", "3", "4"} for r in fwds), \
        "All forwards should have line_number 1-4"
    assert all(r["line_number"] in {"1", "2", "3", "4"} for r in defs), \
        "All D should have pair_number (line_number) 1-4"

    # Both F and D have deployment_score >= 0
    assert all(int(r["deployment_score"]) >= 0 for r in defs if r["deployment_score"]), \
        "D deployment_score must be non-negative"
    assert all(int(r["deployment_score"]) >= 0 for r in fwds if r["deployment_score"]), \
        "F deployment_score must be non-negative"
```

**Step 4: Run all competition tests**

```
python -m pytest v2/competition/ -v
```
Expected: All tests pass (existing + new)

---

### Task 4: Update `game.py` — D gets Pair column, F gets Dep Score column

**Files:**
- Modify: `v2/browser/pages/game.py`

**Step 1: Update `_make_position_table()`**

Find this block in `_make_position_table()` (around line 84):

```python
    if pos == "F":
        columns.append({"name": "Line", "id": "line_number", "type": "numeric"})
        display_cols.append("line_number")
    else:  # D
        columns.append({"name": "Dep Score", "id": "deployment_score", "type": "numeric"})
        display_cols.append("deployment_score")
```

Replace with:

```python
    if pos == "F":
        columns.append({"name": "Line", "id": "line_number", "type": "numeric"})
        columns.append({"name": "Dep Score", "id": "deployment_score", "type": "numeric"})
        display_cols.extend(["line_number", "deployment_score"])
    else:  # D
        columns.append({"name": "Pair", "id": "line_number", "type": "numeric"})
        columns.append({"name": "Dep Score", "id": "deployment_score", "type": "numeric"})
        display_cols.extend(["line_number", "deployment_score"])
```

**Step 2: Verify no test regressions**

```
python -m pytest v2/ -v
```
Expected: All tests pass. (game.py has no unit tests, but this confirms nothing else broke.)

---

### Task 5: Add `fwd_deployment_rate` to `filters.py`, update `skaters.py`

**Files:**
- Modify: `v2/browser/filters.py`
- Modify: `v2/browser/tests/test_deployment_metrics.py`
- Modify: `v2/browser/pages/skaters.py`

**Step 1: Write failing tests for `fwd_deployment_rate`**

In `v2/browser/tests/test_deployment_metrics.py`, replace `test_output_columns` and append new tests:

Replace:
```python
def test_output_columns():
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    assert list(result.columns) == ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]
```

With:
```python
def test_output_columns():
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    assert list(result.columns) == ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate", "fwd_deployment_rate"]
```

Append these tests after `test_deployment_rate_forwards_null`:

```python
def test_fwd_deployment_rate_normalization():
    """F with higher avg deployment_score gets rate > 100; mean = 100."""
    comp_rows = (
        [{"playerId": 1, "team": "EDM", "gameId": g, "position": "F",
          "toi_seconds": 900, "deployment_score": 4000} for g in range(1, 11)]
      + [{"playerId": 2, "team": "EDM", "gameId": g, "position": "F",
          "toi_seconds": 900, "deployment_score": 2000} for g in range(1, 11)]
    )
    ppi_rows = [
        {"playerId": 1, "ppi": 3.0, "ppi_plus": 100.0},
        {"playerId": 2, "ppi": 2.9, "ppi_plus": 98.0},
    ]
    result = compute_deployment_metrics(pd.DataFrame(comp_rows), pd.DataFrame(ppi_rows))
    assert result.loc[1, "fwd_deployment_rate"] > 100
    assert result.loc[2, "fwd_deployment_rate"] < 100
    assert abs(result["fwd_deployment_rate"].mean() - 100.0) < 0.001


def test_fwd_deployment_rate_defense_null():
    """D players receive NaN for fwd_deployment_rate; F receives a value."""
    comp_rows = (
        [{"playerId": 1, "team": "EDM", "gameId": g, "position": "F",
          "toi_seconds": 900, "deployment_score": 4000} for g in range(1, 11)]
      + [{"playerId": 2, "team": "EDM", "gameId": g, "position": "D",
          "toi_seconds": 1000, "deployment_score": 5000} for g in range(1, 11)]
    )
    ppi_rows = [
        {"playerId": 1, "ppi": 3.0, "ppi_plus": 100.0},
        {"playerId": 2, "ppi": 3.0, "ppi_plus": 100.0},
    ]
    result = compute_deployment_metrics(pd.DataFrame(comp_rows), pd.DataFrame(ppi_rows))
    assert not pd.isna(result.loc[1, "fwd_deployment_rate"])   # F → has value
    assert pd.isna(result.loc[2, "fwd_deployment_rate"])       # D → NaN
```

**Step 2: Run to verify tests fail**

```
python -m pytest v2/browser/tests/test_deployment_metrics.py -k "fwd_deployment_rate or output_columns" -v
```
Expected: FAIL — `AssertionError` on column list; `KeyError: 'fwd_deployment_rate'`

**Step 3: Add `fwd_deployment_rate` to `compute_deployment_metrics()` in `filters.py`**

In `v2/browser/filters.py`, find the return statement at the bottom of `compute_deployment_metrics()`:

```python
    return eligible[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]]
```

Replace the entire block from `# Deployment rate — D only` through this return with:

```python
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

    # Forward deployment rate — F only, requires deployment_score column in comp_df
    if "deployment_score" in comp_df.columns:
        f_comp = comp_df[comp_df["position"] == "F"].copy()
        if not f_comp.empty:
            f_comp["deployment_score"] = pd.to_numeric(f_comp["deployment_score"], errors="coerce")
            f_agg = f_comp.groupby("playerId").agg(
                total_score=("deployment_score", "sum"),
                f_gp=("gameId", "nunique"),
            )
            f_agg["avg_score"] = f_agg["total_score"] / f_agg["f_gp"]
            fwd_league_avg = f_agg["avg_score"].mean()
            if fwd_league_avg and fwd_league_avg > 0:
                f_agg["fwd_deployment_rate"] = f_agg["avg_score"] / fwd_league_avg * 100
            else:
                f_agg["fwd_deployment_rate"] = None
            eligible = eligible.join(f_agg[["fwd_deployment_rate"]])
        else:
            eligible["fwd_deployment_rate"] = None
    else:
        eligible["fwd_deployment_rate"] = None

    return eligible[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate", "fwd_deployment_rate"]]
```

**Step 4: Run deployment metrics tests**

```
python -m pytest v2/browser/tests/test_deployment_metrics.py -v
```
Expected: All tests pass including 2 new ones.

**Step 5: Update `skaters.py` to use the new column and split into DPL/DPS+**

In `v2/browser/pages/skaters.py`, make these changes:

1. In `update_skaters()`, find:
```python
        grouped = grouped.join(metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]])
    else:
        for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate"]:
```
Replace with:
```python
        grouped = grouped.join(metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate", "fwd_deployment_rate"]])
    else:
        for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate", "fwd_deployment_rate"]:
```

2. Find:
```python
    for col, decimals in [("ppi", 2), ("ppi_plus", 1), ("wppi", 4), ("wppi_plus", 1), ("deployment_rate", 1), ("avg_line", 1)]:
```
Replace with:
```python
    for col, decimals in [("ppi", 2), ("ppi_plus", 1), ("wppi", 4), ("wppi_plus", 1), ("deployment_rate", 1), ("fwd_deployment_rate", 1), ("avg_line", 1)]:
```

3. Find and replace the `deploy_metric` computation:
```python
    df["deploy_metric"] = df.apply(
        lambda r: r["deployment_rate"] if r["position"] == "D" else r["avg_line"], axis=1
    )
```
Replace with:
```python
    df["dps_plus"] = df.apply(
        lambda r: r["deployment_rate"] if r["position"] == "D" else r["fwd_deployment_rate"], axis=1
    )
```

4. Find in `columns`:
```python
        {"name": "DPL/DPS+", "id": "deploy_metric", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
```
Replace with:
```python
        {"name": "DPL",  "id": "avg_line", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "DPS+", "id": "dps_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
```

5. Find in `display_cols` (the list passed to DataTable):
```python
        "ppi", "ppi_plus", "wppi", "wppi_plus", "deploy_metric",
```
Replace with:
```python
        "ppi", "ppi_plus", "wppi", "wppi_plus", "avg_line", "dps_plus",
```

**Step 6: Run all browser tests**

```
python -m pytest v2/browser/ -v
```
Expected: All tests pass.

---

### Task 6: Add DPS+ to `elite_forwards`, add DPL to `elite_defensemen`, update `elites.py`

**Files:**
- Modify: `v2/browser/tests/test_player_metrics.py`
- Modify: `v2/browser/build_league_db.py`
- Modify: `v2/browser/pages/elites.py`

**Step 1: Write failing tests**

In `v2/browser/tests/test_player_metrics.py`, append these tests after the existing `test_ed_traded_player_combined` test:

```python
# ---------------------------------------------------------------------------
# Elite forwards: DPS+
# ---------------------------------------------------------------------------

def _setup_fwd_deployment_db(conn):
    """Set up minimal DB for testing forward DPS+ in build_elite_forwards_table."""
    # Two qualifying forwards: one facing harder D deployment (higher score)
    comp_rows = []
    for g in range(1, 26):
        comp_rows.append({
            "playerId": 1, "team": "EDM", "gameId": g,
            "position": "F", "toi_seconds": 900, "total_toi_seconds": 1100,
            "line_number": 1, "deployment_score": 300,  # harder deployment
            "comp_fwd": 800, "comp_def": 900,
            "pct_vs_top_fwd": 0.5, "pct_vs_top_def": 0.5,
            "pct_any_elite_fwd": 0.3, "pct_any_elite_def": 0.3,
            "height_in": 73, "weight_lbs": 194,
            "heaviness": 2.66, "weighted_forward_heaviness": 2.66,
            "weighted_defense_heaviness": 2.66, "weighted_team_heaviness": 2.66,
        })
        comp_rows.append({
            "playerId": 2, "team": "EDM", "gameId": g,
            "position": "F", "toi_seconds": 850, "total_toi_seconds": 1100,
            "line_number": 2, "deployment_score": 150,  # easier deployment
            "comp_fwd": 750, "comp_def": 850,
            "pct_vs_top_fwd": 0.4, "pct_vs_top_def": 0.4,
            "pct_any_elite_fwd": 0.2, "pct_any_elite_def": 0.2,
            "height_in": 74, "weight_lbs": 208,
            "heaviness": 2.81, "weighted_forward_heaviness": 2.81,
            "weighted_defense_heaviness": 2.81, "weighted_team_heaviness": 2.81,
        })
    pd.DataFrame(comp_rows).to_sql("competition", conn, if_exists="replace", index=False)
    pts_rows = []
    for g in range(1, 26):
        pts_rows.append({"playerId": 1, "gameId": g, "goals": 1, "assists": 1, "points": 2})
        pts_rows.append({"playerId": 2, "gameId": g, "goals": 1, "assists": 1, "points": 2})
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, if_exists="replace", index=False)


def test_elite_fwd_dps_plus_computed():
    """build_elite_forwards_table adds weighted_dps_plus; harder deployment → higher DPS+."""
    conn = sqlite3.connect(":memory:")
    _setup_fwd_deployment_db(conn)
    build_elite_forwards_table(conn)
    rows = pd.read_sql_query("SELECT * FROM elite_forwards", conn)
    conn.close()
    assert "weighted_dps_plus" in rows.columns
    row1 = rows[rows["playerId"] == 1].iloc[0]
    row2 = rows[rows["playerId"] == 2].iloc[0]
    assert row1["weighted_dps_plus"] > row2["weighted_dps_plus"]
    # League avg normalizes to 100
    assert abs(rows["weighted_dps_plus"].mean() - 100.0) < 0.5


# ---------------------------------------------------------------------------
# Elite defensemen: DPL
# ---------------------------------------------------------------------------

def test_elite_def_dpl_computed():
    """build_elite_defensemen_table adds dpl (avg pair number); pair 1 player has lower DPL."""
    conn = sqlite3.connect(":memory:")
    comp_rows = []
    for g in range(1, 26):
        # D1: pair 1 (top pair, harder deployment)
        comp_rows.append({
            "playerId": 10, "team": "EDM", "gameId": g,
            "position": "D", "toi_seconds": 1200, "total_toi_seconds": 1400,
            "line_number": 1, "deployment_score": 500,
            "comp_fwd": 900, "comp_def": 800,
            "pct_vs_top_fwd": 0.6, "pct_vs_top_def": 0.5,
            "pct_any_elite_fwd": 0.4, "pct_any_elite_def": 0.4,
            "height_in": 74, "weight_lbs": 200,
            "heaviness": 2.70, "weighted_forward_heaviness": 2.70,
            "weighted_defense_heaviness": 2.70, "weighted_team_heaviness": 2.70,
        })
        # D2: pair 3 (bottom pair, easier deployment)
        comp_rows.append({
            "playerId": 11, "team": "EDM", "gameId": g,
            "position": "D", "toi_seconds": 900, "total_toi_seconds": 1400,
            "line_number": 3, "deployment_score": 200,
            "comp_fwd": 750, "comp_def": 700,
            "pct_vs_top_fwd": 0.3, "pct_vs_top_def": 0.3,
            "pct_any_elite_fwd": 0.2, "pct_any_elite_def": 0.2,
            "height_in": 73, "weight_lbs": 195,
            "heaviness": 2.67, "weighted_forward_heaviness": 2.67,
            "weighted_defense_heaviness": 2.67, "weighted_team_heaviness": 2.67,
        })
    pd.DataFrame(comp_rows).to_sql("competition", conn, if_exists="replace", index=False)
    pts_rows = []
    for g in range(1, 26):
        pts_rows.append({"playerId": 10, "gameId": g, "goals": 0, "assists": 1, "points": 1})
        pts_rows.append({"playerId": 11, "gameId": g, "goals": 0, "assists": 1, "points": 1})
    pd.DataFrame(pts_rows).to_sql("points_5v5", conn, if_exists="replace", index=False)
    build_elite_defensemen_table(conn)
    rows = pd.read_sql_query("SELECT * FROM elite_defensemen", conn)
    conn.close()
    assert "dpl" in rows.columns
    row10 = rows[rows["playerId"] == 10].iloc[0]
    row11 = rows[rows["playerId"] == 11].iloc[0]
    assert row10["dpl"] < row11["dpl"]   # pair 1 < pair 3
    assert abs(row10["dpl"] - 1.0) < 0.01
    assert abs(row11["dpl"] - 3.0) < 0.01
```

**Step 2: Run to verify tests fail**

```
python -m pytest v2/browser/tests/test_player_metrics.py -k "dps_plus or dpl" -v
```
Expected: FAIL — `AssertionError: 'weighted_dps_plus' not in columns` and `AssertionError: 'dpl' not in columns`

**Step 3: Add `deployment_score` to the forward competition query and compute `weighted_dps_plus`**

In `v2/browser/build_league_db.py`, in `build_elite_forwards_table()`:

1. Add `c.deployment_score` to the SQL query. Find:
```python
        SELECT c.playerId, c.team, c.gameId,
               c.toi_seconds, c.total_toi_seconds, c.line_number,
               5.0 * c.toi_seconds / tt.team_total AS ttoi_frac
        FROM competition c
```
Replace with:
```python
        SELECT c.playerId, c.team, c.gameId,
               c.toi_seconds, c.total_toi_seconds, c.line_number,
               COALESCE(c.deployment_score, 0) AS deployment_score,
               5.0 * c.toi_seconds / tt.team_total AS ttoi_frac
        FROM competition c
```

2. Add `"weighted_dps_plus"` to `_COLS`:
```python
    _COLS = [
        "playerId", "team", "gp", "toi_min_gp",
        "fs_p60", "l20_p60", "weighted_p60",
        "fs_dpl", "l20_dpl", "weighted_dpl",
        "fs_ttoi_pct", "l20_ttoi_pct", "weighted_ttoi_pct",
        "fs_itoi_pct", "l20_itoi_pct", "weighted_itoi_pct",
        "weighted_dps_plus",
    ]
```

3. Add `fs_depl` and `l20_depl` computation inside the per-player loop. Find the block computing `fs_dpl_raw` and add the deployment score computation right after:

After:
```python
        fs_dpl_raw    = grp["line_number"].dropna()
        fs_dpl        = float(fs_dpl_raw.mean()) if not fs_dpl_raw.empty else None
```

Add:
```python
        fs_depl_raw   = grp["deployment_score"].dropna()
        fs_depl       = float(fs_depl_raw.mean()) if not fs_depl_raw.empty else None
```

4. Inside the `if total_player_gp >= 20:` block for l20 metrics, after `l20_dpl`:
```python
            l20_dpl_raw   = l20_rows["line_number"].dropna()
            l20_dpl       = float(l20_dpl_raw.mean()) if not l20_dpl_raw.empty else None
```

Add:
```python
            l20_depl_raw  = l20_rows["deployment_score"].dropna()
            l20_depl      = float(l20_depl_raw.mean()) if not l20_depl_raw.empty else None
```

5. Add initialization of `l20_depl` alongside `l20_dpl`. Find:
```python
        l20_p60 = l20_ttoi_pct = l20_itoi_pct = l20_dpl = None
```
Replace with:
```python
        l20_p60 = l20_ttoi_pct = l20_itoi_pct = l20_dpl = l20_depl = None
```

6. Add `weighted_depl` computation in the weighted metrics section. Find the existing weighted DPL section:
```python
            if fs_dpl is not None and l20_dpl is not None:
                weighted_dpl = fs_dpl * 0.8 + l20_dpl * 0.2
            else:
                weighted_dpl = fs_dpl  # fall back to full-season if l20 unavailable
```

Add after it:
```python
            if fs_depl is not None and l20_depl is not None:
                weighted_depl = fs_depl * 0.8 + l20_depl * 0.2
            else:
                weighted_depl = fs_depl
```

And in the Phase 2 (full-season only) section, after `weighted_dpl = fs_dpl`:
```python
            weighted_depl = fs_depl
```

7. Add `"weighted_depl"` to the `records.append({...})` dict. Find:
```python
            "weighted_dpl":      round(weighted_dpl, 4) if weighted_dpl is not None else None,
```

Add after it:
```python
            "weighted_depl":     round(weighted_depl, 4) if weighted_depl is not None else None,
```

8. After `out = pd.DataFrame(records)` and before `out.to_sql(...)`, add normalization:
Find:
```python
    out = pd.DataFrame(records)
    out.to_sql("elite_forwards", conn, if_exists="replace", index=False)
```
Replace with:
```python
    out = pd.DataFrame(records)
    fwd_league_avg = out["weighted_depl"].dropna().mean()
    if fwd_league_avg and fwd_league_avg > 0:
        out["weighted_dps_plus"] = out["weighted_depl"] / fwd_league_avg * 100
    else:
        out["weighted_dps_plus"] = None
    out[_COLS].to_sql("elite_forwards", conn, if_exists="replace", index=False)
```

Also update the empty-return case at the top of the function. Find both `pd.DataFrame(columns=_COLS).to_sql(...)` calls and they will automatically include `weighted_dps_plus` since `_COLS` was updated.

**Step 4: Add `dpl` to `build_elite_defensemen_table()`**

In `v2/browser/build_league_db.py`, in `build_elite_defensemen_table()`:

1. Add `c.line_number` to the SQL query. Find:
```python
            c.toi_seconds,
            COALESCE(c.deployment_score, 0) AS deployment_score,
            5.0 * c.toi_seconds / tt.team_total AS ttoi_frac
```
Replace with:
```python
            c.toi_seconds,
            COALESCE(c.deployment_score, 0) AS deployment_score,
            COALESCE(c.line_number, 4) AS line_number,
            5.0 * c.toi_seconds / tt.team_total AS ttoi_frac
```

2. Add `"dpl"` to `_COLS`:
```python
    _COLS = ["playerId", "team", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus"]
```
Replace with:
```python
    _COLS = ["playerId", "team", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus", "dpl"]
```

3. Inside the per-player loop, add `avg_pair` computation. Find:
```python
            rows.append({"playerId": pid, "team": team, "gp": gp,
                "toi_min_gp": round(total_toi / gp / 60, 2),
                "p60": p60, "ttoi_pct": ttoi_pct, "avg_deploy": avg_deploy})
```
Replace with:
```python
            avg_pair = grp["line_number"].mean()
            rows.append({"playerId": pid, "team": team, "gp": gp,
                "toi_min_gp": round(total_toi / gp / 60, 2),
                "p60": p60, "ttoi_pct": ttoi_pct, "avg_deploy": avg_deploy,
                "dpl": round(avg_pair, 2)})
```

4. After computing `dps_plus`, store `dpl` alongside it. The current code ends with:
```python
    df["dps_plus"] = df["avg_deploy"] / league_avg * 100 if league_avg > 0 else 100.0
    elite = df[(df["p60"] > 1.2) & (df["ttoi_pct"] > 35.0) & (df["dps_plus"] > 120.0)].copy()
    elite[_COLS].to_sql("elite_defensemen", conn, if_exists="replace", index=False)
```

The `dpl` column is already in `df` from the `rows.append()` call; `_COLS` already includes `"dpl"`, so `elite[_COLS]` will include it automatically.

**Step 5: Run failing tests to verify they now pass**

```
python -m pytest v2/browser/tests/test_player_metrics.py -k "dps_plus or dpl" -v
```
Expected: 2 PASSED

**Step 6: Update `elites.py` SQL and table builders**

In `v2/browser/pages/elites.py`:

1. Update `_FWD_SQL` to include `weighted_dps_plus`:
```python
_FWD_SQL = """
SELECT e.playerId, e.team, e.gp, e.toi_min_gp,
       e.weighted_p60, e.weighted_dpl, e.weighted_ttoi_pct, e.weighted_itoi_pct,
       e.weighted_dps_plus,
       e.fs_p60, e.fs_dpl, e.fs_ttoi_pct, e.fs_itoi_pct,
       e.l20_p60, e.l20_dpl, e.l20_ttoi_pct, e.l20_itoi_pct,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName
FROM elite_forwards e
LEFT JOIN players p ON e.playerId = p.playerId
ORDER BY e.weighted_p60 DESC
"""
```

2. Update `_DEF_SQL` to include `dpl`:
```python
_DEF_SQL = """
SELECT e.playerId, e.team, e.gp, e.toi_min_gp,
       e.p60, e.ttoi_pct, e.dps_plus, e.dpl,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName
FROM elite_defensemen e
LEFT JOIN players p ON e.playerId = p.playerId
ORDER BY e.p60 DESC
"""
```

3. Update `_build_fwd_table()` to add DPS+ column. Find the `columns` list definition:
```python
        {"name": "iTOI%",   "id": "weighted_itoi_pct",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "team_link", "gp", "toi_min_gp",
        "weighted_p60", "weighted_dpl", "weighted_ttoi_pct", "weighted_itoi_pct",
    ]
```
Replace with:
```python
        {"name": "iTOI%",   "id": "weighted_itoi_pct",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "DPS+",    "id": "weighted_dps_plus",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "team_link", "gp", "toi_min_gp",
        "weighted_p60", "weighted_dpl", "weighted_ttoi_pct", "weighted_itoi_pct",
        "weighted_dps_plus",
    ]
```

4. Update `_build_def_table()` to add DPL column. Find:
```python
        {"name": "DPS+",    "id": "dps_plus",      "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = ["player_link", "team_link", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus"]
```
Replace with:
```python
        {"name": "DPS+",    "id": "dps_plus",      "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "DPL",     "id": "dpl",           "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = ["player_link", "team_link", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus", "dpl"]
```

**Step 7: Run full test suite**

```
python -m pytest v2/ -v
```
Expected: All tests pass (existing 110 + 2 new elite DPS+/DPL tests = 112+)

---

## Verification

After all tasks are complete and tests pass:

1. **Reprocess all 2025 games:**
   ```
   python v2/competition/compute_competition.py 1 1312 2025
   ```
   This regenerates all competition CSVs with D pair numbers in `line_number` and F deployment scores in `deployment_score`.

2. **Rebuild league DB:**
   ```
   python v2/browser/build_league_db.py 2025
   ```
   Verify elite_forwards has `weighted_dps_plus`, elite_defensemen has `dpl`.

3. **Visual checks:**
   - Game page: D table shows "Pair" column with values 1–4; F table shows "Dep Score" with non-negative values
   - Skaters page: separate DPL and DPS+ columns, both populated for all positions
   - Elites Forwards page: new DPS+ column populated
   - Elites Defensemen page: new DPL column populated
