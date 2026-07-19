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
