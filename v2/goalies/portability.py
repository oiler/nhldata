"""P6 portability harness: pre-switch estimates for candidates and baselines.

Per spec 6c: pre window = all shots before switch_date (matched horizon for
candidates and baseline alike); post window = the new stint only. Candidate
orientation is fixed so higher = better goalie. Mid-season cases refit the
switch season's layers with the goalie's post shots excluded (leakage rule).

Usage (Task 5 adds the CLI): python3 v2/goalies/portability.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.difficulty import fit_layer  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
CAND_LAYERS = ("goal", "freeze", "rebound")
ORIENT = {"goal": -1.0, "freeze": 1.0, "rebound": -1.0}
CAND_NAME = {"goal": "stopping", "freeze": "freeze", "rebound": "rebound_control"}


def case_outcome(case: dict, shots_xg: pd.DataFrame, gg: pd.DataFrame):
    post_games = gg[(gg["goalie_id"] == case["goalie_id"])
                    & (gg["game_date"] >= case["switch_date"])
                    & (gg["team_abbrev"] == case["post_team"])]
    keys = set(zip(post_games["season"], post_games["game_id"]))
    s = shots_xg[(shots_xg["goalie_id"] == case["goalie_id"])
                 & shots_xg["fenwick_flag"]]
    s = s[[k in keys for k in zip(s["season"], s["game_id"])]]
    if len(s) == 0:
        return None
    return {"n_post": len(s),
            "outcome": float((s["xg"].sum() - s["is_goal"].sum()) / len(s))}


def pre_gsax(case: dict, shots_xg: pd.DataFrame) -> dict:
    s = shots_xg[(shots_xg["goalie_id"] == case["goalie_id"])
                 & shots_xg["fenwick_flag"]
                 & (shots_xg["game_date"] < case["switch_date"])]
    last = s[s["season"] == case["last_pre_season"]]
    naive = (float((last["xg"].sum() - last["is_goal"].sum()) / len(last))
             if len(last) else np.nan)
    return {"n_pre": len(s),
            "gsax_sum": float(s["xg"].sum() - s["is_goal"].sum()),
            "naive_rate": naive}


def eb_rate(gsax_sum: float, n: int, k: float) -> float:
    return gsax_sum / (n + k)


def term_lookup(case: dict, terms: dict[int, pd.DataFrame],
                normalize: set[str]) -> dict:
    season_frame = terms.get(case["last_pre_season"])
    out = {}
    for layer in CAND_LAYERS:
        name = CAND_NAME[layer]
        if season_frame is None:
            out[name] = np.nan
            continue
        lf = season_frame[season_frame["layer"] == layer]
        if layer in normalize and len(lf) > 1:
            sd = float(lf["term"].std(ddof=0))
            lf = lf.assign(term=(lf["term"] - lf["term"].mean()) / (sd or 1.0))
        row = lf[lf["goalie_id"] == case["goalie_id"]]
        out[name] = (float(ORIENT[layer] * row["term"].iloc[0])
                     if len(row) else np.nan)
    return out


def midseason_refit(season_shots: pd.DataFrame, goalie_id: int, switch_date: str,
                    prior_terms: dict[str, dict[int, float]]) -> dict[str, float]:
    drop = ((season_shots["goalie_id"] == goalie_id)
            & (season_shots["game_date"] >= switch_date))
    clean = season_shots[~drop]
    out = {}
    for layer in CAND_LAYERS:
        fit = fit_layer(clean, layer, prior_centers=prior_terms.get(layer))
        row = fit.goalie_terms[fit.goalie_terms["goalie_id"] == goalie_id]
        out[layer] = float(row["term"].iloc[0]) if len(row) else 0.0
    return out


def pre_perf(case: dict, ledger_dated: pd.DataFrame) -> float:
    mine = ledger_dated[(ledger_dated["goalie_id"] == case["goalie_id"])
                        & (ledger_dated["game_date"] < case["switch_date"])]
    vals = mine["perf_z"].dropna()
    return float(vals.mean()) if len(vals) else np.nan


def _clean(x, y, w):
    x, y, w = np.asarray(x, float), np.asarray(y, float), np.asarray(w, float)
    m = ~(np.isnan(x) | np.isnan(y)) & (w > 0)
    return x[m], y[m], w[m]


def weighted_r(x, y, w) -> float:
    x, y, w = _clean(x, y, w)
    if len(x) < 3:
        return float("nan")
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    vx = np.average((x - mx) ** 2, weights=w)
    vy = np.average((y - my) ** 2, weights=w)
    return float(cov / np.sqrt(vx * vy)) if vx > 0 and vy > 0 else float("nan")


def _ranks(a):
    order = np.argsort(a)
    ranks = np.empty(len(a))
    ranks[order] = np.arange(len(a), dtype=float)
    for v in np.unique(a):                      # average ties
        m = a == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    return ranks


def weighted_spearman(x, y, w) -> float:
    x, y, w = _clean(x, y, w)
    if len(x) < 3:
        return float("nan")
    return weighted_r(_ranks(x), _ranks(y), w)


def paired_bootstrap_dr(cand, base, y, w, n_boot: int = 10000, seed: int = 42) -> dict:
    cand, base, y, w = (np.asarray(a, float) for a in (cand, base, y, w))
    keep = ~(np.isnan(cand) | np.isnan(base) | np.isnan(y)) & (w > 0)
    cand, base, y, w = cand[keep], base[keep], y[keep], w[keep]
    point = weighted_r(cand, y, w) - weighted_r(base, y, w)
    rng = np.random.default_rng(seed)
    n = len(y)
    drs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        drs[b] = (weighted_r(cand[idx], y[idx], w[idx])
                  - weighted_r(base[idx], y[idx], w[idx]))
    drs = drs[~np.isnan(drs)]
    return {"dr": float(point), "lo90": float(np.percentile(drs, 5)),
            "hi90": float(np.percentile(drs, 95)), "n_cases": int(n)}


def _standardize(a, w):
    m = np.average(a, weights=w)
    s = np.sqrt(np.average((a - m) ** 2, weights=w))
    return (a - m) / (s or 1.0)


def incremental_beta(cand, base, y, w) -> float:
    cand, base, y, w = (np.asarray(a, float) for a in (cand, base, y, w))
    keep = ~(np.isnan(cand) | np.isnan(base) | np.isnan(y)) & (w > 0)
    cand, base, y, w = cand[keep], base[keep], y[keep], w[keep]
    X = np.column_stack([np.ones(len(y)), _standardize(base, w),
                         _standardize(cand, w)])
    W = np.diag(w)
    beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ y)
    return float(beta[2])


def fit_k(pseudo: pd.DataFrame, grid=(250, 500, 1000, 2000, 4000)) -> int:
    best_k, best_r = grid[0], -np.inf
    for k in grid:
        rate = pseudo["gsax_sum"] / (pseudo["n_pre"] + k)
        r = weighted_r(rate, pseudo["outcome"], pseudo["weight"])
        if not np.isnan(r) and r > best_r:
            best_k, best_r = k, r
    return int(best_k)


def fit_composite(pseudo: pd.DataFrame,
                  cols=("stopping", "freeze", "rebound_control", "perf"),
                  lam: float = 1.0) -> dict:
    d = pseudo.dropna(subset=list(cols) + ["outcome"])
    w = d["weight"].to_numpy(dtype=float)
    y = d["outcome"].to_numpy(dtype=float)
    means = {c: float(np.average(d[c], weights=w)) for c in cols}
    stds = {c: float(np.sqrt(np.average((d[c] - means[c]) ** 2, weights=w))) or 1.0
            for c in cols}
    X = np.column_stack([(d[c] - means[c]) / stds[c] for c in cols])
    yc = y - np.average(y, weights=w)
    W = np.diag(w / w.mean())
    beta = np.linalg.solve(X.T @ W @ X + lam * np.eye(len(cols)), X.T @ W @ yc)
    return {"means": means, "stds": stds,
            "beta": {c: float(b) for c, b in zip(cols, beta)}}


def apply_composite(row: dict, params: dict) -> float:
    return float(sum(params["beta"][c]
                     * (row[c] - params["means"][c]) / params["stds"][c]
                     for c in params["beta"]))
