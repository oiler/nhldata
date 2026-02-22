# Competition % vs Top Lines Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add two new per-skater metrics to the competition CSV — `pct_vs_top_fwd` and `pct_vs_top_def` — measuring what fraction of a player's 5v5 ice time was spent facing the opposing team's top forwards and top defensemen.

**Architecture:** Add two pure functions to the existing `v2/competition/compute_competition.py` and wire them into the existing pipeline. `build_top_competition` identifies the top-6 forwards and top-4 defensemen per team by game 5v5 TOI. `score_game_pct` iterates the timeline second-by-second and computes, for each skater, the mean fraction of opposing forwards/defensemen who qualified as "top." Both results are merged in `run_game` and written as new columns in the output CSV. The existing `comp_fwd`/`comp_def` columns are kept unchanged.

**Tech Stack:** Python 3.11+, stdlib only. No new dependencies.

---

## Reference

- Script: `v2/competition/compute_competition.py`
- Tests: `v2/competition/tests/test_compute_competition.py`
- Real data: `data/2025/plays/2025020001.json`, `data/2025/generated/timelines/csv/2025020001.csv`
- Existing output schema: `gameId, playerId, team, position, toi_seconds, comp_fwd, comp_def`
- New output schema adds: `pct_vs_top_fwd, pct_vs_top_def` (floats, 0.0–1.0, rounded to 4 decimal places)

**Top competition definitions (per game, per team):**
- Top forwards: top 6 by 5v5 TOI on the opposing team
- Top defensemen: top 4 by 5v5 TOI on the opposing team

