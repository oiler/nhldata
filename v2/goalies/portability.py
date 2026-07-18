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
