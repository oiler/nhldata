# wPPI Formula Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the wPPI formula so that light players who play more get a lower score and heavy players who play more get a higher score, fixing the current behavior where playing time always helps regardless of a player's size.

**Architecture:** The change is entirely in `metrics.py`. The old formula `wPPI = PPI × share` is replaced with `wPPI = (PPI - mean_PPI) × avg_toi_share`. Light players (below-mean PPI) accumulate negative wPPI the more they play; heavy players accumulate positive wPPI. wPPI+ normalization switches from ratio-based (mean = 100 via division) to z-score-based (mean = 100, std = 15), since the new wPPI is centered near zero and cannot be normalized by dividing by a mean. The old per-team `share = avg_toi / team_avg` computation is removed entirely — `avg_toi_share` (already computed in the function as `5 × player_toi / team_toi`) is used for both wPPI and the returned `avg_toi_share` column.

**Tech Stack:** Python, pandas

---

## File Map

- **Modify:** `v2/browser/metrics.py` — replace wPPI formula and normalization
- **Modify:** `v2/browser/tests/test_deployment_metrics.py` — rewrite two wPPI tests that encode the old formula; verify all others still pass

---

### Task 1: Rewrite the wPPI tests to encode the new formula

**Files:**
- Modify: `v2/browser/tests/test_deployment_metrics.py`

Two existing tests encode the old formula and must be rewritten. Four others remain valid and must still pass after the implementation change.

- [ ] **Step 1: Replace `test_wppi_single_team`**

The old test computed `wPPI = PPI × (player_avg_toi / team_avg_toi)`. The new formula is `wPPI = (PPI - mean_PPI) × avg_toi_share` where `avg_toi_share = 5 × player_toi / team_toi`.

Using `_standard_data()`:
- Players 1, 2, 3 on FLA, 6 games each. TOI: 900s, 1000s, 600s per game.
- PPIs: 2.75, 2.97, 2.57 → mean_PPI = (2.75 + 2.97 + 2.57) / 3 = 2.763
- team_toi per game = 900 + 1000 + 600 = 2500
- Player 1 avg_toi_share = 5 × 900 / 2500 = 1.8
- Player 1 wPPI = (2.75 − 2.763) × 1.8 = −0.013 × 1.8 = −0.0234

Replace the existing `test_wppi_single_team` with:

```python
def test_wppi_single_team():
    """
    wPPI = (PPI - mean_PPI) * avg_toi_share.
    Player 1: PPI=2.75, team mean_PPI=(2.75+2.97+2.57)/3=2.763, avg_toi_share=5*900/2500=1.8
    wPPI = (2.75 - 2.763) * 1.8 = -0.0234
    """
    comp, ppi = _standard_data()
    result = compute_deployment_metrics(comp, ppi)
    mean_ppi = (2.75 + 2.97 + 2.57) / 3
    team_toi_per_game = 900 + 1000 + 600  # 2500
    avg_toi_share_p1 = 5 * 900 / team_toi_per_game  # 1.8
    expected_wppi = (2.75 - mean_ppi) * avg_toi_share_p1
    assert abs(result.loc[1, "wppi"] - expected_wppi) < 0.001
```

- [ ] **Step 2: Replace `test_wppi_traded_player`**

The old test asserted `wppi ≈ ppi` (2.60) because the player was the only one on each team, making share = 1.0. With the new formula, a player is the only eligible player → mean_PPI = their own PPI → deviation = 0 → wPPI = 0.

Replace the existing `test_wppi_traded_player` with:

```python
def test_wppi_traded_player():
    """
    Player 5 is the only eligible player on EDM and VAN.
    mean_PPI = player's own PPI → deviation = 0 → wPPI = 0 regardless of TOI.
    """
    comp_rows = []
    for game in range(1, 4):
        comp_rows.append({"playerId": 5, "team": "EDM", "gameId": game, "position": "F", "toi_seconds": 800})
    for game in range(4, 7):
        comp_rows.append({"playerId": 5, "team": "VAN", "gameId": game, "position": "F", "toi_seconds": 800})
    ppi_rows = [{"playerId": 5, "ppi": 2.60, "ppi_plus": 100.0}]
    result = compute_deployment_metrics(_make_comp(comp_rows), _make_ppi(ppi_rows))
    assert abs(result.loc[5, "wppi"] - 0.0) < 0.001
```

