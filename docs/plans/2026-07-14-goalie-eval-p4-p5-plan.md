# Goalie Evaluation P4+P5 (Environment + Game Difficulty/Performance) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the per-game layer (goalie TOI, Game Difficulty Index, difficulty-adjusted + leverage-weighted game ledger) and the team environment profile — after fixing the known `is_rebound` sign anomaly.

**Architecture:** Extends `v2/goalies/` (P0–P3 complete on branch `goalie-eval-p1`). New modules consume the existing shot tables, the tested features/irls/difficulty stack, and raw boxscores. Spec: `docs/plans/2026-06-11-goalie-evaluation-design.md` §6 P4–P5 as revised by §6b (addendum). All derived tables rebuildable from raw.

**Tech Stack:** system python3 (pyenv 3.11, NOT `uv run`), pandas 3.0, numpy 2.4, pytest. No scipy/sklearn.

## Global Constraints

- Branch `goalie-eval-p1` (verify before committing; never push, never master). Local per-task commits authorized.
- No new dependencies. Raw data read-only. Generated CSVs never committed (`data/` is gitignored).
- `distance_adj` clamped ≥ 0 wherever consumed.
- Per §6b: NO idle-gap/"cold goalie" term anywhere (probed null, 2026-07-14).
- Tests: `python3 -m pytest v2/goalies/tests/ -v` per task; full `python3 -m pytest v2/ -q` before finishing. Suite currently 225 green.
- Existing interfaces (do not change signatures): `build_features(df)/STRUCTURE_COLS` (features.py), `fit_penalized_logistic(X, y, penalty, prior_center=None)/predict_proba(X, coef)/FitResult` (irls.py), `fit_layer/LAYERS/layer_frame/LayerFit/predict_structure` (difficulty.py), `gsax_table(df)` (gsax_baseline.py), `chain_seasons` (build_terms.py).
- Shot tables `data/generated/goalies/shots_<season>.csv`, seasons 2021–2025; columns per P0–P2 (incl. `game_id, game_date, home_abbrev, goalie_id, goalie_is_home, period, time_s, distance_adj, shot_type, strength, score_diff, event, is_goal, on_net, dt_prev, prev_type, prev_same_team, prev_x_norm, prev_y_norm, froze, rebound_generated`).
- Boxscore shape (verified on raw): `playerByGameStats.{homeTeam,awayTeam}.goalies[]` each with `playerId`, `toi` ("MM:SS", "00:00" if unused), `starter` (bool), `shotsAgainst`, `goalsAgainst`, `saves`; top-level `homeTeam.abbrev/score`, `awayTeam.abbrev/score`, `gameDate`, `id`.

---

### Task 1: Goalie TOI / goalie-games extraction

**Files:**
- Create: `v2/goalies/toi.py`
- Test: `v2/goalies/tests/test_toi.py`

**Interfaces:**
- Produces: `parse_toi(mmss: str) -> int` (seconds; "61:23" valid — minutes may exceed 59); `extract_goalie_games(box: dict) -> list[dict]` with keys `game_id, game_date, goalie_id, team_abbrev, opp_abbrev, is_home, starter, toi_s, shots_against, goals_against, box_saves` — one row per goalie with `toi_s > 0`; CLI `python3 v2/goalies/toi.py` writing `data/generated/goalies/goalie_games_<season>.csv` (extract columns + `season`) for seasons 2021–2025. Tasks 4–6 consume these CSVs.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_toi.py
from v2.goalies.toi import extract_goalie_games, parse_toi


def _box():
    return {
        "id": 2023020100,
        "gameDate": "2023-10-28",
        "homeTeam": {"abbrev": "EDM", "score": 3},
        "awayTeam": {"abbrev": "CGY", "score": 4},
        "playerByGameStats": {
            "homeTeam": {"goalies": [
                {"playerId": 900, "toi": "58:31", "starter": True,
                 "shotsAgainst": 30, "goalsAgainst": 4, "saves": 26},
                {"playerId": 901, "toi": "00:00", "starter": False,
                 "shotsAgainst": 0, "goalsAgainst": 0, "saves": 0},
            ]},
            "awayTeam": {"goalies": [
                {"playerId": 902, "toi": "60:00", "starter": True,
                 "shotsAgainst": 28, "goalsAgainst": 3, "saves": 25},
            ]},
        },
    }


def test_parse_toi():
    assert parse_toi("58:31") == 3511
    assert parse_toi("61:23") == 3683
    assert parse_toi("00:00") == 0


def test_extract_goalie_games_skips_unused_backup():
    rows = extract_goalie_games(_box())
    assert [r["goalie_id"] for r in rows] == [900, 902]
    home = rows[0]
    assert home["team_abbrev"] == "EDM" and home["opp_abbrev"] == "CGY"
    assert home["is_home"] is True and home["starter"] is True
    assert home["toi_s"] == 3511 and home["shots_against"] == 30
    assert home["goals_against"] == 4 and home["box_saves"] == 26
    assert home["game_date"] == "2023-10-28" and home["game_id"] == 2023020100
    assert rows[1]["is_home"] is False and rows[1]["team_abbrev"] == "CGY"
