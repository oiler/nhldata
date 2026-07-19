# Goalie Freeze Value + Tandem Bound Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Price the freeze skill (post-save branch comparison: frozen vs in-play, next-30s opponent xG) and bound team effects on save outcomes via the tandem pairs — sub-project A of spec §6d.

**Architecture:** One new module `v2/goalies/freeze_value.py`: a per-save window-xGA builder (grouped cumsum + searchsorted), a closed-form linear ridge helper with sandwich SEs, the freeze-effect fits (primary + robustness), the tandem variance decomposition, and a CLI writing the report + the machine-readable `freeze_value.json` that sub-project B consumes. Spec: `docs/plans/2026-06-11-goalie-evaluation-design.md` §6d (governing).

**Tech Stack:** system python3 (pyenv 3.11, NOT `uv run`), pandas 3.0, numpy 2.4, pytest. No scipy/sklearn.

## Global Constraints

- Branch `goalie-eval-p1` (verify before committing; never push, never master). Local per-task commits authorized.
- No new dependencies. Raw data read-only. Generated files never committed (`data/` is gitignored). Outputs to `data/generated/goalies/validation/`.
- Tests: `python3 -m pytest v2/goalies/tests/ -v` per task; full `python3 -m pytest v2/ -q` before finishing. Suite currently **274 green**.
- Existing interfaces unchanged: `blind_shot_xg(df)` (gsax_baseline.py), `build_features/STRUCTURE_COLS` (features.py), `weighted_r` (portability.py).
- §6d method constants, fixed: primary window 30 s, robustness 15 s / 60 s; window truncates at period end (`time_s ≤ 1200`); strict inequality (`time_s > save's time_s`) so the save shot itself is excluded; window sums ALL recorded shot attempts' xg (the blind model prices blocked/missed too); saves subset = `on_net & ~is_goal & froze notna`.
- Ridge penalties mirror era_probe: structure 1.0, intercept 1e-6, `froze` 1e-6 (unpenalized measurement).
- Significance rule for the JSON handoff (pre-registered, §6d verbatim): `|coefficient| ≥ 2× its ridge SE in the 30s primary fit AND same sign in both robustness windows` → else `per_freeze_xga_delta: null`.
- Value conversion baseline: 1,550 saves/season for a starter; freeze-rate spread from the observed per-goalie p10–p90 (computed, not assumed).

---

### Task 1: Window-xGA builder + linear ridge helper

**Files:**
- Create: `v2/goalies/freeze_value.py`
- Test: `v2/goalies/tests/test_freeze_value.py`

**Interfaces:**
- Produces: `window_xga(shots: pd.DataFrame, saves: pd.DataFrame, window_s: int = 30) -> np.ndarray` — for each save row, the sum of `xg` over shots in the SAME `(game_id, goalie_is_home, period)` group with `time_s` strictly greater than the save's and ≤ `min(save_time + window_s, 1200)`. `shots` columns: `game_id, goalie_is_home, period, time_s, xg`; `saves` columns: `game_id, goalie_is_home, period, time_s`. Order of the returned array matches `saves` row order. `ridge_linear(X: np.ndarray, y: np.ndarray, penalty: np.ndarray) -> tuple[np.ndarray, np.ndarray]` — closed-form generalized-ridge (β = (XᵀX+Λ)⁻¹Xᵀy, Λ=diag(penalty)) returning (beta, se) with sandwich SEs: `se = sqrt(σ̂² · diag(A⁻¹ XᵀX A⁻¹))` where `A = XᵀX+Λ` and `σ̂² = RSS/(n−p)`. Tasks 2–3 consume both.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_freeze_value.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.freeze_value import ridge_linear, window_xga