- [ ] **Step 3: Add a test that verifies the directional behavior — light player playing more gets lower wPPI**

Append after the existing wPPI tests:

```python
def test_wppi_light_player_more_toi_lower_score():
    """
    Light player (below mean PPI) who plays more gets more negative wPPI.
    Heavy player (above mean PPI) who plays more gets more positive wPPI.
    avg PPI player always gets wPPI = 0 regardless of minutes.
    Setup: 3 players, same team, same PPI spread, different TOI.
      Player 1: PPI=3.20 (heavy), high TOI → positive wPPI
      Player 2: PPI=2.73 (avg),   any TOI  → wPPI = 0
      Player 3: PPI=2.25 (light), high TOI → negative wPPI
    mean_PPI = (3.20 + 2.73 + 2.25) / 3 = 2.727
    """
    comp_rows = []
    for game in range(1, 7):
        comp_rows.append({"playerId": 1, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 1000})
        comp_rows.append({"playerId": 2, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 1000})
        comp_rows.append({"playerId": 3, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 1000})
    ppi_rows = [
        {"playerId": 1, "ppi": 3.20, "ppi_plus": 117.4},
        {"playerId": 2, "ppi": 2.727, "ppi_plus": 100.0},
        {"playerId": 3, "ppi": 2.25, "ppi_plus": 82.5},
    ]
    result = compute_deployment_metrics(_make_comp(comp_rows), _make_ppi(ppi_rows))
    assert result.loc[1, "wppi"] > 0, "heavy player should have positive wPPI"
    assert abs(result.loc[2, "wppi"]) < 0.01, "avg PPI player should have wPPI ≈ 0"
    assert result.loc[3, "wppi"] < 0, "light player should have negative wPPI"


def test_wppi_light_player_more_toi_amplifies_penalty():
    """
    Light player playing MORE minutes gets a MORE negative wPPI than the same light
    player playing fewer minutes.
    """
    comp_rows = []
    for game in range(1, 7):
        # Player 1: light, high TOI (1000s/game)
        comp_rows.append({"playerId": 1, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 1000})
        # Player 2: light (same PPI), low TOI (400s/game)
        comp_rows.append({"playerId": 2, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 400})
        # Player 3: average PPI filler to set mean_PPI
        comp_rows.append({"playerId": 3, "team": "FLA", "gameId": game, "position": "F", "toi_seconds": 700})
    ppi_rows = [
        {"playerId": 1, "ppi": 2.25, "ppi_plus": 82.5},
        {"playerId": 2, "ppi": 2.25, "ppi_plus": 82.5},
        {"playerId": 3, "ppi": 2.73, "ppi_plus": 100.0},
    ]
    result = compute_deployment_metrics(_make_comp(comp_rows), _make_ppi(ppi_rows))
    # Both light, player 1 plays more → player 1 should have lower (more negative) wPPI
    assert result.loc[1, "wppi"] < result.loc[2, "wppi"]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest v2/browser/tests/test_deployment_metrics.py -k "wppi" -v`

Expected: 4 failures — `test_wppi_single_team`, `test_wppi_traded_player`, `test_wppi_light_player_more_toi_lower_score`, `test_wppi_light_player_more_toi_amplifies_penalty` — all fail because the implementation still uses the old formula. The other wPPI tests (`test_wppi_plus_mean_is_100`, `test_wppi_traded_player_no_inflation`) should still pass.

---

### Task 2: Implement the new wPPI formula in `metrics.py`

**Files:**
- Modify: `v2/browser/metrics.py`

- [ ] **Step 1: Replace the full `compute_wppi_and_toi_share` function**