```

- [ ] **Step 2: Run to verify failure** — `python3 -m pytest v2/goalies/tests/test_toi.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# v2/goalies/toi.py
"""Goalie games (TOI, box counts) from raw boxscores.

Usage: python3 v2/goalies/toi.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def parse_toi(mmss: str) -> int:
    m, s = mmss.split(":")
    return int(m) * 60 + int(s)


def extract_goalie_games(box: dict) -> list[dict]:
    rows = []
    for side, opp in (("homeTeam", "awayTeam"), ("awayTeam", "homeTeam")):
        for g in box["playerByGameStats"][side]["goalies"]:
            toi_s = parse_toi(g["toi"])
            if toi_s == 0:
                continue
            rows.append({
                "game_id": box["id"],
                "game_date": box["gameDate"],
                "goalie_id": g["playerId"],
                "team_abbrev": box[side]["abbrev"],
                "opp_abbrev": box[opp]["abbrev"],
                "is_home": side == "homeTeam",
                "starter": bool(g["starter"]),
                "toi_s": toi_s,
                "shots_against": g["shotsAgainst"],
                "goals_against": g["goalsAgainst"],
                "box_saves": g["saves"],
            })
    return rows


def main() -> None:
    for season in SEASONS:
        rows = []
        for f in sorted((ROOT / "data" / season / "boxscores").glob("*.json")):
            rows.extend(extract_goalie_games(json.loads(f.read_text())))
        df = pd.DataFrame(rows).assign(season=season)
        df.to_csv(GEN / f"goalie_games_{season}.csv", index=False)
        print(f"{season}: {len(df)} goalie-games, {df['goalie_id'].nunique()} goalies, "
              f"total TOI {df['toi_s'].sum() / 3600:.0f} h")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test green, then run the CLI.** Expected per season: ~2,700–2,900 goalie-games (2 starters/game + relief appearances); total TOI ≈ 2,650–2,700 hours (1,312 games × ~2 × ~60 min + OT). Sanity: `goals_against` season sum within ~5% of the shots table's goal count (boxscore GA includes empty-net goals; ours excludes them, so boxscore should be HIGHER by roughly 150–250/season — report the deltas, don't assert).

- [ ] **Step 5: Commit** — `git add v2/goalies/toi.py v2/goalies/tests/test_toi.py && git commit -m "feat(goalies): goalie-game TOI extraction from boxscores"`

---

### Task 2: Fix the `is_rebound` sign anomaly (mandatory pre-percentile)

**Files:**
- Modify: `v2/goalies/features.py` (the `is_rebound` definition + `CORSI_PREV` usage)
- Modify: `v2/goalies/tests/test_features.py` (matching tests)
- Test: as above

**Interfaces:** `build_features` signature and `STRUCTURE_COLS` unchanged; only the `is_rebound` row logic changes. Downstream (difficulty, build_terms, gsax_baseline, gate_p3) consume it unchanged.

**Background:** the goal-layer `is_rebound` coefficient is −0.29 — opposite the literature (rebounds convert MORE, even conditional on location). Suspected dilution: the flag counts any same-team Corsi prior event ≤ 3 s, including blocked and missed shots, and `dt_prev` references the nearest *coordinate-bearing* event. A true rebound follows a SAVE.

- [ ] **Step 1: Run the diagnostic (no code changes yet).** Save as `v2/goalies/rebound_diag.py`:

```python
# v2/goalies/rebound_diag.py
"""Diagnostic: which rebound definition carries the literature-consistent sign?

Usage: python3 v2/goalies/rebound_diag.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.features import STRUCTURE_COLS, build_features  # noqa: E402
from v2.goalies.irls import fit_penalized_logistic  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
df = pd.concat([pd.read_csv(GEN / f"shots_{s}.csv") for s in (2021, 2022, 2023, 2024, 2025)],
               ignore_index=True)
on = df[df["on_net"]].copy()

VARIANTS = {
    "current (CORSI<=3s)": None,  # whatever build_features produces today
    "sog_only<=3s": (on["prev_type"].eq("shot-on-goal")
                     & on["prev_same_team"].fillna(False) & (on["dt_prev"] <= 3)),
    "sog_only<=2s": (on["prev_type"].eq("shot-on-goal")
                     & on["prev_same_team"].fillna(False) & (on["dt_prev"] <= 2)),
}

y = on["is_goal"].to_numpy(dtype=float)
penalty = np.full(len(STRUCTURE_COLS), 1.0)
penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
idx = STRUCTURE_COLS.index("is_rebound")
for name, override in VARIANTS.items():
    X = build_features(on)
    if override is not None:
        X = X.copy()
        X["is_rebound"] = override.astype(float).to_numpy()
    fit = fit_penalized_logistic(X.to_numpy(), y, penalty)
    n_flag = int(X["is_rebound"].sum())
    print(f"{name:>22}: coef={fit.coef[idx]:+.4f} se={fit.se[idx]:.4f} "
          f"n_flagged={n_flag} loglik_obj={fit.objective:.1f}")
```

Decision rule: adopt the variant with a **positive** `is_rebound` coefficient and the lowest objective (better fit); prefer `sog_only<=2s` on ties (tightest physical definition). If NO variant is positive, STOP and report DONE_WITH_CONCERNS with the table — do not force a change.

- [ ] **Step 2: Apply the winning definition in `features.py`.** For `sog_only<=2s` (adjust the constant if the diagnostic picked ≤3s):

```python
# in build_features(), replace the is_rebound line with:
        "is_rebound": (dt <= 2) & same & df["prev_type"].eq("shot-on-goal").to_numpy(),