def _shots():
    # one game, defending side True; times chosen to probe the window edges
    rows = [
        {"game_id": 1, "goalie_is_home": True,  "period": 1, "time_s": 100, "xg": 0.10},
        {"game_id": 1, "goalie_is_home": True,  "period": 1, "time_s": 120, "xg": 0.20},
        {"game_id": 1, "goalie_is_home": True,  "period": 1, "time_s": 131, "xg": 0.40},  # outside 30s of t=100
        {"game_id": 1, "goalie_is_home": False, "period": 1, "time_s": 110, "xg": 0.80},  # other side
        {"game_id": 1, "goalie_is_home": True,  "period": 2, "time_s": 105, "xg": 0.80},  # other period
        {"game_id": 1, "goalie_is_home": True,  "period": 3, "time_s": 1195, "xg": 0.05},
        {"game_id": 1, "goalie_is_home": True,  "period": 3, "time_s": 1199, "xg": 0.07},
    ]
    return pd.DataFrame(rows)


def test_window_xga_same_side_same_period_strict_and_bounded():
    saves = pd.DataFrame([
        {"game_id": 1, "goalie_is_home": True, "period": 1, "time_s": 100},
    ])
    out = window_xga(_shots(), saves, window_s=30)
    # includes t=120 (0.2); excludes the save's own t=100 (strict), t=131 (> t+30),
    # the away-side shot, and the period-2 shot
    assert out[0] == pytest.approx(0.20)


def test_window_xga_truncates_at_period_end():
    saves = pd.DataFrame([
        {"game_id": 1, "goalie_is_home": True, "period": 3, "time_s": 1190},
    ])
    out = window_xga(_shots(), saves, window_s=30)
    # window is (1190, 1200]: includes 1195 and 1199 only
    assert out[0] == pytest.approx(0.12)


def test_window_xga_row_order_preserved():
    saves = pd.DataFrame([
        {"game_id": 1, "goalie_is_home": True, "period": 3, "time_s": 1190},
        {"game_id": 1, "goalie_is_home": True, "period": 1, "time_s": 100},
    ])
    out = window_xga(_shots(), saves, window_s=30)
    assert out[0] == pytest.approx(0.12) and out[1] == pytest.approx(0.20)


def test_ridge_linear_matches_ols_at_tiny_penalty():
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(200), rng.normal(size=200)])
    beta_true = np.array([0.5, -1.2])
    y = X @ beta_true + rng.normal(scale=0.1, size=200)
    beta, se = ridge_linear(X, y, np.full(2, 1e-9))
    ols = np.linalg.lstsq(X, y, rcond=None)[0]
    assert beta == pytest.approx(ols, abs=1e-6)
    assert se[1] == pytest.approx(0.1 / np.sqrt(((X[:, 1] - 0) ** 2).sum()), rel=0.2)


def test_ridge_linear_penalty_shrinks():
    rng = np.random.default_rng(1)
    X = np.column_stack([np.ones(50), rng.normal(size=50)])
    y = X[:, 1] * 2.0 + rng.normal(scale=0.1, size=50)
    b_small, _ = ridge_linear(X, y, np.array([1e-9, 1e-9]))
    b_big, _ = ridge_linear(X, y, np.array([1e-9, 1e6]))
    assert abs(b_big[1]) < abs(b_small[1]) and abs(b_big[1]) < 0.01
