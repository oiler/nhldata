# wPPI Traded-Player Inflation Fix

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix wPPI so traded players are not double-counted relative to single-team players with identical per-game deployment.

**Architecture:** Single change to `build_player_metrics_table()` in `build_league_db.py` — replace the stint-share **sum** with a games-weighted **average**. Rebuild `league.db` after. No browser page changes needed.

**Tech Stack:** Python, pandas, SQLite

---

## The Problem

Current formula sums the per-game share across every team stint:

```
wPPI_i = PPI_i × Σ_t (share_i,t)
```

A player on two teams with `share = 1.0` on each gets `wPPI = PPI × 2.0`, while a single-team player with the same deployment gets `wPPI = PPI × 1.0`. This causes Kulak (EDM→PIT) to show wPPI+ = 235.4, roughly double a comparably deployed player.

## The Fix

Replace the sum with a games-weighted average of shares across stints:

```
wPPI_i = PPI_i × Σ_t (share_i,t × games_i,t) / Σ_t (games_i,t)
```

A player traded mid-season contributes each team's share weighted by how many games they played there, giving the same result as a single-team player with equivalent deployment.

---

## Task 1: Update wPPI formula and rebuild league.db

**Files:**
- Modify: `v2/browser/build_league_db.py`
- Modify: `v2/browser/tests/test_player_metrics.py`
- Modify: `resources/heaviness_calculations.md`

---

### Step 1: Write the failing test

Add `test_wppi_traded_player_no_inflation` to `v2/browser/tests/test_player_metrics.py`.

This test creates a traded player and a single-team player with **identical** per-game deployment and asserts they get the same wPPI. It will **FAIL** with the current formula.

```python
def test_wppi_traded_player_no_inflation():
    """A traded player with the same per-game deployment as a single-team player
    gets the same wPPI — stints are averaged, not summed."""
    conn = sqlite3.connect(":memory:")
    rows = []
    # Player 10: single-team, ANA for 20 games, 900s/game
    for game in range(1, 21):
        rows.append({"playerId": 10, "team": "ANA", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    # Player 11: traded — 10 games on ANA (different gameIds), then 10 games on BOS
    # Same 900s/game deployment as player 10 throughout
    for game in range(101, 111):
        rows.append({"playerId": 11, "team": "ANA", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    for game in range(201, 211):
        rows.append({"playerId": 11, "team": "BOS", "gameId": game, "position": "F",
                     "toi_seconds": 900, "height_in": 72, "weight_lbs": 198})
    df = pd.DataFrame(rows)
    df.to_sql("competition", conn, index=False, if_exists="replace")
    build_player_metrics_table(conn)
    p10 = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 10").fetchone()[0]
    p11 = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 11").fetchone()[0]
    assert abs(p10 - p11) < 0.001, f"Traded player inflation: p10={p10:.4f}, p11={p11:.4f}"
```

**Run:** `cd v2/browser && python -m pytest tests/test_player_metrics.py::test_wppi_traded_player_no_inflation -v`
**Expected:** FAIL — `p11` will be ~2× `p10` with the current sum formula.

---

### Step 2: Update build_player_metrics_table()

In `v2/browser/build_league_db.py`, replace the wPPI block (currently lines 103–120):

**Old:**
```python
# wPPI: PPI × per-game TOI share per team-stint, summed across stints.
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

**New:**
```python
# wPPI: PPI × games-weighted average TOI share across team stints.
# Weighted average (not sum) ensures traded players aren't double-counted
# relative to single-team players with identical per-game deployment.
eligible_comp = comp[comp["playerId"].isin(eligible.index)]
player_team_toi   = eligible_comp.groupby(["playerId", "team"])["toi_seconds"].sum()
player_team_games = eligible_comp.groupby(["playerId", "team"])["gameId"].nunique()
player_avg_toi    = player_team_toi / player_team_games  # avg seconds/game per stint

team_total_toi    = eligible_comp.groupby("team")["toi_seconds"].sum()
team_unique_games = eligible_comp.groupby("team")["gameId"].nunique()
team_avg_toi      = team_total_toi / team_unique_games   # team avg eligible-seconds/game