```

Remove `CORSI_PREV`/`prev_corsi` if now unused. Update the docstring: rebound = same-team shot-on-goal (a save) within the window — blocked/missed prior attempts are NOT rebounds (they diluted the flag and flipped its sign).

- [ ] **Step 3: Update tests.** In `test_features.py::test_rebound_rush_crossice_flags`, the first row (`prev_type="shot-on-goal", dt_prev=2`) stays `is_rebound == 1`; ADD a row with `prev_type="blocked-shot", dt_prev=1, prev_same_team=True` asserting `is_rebound == 0` (and `is_crossice_quick` per its own rule). Run `python3 -m pytest v2/goalies/tests/test_features.py -v` — green.

- [ ] **Step 4: Regenerate downstream tables and verify the fix took.**

```bash
python3 v2/goalies/build_terms.py && python3 v2/goalies/gsax_baseline.py && python3 v2/goalies/gate_p3.py
```

Confirm in the new structure_coefs CSVs that the goal-layer `is_rebound` coefficient is now positive in every season. Compare the regenerated `gate_p3_report.txt` headline numbers to the prior run (freeze year-pair r, goal-layer common-population r): report the deltas — they should be small (the gate conclusions must not silently change; if freeze moves by more than ±0.05 or the goal-vs-GSAx ordering flips, STOP and report).

- [ ] **Step 5: Run full suite, commit** — `python3 -m pytest v2/ -q` green; `git add v2/goalies/features.py v2/goalies/tests/test_features.py v2/goalies/rebound_diag.py && git commit -m "fix(goalies): rebound flag = post-save shots only; sign anomaly resolved"`

---

### Task 3: Win-probability table and leverage weights

**Files:**
- Create: `v2/goalies/leverage.py`
- Test: `v2/goalies/tests/test_leverage.py`

**Interfaces:**
- Produces: `wp_table(states: pd.DataFrame) -> pd.DataFrame` — input columns `score_diff, period, time_s, won` (one row per sampled game-state from the goalie team's perspective); output indexed table with columns `score_diff_c` (clipped ±3), `period_c` (clipped 1–4), `time_bucket` (`time_s // 300`), `wp` (mean of `won`), `n`. `leverage_weight(row, table) -> float` = `wp(state) − wp(state with score_diff_c − 1)` — the win-probability a goal against would cost; falls back to 0.0 when either cell is missing or has `n < 200`. CLI `python3 v2/goalies/leverage.py` builds the table from all five seasons' shots joined to game winners and writes `data/generated/goalies/wp_table.csv`. Task 5 consumes both functions and the CSV.
- Winner source: `goalie_games_<season>.csv` is NOT needed — join shots to boxscore final scores via a small winners frame built from `data/<season>/boxscores/*.json` top-level `homeTeam.score`/`awayTeam.score`: goalie's team won = (`goalie_is_home` and home score > away score) or (not `goalie_is_home` and away > home). OT/SO wins count as wins.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_leverage.py
import pandas as pd
import pytest

from v2.goalies.leverage import leverage_weight, wp_table


def _states():
    rows = []
    # tied late: 50/50; up 1 late: 80/20 — 300 samples each so n-guard passes
    for won, n in ((1, 150), (0, 150)):
        rows += [{"score_diff": 0, "period": 3, "time_s": 900, "won": won}] * n
    for won, n in ((1, 240), (0, 60)):
        rows += [{"score_diff": 1, "period": 3, "time_s": 900, "won": won}] * n
    return pd.DataFrame(rows)


def test_wp_table_means_and_clipping():
    t = wp_table(_states())
    tied = t[(t.score_diff_c == 0) & (t.period_c == 3) & (t.time_bucket == 3)]
    up1 = t[(t.score_diff_c == 1) & (t.period_c == 3) & (t.time_bucket == 3)]
    assert tied.iloc[0]["wp"] == pytest.approx(0.5)
    assert up1.iloc[0]["wp"] == pytest.approx(0.8)
    assert tied.iloc[0]["n"] == 300


def test_wp_table_clips_extremes():
    df = pd.DataFrame([{"score_diff": 5, "period": 6, "time_s": 100, "won": 1}] * 3)
    t = wp_table(df)
    assert t.iloc[0]["score_diff_c"] == 3 and t.iloc[0]["period_c"] == 4


def test_leverage_weight_is_wp_drop_of_a_goal_against():
    t = wp_table(_states())
    row = {"score_diff": 1, "period": 3, "time_s": 900}
    # up 1 late (wp .8) -> tied late (wp .5): a goal against costs .3
    assert leverage_weight(row, t) == pytest.approx(0.3)


