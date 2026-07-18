"""P6 portability harness: pre-switch estimates for candidates and baselines.

Per spec 6c: pre window = all shots before switch_date (matched horizon for
candidates and baseline alike); post window = the new stint only. Candidate
orientation is fixed so higher = better goalie. Mid-season cases refit the
switch season's layers with the goalie's post shots excluded (leakage rule).

Usage (Task 5 adds the CLI): python3 v2/goalies/portability.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.difficulty import fit_layer  # noqa: E402
from v2.goalies.gsax_baseline import blind_shot_xg  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
CAND_LAYERS = ("goal", "freeze", "rebound")
ORIENT = {"goal": -1.0, "freeze": 1.0, "rebound": -1.0}
CAND_NAME = {"goal": "stopping", "freeze": "freeze", "rebound": "rebound_control"}


def case_outcome(case: dict, shots_xg: pd.DataFrame, gg: pd.DataFrame,
                 season_only: int | None = None):
    post_games = gg[(gg["goalie_id"] == case["goalie_id"])
                    & (gg["game_date"] >= case["switch_date"])
                    & (gg["team_abbrev"] == case["post_team"])]
    if season_only is not None:
        post_games = post_games[post_games["season"] == season_only]
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
    if len(drs) == 0:
        return {"dr": float(point), "lo90": float("nan"),
                "hi90": float("nan"), "n_cases": int(n)}
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


def build_shots_xg() -> pd.DataFrame:
    frames = []
    for s in SEASONS:
        # dtype checkpoint: case_outcome's tuple-membership join on
        # (season, game_id) fails silently (drops the case) if dtypes
        # mismatch across frames -- cast explicitly here.
        shots = pd.read_csv(GEN / f"shots_{s}.csv").astype(
            {"season": "int64", "game_id": "int64"})
        xg = blind_shot_xg(shots)
        frames.append(pd.DataFrame({
            "season": shots["season"], "game_id": shots["game_id"],
            "goalie_id": shots["goalie_id"], "game_date": shots["game_date"],
            "fenwick_flag": shots["event"] != "blocked-shot",
            "xg": xg, "is_goal": shots["is_goal"],
        }))
    return pd.concat(frames, ignore_index=True)


def load_terms() -> dict[int, pd.DataFrame]:
    return {int(s): pd.read_csv(GEN / f"goalie_terms_{s}.csv") for s in SEASONS}


def run_midseason_refits(cases: pd.DataFrame, terms: dict[int, pd.DataFrame]) -> pd.DataFrame:
    cache_path = VAL / "midseason_refits.csv"
    cached = (pd.read_csv(cache_path) if cache_path.exists()
              else pd.DataFrame(columns=["case_id", "layer", "term"]))
    done = set(cached["case_id"])
    rows = list(cached.to_dict("records"))
    todo = cases[(cases["switch_type"] == "midseason") & ~cases["case_id"].isin(done)]
    for _, c in todo.iterrows():
        season = int(c["first_post_season"])
        season_shots = pd.read_csv(GEN / f"shots_{season}.csv").astype(
            {"season": "int64", "game_id": "int64"})
        prev = terms.get(season - 1)
        prior_terms = {}
        if prev is not None:
            for layer in CAND_LAYERS:
                lf = prev[prev["layer"] == layer]
                prior_terms[layer] = dict(zip(lf["goalie_id"], lf["term"]))
        refit = midseason_refit(season_shots, int(c["goalie_id"]),
                                c["switch_date"], prior_terms)
        rows.extend({"case_id": c["case_id"], "layer": layer, "term": t}
                    for layer, t in refit.items())
        print(f"refit {c['case_id']}: " +
              " ".join(f"{l}={t:+.3f}" for l, t in refit.items()))
    out = pd.DataFrame(rows)
    out.to_csv(cache_path, index=False)
    return out


def rebound_indep_lookup(case: dict, terms: dict[int, pd.DataFrame],
                         normalize: set[str]) -> float:
    """Independent (non-chained) rebound term for the last pre-switch season.

    Per spec 6c, the era-B sensitivity row compares against `term_indep`
    (the season's own independent fit), never the chained `term` that
    normal lookup and mid-season refits use.
    """
    season_frame = terms.get(case["last_pre_season"])
    if season_frame is None:
        return np.nan
    lf = season_frame[season_frame["layer"] == "rebound"]
    if "rebound" in normalize and len(lf) > 1:
        sd = float(lf["term_indep"].std(ddof=0))
        lf = lf.assign(term_indep=(lf["term_indep"] - lf["term_indep"].mean()) / (sd or 1.0))
    row = lf[lf["goalie_id"] == case["goalie_id"]]
    return (float(ORIENT["rebound"] * row["term_indep"].iloc[0])
            if len(row) else np.nan)


def case_estimates(cases: pd.DataFrame, shots_xg: pd.DataFrame, gg: pd.DataFrame,
                   terms: dict[int, pd.DataFrame], ledger_dated: pd.DataFrame,
                   normalize: set[str], refits: pd.DataFrame, k: float | None) -> pd.DataFrame:
    rows = []
    for _, c in cases.iterrows():
        case = c.to_dict()
        # Pseudo (nonswitch) cases are registered with post = first_post_season
        # only (switch_registry.nonswitch_pseudo_cases); case_outcome's default
        # "all future games with post_team" would let the outcome span into
        # first_post_season+1 for goalies who stay on the same team multiple
        # years, contradicting the registered window. Real cases keep the
        # full post-stint window (registry has no season cap for them).
        season_only = (int(case["first_post_season"])
                       if case["switch_type"] == "nonswitch" else None)
        oc = case_outcome(case, shots_xg, gg, season_only=season_only)
        if oc is None:
            continue
        pg = pre_gsax(case, shots_xg)
        cand = term_lookup(case, terms, normalize)
        if case["switch_type"] == "midseason":
            mine = refits[refits["case_id"] == case["case_id"]]
            season_frame = terms.get(case["last_pre_season"])
            for layer in CAND_LAYERS:
                row = mine[mine["layer"] == layer]
                if not len(row):
                    continue
                refit_term = float(row["term"].iloc[0])
                # The refit is on the same raw scale as the season's term
                # population (both come from fit_layer on that season's
                # shots); a single goalie's excluded post shots move the
                # population mean/std negligibly, so re-using the full
                # season population transform is the consistent choice --
                # it keeps midseason cases on the same z-scale as offseason
                # cases for layers term_lookup normalizes.
                if layer in normalize and season_frame is not None:
                    lf = season_frame[season_frame["layer"] == layer]
                    if len(lf) > 1:
                        mean = float(lf["term"].mean())
                        sd = float(lf["term"].std(ddof=0)) or 1.0
                        refit_term = (refit_term - mean) / sd
                cand[CAND_NAME[layer]] = float(ORIENT[layer] * refit_term)
        # rebound_control_indep is never refit for midseason cases (only the
        # chained `term` gets a midseason refit above) -- the full-season
        # term_indep would leak the goalie's post-trade shots into the era-B
        # sensitivity candidate. That path is dormant this run, so NaN here is
        # cheap and honest; paired_bootstrap_dr/weighted_r drop NaN rows.
        rebound_indep = (np.nan if case["switch_type"] == "midseason"
                        else rebound_indep_lookup(case, terms, normalize))
        rows.append({**case, **oc, **pg, **cand,
                     "rebound_control_indep": rebound_indep,
                     "perf": pre_perf(case, ledger_dated),
                     "baseline_naive": pg["naive_rate"],
                     **({"baseline_eb": eb_rate(pg["gsax_sum"], pg["n_pre"], k)}
                        if k is not None else {})})
    return pd.DataFrame(rows)


def main() -> None:
    VAL.mkdir(parents=True, exist_ok=True)
    registry = pd.read_csv(VAL / "switch_registry.csv")
    real = registry[registry["switch_type"] != "nonswitch"].reset_index(drop=True)
    pseudo_reg = registry[registry["switch_type"] == "nonswitch"].reset_index(drop=True)
    verdicts = json.loads((VAL / "era_probe_verdict.json").read_text())
    normalize = set()
    if verdicts["froze"] == "normalize":
        normalize.add("freeze")
    if verdicts["rebound_generated"] == "normalize":
        normalize.add("rebound")

    shots_xg = build_shots_xg()
    # dtype checkpoint: cast season/game_id explicitly so the case_outcome
    # tuple-membership join can't fail silently on a dtype mismatch.
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True).astype({"season": "int64", "game_id": "int64"})
    terms = load_terms()
    ledger_dated = pd.read_csv(GEN / "game_ledger.csv").astype(
        {"season": "int64", "game_id": "int64"}).merge(
        gg[["season", "game_id", "goalie_id", "game_date"]],
        on=["season", "game_id", "goalie_id"], how="left")
    refits = run_midseason_refits(real, terms)

    # (4) frozen params from pseudo-cases ONLY, before any real case is scored
    pseudo = case_estimates(pseudo_reg, shots_xg, gg, terms, ledger_dated,
                            normalize, refits, k=None)
    k = fit_k(pseudo)
    pseudo["baseline_eb"] = pseudo.apply(
        lambda r: eb_rate(r["gsax_sum"], r["n_pre"], k), axis=1)
    comp = fit_composite(pseudo)
    (VAL / "frozen_params.json").write_text(json.dumps(
        {"k": k, "composite": comp, "normalize": sorted(normalize)}, indent=2))

    # (5) real cases
    cases = case_estimates(real, shots_xg, gg, terms, ledger_dated,
                           normalize, refits, k=float(k))

    # coverage checkpoint: case_outcome returning None drops a case silently.
    # A real-case drop must stop the run, not shrink the study population
    # quietly -- surface the offending case_ids.
    dropped = sorted(set(real["case_id"]) - set(cases["case_id"]))
    print(f"real case coverage: {len(cases)}/{len(real)} scored, dropped={dropped}")
    assert not dropped, (
        "case_outcome dropped real cases (season/game_id dtype or join "
        f"mismatch?): {dropped}")

    cases["composite"] = cases.apply(
        lambda r: (apply_composite(r.to_dict(), comp)
                   if not any(np.isnan(r[c]) for c in comp["beta"]) else np.nan),
        axis=1)
    cases.to_csv(VAL / "portability_cases.csv", index=False)

    nan_counts = {c: int(cases[c].isna().sum())
                  for c in ("stopping", "freeze", "rebound_control", "composite")}
    print(f"NaN candidate counts (goalie absent from layer): {nan_counts}")
    print(f"n_post==0 count: {int((cases['n_post'] <= 0).sum())}, "
          f"baseline_eb NaN count: {int(cases['baseline_eb'].isna().sum())}")

    # (6) gate table
    y, w = cases["outcome"], cases["weight"]
    base = cases["baseline_eb"]
    gate = []
    for cand_col in ("stopping", "freeze", "rebound_control", "perf", "composite"):
        boot = paired_bootstrap_dr(cases[cand_col], base, y, w)
        gate.append({"candidate": cand_col, **boot,
                     "r_cand": weighted_r(cases[cand_col], y, w),
                     "r_base_eb": weighted_r(base, y, w),
                     "r_base_naive": weighted_r(cases["baseline_naive"], y, w),
                     "spearman_cand": weighted_spearman(cases[cand_col], y, w),
                     "incr_beta": incremental_beta(cases[cand_col], base, y, w)})
    if verdicts["rebound_generated"] == "sensitivity":
        eb = cases[(cases["last_pre_season"] >= 2023)
                   & (cases["first_post_season"] >= 2023)]
        boot = paired_bootstrap_dr(eb["rebound_control_indep"], eb["baseline_eb"],
                                   eb["outcome"], eb["weight"])
        gate.append({"candidate": "rebound_control_eraB", **boot,
                     "r_cand": weighted_r(eb["rebound_control_indep"], eb["outcome"], eb["weight"]),
                     "r_base_eb": weighted_r(eb["baseline_eb"], eb["outcome"], eb["weight"]),
                     "r_base_naive": np.nan,
                     "spearman_cand": weighted_spearman(eb["rebound_control_indep"], eb["outcome"], eb["weight"]),
                     "incr_beta": np.nan})
    gate_df = pd.DataFrame(gate)
    gate_df.to_csv(VAL / "gate_table.csv", index=False)
    print(f"K={k}, normalize={sorted(normalize)}, {len(cases)} real cases scored")
    print(gate_df.to_string(index=False))


if __name__ == "__main__":
    main()