```

- [ ] **Step 2: Run to verify failure** — `python3 -m pytest v2/goalies/tests/test_freeze_value.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# v2/goalies/freeze_value.py
"""Freeze value-pathway study + tandem team-effect bound (spec 6d, sub-project A).

Prices the post-save branch: frozen (stoppage -> faceoff -> play) vs in-play,
as opponent xG in the next 30 game-clock seconds, truncated at period end.
Estimator: closed-form generalized-ridge linear regression, froze effectively
unpenalized. Either sign is a finding.

Usage: python3 v2/goalies/freeze_value.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.features import STRUCTURE_COLS, build_features  # noqa: E402
from v2.goalies.gsax_baseline import blind_shot_xg  # noqa: E402
from v2.goalies.portability import weighted_r  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
PERIOD_END_S = 1200
WINDOWS = (30, 15, 60)          # primary first, then robustness
SAVES_PER_SEASON = 1550


def window_xga(shots: pd.DataFrame, saves: pd.DataFrame, window_s: int = 30) -> np.ndarray:
    key = ["game_id", "goalie_is_home", "period"]
    s = shots.sort_values(key + ["time_s"], kind="stable")
    groups = {}
    for k, grp in s.groupby(key, sort=False):
        t = grp["time_s"].to_numpy(dtype=float)
        cs = np.concatenate([[0.0], np.cumsum(grp["xg"].to_numpy(dtype=float))])
        groups[k] = (t, cs)
    out = np.zeros(len(saves))
    for i, row in enumerate(saves[key + ["time_s"]].itertuples(index=False)):
        k = (row.game_id, row.goalie_is_home, row.period)
        if k not in groups:
            continue
        t, cs = groups[k]
        t0 = float(row.time_s)
        lo = np.searchsorted(t, t0, side="right")
        hi = np.searchsorted(t, min(t0 + window_s, PERIOD_END_S), side="right")
        out[i] = cs[hi] - cs[lo]
    return out


def ridge_linear(X: np.ndarray, y: np.ndarray, penalty: np.ndarray):
    A = X.T @ X + np.diag(penalty)
    A_inv = np.linalg.inv(A)
    beta = A_inv @ X.T @ y
    resid = y - X @ beta
    dof = max(len(y) - X.shape[1], 1)
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * (A_inv @ (X.T @ X) @ A_inv)
    return beta, np.sqrt(np.diag(cov))
```

- [ ] **Step 4: Tests green** — `python3 -m pytest v2/goalies/tests/test_freeze_value.py -v`; full suite green.

- [ ] **Step 5: Commit** — `git add v2/goalies/freeze_value.py v2/goalies/tests/test_freeze_value.py && git commit -m "feat(goalies): window-xGA builder and linear ridge for freeze value study"`

---

### Task 2: Freeze-effect fits (primary, within-goalie, era split) + value conversion

**Files:**
- Modify: `v2/goalies/freeze_value.py` (append)
- Modify: `v2/goalies/tests/test_freeze_value.py` (append)

**Interfaces:**
- Consumes: `window_xga`, `ridge_linear`, `build_features/STRUCTURE_COLS` (froze appended last, era_probe pattern).
- Produces: `freeze_effect(saves: pd.DataFrame, y: np.ndarray, demean_by_goalie: bool = False) -> dict` — keys `coef, se, n` for the froze column; `saves` must carry all build_features inputs plus `froze` (float 0/1) and `goalie_id`. When `demean_by_goalie`, y and froze are demeaned within goalie before the fit (structure features enter raw). `season_value(delta: float, rate_lo: float, rate_hi: float, saves_per_season: int = SAVES_PER_SEASON) -> dict` — keys `goals_low, goals_high`: `delta × saves_per_season × rate` at each end of the freeze-rate spread (sign preserved; negative delta ⇒ negative "goals allowed added", i.e. suppression value). Task 3 consumes both.

- [ ] **Step 1: Append the failing tests**

```python
# append to v2/goalies/tests/test_freeze_value.py
from v2.goalies.freeze_value import freeze_effect, season_value


def _saves_frame(n, froze_effect, goalie_bias=0.0, seed=5):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        gid = i % 4
        froze = float(rng.random() < 0.3 + (0.2 if goalie_bias and gid < 2 else 0.0))
        rows.append({
            "goalie_id": gid, "froze": froze,
            "distance_adj": 30.0, "angle": 20.0, "shot_type": "wrist",
            "strength": "ev", "score_diff": 0, "goalie_is_home": True,
            "dt_prev": np.nan, "prev_type": np.nan, "prev_same_team": np.nan,
            "prev_x_norm": np.nan, "prev_y_norm": np.nan, "y_norm": 0.0,
            "x_norm": 60.0, "period": 1, "time_s": 300,
            "on_net": True, "is_goal": False,
        })
    df = pd.DataFrame(rows)
    y = (0.02 + froze_effect * df["froze"].to_numpy()
         + (goalie_bias * (df["goalie_id"] < 2).to_numpy())
         + rng.normal(scale=0.005, size=n))
    return df, y


def test_freeze_effect_recovers_injected_delta():
    df, y = _saves_frame(8000, froze_effect=-0.010)
    r = freeze_effect(df, y)
    assert r["coef"] == pytest.approx(-0.010, abs=0.002)
    assert abs(r["coef"]) > 2 * r["se"]


def test_freeze_effect_within_goalie_removes_goalie_confound():
    # goalies 0-1 both freeze more AND face higher baseline xGA (no true effect)
    df, y = _saves_frame(8000, froze_effect=0.0, goalie_bias=0.02)
    raw = freeze_effect(df, y)
    demeaned = freeze_effect(df, y, demean_by_goalie=True)
    assert abs(demeaned["coef"]) < abs(raw["coef"])
    assert abs(demeaned["coef"]) < 2 * demeaned["se"]


def test_season_value_scales_by_rate_spread():
    v = season_value(-0.001, rate_lo=0.27, rate_hi=0.35, saves_per_season=1000)
    assert v["goals_low"] == pytest.approx(-0.27)
    assert v["goals_high"] == pytest.approx(-0.35)
```

- [ ] **Step 2: Run to verify failure** — `ImportError` on the new names.

- [ ] **Step 3: Append the implementation**

```python
# append to v2/goalies/freeze_value.py

def freeze_effect(saves: pd.DataFrame, y: np.ndarray,
                  demean_by_goalie: bool = False) -> dict:
    froze = saves["froze"].to_numpy(dtype=float)
    yy = np.asarray(y, dtype=float)
    if demean_by_goalie:
        g = saves["goalie_id"].to_numpy()
        d = pd.DataFrame({"g": g, "y": yy, "f": froze})
        yy = (d["y"] - d.groupby("g")["y"].transform("mean")).to_numpy()
        froze = (d["f"] - d.groupby("g")["f"].transform("mean")).to_numpy()
    X = np.hstack([build_features(saves).to_numpy(), froze[:, None]])
    penalty = np.full(X.shape[1], 1.0)
    penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
    penalty[-1] = 1e-6
    beta, se = ridge_linear(X, yy, penalty)
    return {"coef": float(beta[-1]), "se": float(se[-1]), "n": len(yy)}


def season_value(delta: float, rate_lo: float, rate_hi: float,
                 saves_per_season: int = SAVES_PER_SEASON) -> dict:
    return {"goals_low": delta * saves_per_season * rate_lo,
            "goals_high": delta * saves_per_season * rate_hi}
```

- [ ] **Step 4: Tests green, full suite green.**

- [ ] **Step 5: Commit** — `git add v2/goalies/freeze_value.py v2/goalies/tests/test_freeze_value.py && git commit -m "feat(goalies): freeze-effect estimator with within-goalie robustness and value conversion"`

---

### Task 3: Tandem bound + CLI + report + JSON handoff

**Files:**
- Modify: `v2/goalies/freeze_value.py` (append)
- Modify: `v2/goalies/tests/test_freeze_value.py` (append)

**Interfaces:**
- Produces: `tandem_bound(rates: pd.DataFrame) -> dict` — input one row per tandem-pair goalie: `season, team, goalie_id, gsax_rate, n` (exactly 2 rows per (season, team)); output keys `partner_r` (weighted r of hi/lo partners' rates, weight = min(pair n)), `between_share` (weighted between-team share of total variance of gsax_rate), `sd_rate` (weighted sd), `bound_sv_pts` (= `between_share × sd_rate`, the implied team component in per-shot sv% points), `n_pairs`. CLI `python3 v2/goalies/freeze_value.py` runs everything and writes `validation/freeze_value_report.txt` + `validation/freeze_value.json` (`{"per_freeze_xga_delta": float|null, "window_s": 30, "significant": bool}` per the §6d rule). Sub-project B consumes the JSON.
- Note on the deliberate small duplication: `repeatability.tandem_table` returns gaps, not partner rates — this module needs both partners' rates and workloads for the correlation/ICC, so it selects pairs itself with the same rules (top-2 by fenwick, both ≥ 600). Keep the selection identical; do not refactor repeatability.py.

- [ ] **Step 1: Append the failing tests**

```python
# append to v2/goalies/tests/test_freeze_value.py
from v2.goalies.freeze_value import tandem_bound


def test_tandem_bound_team_driven_vs_independent():
    # Partners are labeled starter/backup by WORKLOAD (n), which is exogenous to
    # gsax_rate — labeling by the outcome (hi/lo rate) would inject the
    # order-statistic floor corr(max, min) = 1/(pi-1) ~ 0.467 under independence
    # (plan defect caught at execution 2026-07-19; method corrected).
    rng = np.random.default_rng(7)
    rows_team, rows_indep = [], []
    for i in range(200):
        team_eff = rng.normal(scale=0.01)
        for j, g in enumerate((i * 2, i * 2 + 1)):
            base = {"season": 2023, "team": f"T{i}", "goalie_id": g,
                    "n": 1400 if j == 0 else 900}
            rows_team.append({**base, "gsax_rate": team_eff + rng.normal(scale=0.002)})
            rows_indep.append({**base, "gsax_rate": rng.normal(scale=0.01)})
    driven = tandem_bound(pd.DataFrame(rows_team))
    indep = tandem_bound(pd.DataFrame(rows_indep))
    assert driven["partner_r"] > 0.6 and abs(indep["partner_r"]) < 0.2
    assert driven["between_share"] > indep["between_share"]
    assert driven["n_pairs"] == 200
```

- [ ] **Step 2: Run to verify failure** — `ImportError`.

- [ ] **Step 3: Append the implementation**

```python
# append to v2/goalies/freeze_value.py

def tandem_bound(rates: pd.DataFrame) -> dict:
    pairs = []
    for (_, _), grp in rates.groupby(["season", "team"]):
        if len(grp) != 2:
            continue
        # label by workload (exogenous), never by the outcome: sorting hi/lo on
        # gsax_rate would put corr(max, min) ~ 0.467 under full independence
        starter, backup = grp.sort_values(
            ["n", "goalie_id"], ascending=[False, True]).itertuples(index=False)
        pairs.append({"starter": starter.gsax_rate, "backup": backup.gsax_rate,
                      "w": min(starter.n, backup.n)})
    p = pd.DataFrame(pairs)
    partner_r = weighted_r(p["starter"], p["backup"], p["w"])
    w = rates["n"].to_numpy(dtype=float)
    x = rates["gsax_rate"].to_numpy(dtype=float)
    mu = np.average(x, weights=w)
    total_var = np.average((x - mu) ** 2, weights=w)
    team_means = rates.groupby(["season", "team"]).apply(
        lambda g: pd.Series({"m": np.average(g["gsax_rate"], weights=g["n"]),
                             "w": g["n"].sum()}), include_groups=False)
    between_var = np.average((team_means["m"] - mu) ** 2, weights=team_means["w"])
    # subtract the sampling contribution a finite pair adds to between-var? No:
    # report the RAW between share as an upper bound (spec: bound, not estimate)
    between_share = float(between_var / total_var) if total_var > 0 else float("nan")
    sd_rate = float(np.sqrt(total_var))
    return {"partner_r": float(partner_r), "between_share": between_share,
            "sd_rate": sd_rate, "bound_sv_pts": between_share * sd_rate,
            "n_pairs": len(p)}


def _load_saves_and_shots():
    frames = []
    for season in SEASONS:
        shots = pd.read_csv(GEN / f"shots_{season}.csv")
        shots["xg"] = blind_shot_xg(shots)
        frames.append(shots)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    VAL.mkdir(parents=True, exist_ok=True)
    shots = _load_saves_and_shots()
    saves = shots[shots["on_net"] & ~shots["is_goal"] & shots["froze"].notna()].copy()
    lines = []

    fits = {}
    for w in WINDOWS:
        y = window_xga(shots, saves, window_s=w)
        fits[w] = freeze_effect(saves, y)
        raw_gap = float(np.mean(y[saves["froze"] == 1]) - np.mean(y[saves["froze"] == 0]))
        lines.append(f"window {w:>2}s: coef={fits[w]['coef']:+.5f} se={fits[w]['se']:.5f} "
                     f"n={fits[w]['n']} raw_frozen_minus_inplay={raw_gap:+.5f}")

    y30 = window_xga(shots, saves, window_s=30)
    wg = freeze_effect(saves, y30, demean_by_goalie=True)
    lines.append(f"within-goalie 30s: coef={wg['coef']:+.5f} se={wg['se']:.5f}")
    for label, seasons in (("eraA", (2021, 2022)), ("eraB", (2023, 2024, 2025))):
        m = saves["season"].isin(seasons).to_numpy()
        e = freeze_effect(saves[m], y30[m])
        lines.append(f"{label} 30s: coef={e['coef']:+.5f} se={e['se']:.5f} n={e['n']}")

    primary = fits[30]
    significant = (abs(primary["coef"]) >= 2 * primary["se"]
                   and np.sign(fits[15]["coef"]) == np.sign(primary["coef"])
                   and np.sign(fits[60]["coef"]) == np.sign(primary["coef"]))
    per_goalie_rate = saves.groupby("goalie_id")["froze"].agg(["mean", "size"])
    big = per_goalie_rate[per_goalie_rate["size"] >= 500]["mean"]
    val = season_value(primary["coef"], float(big.quantile(0.1)), float(big.quantile(0.9)))
    lines.append(f"significant per 6d rule: {significant}")
    lines.append(f"freeze-rate spread (>=500 saves): p10={big.quantile(0.1):.3f} "
                 f"p90={big.quantile(0.9):.3f}")
    lines.append(f"season value at spread ends: {val['goals_low']:+.2f} to "
                 f"{val['goals_high']:+.2f} goals/season (negative = suppression)")

    fen = shots[shots["event"] != "blocked-shot"]
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    team_of = gg.groupby(["season", "goalie_id"])["team_abbrev"].agg(
        lambda s: s.mode().iloc[0]).rename("team").reset_index()
    per = fen.groupby(["season", "goalie_id"]).agg(
        n=("xg", "size"), xga=("xg", "sum"), ga=("is_goal", "sum")).reset_index()
    per["gsax_rate"] = (per["xga"] - per["ga"]) / per["n"]
    per = per.merge(team_of, on=["season", "goalie_id"])
    pairs = (per[per["n"] >= 600].sort_values("n", ascending=False)
             .groupby(["season", "team"]).head(2))
    counts = pairs.groupby(["season", "team"]).size()
    pairs = pairs.set_index(["season", "team"]).loc[counts[counts == 2].index].reset_index()
    tb = tandem_bound(pairs[["season", "team", "goalie_id", "gsax_rate", "n"]])
    lines.append(f"\ntandem bound: partner_r={tb['partner_r']:+.3f} "
                 f"between_share={tb['between_share']:.3f} sd_rate={tb['sd_rate']:.4f} "
                 f"bound={tb['bound_sv_pts']:.4f} sv-pts/shot over {tb['n_pairs']} pairs "
                 f"(JLikens anchor ~0.006)")

    report = "\n".join(lines)
    (VAL / "freeze_value_report.txt").write_text(report + "\n")
    (VAL / "freeze_value.json").write_text(json.dumps({
        "per_freeze_xga_delta": primary["coef"] if significant else None,
        "window_s": 30, "significant": bool(significant)}, indent=2))
    print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests green, run the CLI.** Runtime: 5 xg fits (~1 min) + three window passes over ~490k saves (grouped-cumsum path — if a pass exceeds ~2 min something is quadratic; stop and check). Anchors (report, don't force): mean 30s window xGA ≈ 0.020–0.030 (league ~2.8 xG/60 ≈ 0.023/30s); the RAW frozen-minus-inplay gap is expected NEGATIVE (freezing kills rebounds) and larger in magnitude than the adjusted coefficient (controls absorb the shot-danger confound); the within-goalie coefficient should agree in sign with the primary if the effect is real. Either significance outcome is a valid finding — do NOT tune anything to reach significance. Report the era-split difference plainly.

- [ ] **Step 5: Full suite, commit** — `git add v2/goalies/freeze_value.py v2/goalies/tests/test_freeze_value.py && git commit -m "feat(goalies): freeze value study CLI, tandem bound, report + JSON handoff"`

---

## After this plan

Deliverables oiler reviews: `validation/freeze_value_report.txt` (freeze pricing + tandem bound) and `freeze_value.json` (B's input). Execution continues directly into `docs/plans/2026-07-19-goalie-browser-plan.md` (sub-project B) per the approved back-to-back decision — B's Task 1 consumes the JSON whether or not it carries a value.