def test_leverage_weight_missing_cell_returns_zero():
    t = wp_table(_states())
    assert leverage_weight({"score_diff": -2, "period": 1, "time_s": 0}, t) == 0.0
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# v2/goalies/leverage.py
"""Empirical win-probability table and per-shot leverage weights.

State from the GOALIE team's perspective; wp = P(goalie's team wins),
OT/SO wins included. Leverage of a shot = win probability its goal would cost.

Usage: python3 v2/goalies/leverage.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
MIN_CELL = 200


def wp_table(states: pd.DataFrame) -> pd.DataFrame:
    s = states.assign(
        score_diff_c=states["score_diff"].clip(-3, 3),
        period_c=states["period"].clip(1, 4),
        time_bucket=states["time_s"] // 300,
    )
    return (s.groupby(["score_diff_c", "period_c", "time_bucket"])
            .agg(wp=("won", "mean"), n=("won", "size")).reset_index())


def _cell(table: pd.DataFrame, sd: int, p: int, tb: int):
    hit = table[(table.score_diff_c == sd) & (table.period_c == p) & (table.time_bucket == tb)]
    if len(hit) == 0 or hit.iloc[0]["n"] < MIN_CELL:
        return None
    return float(hit.iloc[0]["wp"])


def leverage_weight(row, table: pd.DataFrame) -> float:
    sd = int(max(-3, min(3, row["score_diff"])))
    p = int(max(1, min(4, row["period"])))
    tb = int(row["time_s"] // 300)
    before = _cell(table, sd, p, tb)
    after = _cell(table, max(-3, sd - 1), p, tb)
    if before is None or after is None:
        return 0.0
    return before - after


def game_winners(season: str) -> pd.DataFrame:
    rows = []
    for f in sorted((ROOT / "data" / season / "boxscores").glob("*.json")):
        b = json.loads(f.read_text())
        rows.append({"game_id": b["id"], "home_won": b["homeTeam"]["score"] > b["awayTeam"]["score"]})
    return pd.DataFrame(rows)


def main() -> None:
    frames = []
    for season in SEASONS:
        shots = pd.read_csv(GEN / f"shots_{season}.csv",
                            usecols=["game_id", "goalie_is_home", "score_diff", "period", "time_s"])
        winners = game_winners(season)
        m = shots.merge(winners, on="game_id")
        m["won"] = (m["goalie_is_home"] == m["home_won"]).astype(float)
        frames.append(m[["score_diff", "period", "time_s", "won"]])
    table = wp_table(pd.concat(frames, ignore_index=True))
    table.to_csv(GEN / "wp_table.csv", index=False)
    tied3 = table[(table.score_diff_c == 0) & (table.period_c == 3)]
    print(f"wp_table: {len(table)} cells; tied-3rd wp by bucket:\n{tied3.to_string(index=False)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests green, run the CLI.** Sanity anchors: tied-game cells sit near 0.5 (home-ice asymmetry pools out since states come from both goalies' perspectives — tied cells should be 0.48–0.52); leading cells rise toward 1.0 as time_bucket increases in period 3. If tied-late wp is outside 0.45–0.55, STOP and investigate the join.

- [ ] **Step 5: Commit** — `git add v2/goalies/leverage.py v2/goalies/tests/test_leverage.py && git commit -m "feat(goalies): empirical win-probability table and leverage weights"`

---

### Task 4: Game Difficulty Index

**Files:**
- Create: `v2/goalies/game_difficulty.py`
- Modify: `v2/goalies/gsax_baseline.py` — extract the per-shot blind xG into a reusable helper
- Test: `v2/goalies/tests/test_game_difficulty.py`

**Interfaces:**
- In `gsax_baseline.py`: refactor so the model fit is exposed as `blind_shot_xg(df: pd.DataFrame) -> np.ndarray` (fits the goalie-blind goal model on df, returns per-shot goal probabilities, same order as df) and `gsax_table` calls it; behavior of `gsax_table` unchanged (existing test must still pass untouched).
- In `game_difficulty.py`: `game_rows(shots: pd.DataFrame, xg: np.ndarray, toi: pd.DataFrame) -> pd.DataFrame` — per (season, game_id, goalie_id): `shots_faced, xg_faced, hd_shots` (distance_adj clamped < 15), `rush_shots, rebound_shots, crossice_shots` (feature-definition flags recomputed from the raw columns exactly as features.py defines them), joined to `toi_s` from the goalie-games table (inner join; report dropped rows), `xg_per60 = xg_faced * 3600 / toi_s`, `hd_share = hd_shots / shots_faced`. `add_difficulty_pct(games: pd.DataFrame, min_toi_s: int = 1200) -> pd.DataFrame` — adds `difficulty_pct`: the percentile rank (0–100) of `xg_per60` among ALL goalie-games with `toi_s ≥ min_toi_s` pooled across seasons (games under the TOI floor get NaN). CLI writes `data/generated/goalies/game_difficulty.csv` (all seasons, one file). Tasks 5–6 consume it.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_game_difficulty.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.game_difficulty import add_difficulty_pct, game_rows


def _shots():
    rows = []
    for gid, goalie, n, dist in ((1, 900, 20, 10.0), (2, 900, 10, 40.0)):
        for _ in range(n):
            rows.append({"season": 2023, "game_id": gid, "goalie_id": goalie,
                         "distance_adj": dist, "dt_prev": np.nan, "prev_type": np.nan,
                         "prev_same_team": np.nan, "prev_x_norm": np.nan,
                         "prev_y_norm": np.nan, "y_norm": 5.0})
    return pd.DataFrame(rows)


def _toi():
    return pd.DataFrame([
        {"season": 2023, "game_id": 1, "goalie_id": 900, "toi_s": 3600},
        {"season": 2023, "game_id": 2, "goalie_id": 900, "toi_s": 1800},
    ])


def test_game_rows_aggregates_and_rates():
    shots = _shots()
    xg = np.where(shots["distance_adj"] < 15, 0.15, 0.03)
    g = game_rows(shots, xg, _toi()).set_index("game_id")
    assert g.loc[1, "shots_faced"] == 20 and g.loc[1, "hd_share"] == 1.0
    assert g.loc[1, "xg_faced"] == pytest.approx(3.0)
    assert g.loc[1, "xg_per60"] == pytest.approx(3.0)          # 3.0 xg in 60 min
    assert g.loc[2, "xg_per60"] == pytest.approx(0.6)          # 0.3 xg in 30 min


def test_difficulty_pct_ranks_and_toi_floor():
    games = pd.DataFrame({
        "xg_per60": [1.0, 2.0, 3.0, 4.0, 99.0],
        "toi_s": [3600, 3600, 3600, 3600, 600],   # last one under the floor
    })
    out = add_difficulty_pct(games)
    ranked = out["difficulty_pct"].tolist()
    assert ranked[3] > ranked[2] > ranked[1] > ranked[0]
    assert np.isnan(ranked[4])
    assert ranked[3] == pytest.approx(100.0)
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement.** In `gsax_baseline.py`, extract:

```python
def blind_shot_xg(df: pd.DataFrame) -> np.ndarray:
    """Per-shot goalie-blind goal probability (the model behind gsax_table)."""
    X = build_features(df).to_numpy()
    y = df["is_goal"].to_numpy(dtype=float)
    penalty = np.full(len(STRUCTURE_COLS), 1.0)
    penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
    fit = fit_penalized_logistic(X, y, penalty)
    return predict_proba(X, fit.coef)
```

and have `gsax_table` use `xg = blind_shot_xg(df)`. Then:

```python
# v2/goalies/game_difficulty.py
"""Game Difficulty Index: how hard was each goalie-game's workload?

