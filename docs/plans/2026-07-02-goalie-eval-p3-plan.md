# Goalie Evaluation P3 (Difficulty Model + Goalie Terms) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fit the layered shot-difficulty models with per-goalie regularized terms (mini-Magnus), produce the GSAx baseline, and answer the P3 phase-gate question: do goalie terms separate from noise?

**Architecture:** Pure-numpy penalized IRLS (generalized ridge with per-coefficient penalties and prior centers) fit on the P0–P2 shot tables, one model per outcome layer (on-net, freeze, goal, rebound-generation), goalie identities as heavily-shrunk terms inside each model. A goalie-blind single-layer model provides the GSAx baseline. A gate-analysis script quantifies signal-vs-noise. Spec: `docs/plans/2026-06-11-goalie-evaluation-design.md` (§6 P3, §7 gate).

**Tech Stack:** Python 3.11 (system pyenv python3 — NOT `uv run`), pandas 3.0, numpy 2.4, pytest. NO scipy/sklearn/statsmodels — the solver is numpy-only by spec decision (differential penalties).

## Global Constraints

- Continue on branch `goalie-eval-p1` (P0–P2 commits already there, unmerged); local per-task commits authorized; NEVER push, never commit to master/main.
- No new dependencies. Raw data and P0–P2 generated CSVs are inputs; never mutated.
- `distance_adj` must be clamped to ≥ 0 wherever consumed (known floor of −0.099 from the tail-extension fix).
- Gate correlations (split-half, year-pair) MUST use independently-fit seasons (no chained priors) — chained priors mechanically inflate year-to-year correlation (the spec's own repeatability trap).
- Sign convention: raw layer terms are on the logit of the modeled outcome (positive `goal`-layer term = more goals allowed = bad goalie). Derived "skill" columns negate where needed so positive = good; both are stored.
- Tests: `python3 -m pytest v2/goalies/tests/ -v` per task; full `python3 -m pytest v2/ -q` before finishing.
- Shot tables: `data/generated/goalies/shots_<season>.csv` for seasons 2021–2025, columns as built in P0–P2 (note: `froze`/`rebound_generated` are nullable floats 1.0/0.0/NaN; `season` reloads as int64; `prev_*` fields are NaN when no same-period coordinate-bearing prior event exists).

---

### Task 1: Feature builder

**Files:**
- Create: `v2/goalies/features.py`
- Test: `v2/goalies/tests/test_features.py`

**Interfaces:**
- Consumes: shot-table DataFrames (P0–P2 schema above).
- Produces: `build_features(df: pd.DataFrame) -> pd.DataFrame` returning float64 columns in this exact order: `intercept, dist, log1p_dist, angle, snap, slap, backhand, tip_deflect, other_type, pp, sh, trail2, trail1, lead1, lead2, is_rebound, is_rush, is_crossice_quick, is_home`. Constant `STRUCTURE_COLS` (that list). Tasks 3 and 5 consume both.
- Definitions (binding): `dist` = `distance_adj` clamped to ≥ 0; `log1p_dist` = log1p(clamped); `angle` as-is. Shot-type base = wrist; `tip_deflect` = tip-in or deflected; `other_type` = wrap-around/bat/poke/between-legs/cradle. Strength base = EV (dummies from the goalie-team-perspective `strength` column: `pp` = "PP", `sh` = "SH"). Score base = tied: `trail2` = score_diff ≤ −2, `trail1` = −1, `lead1` = +1, `lead2` = ≥ +2 (goalie team's perspective, from `score_diff`). Flags (NaN prev fields → False): `is_rebound` = dt_prev ≤ 3 AND prev_same_team AND prev_type ∈ {goal, shot-on-goal, missed-shot, blocked-shot}; `is_rush` = dt_prev ≤ 4 AND prev_x_norm < 25 (prior event outside the attacking zone); `is_crossice_quick` = dt_prev ≤ 3 AND prev_same_team AND prev_y_norm × y_norm < 0 AND |prev_y_norm| ≥ 5. `is_home` = goalie_is_home.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_features.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.features import STRUCTURE_COLS, build_features


def _row(**over):
    base = {
        "distance_adj": 30.0, "angle": 20.0, "shot_type": "wrist",
        "strength": "EV", "score_diff": 0, "goalie_is_home": True,
        "dt_prev": np.nan, "prev_type": np.nan, "prev_same_team": np.nan,
        "prev_x_norm": np.nan, "prev_y_norm": np.nan, "y_norm": 10.0,
    }
    base.update(over)
    return base


def test_column_order_and_intercept():
    X = build_features(pd.DataFrame([_row()]))
    assert list(X.columns) == STRUCTURE_COLS
    assert X.iloc[0]["intercept"] == 1.0
    assert X.dtypes.unique().tolist() == [np.dtype("float64")]


def test_distance_clamped_and_logged():
    X = build_features(pd.DataFrame([_row(distance_adj=-0.099)]))
    assert X.iloc[0]["dist"] == 0.0
    assert X.iloc[0]["log1p_dist"] == 0.0


def test_shot_type_dummies():
    X = build_features(pd.DataFrame([
        _row(shot_type="wrist"), _row(shot_type="snap"), _row(shot_type="tip-in"),
        _row(shot_type="deflected"), _row(shot_type="poke"),
    ]))
    assert X["snap"].tolist() == [0, 1, 0, 0, 0]
    assert X["tip_deflect"].tolist() == [0, 0, 1, 1, 0]
    assert X["other_type"].tolist() == [0, 0, 0, 0, 1]


def test_strength_and_score_dummies():
    X = build_features(pd.DataFrame([
        _row(strength="PP", score_diff=-3), _row(strength="SH", score_diff=1),
    ]))
    assert X.iloc[0][["pp", "sh", "trail2", "lead1"]].tolist() == [1, 0, 1, 0]
    assert X.iloc[1][["pp", "sh", "trail2", "lead1"]].tolist() == [0, 1, 0, 1]


def test_rebound_rush_crossice_flags():
    X = build_features(pd.DataFrame([
        _row(dt_prev=2, prev_same_team=True, prev_type="shot-on-goal",
             prev_x_norm=80.0, prev_y_norm=-8.0, y_norm=10.0),   # rebound + crossice, not rush
        _row(dt_prev=3, prev_same_team=False, prev_type="giveaway",
             prev_x_norm=10.0, prev_y_norm=2.0),                  # rush only (x<25, dt<=4)
        _row(),                                                    # all NaN -> all False
    ]))
    assert X["is_rebound"].tolist() == [1, 0, 0]
    assert X["is_crossice_quick"].tolist() == [1, 0, 0]
    assert X["is_rush"].tolist() == [0, 1, 0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest v2/goalies/tests/test_features.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.goalies.features'`

- [ ] **Step 3: Write the implementation**

```python
# v2/goalies/features.py
"""Structure features for the layered difficulty models.

All columns float64; base categories: wrist shot, EV strength, tied score.
distance_adj is clamped to >= 0 (known -0.099 floor from quantile tail extension).
"""

import numpy as np
import pandas as pd

STRUCTURE_COLS = [
    "intercept", "dist", "log1p_dist", "angle",
    "snap", "slap", "backhand", "tip_deflect", "other_type",
    "pp", "sh", "trail2", "trail1", "lead1", "lead2",
    "is_rebound", "is_rush", "is_crossice_quick", "is_home",
]

CORSI_PREV = {"goal", "shot-on-goal", "missed-shot", "blocked-shot"}
OTHER_TYPES = {"wrap-around", "bat", "poke", "between-legs", "cradle"}


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    d = np.maximum(df["distance_adj"].to_numpy(dtype=float), 0.0)
    same = df["prev_same_team"].fillna(False).astype(bool).to_numpy()
    dt = df["dt_prev"].to_numpy(dtype=float)
    prev_x = df["prev_x_norm"].to_numpy(dtype=float)
    cross = df["prev_y_norm"].to_numpy(dtype=float) * df["y_norm"].to_numpy(dtype=float)
    prev_y_abs = np.abs(df["prev_y_norm"].to_numpy(dtype=float))
    prev_corsi = df["prev_type"].isin(CORSI_PREV).to_numpy()

    out = pd.DataFrame({
        "intercept": 1.0,
        "dist": d,
        "log1p_dist": np.log1p(d),
        "angle": df["angle"].to_numpy(dtype=float),
        "snap": df["shot_type"].eq("snap"),
        "slap": df["shot_type"].eq("slap"),
        "backhand": df["shot_type"].eq("backhand"),
        "tip_deflect": df["shot_type"].isin(["tip-in", "deflected"]),
        "other_type": df["shot_type"].isin(OTHER_TYPES),
        "pp": df["strength"].eq("PP"),
        "sh": df["strength"].eq("SH"),
        "trail2": df["score_diff"].le(-2),
        "trail1": df["score_diff"].eq(-1),
        "lead1": df["score_diff"].eq(1),
        "lead2": df["score_diff"].ge(2),
        "is_rebound": (dt <= 3) & same & prev_corsi,
        "is_rush": (dt <= 4) & (prev_x < 25),
        "is_crossice_quick": (dt <= 3) & same & (cross < 0) & (prev_y_abs >= 5),
        "is_home": df["goalie_is_home"].astype(bool),
    }, index=df.index)
    return out.astype("float64")[STRUCTURE_COLS]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest v2/goalies/tests/test_features.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/features.py v2/goalies/tests/test_features.py
git commit -m "feat(goalies): structure features for difficulty layers"
```

---

### Task 2: Penalized IRLS solver

**Files:**
- Create: `v2/goalies/irls.py`
- Test: `v2/goalies/tests/test_irls.py`

**Interfaces:**
- Consumes: nothing project-specific (pure numpy).
- Produces: `FitResult` dataclass with fields `coef: np.ndarray`, `se: np.ndarray`, `converged: bool`, `n_iter: int`, `objective: float`; function `fit_penalized_logistic(X: np.ndarray, y: np.ndarray, penalty: np.ndarray, prior_center: np.ndarray | None = None, max_iter: int = 50, tol: float = 1e-8) -> FitResult` minimizing `-loglik + 0.5 * sum(penalty_j * (beta_j - center_j)^2)`; helper `predict_proba(X, coef) -> np.ndarray`. Tasks 3 and 5 consume all three.
- Numerical requirements: linear predictor clipped to ±30 before sigmoid; Newton step with step-halving when the penalized objective worsens (max 10 halvings); `se` = sqrt(diag(inv(H))) at the optimum, H = X'WX + diag(penalty).

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_irls.py
import numpy as np
import pytest

from v2.goalies.irls import FitResult, fit_penalized_logistic, predict_proba


def _simulate(n=20000, beta=(0.4, -1.0, 0.25), seed=3):
    rng = np.random.default_rng(seed)
    X = np.column_stack([np.ones(n), rng.normal(0, 1, n), rng.normal(0, 1, n)])
    p = 1 / (1 + np.exp(-(X @ np.array(beta))))
    return X, (rng.uniform(size=n) < p).astype(float)


def test_recovers_known_coefficients_with_tiny_penalty():
    X, y = _simulate()
    fit = fit_penalized_logistic(X, y, penalty=np.full(3, 1e-6))
    assert fit.converged
    assert fit.coef == pytest.approx([0.4, -1.0, 0.25], abs=0.08)


def test_gradient_is_zero_at_optimum():
    X, y = _simulate(n=5000)
    pen = np.array([1e-6, 5.0, 50.0])
    fit = fit_penalized_logistic(X, y, penalty=pen)
    mu = predict_proba(X, fit.coef)
    grad = X.T @ (y - mu) - pen * fit.coef
    assert np.abs(grad).max() < 1e-4


def test_penalty_shrinks_toward_center():
    X, y = _simulate(n=5000)
    center = np.array([0.0, 0.5, 0.0])
    small = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 1.0, 1e-6]),
                                   prior_center=center)
    huge = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 1e9, 1e-6]),
                                  prior_center=center)
    assert huge.coef[1] == pytest.approx(0.5, abs=1e-3)          # pinned to center
    assert abs(small.coef[1] - 0.5) > abs(huge.coef[1] - 0.5)    # monotone pull