**Metric definition:**
For each 5v5 second a player is on ice, compute:
- `fwd_frac` = (# opposing forwards in top-6) / (# opposing forwards on ice)
- `def_frac` = (# opposing defensemen in top-4) / (# opposing defensemen on ice)

`pct_vs_top_fwd` = mean of `fwd_frac` across all 5v5 seconds. Same for `pct_vs_top_def`.

Using a fraction per second (rather than binary yes/no) handles partial line changes — e.g., if 2 of 3 opposing forwards are top-6, that second contributes 0.667, not 1.0.

**Key implementation note:** `build_top_competition` is called after `compute_game_toi`, so the `toi` dict it receives already reflects only the 5v5-situation seconds (per `SCORED_SITUATIONS`). This means "top-6 by 5v5 TOI" naturally reflects 5v5 deployment, not overall TOI.

---

## Task 1: build_top_competition()

Identify the top-6 forwards and top-4 defensemen per team from the game's 5v5 TOI dict.

**Files:**
- Modify: `v2/competition/compute_competition.py` (add after `compute_game_toi`)
- Modify: `v2/competition/tests/test_compute_competition.py` (append tests)

**Step 1: Write the failing tests**

Append to `v2/competition/tests/test_compute_competition.py`:

```python
from compute_competition import build_top_competition


def test_build_top_competition_top6_fwd_top4_def():
    """Top-6 forwards and top-4 defensemen selected per team by TOI."""
    # EDM: 6 forwards (F1–F6 top, F7 bottom), 4 defensemen (D1–D4 top, D5 bottom)
    # FLA: same structure on other side
    toi = {
        # EDM forwards — F7 (pid 17) has lowest TOI, should be excluded
        11: 1000, 12: 900, 13: 800, 14: 700, 15: 600, 16: 500, 17: 100,
        # EDM defense — D5 (pid 25) has lowest TOI, should be excluded
        21: 1000, 22: 900, 23: 800, 24: 700, 25: 100,
        # FLA forwards
        31: 1000, 32: 900, 33: 800, 34: 700, 35: 600, 36: 500, 37: 100,
        # FLA defense
        41: 1000, 42: 900, 43: 800, 44: 700, 45: 100,
    }
    positions = {
        11: "F", 12: "F", 13: "F", 14: "F", 15: "F", 16: "F", 17: "F",
        21: "D", 22: "D", 23: "D", 24: "D", 25: "D",
        31: "F", 32: "F", 33: "F", 34: "F", 35: "F", 36: "F", 37: "F",
        41: "D", 42: "D", 43: "D", 44: "D", 45: "D",
    }
    teams = {
        11: "EDM", 12: "EDM", 13: "EDM", 14: "EDM", 15: "EDM", 16: "EDM", 17: "EDM",
        21: "EDM", 22: "EDM", 23: "EDM", 24: "EDM", 25: "EDM",
        31: "FLA", 32: "FLA", 33: "FLA", 34: "FLA", 35: "FLA", 36: "FLA", 37: "FLA",
        41: "FLA", 42: "FLA", 43: "FLA", 44: "FLA", 45: "FLA",
    }

    top = build_top_competition(toi, positions, teams)

    assert top["EDM"]["top_fwd"] == {11, 12, 13, 14, 15, 16}  # not 17
    assert top["EDM"]["top_def"] == {21, 22, 23, 24}           # not 25
    assert top["FLA"]["top_fwd"] == {31, 32, 33, 34, 35, 36}  # not 37
    assert top["FLA"]["top_def"] == {41, 42, 43, 44}           # not 45


def test_build_top_competition_fewer_than_threshold():
    """If a team has fewer players than the threshold, all qualify."""
    toi = {1: 500, 2: 400, 3: 300}  # only 3 forwards, all EDM
    positions = {1: "F", 2: "F", 3: "F"}
    teams = {1: "EDM", 2: "EDM", 3: "EDM"}

    top = build_top_competition(toi, positions, teams)

    # Fewer than 6 forwards → all 3 qualify
    assert top["EDM"]["top_fwd"] == {1, 2, 3}
    assert top["EDM"]["top_def"] == set()
```

**Step 2: Run tests to confirm failure**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/competition/tests/test_compute_competition.py::test_build_top_competition_top6_fwd_top4_def -v
```

Expected: `ImportError: cannot import name 'build_top_competition'`

**Step 3: Implement build_top_competition()**

Add this function to `v2/competition/compute_competition.py` after `compute_game_toi`:

```python
def build_top_competition(
    toi: Dict[int, int],
    positions: Dict[int, str],
    teams: Dict[int, str],
) -> Dict[str, Dict[str, set]]:
    """
    Identify top-6 forwards and top-4 defensemen per team by 5v5 TOI.

    Returns:
        {teamAbbrev: {"top_fwd": {playerId, ...}, "top_def": {playerId, ...}}}
    """
    team_fwds: Dict[str, List] = {}
    team_defs: Dict[str, List] = {}

    for pid, seconds in toi.items():
        team = teams.get(pid, "")
        pos = positions.get(pid, "F")
        if pos == "F":
            team_fwds.setdefault(team, []).append((pid, seconds))
        elif pos == "D":
            team_defs.setdefault(team, []).append((pid, seconds))

    result: Dict[str, Dict[str, set]] = {}
    all_teams = set(team_fwds) | set(team_defs)
    for team in all_teams:
        fwds = sorted(team_fwds.get(team, []), key=lambda x: x[1], reverse=True)
        defs = sorted(team_defs.get(team, []), key=lambda x: x[1], reverse=True)
        result[team] = {
            "top_fwd": {pid for pid, _ in fwds[:6]},
            "top_def": {pid for pid, _ in defs[:4]},
        }

    return result
```

**Step 4: Run all tests**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py -v
```

Expected: all previous tests + 2 new tests = 10 PASS

---

## Task 2: score_game_pct()

For each 5v5 second per skater, compute the fraction of opposing forwards/defensemen who are "top competition," then average across the game.

**Files:**
- Modify: `v2/competition/compute_competition.py` (add after `build_top_competition`)
- Modify: `v2/competition/tests/test_compute_competition.py` (append tests)

**Step 1: Work out expected values by hand**

Setup:
- Away skaters: 1(F), 2(F), 3(F), 4(D), 5(D) — all EDM
- Home skaters: 6(F,top), 7(F,top), 20(F,NOT top), 9(D,top), 10(D,top) — all FLA
- FLA top_fwd = {6, 7} (20 is bottom-6), FLA top_def = {9, 10}

For away player 1 (F), opponents = [6, 7, 20, 9, 10]:
- opp_fwds = [6, 7, 20]; top_fwd_count = 2 (6 and 7); fwd_frac = 2/3 = 0.6667
- opp_defs = [9, 10]; top_def_count = 2; def_frac = 2/2 = 1.0
- With 1 row: pct_vs_top_fwd = 0.6667, pct_vs_top_def = 1.0

For home player 6 (F, top), opponents = [1, 2, 3, 4, 5]:
- EDM top_fwd = {1, 2, 3}, top_def = {4, 5}
- opp_fwds = [1, 2, 3]; top_fwd_count = 3; fwd_frac = 3/3 = 1.0
- opp_defs = [4, 5]; top_def_count = 2; def_frac = 2/2 = 1.0
- pct_vs_top_fwd = 1.0, pct_vs_top_def = 1.0

**Step 2: Write the failing test**

Append to `v2/competition/tests/test_compute_competition.py`:

```python
from compute_competition import score_game_pct


def test_score_game_pct_single_row():
    rows = [{"situationCode": "1551",
             "awaySkaters": "1|2|3|4|5",
             "homeSkaters": "6|7|20|9|10"}]
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 20: "F", 9: "D", 10: "D"}
    teams = {1: "EDM", 2: "EDM", 3: "EDM", 4: "EDM", 5: "EDM",
             6: "FLA", 7: "FLA", 20: "FLA", 9: "FLA", 10: "FLA"}
    # FLA top_fwd = {6,7} (20 has lowest TOI), FLA top_def = {9,10}
    # EDM top_fwd = {1,2,3}, EDM top_def = {4,5}
    toi = {1: 1000, 2: 900, 3: 800, 4: 700, 5: 600,
           6: 1000, 7: 900, 20: 100, 9: 800, 10: 700}
    top_comp = build_top_competition(toi, positions, teams)

    result = score_game_pct(rows, positions, teams, top_comp)

    # Away player 1: opp fwds [6,7,20], 2 are top → 2/3
    assert abs(result[1]["pct_vs_top_fwd"] - 2/3) < 0.001
    assert abs(result[1]["pct_vs_top_def"] - 1.0) < 0.001

    # Home player 6: opp fwds [1,2,3], all top → 1.0
    assert abs(result[6]["pct_vs_top_fwd"] - 1.0) < 0.001
    assert abs(result[6]["pct_vs_top_def"] - 1.0) < 0.001


def test_score_game_pct_skips_non_5v5():
    rows = [
        {"situationCode": "1441", "awaySkaters": "1|2|3|4",   "homeSkaters": "6|7|8|9"},
        {"situationCode": "1551", "awaySkaters": "1|2|3|4|5", "homeSkaters": "6|7|20|9|10"},
    ]
    positions = {1: "F", 2: "F", 3: "F", 4: "D", 5: "D",
                 6: "F", 7: "F", 20: "F", 9: "D", 10: "D",
                 8: "F"}
    teams = {1: "EDM", 2: "EDM", 3: "EDM", 4: "EDM", 5: "EDM",
             6: "FLA", 7: "FLA", 20: "FLA", 8: "FLA", 9: "FLA", 10: "FLA"}
    toi = {1: 1000, 2: 900, 3: 800, 4: 700, 5: 600,
           6: 1000, 7: 900, 20: 100, 9: 800, 10: 700}
    top_comp = build_top_competition(toi, positions, teams)

    result = score_game_pct(rows, positions, teams, top_comp)

    # Player 5 only appears in the 1551 row — must be in result
    assert 5 in result
    # Player 1 appears in both rows but only 1551 is scored — same pct as single-row test
    assert abs(result[1]["pct_vs_top_fwd"] - 2/3) < 0.001
```

**Step 3: Run tests to confirm failure**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py::test_score_game_pct_single_row -v
```

Expected: `ImportError: cannot import name 'score_game_pct'`

**Step 4: Implement score_game_pct()**

Add this function to `v2/competition/compute_competition.py` after `build_top_competition`:

```python
def score_game_pct(
    rows: List[dict],
    positions: Dict[int, str],
    teams: Dict[int, str],
    top_comp: Dict[str, Dict[str, set]],
) -> Dict[int, dict]:
    """
    For every skater in every 5v5 second, compute the fraction of opposing
    forwards who are top-6 and opposing defensemen who are top-4.

    Returns:
        {playerId: {"pct_vs_top_fwd": float, "pct_vs_top_def": float}}
    """
    accum: Dict[int, dict] = {}

    for row in rows:
        if row["situationCode"] not in SCORED_SITUATIONS:
            continue

        away = [int(p) for p in row["awaySkaters"].split("|")] if row.get("awaySkaters") else []
        home = [int(p) for p in row["homeSkaters"].split("|")] if row.get("homeSkaters") else []

        for player_id, opponents in (
            [(p, home) for p in away] +
            [(p, away) for p in home]
        ):
            if positions.get(player_id, "F") == "G":
                continue

            if player_id not in accum:
                accum[player_id] = {"fwd_fracs": [], "def_fracs": []}

            opp_team = teams.get(opponents[0], "") if opponents else ""
            opp_top = top_comp.get(opp_team, {"top_fwd": set(), "top_def": set()})

            opp_fwds = [p for p in opponents if positions.get(p, "F") == "F"]
            opp_defs = [p for p in opponents if positions.get(p, "F") == "D"]

            if opp_fwds:
                top_count = sum(1 for p in opp_fwds if p in opp_top["top_fwd"])
                accum[player_id]["fwd_fracs"].append(top_count / len(opp_fwds))

            if opp_defs:
                top_count = sum(1 for p in opp_defs if p in opp_top["top_def"])
                accum[player_id]["def_fracs"].append(top_count / len(opp_defs))

    result: Dict[int, dict] = {}
    for pid, data in accum.items():
        fwd_fracs = data["fwd_fracs"]
        def_fracs = data["def_fracs"]
        result[pid] = {
            "pct_vs_top_fwd": sum(fwd_fracs) / len(fwd_fracs) if fwd_fracs else 0.0,
            "pct_vs_top_def": sum(def_fracs) / len(def_fracs) if def_fracs else 0.0,
        }

    return result
```

**Step 5: Run all tests**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py -v
```

Expected: all previous tests + 4 new tests = 12 PASS

---

## Task 3: Wire into pipeline and update output

Update `run_game` to call both new functions and merge results. Update `write_output` to include the two new columns. Update the integration test.

**Files:**
- Modify: `v2/competition/compute_competition.py`
- Modify: `v2/competition/tests/test_compute_competition.py`

**Step 1: Update run_game()**

Replace the existing `run_game` function:

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

    # Merge pct scores into main scores dict
    for pid in scores:
        if pid in pct_scores:
            scores[pid].update(pct_scores[pid])

    return write_output(game_id, season, scores, toi, positions, teams)
```

**Step 2: Update write_output()**

Replace the existing `write_output` function:

```python
def write_output(game_id: str, season: str, scores: Dict[int, dict],
                 toi: Dict[int, int], positions: Dict[int, str],
                 teams: Dict[int, str]) -> Path:
    """Write per-player competition scores to CSV."""
    out_dir = DATA_DIR / season / "generated" / "competition"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{game_id}.csv"

    rows = []
    for pid, data in scores.items():
        rows.append({
            "gameId":           game_id,
            "playerId":         pid,
            "team":             teams.get(pid, ""),
            "position":         positions.get(pid, "F"),
            "toi_seconds":      toi.get(pid, 0),
            "comp_fwd":         round(data["comp_fwd"], 2),
            "comp_def":         round(data["comp_def"], 2),
            "pct_vs_top_fwd":   round(data.get("pct_vs_top_fwd", 0.0), 4),
            "pct_vs_top_def":   round(data.get("pct_vs_top_def", 0.0), 4),
        })

    rows.sort(key=lambda r: r["toi_seconds"], reverse=True)

    fieldnames = [
        "gameId", "playerId", "team", "position", "toi_seconds",
        "comp_fwd", "comp_def", "pct_vs_top_fwd", "pct_vs_top_def",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return out_path
```

**Step 3: Update the integration test**

In `test_run_game_produces_output`, update the required columns set and add assertions for the new columns:

Replace:
```python
    required = {"gameId", "playerId", "team", "position", "toi_seconds", "comp_fwd", "comp_def"}
```

With:
```python
    required = {"gameId", "playerId", "team", "position", "toi_seconds",
                "comp_fwd", "comp_def", "pct_vs_top_fwd", "pct_vs_top_def"}
```

Also add after the position assertion:
```python
    # pct columns must be in [0.0, 1.0]
    for row in rows:
        assert 0.0 <= float(row["pct_vs_top_fwd"]) <= 1.0, \
            f"Player {row['playerId']} pct_vs_top_fwd out of range: {row['pct_vs_top_fwd']}"
        assert 0.0 <= float(row["pct_vs_top_def"]) <= 1.0, \
            f"Player {row['playerId']} pct_vs_top_def out of range: {row['pct_vs_top_def']}"
```

**Step 4: Run all tests**

```bash
python -m pytest v2/competition/tests/test_compute_competition.py -v
```

Expected: 12 PASS (8 original + 4 new)

**Step 5: Spot-check the output**

```bash
python v2/competition/compute_competition.py 1 2025
head -5 data/2025/generated/competition/2025020001.csv
```

Expected: header includes `pct_vs_top_fwd` and `pct_vs_top_def`. Top players should show values roughly in the 0.5–0.9 range. A player who faces the opponent's top line every shift would approach 1.0; a sheltered bottom-liner would be lower.

---

## Verification Checklist

After all tasks complete:

- [ ] `python -m pytest v2/competition/tests/ -v` — 12 green
- [ ] Output CSV has 9 columns: `gameId, playerId, team, position, toi_seconds, comp_fwd, comp_def, pct_vs_top_fwd, pct_vs_top_def`
- [ ] All `pct_vs_top_fwd` and `pct_vs_top_def` values are between 0.0 and 1.0
- [ ] Top-line players have noticeably different pct values than bottom-liners in the same game