difficulty_pct = percentile of xG-faced-per-60 among all goalie-games
(toi >= 20 min), pooled across seasons. Components reported alongside.
Per spec addendum 6b: no idle-gap term (probed null 2026-07-14).

Usage: python3 v2/goalies/game_difficulty.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.gsax_baseline import blind_shot_xg  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def game_rows(shots: pd.DataFrame, xg: np.ndarray, toi: pd.DataFrame) -> pd.DataFrame:
    s = shots.assign(
        xg=xg,
        hd=(np.maximum(shots["distance_adj"], 0) < 15),
        rush=(shots["dt_prev"] <= 4) & (shots["prev_x_norm"] < 25),
        rebound=(shots["dt_prev"] <= 2) & shots["prev_same_team"].fillna(False)
                & shots["prev_type"].eq("shot-on-goal"),
        crossice=(shots["dt_prev"] <= 3) & shots["prev_same_team"].fillna(False)
                 & (shots["prev_y_norm"] * shots["y_norm"] < 0)
                 & (shots["prev_y_norm"].abs() >= 5),
    )
    g = s.groupby(["season", "game_id", "goalie_id"]).agg(
        shots_faced=("xg", "size"), xg_faced=("xg", "sum"),
        hd_shots=("hd", "sum"), rush_shots=("rush", "sum"),
        rebound_shots=("rebound", "sum"), crossice_shots=("crossice", "sum"),
    ).reset_index()
    merged = g.merge(toi[["season", "game_id", "goalie_id", "toi_s"]].assign(
        season=toi["season"].astype(g["season"].dtype)),
        on=["season", "game_id", "goalie_id"], how="inner")
    dropped = len(g) - len(merged)
    if dropped:
        print(f"note: {dropped} goalie-games had shots but no TOI row (dropped)")
    merged["xg_per60"] = merged["xg_faced"] * 3600 / merged["toi_s"]
    merged["hd_share"] = merged["hd_shots"] / merged["shots_faced"]
    return merged


def add_difficulty_pct(games: pd.DataFrame, min_toi_s: int = 1200) -> pd.DataFrame:
    out = games.copy()
    eligible = out["toi_s"] >= min_toi_s
    out["difficulty_pct"] = np.nan
    out.loc[eligible, "difficulty_pct"] = out.loc[eligible, "xg_per60"].rank(pct=True) * 100
    return out


def main() -> None:
    frames = []
    for season in SEASONS:
        shots = pd.read_csv(GEN / f"shots_{season}.csv")
        toi = pd.read_csv(GEN / f"goalie_games_{season}.csv")
        frames.append(game_rows(shots, blind_shot_xg(shots), toi))
    games = add_difficulty_pct(pd.concat(frames, ignore_index=True))
    games.to_csv(GEN / "game_difficulty.csv", index=False)
    e = games[games["difficulty_pct"].notna()]
    print(f"{len(games)} goalie-games ({len(e)} eligible); "
          f"xg_per60 median {e['xg_per60'].median():.2f}, "
          f"p10 {e['xg_per60'].quantile(.1):.2f}, p90 {e['xg_per60'].quantile(.9):.2f}")


if __name__ == "__main__":
    main()
