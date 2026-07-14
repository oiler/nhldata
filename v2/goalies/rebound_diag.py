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