The current function has two separate share computations: `share = avg_toi / team_avg` (used for wPPI) and `toi_share = 5 × toi_seconds / game_team_toi` (used for avg_toi_share). The new function uses only the second, cleaner computation for both.

Replace the entire function body with:

```python
def compute_wppi_and_toi_share(eligible: pd.DataFrame, comp_df: pd.DataFrame) -> pd.DataFrame:
    """Compute wPPI, wPPI+, avg_toi_share for eligible players.

    wPPI formula: (PPI - mean_PPI) × avg_toi_share
    - Below-mean PPI players accumulate negative wPPI as they play more.
    - Above-mean PPI players accumulate positive wPPI as they play more.
    - A player at exactly mean PPI gets wPPI = 0 regardless of minutes.

    avg_toi_share: per-game mean of (5 × player_toi / team_toi).
    wPPI+: z-score normalized, mean=100, std=15.

    Args:
        eligible: DataFrame indexed by playerId with at least a 'ppi' column.
                  Rows should already be filtered to eligible players (GP >= 5).
        comp_df:  Full competition data with columns:
                  playerId, team, gameId, toi_seconds.

    Returns:
        Copy of eligible with added columns: wppi, wppi_plus, avg_toi_share.
        Players with missing avg_toi_share are dropped.
        Returns empty DataFrame if no valid values can be computed.
    """
    eligible = eligible.copy()

    # avg_toi_share: mean of per-game (5 × player_toi / team_toi) across player's games.
    # team_toi uses full comp (all skaters, not just eligible), matching real game deployment totals.
    game_team_toi = comp_df.groupby(["team", "gameId"])["toi_seconds"].transform("sum")
    cs = comp_df.copy()
    cs["toi_share"] = 5.0 * cs["toi_seconds"] / game_team_toi.where(game_team_toi > 0)
    avg_toi_share = (
        cs[cs["playerId"].isin(eligible.index)]
        .groupby("playerId")["toi_share"]
        .mean()
        .rename("avg_toi_share")
    )
    eligible = eligible.join(avg_toi_share)
    eligible = eligible[eligible["avg_toi_share"].notna()]

    if eligible.empty:
        return pd.DataFrame()

    # wPPI: deviation from mean PPI, scaled by TOI share.
    # Light players (below mean) who play more drag their score further negative.
    # Heavy players (above mean) who play more push their score further positive.
    mean_ppi = eligible["ppi"].mean()
    eligible["wppi"] = (eligible["ppi"] - mean_ppi) * eligible["avg_toi_share"]

    # wPPI+: z-score normalized, centered at 100 with std=15.
    # Cannot use ratio normalization (mean wPPI ≈ 0), so use z-score instead.
    wppi_std = eligible["wppi"].std()
    if wppi_std and wppi_std > 0:
        eligible["wppi_plus"] = 100.0 + (eligible["wppi"] - eligible["wppi"].mean()) / wppi_std * 15.0
    else:
        eligible["wppi_plus"] = 100.0

    return eligible
```

- [ ] **Step 2: Run the wPPI tests**

Run: `python -m pytest v2/browser/tests/test_deployment_metrics.py -k "wppi" -v`

Expected: All wPPI tests pass.

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest v2/ -v`

Expected: All 127 tests pass (125 existing + 2 new).

---

## Verification

After implementation, rebuild the DB and spot-check the sample players:

```sql
SELECT p.firstName, p.lastName, pm.ppi, pm.ppi_plus, pm.wppi, pm.wppi_plus, pm.avg_toi_share
FROM player_metrics pm
JOIN players p ON pm.playerId = p.playerId
WHERE p.lastName IN ('Hughes', 'Sanderson', 'Protas', 'Rempe', 'Ehlers')
ORDER BY pm.wppi_plus DESC
```

Expected ordering by wPPI+: Protas > Rempe > Sanderson (≈100) > Hughes > Ehlers

Quinn Hughes should have wPPI+ well below 100 despite heavy minutes. Matt Rempe should score above 100 despite limited minutes because his PPI deviation is large enough to overcome the low tTOI%.