```

Note: the rebound/crossice flag recomputation must match Task 2's FINAL `is_rebound` definition — if the diagnostic selected ≤3s, change the constant here to match, and say so in the report.

- [ ] **Step 4: Tests green (including the untouched gsax test), run the CLI.** Anchors: median xg_per60 ≈ 2.4–3.1 (league GA/60 minus empty-netters); p90/p10 ratio ≥ 1.8 — if the spread is much tighter, the "games differ" premise itself is in question: report it prominently either way.

- [ ] **Step 5: Full suite, commit** — `git add v2/goalies/game_difficulty.py v2/goalies/gsax_baseline.py v2/goalies/tests/test_game_difficulty.py && git commit -m "feat(goalies): game difficulty index (xg-per-60 percentile + workload mix)"`

---

### Task 5: Per-game performance ledger

**Files:**
- Create: `v2/goalies/game_ledger.py`
- Test: `v2/goalies/tests/test_game_ledger.py`

**Interfaces:**
- Produces: `ledger_rows(shots: pd.DataFrame, xg: np.ndarray, lev: np.ndarray) -> pd.DataFrame` — per (season, game_id, goalie_id): `ga` (goals), `xga` (sum xg), `gsax_game = xga − ga`, `perf_z = (xga − ga) / sqrt(sum(xg*(1−xg)))` (difficulty-adjusted game z-score; NaN when the variance sum is 0), `lev_value = sum(lev_i * (xg_i − goal_i))` (leverage-weighted value added vs expectation). CLI joins `game_difficulty.csv` (adds `difficulty_pct, xg_per60, toi_s` and `gsax_per60 = gsax_game * 3600 / toi_s`) and writes `data/generated/goalies/game_ledger.csv`. P6 and the browser layer consume it.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_game_ledger.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.game_ledger import ledger_rows


def test_ledger_math():
    shots = pd.DataFrame({
        "season": [2023] * 4, "game_id": [1] * 4, "goalie_id": [900] * 4,
        "is_goal": [True, False, False, False],
    })
    xg = np.array([0.5, 0.5, 0.1, 0.1])
    lev = np.array([0.2, 0.2, 0.1, 0.1])
    r = ledger_rows(shots, xg, lev).iloc[0]
    assert r["ga"] == 1 and r["xga"] == pytest.approx(1.2)
    assert r["gsax_game"] == pytest.approx(0.2)
    var = 2 * 0.5 * 0.5 + 2 * 0.1 * 0.9
    assert r["perf_z"] == pytest.approx(0.2 / np.sqrt(var))
    # lev_value: 0.2*(0.5-1) + 0.2*(0.5-0) + 0.1*(0.1-0)*2
    assert r["lev_value"] == pytest.approx(-0.1 + 0.1 + 0.02)


def test_ledger_zero_variance_guard():
    shots = pd.DataFrame({"season": [2023], "game_id": [1], "goalie_id": [900],
                          "is_goal": [False]})
    r = ledger_rows(shots, np.array([0.0]), np.array([0.0])).iloc[0]
    assert np.isnan(r["perf_z"])
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# v2/goalies/game_ledger.py
"""Per-game goalie ledger: results, difficulty-adjusted z, leverage-weighted value.

A game is its own story: raw GA/xGA, difficulty-adjusted perf_z, and
leverage-weighted value are reported side by side with the game's
difficulty percentile — never collapsed into one number.

Usage: python3 v2/goalies/game_ledger.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.gsax_baseline import blind_shot_xg  # noqa: E402
from v2.goalies.leverage import leverage_weight  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def ledger_rows(shots: pd.DataFrame, xg: np.ndarray, lev: np.ndarray) -> pd.DataFrame:
    s = shots.assign(xg=xg, lev=lev,
                     var=xg * (1 - xg),
                     lev_delta=lev * (xg - shots["is_goal"].astype(float)))
    g = s.groupby(["season", "game_id", "goalie_id"]).agg(
        ga=("is_goal", "sum"), xga=("xg", "sum"),
        var_sum=("var", "sum"), lev_value=("lev_delta", "sum"),
    ).reset_index()
    g["gsax_game"] = g["xga"] - g["ga"]
    g["perf_z"] = np.where(g["var_sum"] > 0, g["gsax_game"] / np.sqrt(g["var_sum"]), np.nan)
    return g.drop(columns=["var_sum"])


def main() -> None:
    wp = pd.read_csv(GEN / "wp_table.csv")
    frames = []
    for season in SEASONS:
        shots = pd.read_csv(GEN / f"shots_{season}.csv")
        xg = blind_shot_xg(shots)
        lev = np.array([leverage_weight(row, wp) for row in
                        shots[["score_diff", "period", "time_s"]].to_dict("records")])
        frames.append(ledger_rows(shots, xg, lev))
    ledger = pd.concat(frames, ignore_index=True)
    diff = pd.read_csv(GEN / "game_difficulty.csv")[
        ["season", "game_id", "goalie_id", "difficulty_pct", "xg_per60", "toi_s"]]
    ledger = ledger.merge(diff, on=["season", "game_id", "goalie_id"], how="left")
    ledger["gsax_per60"] = ledger["gsax_game"] * 3600 / ledger["toi_s"]
    ledger.to_csv(GEN / "game_ledger.csv", index=False)
    print(f"{len(ledger)} goalie-games; mean perf_z {ledger['perf_z'].mean():+.3f} "
          f"(should be ~0); mean lev_value {ledger['lev_value'].mean():+.4f}")


if __name__ == "__main__":
    main()
```

Performance note: the per-row `leverage_weight` loop over ~560k shots will be slow if `_cell` filters the table each call. If runtime exceeds ~2 minutes, build a dict lookup once — `lut = {(r.score_diff_c, r.period_c, r.time_bucket): (r.wp, r.n) for r in wp.itertuples()}` — and vectorize; same values, report which path you used.

