# Player Heaviness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add height, weight, per-player heaviness score, and team heaviness score to the competition output CSV.

**Architecture:** Three pure functions are added to `compute_competition.py` — `load_player_physicals` reads height/weight from the existing per-player JSON files, `compute_heaviness` computes `weight_lbs / height_in`, and `compute_team_heaviness` computes the TOI-weighted mean heaviness per team. In `run_game`, physical data is merged into the `scores` dict before `write_output`, keeping the pipeline pattern consistent with how `pct_scores` was handled. Goalies are already excluded from output; players missing a physicals file get zeros for all three columns.

**Tech Stack:** Python 3.11+, stdlib only. No new dependencies.

---

## Reference

- Script: `v2/competition/compute_competition.py`
- Tests: `v2/competition/tests/test_compute_competition.py`
- Player data: `data/2025/players/{playerId}.json` — fields used: `heightInInches`, `weightInPounds`
- Current output schema: `gameId, playerId, team, position, toi_seconds, comp_fwd, comp_def, pct_vs_top_fwd, pct_vs_top_def`
- New output schema adds: `height_in` (int), `weight_lbs` (int), `heaviness` (float, 4dp), `team_heaviness` (float, 4dp)

**Metric definitions:**

- `height_in`: total height in inches (e.g. 6'1" → 73). Pulled directly from `heightInInches`.
- `weight_lbs`: weight in pounds. Pulled directly from `weightInPounds`.
- `heaviness`: `weight_lbs / height_in`, rounded to 4 decimal places. A 200 lb / 72 in player scores 2.7778. Missing height → 0.0.
- `team_heaviness`: TOI-weighted mean `heaviness` across all skaters (non-goalies) on the team in this game. Players missing physicals are excluded from the average. Formula: `sum(heaviness_i * toi_i) / sum(toi_i)` for all eligible skaters on the team.

---

## Task 1: `load_player_physicals` and `compute_heaviness`

Two pure functions. `load_player_physicals` reads player JSON files. `compute_heaviness` computes the ratio.

**Files:**
- Modify: `v2/competition/compute_competition.py` (add after `load_plays`, currently around line 238)
- Test: `v2/competition/tests/test_compute_competition.py` (append tests)

**Step 1: Write the failing tests**

Append to `v2/competition/tests/test_compute_competition.py`:

```python
from compute_competition import load_player_physicals, compute_heaviness


def test_load_player_physicals_returns_height_weight():
    """Load height/weight for a known player from real data files.

    NOTE: Must be run from project root (data/ is relative to cwd).
    Uses Connor McDavid (8478402) as a known stable test case.
    """
    physicals = load_player_physicals([8478402], "2025")
    assert 8478402 in physicals
    assert physicals[8478402]["height_in"] > 0
    assert physicals[8478402]["weight_lbs"] > 0


def test_load_player_physicals_missing_player_skipped():
    """A player ID with no file is silently skipped, not an error."""
    physicals = load_player_physicals([999999999], "2025")
    assert 999999999 not in physicals


def test_compute_heaviness_200lbs_72in():
    """200 / 72 = 2.7778"""
    assert abs(compute_heaviness(72, 200) - 200 / 72) < 0.0001


def test_compute_heaviness_zero_height_returns_zero():
    """Guard against division by zero when height is missing."""
    assert compute_heaviness(0, 200) == 0.0
```

**Step 2: Run tests to confirm failure**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/competition/tests/test_compute_competition.py::test_compute_heaviness_200lbs_72in -v
```

Expected: `ImportError: cannot import name 'compute_heaviness'`

**Step 3: Implement the two functions**

Add after `load_plays` (around line 238) in `v2/competition/compute_competition.py`:

```python
def load_player_physicals(
    player_ids: List[int],
    season: str,
) -> Dict[int, dict]:
    """
    Load height and weight from per-player JSON files.

    Returns:
        {playerId: {"height_in": int, "weight_lbs": int}}
        Players with no file are absent from the result.
    """
    physicals: Dict[int, dict] = {}
    for pid in player_ids:
        path = DATA_DIR / season / "players" / f"{pid}.json"
        try:
            with open(path) as f:
                data = json.load(f)
            physicals[pid] = {
                "height_in":  data.get("heightInInches", 0),
                "weight_lbs": data.get("weightInPounds", 0),
            }
        except FileNotFoundError:
            pass
    return physicals


def compute_heaviness(height_in: int, weight_lbs: int) -> float:
    """
    Compute heaviness score: weight_lbs / height_in.

    Returns 0.0 if height is zero (missing data guard).
    """
    if height_in == 0:
        return 0.0
    return weight_lbs / height_in
```

**Step 4: Run all tests**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/competition/tests/test_compute_competition.py -v
```

Expected: all previous tests + 4 new tests pass.

---

## Task 2: `compute_team_heaviness`

TOI-weighted mean heaviness per team. Goalies excluded. Players without physicals excluded from the average.

**Files:**
- Modify: `v2/competition/compute_competition.py` (add after `compute_heaviness`)
- Test: `v2/competition/tests/test_compute_competition.py` (append tests)

**Step 1: Work out expected values by hand**

Setup: EDM has two skaters.
- Player 1: height=72, weight=200 → heaviness=2.7778, toi=600
- Player 2: height=74, weight=220 → heaviness=2.9730, toi=300
- team_heaviness = (2.7778×600 + 2.9730×300) / (600+300) = (1666.67 + 891.89) / 900 = 2.8428

**Step 2: Write the failing tests**

Append to `v2/competition/tests/test_compute_competition.py`:

```python
from compute_competition import compute_team_heaviness


def test_compute_team_heaviness_toi_weighted_average():
    """Team heaviness is the TOI-weighted mean of individual heaviness scores."""
    toi       = {1: 600, 2: 300}
    positions = {1: "F", 2: "F"}
    teams     = {1: "EDM", 2: "EDM"}
    physicals = {
        1: {"height_in": 72, "weight_lbs": 200},
        2: {"height_in": 74, "weight_lbs": 220},
    }
    result   = compute_team_heaviness(toi, positions, teams, physicals)
    h1, h2   = 200 / 72, 220 / 74
    expected = (h1 * 600 + h2 * 300) / (600 + 300)
    assert abs(result["EDM"] - expected) < 0.0001


def test_compute_team_heaviness_skips_missing_physicals():
    """Players with no physicals entry are excluded from the average."""
    toi       = {1: 600, 2: 300}
    positions = {1: "F", 2: "F"}
    teams     = {1: "EDM", 2: "EDM"}
    physicals = {1: {"height_in": 72, "weight_lbs": 200}}  # player 2 absent
    result    = compute_team_heaviness(toi, positions, teams, physicals)
    assert abs(result["EDM"] - 200 / 72) < 0.0001


def test_compute_team_heaviness_skips_goalies():
    """Goalies are excluded even if they have physicals."""
    toi       = {1: 600, 99: 1200}
    positions = {1: "F", 99: "G"}
    teams     = {1: "EDM", 99: "EDM"}
    physicals = {
        1:  {"height_in": 72, "weight_lbs": 200},
        99: {"height_in": 75, "weight_lbs": 215},
    }
    result = compute_team_heaviness(toi, positions, teams, physicals)
    assert abs(result["EDM"] - 200 / 72) < 0.0001


def test_compute_team_heaviness_two_teams():
    """Produces separate entries for each team."""
    toi       = {1: 600, 2: 600}
    positions = {1: "F", 2: "F"}
    teams     = {1: "EDM", 2: "CGY"}
    physicals = {
        1: {"height_in": 72, "weight_lbs": 200},
        2: {"height_in": 76, "weight_lbs": 240},
    }
    result = compute_team_heaviness(toi, positions, teams, physicals)
    assert abs(result["EDM"] - 200 / 72) < 0.0001
    assert abs(result["CGY"] - 240 / 76) < 0.0001
```

**Step 3: Run tests to confirm failure**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/competition/tests/test_compute_competition.py::test_compute_team_heaviness_toi_weighted_average -v
```

Expected: `ImportError: cannot import name 'compute_team_heaviness'`

**Step 4: Implement `compute_team_heaviness`**

Add directly after `compute_heaviness` in `v2/competition/compute_competition.py`:

```python
def compute_team_heaviness(
    toi: Dict[int, int],
    positions: Dict[int, str],
    teams: Dict[int, str],
    physicals: Dict[int, dict],
) -> Dict[str, float]:
    """
    Compute TOI-weighted mean heaviness per team for skaters only.

    Players absent from physicals are excluded from the average.
    Goalies are excluded.

    Returns:
        {teamAbbrev: team_heaviness_float}
    """
    weighted: Dict[str, float] = {}   # team -> sum(heaviness * toi)
    total_toi: Dict[str, int] = {}    # team -> sum(toi)

    for pid, seconds in toi.items():
        if positions.get(pid, "F") == "G":
            continue
        if pid not in physicals:
            continue
        h = physicals[pid]["height_in"]
        w = physicals[pid]["weight_lbs"]
        score = compute_heaviness(h, w)
        if score == 0.0:
            continue
        team = teams.get(pid, "")
        if not team:
            continue
        weighted[team]  = weighted.get(team, 0.0)  + score * seconds
        total_toi[team] = total_toi.get(team, 0)   + seconds

    return {
        team: weighted[team] / total_toi[team]
        for team in weighted
        if total_toi.get(team, 0) > 0
    }
```

**Step 5: Run all tests**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/competition/tests/test_compute_competition.py -v
```

Expected: all previous + 4 new = passing total.

---

## Task 3: Wire into pipeline and update output

Update `run_game` to call the two new functions and fold results into `scores`. Update `write_output` to emit four new columns. Update the integration test.

**Files:**
- Modify: `v2/competition/compute_competition.py` (`run_game` and `write_output`)
- Modify: `v2/competition/tests/test_compute_competition.py` (`test_run_game_produces_output`)

**Step 1: Update `run_game`**

In `run_game`, after the `pct_scores` merge block, add:

```python
    physicals     = load_player_physicals(list(toi.keys()), season)
    team_heaviness = compute_team_heaviness(toi, positions, teams, physicals)

    for pid in scores:
        ph    = physicals.get(pid, {})
        h_in  = ph.get("height_in", 0)
        w_lbs = ph.get("weight_lbs", 0)
        team  = teams.get(pid, "")
        scores[pid]["height_in"]       = h_in
        scores[pid]["weight_lbs"]      = w_lbs
        scores[pid]["heaviness"]       = round(compute_heaviness(h_in, w_lbs), 4)
        scores[pid]["team_heaviness"]  = round(team_heaviness.get(team, 0.0), 4)
```

The full updated `run_game` function:

```python
def run_game(game_number: int, season: str) -> Path:
    """Full pipeline for a single game. Returns path to output CSV."""
    game_id = f"{season}{GAME_TYPE}{game_number:04d}"

    plays_data = load_plays(season, game_id)
    positions, teams = build_lookups(plays_data)

    timeline_rows = load_timeline(season, game_id)
    toi = compute_game_toi(timeline_rows)

    scores = score_game(timeline_rows, toi, positions)
    top_comp = build_top_competition(toi, positions, teams)
    pct_scores = score_game_pct(timeline_rows, positions, teams, top_comp)

    for pid in scores:
        if pid in pct_scores:  # goalies and edge-case players may be absent from pct_scores
            scores[pid].update(pct_scores[pid])

    physicals      = load_player_physicals(list(toi.keys()), season)
    team_heaviness = compute_team_heaviness(toi, positions, teams, physicals)

    for pid in scores:
        ph    = physicals.get(pid, {})
        h_in  = ph.get("height_in", 0)
        w_lbs = ph.get("weight_lbs", 0)
        team  = teams.get(pid, "")
        scores[pid]["height_in"]      = h_in
        scores[pid]["weight_lbs"]     = w_lbs
        scores[pid]["heaviness"]      = round(compute_heaviness(h_in, w_lbs), 4)
        scores[pid]["team_heaviness"] = round(team_heaviness.get(team, 0.0), 4)

    return write_output(game_id, season, scores, toi, positions, teams)
```

**Step 2: Update `write_output`**

Add four new fields to each row dict and extend `fieldnames`.

In the row-building block, after `"pct_vs_top_def"`, add:

```python
            "height_in":       data.get("height_in", 0),
            "weight_lbs":      data.get("weight_lbs", 0),
            "heaviness":       data.get("heaviness", 0.0),
            "team_heaviness":  data.get("team_heaviness", 0.0),
```

Update `fieldnames` to:

```python
    fieldnames = [
        "gameId", "playerId", "team", "position", "toi_seconds",
        "comp_fwd", "comp_def", "pct_vs_top_fwd", "pct_vs_top_def",
        "height_in", "weight_lbs", "heaviness", "team_heaviness",
    ]
```

**Step 3: Update the integration test**

In `test_run_game_produces_output`, update `required`:

```python
    required = {"gameId", "playerId", "team", "position", "toi_seconds",
                "comp_fwd", "comp_def", "pct_vs_top_fwd", "pct_vs_top_def",
                "height_in", "weight_lbs", "heaviness", "team_heaviness"}
```

After the existing pct range check and non-zero pct assertion, add:

```python
    # heaviness must be >= 0.0; most players should have a non-zero value
    for row in rows:
        assert float(row["heaviness"]) >= 0.0, \
            f"Player {row['playerId']} has negative heaviness"
        assert float(row["team_heaviness"]) >= 0.0, \
            f"Player {row['playerId']} has negative team_heaviness"

    # Sanity: at least one player has a non-zero heaviness (physicals file exists)
    assert any(float(row["heaviness"]) > 0.0 for row in rows), \
        "Expected at least one player with non-zero heaviness"
```

**Step 4: Run all tests**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/competition/tests/test_compute_competition.py -v
```

Expected: all tests pass.

**Step 5: Spot-check the output**

```bash
cd /Users/jrf1039/files/projects/nhl && python v2/competition/compute_competition.py 1 2025 && head -5 data/2025/generated/competition/2025020001.csv
```

Expected:
- Header includes `height_in`, `weight_lbs`, `heaviness`, `team_heaviness`
- Heaviness values in roughly 2.5–3.2 range (typical NHL skater: 170–240 lbs, 68–78 in)
- All players on the same team in the same game share the same `team_heaviness` value

---

## Verification Checklist

After all tasks complete:

- [ ] `python -m pytest v2/competition/tests/ -v` — all green
- [ ] Output CSV has 13 columns
- [ ] `height_in` values are in the 68–80 range for known players
- [ ] `heaviness` values are in the 2.3–3.3 range
- [ ] All players on the same team in a game have the same `team_heaviness`
- [ ] Players missing a physicals file show `0` / `0.0` (not an error)
