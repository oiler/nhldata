# wPPI Per-Game Normalization Fix

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix wPPI so it uses average TOI per game rather than total season TOI for the share calculation, removing the games-played penalty for players who missed time.

**Architecture:** Single change to `build_player_metrics_table()` in `build_league_db.py`. No browser pages change — the fix is purely in the computation layer. Rebuild `league.db` after.

**Tech Stack:** Python, pandas, SQLite

---

## The Problem

Current formula:
```
share_i,t = total_TOI_i,t / team_total_eligible_TOI_t
```

A player who played 35 games at 15 min/game has ~half the total TOI of one who played 75 games at 15 min/game — so their share, and therefore wPPI, is ~half as large even though their per-game deployment is identical.

## The Fix

Replace the share denominator with average TOI per game:

```
avg_toi_i,t       = total_TOI_i,t / games_played_i,t
team_avg_toi_t    = team_total_eligible_TOI_t / team_unique_eligible_games_t
share_i,t         = avg_toi_i,t / team_avg_toi_t
wPPI_i            = Σ_t (PPI_i × share_i,t)
```

Now two players with the same TOI per game get the same share, regardless of how many games they played.

---

## Task 1: Update wPPI formula and rebuild league.db

**Files:**
- Modify: `v2/browser/build_league_db.py`
- Modify: `v2/browser/tests/test_player_metrics.py`
- Modify: `resources/heaviness_calculations.md`

---

### Step 1: Write the failing test

Add `test_wppi_per_game_normalization` to `v2/browser/tests/test_player_metrics.py`.

This test creates two players on the same team with identical TOI per game but different games played, and asserts they get equal wPPI. It will **FAIL** with the current formula.

```python
def test_wppi_per_game_normalization():
    """Players with same TOI/game but different games played get the same wPPI."""
    conn = sqlite3.connect(":memory:")
    rows = []
    # Player 10: FLA F, 8 games, 900s/game
    for game in range(1, 9):
        rows.append({"playerId": 10, "team": "FLA", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    # Player 11: FLA F, 5 games, 900s/game — same per-game rate, fewer games played
    for game in range(11, 16):
        rows.append({"playerId": 11, "team": "FLA", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    df = pd.DataFrame(rows)
    df.to_sql("competition", conn, index=False, if_exists="replace")
    build_player_metrics_table(conn)
    p10 = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 10").fetchone()[0]
    p11 = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 11").fetchone()[0]
    assert abs(p10 - p11) < 0.001
```

**Run:** `cd v2/browser && python -m pytest tests/test_player_metrics.py::test_wppi_per_game_normalization -v`
**Expected:** FAIL — `|p10 - p11|` will be ~0.634 with the current formula.

---

### Step 2: Update build_player_metrics_table()

In `v2/browser/build_league_db.py`, replace the wPPI block (currently lines 103–114):

**Old:**
```python
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
```

**New:**
```python
# wPPI: PPI × per-game TOI share per team-stint, summed across stints
# Using per-game rates removes the penalty for players who missed games.
eligible_comp = comp[comp["playerId"].isin(eligible.index)]
player_team_toi   = eligible_comp.groupby(["playerId", "team"])["toi_seconds"].sum()
player_team_games = eligible_comp.groupby(["playerId", "team"])["gameId"].nunique()
player_avg_toi    = player_team_toi / player_team_games  # avg seconds/game per stint

team_total_toi    = eligible_comp.groupby("team")["toi_seconds"].sum()
team_unique_games = eligible_comp.groupby("team")["gameId"].nunique()
team_avg_toi      = team_total_toi / team_unique_games   # team avg eligible-seconds/game

wppi_map: dict = {}
for (pid, team), avg_toi in player_avg_toi.items():
    team_avg = team_avg_toi.get(team, 0)
    if team_avg == 0:
        continue
    share = avg_toi / team_avg
    wppi_map[pid] = wppi_map.get(pid, 0.0) + eligible.loc[pid, "ppi"] * share
```

---

### Step 3: Run unit tests

**Run:** `cd v2/browser && python -m pytest tests/test_player_metrics.py -v`
**Expected:** All 7 tests pass (6 existing + 1 new).

Note: The existing `test_wppi_traded_player` expected value is unchanged — in that fixture player 3 is the only eligible player on each team, so per-game and total-TOI shares are identical.

---

### Step 4: Update resources/heaviness_calculations.md

Update the wPPI section to reflect the per-game formula. Replace the "Step 1–3" block for wPPI:

**Old Step 2 (Compute team total 5v5 TOI):**
```
TOI_team,t = sum of 5v5 TOI for all eligible skaters on that team
```

**New Step 2:**
```
avg_TOI_i,t   = TOI_i,t / games_played_i,t        (player avg TOI per game on team t)
avg_TOI_team,t = TOI_team,t / unique_games_team,t  (team avg eligible-player TOI per game)
```

**Old Step 3 (TOI share):**
```
shareᵢ,t = TOIᵢ,t / TOI_team,t
```

**New Step 3:**
```
shareᵢ,t = avg_TOI_i,t / avg_TOI_team,t
```

Update the Interpretation section to note: "Games missed due to injury or trade do not reduce a player's wPPI — only their average per-game deployment matters."

---

### Step 5: Rebuild league.db

**Run:** `python v2/browser/build_league_db.py`
**Expected:** Output includes `player_metrics: NNN rows`

---

### Step 6: Run full test suite

**Run:** `cd v2/browser && python -m pytest tests/ -v`
**Expected:** All 22 tests pass.

---

### Step 7: Commit

```bash
git add v2/browser/build_league_db.py \
        v2/browser/tests/test_player_metrics.py \
        resources/heaviness_calculations.md
git commit -m "fix: normalize wPPI by per-game TOI to remove games-played penalty"
```