- [ ] **Step 4: Tests green, run the CLI.** Anchors: mean perf_z within ±0.03 of 0 (in-sample calibration); mean lev_value within ±0.005 of 0; per-game gsax distribution roughly symmetric.

- [ ] **Step 5: Full suite, commit** — `git add v2/goalies/game_ledger.py v2/goalies/tests/test_game_ledger.py && git commit -m "feat(goalies): per-game ledger (gsax, difficulty-adjusted z, leverage value)"`

---

### Task 6: Team environment profile (P4)

**Files:**
- Create: `v2/goalies/environment.py`
- Test: `v2/goalies/tests/test_environment.py`

**Interfaces:**
- Produces: `team_environment(games: pd.DataFrame, goalie_games: pd.DataFrame, shots: pd.DataFrame) -> pd.DataFrame` — per (season, team_abbrev): `gp` (goalie-games), `mean_difficulty_pct`, `mean_xg_faced_per60`, `hd_share`, `crossice_rate` (crossice shots per 60), `tip_share` (tip-in+deflected share of shots faced), `d_shot_share` (shooter_position == "D" share), `b2b_games` (games where the TEAM's previous game_date is exactly 1 day earlier — sort by game_date, not game_id). `arena_freeze_offsets(shots: pd.DataFrame) -> pd.DataFrame` — per home_abbrev: visiting goalies' freeze rate at that arena minus those same goalies' overall away freeze rate (the P4 scorer-timing check); columns `home_abbrev, n_saves, freeze_offset`. CLI writes `data/generated/goalies/team_environment.csv` and `arena_freeze_offsets.csv`.
- Team attribution: join shots to goalie team via `goalie_is_home` → `home_abbrev` (home goalie) or via the goalie-games table's `team_abbrev` on (season, game_id, goalie_id) for away goalies. Use the goalie-games join for BOTH (single code path).

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_environment.py
import pandas as pd
import pytest

from v2.goalies.environment import arena_freeze_offsets, team_environment


def test_b2b_uses_game_date_not_id():
    games = pd.DataFrame({
        "season": [2021] * 3, "game_id": [500, 100, 300],  # ids out of order on purpose
        "goalie_id": [1, 1, 1], "difficulty_pct": [50.0] * 3,
        "xg_per60": [2.5] * 3, "hd_share": [0.2] * 3,
        "shots_faced": [30] * 3, "crossice_shots": [2] * 3, "toi_s": [3600] * 3,
    })
    gg = pd.DataFrame({
        "season": [2021] * 3, "game_id": [500, 100, 300], "goalie_id": [1] * 3,
        "team_abbrev": ["EDM"] * 3,
        "game_date": ["2021-11-03", "2021-11-01", "2021-11-02"],
    })
    shots = pd.DataFrame({
        "season": [2021] * 2, "game_id": [500, 100], "goalie_id": [1, 1],
        "shot_type": ["tip-in", "wrist"], "shooter_position": ["D", "F"],
        "on_net": [True, True], "is_goal": [False, False], "froze": [1.0, 0.0],
        "goalie_is_home": [True, True], "home_abbrev": ["EDM", "EDM"],
    })
    env = team_environment(games, gg, shots).iloc[0]
    # dates 11-01, 11-02, 11-03 are consecutive: two back-to-backs
    assert env["b2b_games"] == 2
    assert env["gp"] == 3 and env["tip_share"] == pytest.approx(0.5)
    assert env["d_shot_share"] == pytest.approx(0.5)


def test_arena_freeze_offsets_sign():
    # arena AAA freezes visiting goalies' saves at 0.6; their away baseline is 0.4
    rows = []
    for arena, n_frozen, n in (("AAA", 60, 100), ("BBB", 40, 100)):
        for i in range(n):
            rows.append({"home_abbrev": arena, "goalie_is_home": False,
                         "goalie_id": 7, "on_net": True, "is_goal": False,
                         "froze": 1.0 if i < n_frozen else 0.0})
    off = arena_freeze_offsets(pd.DataFrame(rows)).set_index("home_abbrev")
    assert off.loc["AAA", "freeze_offset"] == pytest.approx(0.1)
    assert off.loc["BBB", "freeze_offset"] == pytest.approx(-0.1)
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# v2/goalies/environment.py
"""Team environment profile: how hard does each team make its goalies' lives?

The 'o-line grade': per team-season workload difficulty served to own goalies,
plus schedule burden and the arena freeze-timing check (spec addendum 6b).

Usage: python3 v2/goalies/environment.py
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
TIP_TYPES = {"tip-in", "deflected"}


def team_environment(games: pd.DataFrame, goalie_games: pd.DataFrame,
                     shots: pd.DataFrame) -> pd.DataFrame:
    key = ["season", "game_id", "goalie_id"]
    g = games.merge(goalie_games[key + ["team_abbrev", "game_date"]], on=key)

    shot_team = shots.merge(goalie_games[key + ["team_abbrev"]], on=key)
    shot_agg = shot_team.groupby(["season", "team_abbrev"]).agg(
        tip_share=("shot_type", lambda s: s.isin(TIP_TYPES).mean()),
        d_shot_share=("shooter_position", lambda s: s.eq("D").mean()),
    ).reset_index()

    team_games = (g.sort_values("game_date")
                  .drop_duplicates(["season", "team_abbrev", "game_id"]))
    team_games["prev_date"] = team_games.groupby(["season", "team_abbrev"])["game_date"].shift()
    team_games["b2b"] = (pd.to_datetime(team_games["game_date"])
                         - pd.to_datetime(team_games["prev_date"])).dt.days == 1

    env = g.groupby(["season", "team_abbrev"]).agg(
        gp=("game_id", "size"),
        mean_difficulty_pct=("difficulty_pct", "mean"),
        mean_xg_faced_per60=("xg_per60", "mean"),
        hd_share=("hd_share", "mean"),
        crossice_per60=("crossice_shots", lambda s: float("nan")),  # replaced below
    ).reset_index()
    cross = g.groupby(["season", "team_abbrev"]).apply(
        lambda x: x["crossice_shots"].sum() * 3600 / x["toi_s"].sum(),
        include_groups=False).rename("crossice_per60").reset_index()
    env = env.drop(columns=["crossice_per60"]).merge(cross, on=["season", "team_abbrev"])
    b2b = team_games.groupby(["season", "team_abbrev"])["b2b"].sum().rename("b2b_games").reset_index()
    return env.merge(b2b, on=["season", "team_abbrev"]).merge(shot_agg, on=["season", "team_abbrev"])


def arena_freeze_offsets(shots: pd.DataFrame) -> pd.DataFrame:
    saves = shots[(shots["on_net"]) & (~shots["is_goal"]) & (~shots["goalie_is_home"])]
    per_goalie_arena = saves.groupby(["goalie_id", "home_abbrev"])["froze"].agg(["mean", "size"])
    overall = saves.groupby("goalie_id")["froze"].mean().rename("away_base")
    j = per_goalie_arena.reset_index().merge(overall, on="goalie_id")
    j["off"] = j["mean"] - j["away_base"]
    out = j.groupby("home_abbrev").apply(
        lambda x: pd.Series({"n_saves": x["size"].sum(),
                             "freeze_offset": (x["off"] * x["size"]).sum() / x["size"].sum()}),
        include_groups=False).reset_index()
    return out


def main() -> None:
    games = pd.read_csv(GEN / "game_difficulty.csv")
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS], ignore_index=True)
    shots = pd.concat([pd.read_csv(GEN / f"shots_{s}.csv") for s in SEASONS], ignore_index=True)
    env = team_environment(games, gg, shots)
    env.to_csv(GEN / "team_environment.csv", index=False)
    offs = arena_freeze_offsets(shots)
    offs.to_csv(GEN / "arena_freeze_offsets.csv", index=False)
    print(env.sort_values("mean_xg_faced_per60").tail(5).to_string(index=False))
    print(f"arena freeze offsets: max |offset| = {offs['freeze_offset'].abs().max():.3f}")


if __name__ == "__main__":
    main()
```

Implementation note: the `crossice_per60` placeholder-then-replace construction is clumsy — implementers may compute it directly in a single groupby-apply instead, as long as the output column set matches the interface. `include_groups=False` is required on pandas 3.x groupby.apply.

- [ ] **Step 4: Tests green, run the CLI.** Anchors: 32 teams × 5 seasons = 160 env rows; b2b_games per team-season ≈ 10–16; arena freeze offsets max |offset| expected ≤ ~0.05 (flag any arena beyond it in the task report — that's the P4 scorer-timing finding).

- [ ] **Step 5: Full suite, commit** — `git add v2/goalies/environment.py v2/goalies/tests/test_environment.py && git commit -m "feat(goalies): team environment profile and arena freeze offsets"`

---

### Task 7: P4+P5 report + suite

**Files:**
- Create: `v2/goalies/report_p4p5.py` (no test — report script over tested computations)

**Interfaces:** CLI writing `data/generated/goalies/p4p5_report.txt`: per-season goalie-game counts and TOI totals; game-difficulty distribution (median/p10/p90 xg_per60, hardest and easiest 5 games with goalie and date); correlation of difficulty_pct with GA (expect positive) and with perf_z (expect ≈ 0 — difficulty-adjustment working); hardest/easiest 5 team environments; arena freeze offsets over |0.03|; ledger calibration lines (mean perf_z, mean lev_value); new goal-layer `is_rebound` coefficient per season (post-Task-2).

- [ ] **Step 1: Write the report script** — straightforward pandas over the generated CSVs plus `structure_coefs_<season>.csv`; print and write. Follow the shape of `v2/goalies/verify_foundation.py`.
- [ ] **Step 2: Run it; check the two correlation anchors** (difficulty↔GA positive, difficulty↔perf_z ≈ 0 within ±0.05). If perf_z correlates with difficulty beyond that, the difficulty adjustment is leaking — STOP and report.
- [ ] **Step 3: Full suite** — `python3 -m pytest v2/ -q` all green.
- [ ] **Step 4: Commit** — `git add v2/goalies/report_p4p5.py && git commit -m "feat(goalies): P4+P5 report"`

---

## After this plan

Deliverables oiler reviews: `p4p5_report.txt`, `game_ledger.csv` (spot-check a few games he remembers), `team_environment.csv`. Then the P6 plan (portability harness: switch registry, candidate metrics = chained stopping terms, freeze terms, rebound terms, per-game difficulty-adjusted aggregates, all vs the GSAx baseline). The rebound-definition change (Task 2) regenerates the P3 gate report; its deltas are part of the review packet.