share_numerator: dict = {}
share_denominator: dict = {}
for (pid, team), avg_toi in player_avg_toi.items():
    team_avg = team_avg_toi.get(team, 0)
    if team_avg == 0:
        continue
    share = avg_toi / team_avg
    games = int(player_team_games.get((pid, team), 1))
    share_numerator[pid] = share_numerator.get(pid, 0.0) + share * games
    share_denominator[pid] = share_denominator.get(pid, 0) + games

wppi_map: dict = {}
for pid, numerator in share_numerator.items():
    denom = share_denominator.get(pid, 0)
    if denom == 0:
        continue
    weighted_avg_share = numerator / denom
    wppi_map[pid] = eligible.loc[pid, "ppi"] * weighted_avg_share
```

---

### Step 3: Update test_wppi_traded_player

The existing `test_wppi_traded_player` expects the old sum of shares and will now fail. Update its expected value and docstring in `v2/browser/tests/test_player_metrics.py`:

**Old (lines 71–85):**
```python
def test_wppi_traded_player():
    """
    Player 3 is the only eligible player on EDM and VAN.
    Per-game avg TOI: 1800s / 3 games = 600s/game per stint.
    Team avg TOI per game on each team is also 600s/game (same player).
    So share = 600/600 = 1.0 on each team.
    wPPI = PPI × (1.0 + 1.0).
    """
    conn = _setup_db()
    build_player_metrics_table(conn)
    row = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 3").fetchone()
    assert row is not None
    # per-game share: (player avg toi / team avg toi) per stint
    expected = (180 / 70) * (600 / 600 + 600 / 600)
    assert abs(row[0] - expected) < 0.001
```

**New:**
```python
def test_wppi_traded_player():
    """
    Player 3 is the only eligible player on EDM (3 games) and VAN (3 games).
    Per-game avg TOI: 600s/game per stint; team avg also 600s/game.
    So share = 1.0 on each team.
    Games-weighted average: wPPI = PPI × (1.0×3 + 1.0×3) / (3+3) = PPI × 1.0.
    """
    conn = _setup_db()
    build_player_metrics_table(conn)
    row = conn.execute("SELECT wppi FROM player_metrics WHERE playerId = 3").fetchone()
    assert row is not None
    # games-weighted average of per-game shares across stints
    expected = (180 / 70) * (1.0 * 3 + 1.0 * 3) / (3 + 3)
    assert abs(row[0] - expected) < 0.001
```

---

### Step 4: Run unit tests

**Run:** `cd v2/browser && python -m pytest tests/test_player_metrics.py -v`
**Expected:** All 8 tests pass (7 existing + 1 new).

---

### Step 5: Update resources/heaviness_calculations.md

In the wPPI section, update Step 4 and the Interpretation section.

**Old Step 4:**
```
wPPIᵢ,t = PPIᵢ × shareᵢ,t

If player is traded, sum across team stints:

wPPIᵢ = Σ (wPPIᵢ,t)
```

**New Step 4:**
```
For each team stint, compute a games-weighted average of shares:

wPPIᵢ = PPIᵢ × Σ_t (shareᵢ,t × games_i,t) / Σ_t (games_i,t)

where games_i,t = number of distinct games played on team t.
This weighted average ensures a traded player with the same deployment on each team
gets the same wPPI as a single-team player with identical deployment.
```

In the Interpretation section, replace:
```
Games missed due to injury or mid-season trade do not reduce a player's wPPI —
only their average per-game deployment matters.
```
With:
```
Games missed due to injury do not reduce a player's wPPI — only per-game deployment matters.
Mid-season trades are handled by weighting each team stint by games played, so a traded
player with identical deployment on both teams gets the same wPPI as a single-team player.
```

---

### Step 6: Rebuild league.db

**Run:** `python v2/browser/build_league_db.py`
**Expected:** Output includes `player_metrics: NNN rows`

---

### Step 7: Run full test suite

**Run:** `cd v2/browser && python -m pytest tests/ -v`
**Expected:** All 23 tests pass.

---

### Step 8: Commit

```bash
git add v2/browser/build_league_db.py \
        v2/browser/tests/test_player_metrics.py \
        resources/heaviness_calculations.md
git commit -m "fix: use games-weighted average for wPPI to prevent traded-player inflation"
```