def test_separation_stays_finite():
    # a column perfectly predicting y would diverge unpenalized; penalty keeps it finite
    n = 1000
    X = np.column_stack([np.ones(n), np.repeat([0.0, 1.0], n // 2)])
    y = np.repeat([0.0, 1.0], n // 2)
    fit = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 2.0]))
    assert fit.converged and np.isfinite(fit.coef).all() and np.isfinite(fit.se).all()


def test_se_shrinks_with_penalty():
    X, y = _simulate(n=5000)
    loose = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 1e-6, 1e-6]))
    tight = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 100.0, 1e-6]))
    assert tight.se[1] < loose.se[1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest v2/goalies/tests/test_irls.py -v`
Expected: FAIL — `ModuleNotFoundError` (irls missing)

- [ ] **Step 3: Write the implementation**

```python
# v2/goalies/irls.py
"""Penalized logistic regression via Newton-IRLS, numpy only.

Generalized ridge: per-coefficient L2 penalties and prior centers, which
sklearn's uniform-penalty LogisticRegression cannot express (spec decision).
Objective: -loglik + 0.5 * sum(penalty_j * (beta_j - center_j)^2).
"""

from dataclasses import dataclass

import numpy as np

ETA_CLIP = 30.0


@dataclass
class FitResult:
    coef: np.ndarray
    se: np.ndarray
    converged: bool
    n_iter: int
    objective: float


def predict_proba(X: np.ndarray, coef: np.ndarray) -> np.ndarray:
    eta = np.clip(X @ coef, -ETA_CLIP, ETA_CLIP)
    return 1.0 / (1.0 + np.exp(-eta))


def _objective(X, y, beta, penalty, center) -> float:
    eta = np.clip(X @ beta, -ETA_CLIP, ETA_CLIP)
    loglik = float(y @ eta - np.logaddexp(0.0, eta).sum())
    return -loglik + 0.5 * float(penalty @ (beta - center) ** 2)


def fit_penalized_logistic(X, y, penalty, prior_center=None,
                           max_iter: int = 50, tol: float = 1e-8) -> FitResult:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    penalty = np.asarray(penalty, dtype=float)
    center = np.zeros(X.shape[1]) if prior_center is None else np.asarray(prior_center, dtype=float)

    beta = center.copy()
    obj = _objective(X, y, beta, penalty, center)
    converged = False
    it = 0
    H = np.eye(X.shape[1])
    for it in range(1, max_iter + 1):
        mu = predict_proba(X, beta)
        w = mu * (1.0 - mu)
        grad = X.T @ (y - mu) - penalty * (beta - center)
        H = X.T @ (X * w[:, None]) + np.diag(penalty)
        step = np.linalg.solve(H, grad)

        scale = 1.0
        for _ in range(10):  # step-halving keeps the objective monotone
            candidate = beta + scale * step
            cand_obj = _objective(X, y, candidate, penalty, center)
            if cand_obj <= obj + 1e-12:
                break
            scale *= 0.5
        beta = beta + scale * step
        new_obj = _objective(X, y, beta, penalty, center)
        if np.abs(scale * step).max() < tol or abs(obj - new_obj) < tol:
            obj = new_obj
            converged = True
            break
        obj = new_obj

    se = np.sqrt(np.diag(np.linalg.inv(H)))
    return FitResult(coef=beta, se=se, converged=converged, n_iter=it, objective=obj)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest v2/goalies/tests/test_irls.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/irls.py v2/goalies/tests/test_irls.py
git commit -m "feat(goalies): penalized IRLS solver with per-coef penalties and prior centers"
```

---

### Task 3: Layer models with goalie terms

**Files:**
- Create: `v2/goalies/difficulty.py`
- Test: `v2/goalies/tests/test_difficulty.py`

**Interfaces:**
- Consumes: `build_features`, `STRUCTURE_COLS` (Task 1); `fit_penalized_logistic`, `predict_proba` (Task 2).
- Produces:
  - `LAYERS: dict[str, dict]` — `{"onnet": {"y": "on_net", "subset": "all"}, "freeze": {"y": "froze", "subset": "saves"}, "goal": {"y": "is_goal", "subset": "onnet"}, "rebound": {"y": "rebound_generated", "subset": "saves"}}`.
  - `layer_frame(df, layer) -> pd.DataFrame` — applies the subset (`all` = every row; `onnet` = `on_net == True`; `saves` = on-net non-goals) and drops rows where the y column is NaN.
  - `fit_layer(df, layer, *, goalie_prior_shots: float = 1000.0, structure_penalty: float = 1.0, prior_centers: dict[int, float] | None = None, include_goalies: bool = True) -> LayerFit` where `LayerFit` is a dataclass with `goalie_terms: pd.DataFrame` (columns `goalie_id, term, se, n_shots`; empty when `include_goalies=False`), `structure: pd.Series` (indexed by STRUCTURE_COLS), `fit: FitResult`, `base_rate: float`.
  - Goalie penalty: `lambda_g = goalie_prior_shots * base_rate * (1 - base_rate)` (prior evidence worth N league-average shots); structure penalty = `structure_penalty` on all structure cols except `intercept` (1e-6). Goalie prior centers default 0.0, overridden per-goalie via `prior_centers`.
  - `predict_structure(df, layer_fit) -> np.ndarray` — probabilities from structure coefficients only (goalie-blind view of the same fit; used for percentile scoring in P5).
- Task 4 consumes `fit_layer`/`LAYERS`; Task 6 consumes `layer_frame` and `fit_layer`.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_difficulty.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.difficulty import LAYERS, LayerFit, fit_layer, layer_frame


def _synthetic_shots(n_per_goalie=3000, seed=11):
    """Two goalies, identical shot mix; goalie 2 allows goals at +0.8 logits."""
    rng = np.random.default_rng(seed)
    rows = []
    for gid, skill in ((900, 0.0), (901, 0.8)):
        dist = rng.uniform(5, 60, n_per_goalie)
        eta = 0.5 - 0.09 * dist + skill
        p = 1 / (1 + np.exp(-eta))
        goals = rng.uniform(size=n_per_goalie) < p
        for d, g in zip(dist, goals):
            rows.append({
                "goalie_id": gid, "is_goal": bool(g), "on_net": True,
                "froze": np.nan if g else float(rng.uniform() < 0.3),
                "rebound_generated": np.nan if g else 0.0,
                "distance_adj": d, "angle": 15.0, "shot_type": "wrist",
                "strength": "EV", "score_diff": 0, "goalie_is_home": True,
                "dt_prev": np.nan, "prev_type": np.nan, "prev_same_team": np.nan,
                "prev_x_norm": np.nan, "prev_y_norm": np.nan, "y_norm": 5.0,
            })
    return pd.DataFrame(rows)


def test_layer_frame_subsets():
    df = _synthetic_shots(200)
    assert len(layer_frame(df, "onnet")) == len(df)
    goal_frame = layer_frame(df, "goal")
    assert (goal_frame["on_net"] == True).all()  # noqa: E712
    saves = layer_frame(df, "freeze")
    assert not saves["is_goal"].any() and saves["froze"].notna().all()


def test_goalie_terms_recover_ordering_and_shrink():
    df = _synthetic_shots()
    fit = fit_layer(df, "goal", goalie_prior_shots=1000.0)
    terms = fit.goalie_terms.set_index("goalie_id")["term"]
    assert terms[901] > terms[900]              # worse goalie has higher goal term
    assert 0.05 < (terms[901] - terms[900]) < 0.8   # shrunken below true 0.8 gap
    assert fit.goalie_terms.set_index("goalie_id").loc[900, "n_shots"] == 3000


def test_blind_fit_has_no_goalie_terms():
    df = _synthetic_shots(500)
    fit = fit_layer(df, "goal", include_goalies=False)
    assert fit.goalie_terms.empty
    assert fit.structure["dist"] < 0            # farther = fewer goals


def test_prior_centers_pull_estimates():
    df = _synthetic_shots(300)
    anchored = fit_layer(df, "goal", goalie_prior_shots=100000.0,
                         prior_centers={900: -0.5, 901: -0.5})
    terms = anchored.goalie_terms.set_index("goalie_id")["term"]
    assert terms[900] == pytest.approx(-0.5, abs=0.05)
    assert terms[901] == pytest.approx(-0.5, abs=0.05)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest v2/goalies/tests/test_difficulty.py -v`
Expected: FAIL — `ModuleNotFoundError` (difficulty missing)

- [ ] **Step 3: Write the implementation**

```python
# v2/goalies/difficulty.py
"""Layered difficulty models with per-goalie regularized terms (mini-Magnus).

Each layer is a penalized logistic regression on structure features plus a
goalie one-hot block. Goalie terms are shrunk toward prior centers with
penalty worth `goalie_prior_shots` league-average shots of evidence.
Raw terms are on the logit of the modeled outcome: positive `goal` term =
more goals allowed (bad); downstream reporting negates where positive=good.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from v2.goalies.features import STRUCTURE_COLS, build_features
from v2.goalies.irls import FitResult, fit_penalized_logistic, predict_proba

LAYERS = {
    "onnet": {"y": "on_net", "subset": "all"},
    "freeze": {"y": "froze", "subset": "saves"},
    "goal": {"y": "is_goal", "subset": "onnet"},
    "rebound": {"y": "rebound_generated", "subset": "saves"},
}


@dataclass
class LayerFit:
    goalie_terms: pd.DataFrame
    structure: pd.Series
    fit: FitResult
    base_rate: float


def layer_frame(df: pd.DataFrame, layer: str) -> pd.DataFrame:
    subset = LAYERS[layer]["subset"]
    if subset == "onnet":
        df = df[df["on_net"]]
    elif subset == "saves":
        df = df[df["on_net"] & ~df["is_goal"]]
    return df[df[LAYERS[layer]["y"]].notna()]


def fit_layer(df: pd.DataFrame, layer: str, *, goalie_prior_shots: float = 1000.0,
              structure_penalty: float = 1.0,
              prior_centers: dict[int, float] | None = None,
              include_goalies: bool = True) -> LayerFit:
    frame = layer_frame(df, layer)
    y = frame[LAYERS[layer]["y"]].to_numpy(dtype=float)
    X_struct = build_features(frame).to_numpy()
    base_rate = float(y.mean())

    n_struct = len(STRUCTURE_COLS)
    pen_struct = np.full(n_struct, structure_penalty)
    pen_struct[STRUCTURE_COLS.index("intercept")] = 1e-6

    if include_goalies:
        goalies = np.sort(frame["goalie_id"].unique())
        gidx = {g: i for i, g in enumerate(goalies)}
        G = np.zeros((len(frame), len(goalies)))
        G[np.arange(len(frame)), frame["goalie_id"].map(gidx).to_numpy()] = 1.0
        X = np.hstack([X_struct, G])
        lam_g = goalie_prior_shots * base_rate * (1.0 - base_rate)
        penalty = np.concatenate([pen_struct, np.full(len(goalies), lam_g)])
        centers = np.zeros(X.shape[1])
        if prior_centers:
            for g, c in prior_centers.items():
                if g in gidx:
                    centers[n_struct + gidx[g]] = c
    else:
        goalies = np.array([], dtype=int)
        X = X_struct
        penalty = pen_struct
        centers = np.zeros(X.shape[1])

    fit = fit_penalized_logistic(X, y, penalty, prior_center=centers)

    if include_goalies:
        counts = frame["goalie_id"].value_counts()
        terms = pd.DataFrame({
            "goalie_id": goalies,
            "term": fit.coef[n_struct:],
            "se": fit.se[n_struct:],
            "n_shots": [int(counts[g]) for g in goalies],
        })
    else:
        terms = pd.DataFrame(columns=["goalie_id", "term", "se", "n_shots"])

    structure = pd.Series(fit.coef[:n_struct], index=STRUCTURE_COLS)
    return LayerFit(goalie_terms=terms, structure=structure, fit=fit, base_rate=base_rate)


def predict_structure(df: pd.DataFrame, layer_fit: LayerFit) -> np.ndarray:
    """Probabilities from structure coefficients only — the goalie-blind view."""
    return predict_proba(build_features(df).to_numpy(), layer_fit.structure.to_numpy())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest v2/goalies/tests/test_difficulty.py -v`
Expected: 4 PASS (the recovery test fits ~6000×21 IRLS — a few seconds)

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/difficulty.py v2/goalies/tests/test_difficulty.py
git commit -m "feat(goalies): layered difficulty models with shrunken goalie terms"
```

---

### Task 4: Season fitting CLI (chained + independent variants)

**Files:**
- Create: `v2/goalies/build_terms.py`
- Test: `v2/goalies/tests/test_build_terms.py`

**Interfaces:**
- Consumes: `fit_layer`, `LAYERS` (Task 3).
- Produces: CLI `python3 v2/goalies/build_terms.py` fitting seasons 2021→2025 in order, all four layers each, writing per season `data/generated/goalies/goalie_terms_<season>.csv` with columns `goalie_id, layer, term, se, n_shots, term_indep, se_indep` — `term` = chained fit (prior centers = previous season's chained terms for that layer), `term_indep` = independent fit (centers 0, no chaining; REQUIRED for gate correlations) — plus `structure_coefs_<season>.csv` (`layer, feature, coef`). Function `chain_seasons(season_dfs: dict[str, pd.DataFrame], layer: str, goalie_prior_shots: float = 1000.0) -> dict[str, pd.DataFrame]` returning per-season term frames with both variants (unit-testable core). Task 6 consumes the CSVs.

- [ ] **Step 1: Write the failing test**

```python
# v2/goalies/tests/test_build_terms.py
import numpy as np
import pandas as pd

from v2.goalies.build_terms import chain_seasons
from v2.goalies.tests.test_difficulty import _synthetic_shots


def test_chain_seasons_two_seasons_carry_priors():
    s1 = _synthetic_shots(1500, seed=1)
    s2 = _synthetic_shots(1500, seed=2)
    out = chain_seasons({"2021": s1, "2022": s2}, "goal")
    assert set(out) == {"2021", "2022"}
    t2 = out["2022"].set_index("goalie_id")
    assert {"term", "se", "n_shots", "term_indep", "se_indep"} <= set(t2.columns)
    # chained 2022 estimate for the bad goalie sits closer to his 2021 term
    # than the independent one does to zero-centered shrinkage alone
    t1 = out["2021"].set_index("goalie_id")
    assert abs(t2.loc[901, "term"] - t1.loc[901, "term"]) < abs(t2.loc[901, "term_indep"] - 0.0)
    # independent variant must not depend on season order (no chaining leakage)
    solo = chain_seasons({"2022": s2}, "goal")["2022"].set_index("goalie_id")
    assert np.isclose(solo.loc[901, "term_indep"], t2.loc[901, "term_indep"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest v2/goalies/tests/test_build_terms.py -v`
Expected: FAIL — `ModuleNotFoundError` (build_terms missing)

- [ ] **Step 3: Write the implementation**

```python
# v2/goalies/build_terms.py
"""Fit all difficulty layers per season; write chained + independent goalie terms.

Chained: each season's goalie priors center on the previous season's chained
terms (McCurdy-style information carry-over) — used for the eventual talent
estimates. Independent: zero-centered per-season fits — REQUIRED for the gate's
repeatability correlations, which chained priors would mechanically inflate.

Usage: python3 v2/goalies/build_terms.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from v2.goalies.difficulty import LAYERS, fit_layer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def chain_seasons(season_dfs: dict[str, pd.DataFrame], layer: str,
                  goalie_prior_shots: float = 1000.0) -> dict[str, pd.DataFrame]:
    out = {}
    prior = None
    for season in sorted(season_dfs):
        df = season_dfs[season]
        chained = fit_layer(df, layer, goalie_prior_shots=goalie_prior_shots,
                            prior_centers=prior)
        indep = fit_layer(df, layer, goalie_prior_shots=goalie_prior_shots)
        merged = chained.goalie_terms.merge(
            indep.goalie_terms[["goalie_id", "term", "se"]].rename(
                columns={"term": "term_indep", "se": "se_indep"}),
            on="goalie_id")
        out[season] = merged
        prior = dict(zip(merged["goalie_id"], merged["term"]))
    return out


def main() -> None:
    season_dfs = {s: pd.read_csv(GEN / f"shots_{s}.csv") for s in SEASONS}
    per_season_terms = {s: [] for s in SEASONS}
    structure_rows = {s: [] for s in SEASONS}

    for layer in LAYERS:
        chained = chain_seasons(season_dfs, layer)
        for season, terms in chained.items():
            per_season_terms[season].append(terms.assign(layer=layer))
        for season, df in season_dfs.items():
            fit = fit_layer(df, layer, include_goalies=False)
            structure_rows[season].extend(
                {"layer": layer, "feature": f, "coef": c}
                for f, c in fit.structure.items())

    for season in SEASONS:
        pd.concat(per_season_terms[season], ignore_index=True)[
            ["goalie_id", "layer", "term", "se", "n_shots", "term_indep", "se_indep"]
        ].to_csv(GEN / f"goalie_terms_{season}.csv", index=False)
        pd.DataFrame(structure_rows[season]).to_csv(
            GEN / f"structure_coefs_{season}.csv", index=False)
        print(f"{season}: terms + structure written")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test, then the full build**

Run: `python3 -m pytest v2/goalies/tests/test_build_terms.py -v` — PASS.

```bash
python3 v2/goalies/build_terms.py
```

Expected: five `goalie_terms_<season>.csv` + five `structure_coefs_<season>.csv`; runtime minutes-scale (4 layers × 5 seasons × 2 variants of ~60–113k×~120 IRLS, plus 4×5 blind fits). Sanity: in every season's goal layer, `structure` must show `dist < 0` (verify via a quick read of structure_coefs — farther shots score less) and, in seasons after 2021, sd of chained `term` should be **wider than or equal to** sd of `term_indep` among returning goalies — chaining centers priors on each goalie's own prior value instead of zero, so persistent skill accumulates rather than being shrunk away. (Original plan text stated the opposite direction; corrected during execution — implementer caught it.)

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/build_terms.py v2/goalies/tests/test_build_terms.py
git commit -m "feat(goalies): per-season layer fitting with chained and independent goalie terms"
```

---

### Task 5: GSAx baseline

**Files:**
- Create: `v2/goalies/gsax_baseline.py`
- Test: `v2/goalies/tests/test_gsax_baseline.py`

**Interfaces:**
- Consumes: `build_features` (Task 1), `fit_penalized_logistic`, `predict_proba` (Task 2).
- Produces: `gsax_table(df: pd.DataFrame) -> pd.DataFrame` — fits a goalie-BLIND single-layer goal model (`is_goal` on all unblocked shots, structure features only, structure_penalty 1.0/intercept 1e-6), then aggregates per goalie: columns `goalie_id, shots, xga, ga, gsax, gsax_per100` (`gsax = xga − ga`; `gsax_per100 = 100 * gsax / shots`). CLI `python3 v2/goalies/gsax_baseline.py` writes `data/generated/goalies/gsax_<season>.csv` for all five seasons. Task 6 consumes the CSVs. This is the vanilla-GSAx comparator mandated by the spec's validation design.

- [ ] **Step 1: Write the failing test**

```python
# v2/goalies/tests/test_gsax_baseline.py
import pytest

from v2.goalies.gsax_baseline import gsax_table
from v2.goalies.tests.test_difficulty import _synthetic_shots


def test_gsax_identifies_the_weaker_goalie():
    df = _synthetic_shots(3000)
    table = gsax_table(df).set_index("goalie_id")
    # goalie 901 allows +0.8 logits more than the blind model expects
    assert table.loc[901, "gsax"] < table.loc[900, "gsax"]
    assert table.loc[900, "shots"] == 3000
    # xGA sums to total expected goals: with symmetric goalies, total xga ~ total ga
    total = table["xga"].sum() / table["ga"].sum()
    assert total == pytest.approx(1.0, abs=0.05)
    assert table.loc[900, "gsax_per100"] == pytest.approx(
        100 * table.loc[900, "gsax"] / 3000)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest v2/goalies/tests/test_gsax_baseline.py -v`
Expected: FAIL — `ModuleNotFoundError` (gsax_baseline missing)

- [ ] **Step 3: Write the implementation**

```python
# v2/goalies/gsax_baseline.py
"""Vanilla GSAx baseline: goalie-blind xG minus goals against, per goalie-season.

The comparator the spec's validation design requires (portability and
repeatability must be judged against this, not against raw save%).

Usage: python3 v2/goalies/gsax_baseline.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from v2.goalies.features import STRUCTURE_COLS, build_features  # noqa: E402
from v2.goalies.irls import fit_penalized_logistic, predict_proba  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def gsax_table(df: pd.DataFrame) -> pd.DataFrame:
    X = build_features(df).to_numpy()
    y = df["is_goal"].to_numpy(dtype=float)
    penalty = np.full(len(STRUCTURE_COLS), 1.0)
    penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
    fit = fit_penalized_logistic(X, y, penalty)
    xg = predict_proba(X, fit.coef)
    agg = df.assign(xg=xg).groupby("goalie_id").agg(
        shots=("is_goal", "size"), xga=("xg", "sum"), ga=("is_goal", "sum"))
    agg["gsax"] = agg["xga"] - agg["ga"]
    agg["gsax_per100"] = 100 * agg["gsax"] / agg["shots"]
    return agg.reset_index()


def main() -> None:
    for season in SEASONS:
        df = pd.read_csv(GEN / f"shots_{season}.csv")
        table = gsax_table(df)
        table.to_csv(GEN / f"gsax_{season}.csv", index=False)
        print(f"{season}: gsax for {len(table)} goalies "
              f"(league xga {table['xga'].sum():.0f} vs ga {table['ga'].sum()})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test, then the CLI**

Run: `python3 -m pytest v2/goalies/tests/test_gsax_baseline.py -v` — PASS.

```bash
python3 v2/goalies/gsax_baseline.py
```

Expected: five `gsax_<season>.csv`; league xga within ~2% of league ga each season (a calibrated model's expected goals track actual league goals).

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/gsax_baseline.py v2/goalies/tests/test_gsax_baseline.py
git commit -m "feat(goalies): goalie-blind GSAx baseline tables"
```

---

### Task 6: Phase-gate analysis

**Files:**
- Create: `v2/goalies/gate_p3.py`
- Test: `v2/goalies/tests/test_gate_p3.py`

**Interfaces:**
- Consumes: `goalie_terms_<season>.csv` (Task 4), `gsax_<season>.csv` (Task 5), `shots_<season>.csv`, `fit_layer`/`layer_frame` (Task 3).
- Produces: CLI `python3 v2/goalies/gate_p3.py` writing `data/generated/goalies/gate_p3_report.txt`. Pure helpers (unit-tested): `signal_share(terms: pd.DataFrame) -> float` — `max(0, var(term_indep) − mean(se_indep²)) / var(term_indep)` (share of observed term variance not attributable to estimation noise); `year_pair_r(a: pd.DataFrame, b: pd.DataFrame, col: str, min_shots: int = 1000) -> tuple[float, int]` — Pearson r over goalies meeting `n_shots ≥ min_shots` (for gsax frames, `shots ≥ min_shots`) in both frames, plus pair count.
- Report contents (all from INDEPENDENT terms, per the global constraint):
  1. Per layer per season: n goalies, sd(term_indep), mean se_indep, signal_share.
  2. Year-pair repeatability per layer (4 season pairs, min 1000 shots both sides): r and n. Same for GSAx (`gsax_per100`).
  3. Split-half: for the goal and freeze layers, season 2023 (mid-window): split games by even/odd `game_id`, independent `fit_layer` on each half, Pearson r across goalies with ≥500 layer-shots in both halves.
  4. Sensitivity: goal-layer independent terms for 2023 refit at `goalie_prior_shots` ∈ {250, 1000, 4000}; Spearman rank correlation between each pair of settings.
  5. Verdict block (printed numbers, no auto-verdict): expected anchors from the spec — freeze repeatability ≈ 0.5+, GSAx-style stopping ≈ 0.12; the gate question is whether the goal-layer's signal_share and year-pair r beat the GSAx baseline's.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_gate_p3.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.gate_p3 import signal_share, year_pair_r


def test_signal_share_zero_when_noise_explains_all():
    terms = pd.DataFrame({"term_indep": [0.1, -0.1], "se_indep": [1.0, 1.0]})
    assert signal_share(terms) == 0.0


def test_signal_share_high_when_spread_exceeds_noise():
    rng = np.random.default_rng(5)
    terms = pd.DataFrame({"term_indep": rng.normal(0, 1.0, 200),
                          "se_indep": np.full(200, 0.1)})
    assert signal_share(terms) > 0.95


def test_year_pair_r_filters_and_correlates():
    a = pd.DataFrame({"goalie_id": [1, 2, 3, 4], "term_indep": [0.4, 0.2, -0.2, -0.4],
                      "n_shots": [2000, 2000, 2000, 500]})
    b = pd.DataFrame({"goalie_id": [1, 2, 3, 5], "term_indep": [0.3, 0.1, -0.3, 0.9],
                      "n_shots": [2000, 2000, 2000, 2000]})
    r, n = year_pair_r(a, b, "term_indep")
    assert n == 3                       # goalie 4 under min_shots, goalie 5 unmatched
    assert r == pytest.approx(1.0, abs=0.05)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest v2/goalies/tests/test_gate_p3.py -v`
Expected: FAIL — `ModuleNotFoundError` (gate_p3 missing)

- [ ] **Step 3: Write the implementation**

```python
# v2/goalies/gate_p3.py
"""P3 phase-gate analysis: do goalie terms separate from noise?

All correlations use INDEPENDENT per-season fits (term_indep) — chained
priors would mechanically inflate repeatability.

Usage: python3 v2/goalies/gate_p3.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from v2.goalies.difficulty import LAYERS, fit_layer, layer_frame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def signal_share(terms: pd.DataFrame) -> float:
    var_obs = float(terms["term_indep"].var(ddof=1))
    noise = float((terms["se_indep"] ** 2).mean())
    if var_obs <= 0:
        return 0.0
    return max(0.0, var_obs - noise) / var_obs


def year_pair_r(a: pd.DataFrame, b: pd.DataFrame, col: str,
                min_shots: int = 1000) -> tuple[float, int]:
    shot_col = "n_shots" if "n_shots" in a.columns else "shots"
    a = a[a[shot_col] >= min_shots]
    b = b[b[shot_col] >= min_shots]
    merged = a.merge(b, on="goalie_id", suffixes=("_a", "_b"))
    if len(merged) < 3:
        return float("nan"), len(merged)
    r = float(np.corrcoef(merged[f"{col}_a"], merged[f"{col}_b"])[0, 1])
    return r, len(merged)


def main() -> None:
    lines = []
    terms = {s: pd.read_csv(GEN / f"goalie_terms_{s}.csv") for s in SEASONS}
    gsax = {s: pd.read_csv(GEN / f"gsax_{s}.csv") for s in SEASONS}

    lines.append("=== 1. Signal share per layer-season (indep fits) ===")
    for layer in LAYERS:
        for s in SEASONS:
            t = terms[s][terms[s]["layer"] == layer]
            lines.append(f"{layer} {s}: n={len(t)} sd={t['term_indep'].std(ddof=1):.4f} "
                         f"mean_se={t['se_indep'].mean():.4f} signal_share={signal_share(t):.3f}")

    lines.append("\n=== 2. Year-pair repeatability (min 1000 shots both sides) ===")
    for layer in LAYERS:
        rs = []
        for s1, s2 in zip(SEASONS, SEASONS[1:]):
            a = terms[s1][terms[s1]["layer"] == layer]
            b = terms[s2][terms[s2]["layer"] == layer]
            r, n = year_pair_r(a, b, "term_indep")
            rs.append(f"{s1}->{s2}: r={r:.3f} (n={n})")
        lines.append(f"{layer}: " + "  ".join(rs))
    rs = []
    for s1, s2 in zip(SEASONS, SEASONS[1:]):
        r, n = year_pair_r(gsax[s1], gsax[s2], "gsax_per100")
        rs.append(f"{s1}->{s2}: r={r:.3f} (n={n})")
    lines.append("GSAx baseline: " + "  ".join(rs))

    lines.append("\n=== 3. Split-half (2023, even/odd game_id) ===")
    df23 = pd.read_csv(GEN / "shots_2023.csv")
    for layer in ("goal", "freeze"):
        halves = []
        for parity in (0, 1):
            half = df23[df23["game_id"] % 2 == parity]
            fit = fit_layer(half, layer)
            halves.append(fit.goalie_terms.rename(columns={"term": "term_indep",
                                                           "se": "se_indep"}))
        r, n = year_pair_r(halves[0], halves[1], "term_indep", min_shots=500)
        lines.append(f"{layer}: split-half r={r:.3f} (n={n})")

    lines.append("\n=== 4. Prior-strength sensitivity (goal layer, 2023) ===")
    fits = {ps: fit_layer(df23, "goal", goalie_prior_shots=ps).goalie_terms
            for ps in (250, 1000, 4000)}
    for a, b in ((250, 1000), (1000, 4000), (250, 4000)):
        merged = fits[a].merge(fits[b], on="goalie_id", suffixes=("_a", "_b"))
        rho = float(merged["term_a"].rank().corr(merged["term_b"].rank()))
        lines.append(f"prior {a} vs {b}: spearman={rho:.3f}")

    lines.append("\n=== 5. Gate anchors (spec) ===")
    lines.append("freeze year-pair expected ~0.5+; GSAx-style stopping ~0.12.")
    lines.append("Gate question: does goal-layer signal_share / year-pair r beat GSAx?")

    report = "\n".join(lines)
    print(report)
    (GEN / "gate_p3_report.txt").write_text(report + "\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests, then the gate analysis**

Run: `python3 -m pytest v2/goalies/tests/test_gate_p3.py -v` — 3 PASS.

```bash
python3 v2/goalies/gate_p3.py
```

Expected runtime: minutes (split-half refits + 3 sensitivity refits). Report written. Do NOT pre-judge the numbers — the gate verdict is oiler's.

- [ ] **Step 5: Run the FULL suite and commit**

Run: `python3 -m pytest v2/ -q`
Expected: all green.

```bash
git add v2/goalies/gate_p3.py v2/goalies/tests/test_gate_p3.py
git commit -m "feat(goalies): P3 phase-gate analysis (signal share, repeatability, sensitivity)"
```

---

## After this plan

`gate_p3_report.txt` goes to oiler with the P3 gate question: do goalie terms separate from noise, and does anything beat the GSAx baseline's repeatability? P4–P6 (environment profile, percentile scoring + leverage ledger, portability validation harness) get their plan only after that reading — the spec anticipates that a null here is a valid, publishable outcome that would reshape what P4–P6 should even measure.
