"""Freeze value x strength decomposition (5v5 program item 3; pooled by design).

Adds froze x SH and froze x PP interactions to the 30s branch-pricing
regression: a PK freeze buys a line change, so its value may differ from EV.
Sharpens the positive freeze-value result -- NOT a null re-test; runs on
all-situations data per the pre-registration addendum.

Usage: python3 v2/goalies/freeze_by_strength.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.features import STRUCTURE_COLS, build_features  # noqa: E402
from v2.goalies.freeze_value import (_load_saves_and_shots, ridge_linear,  # noqa: E402
                                     window_xga)

VAL = ROOT / "data" / "generated" / "goalies" / "validation"


def freeze_strength_design(saves: pd.DataFrame) -> np.ndarray:
    froze = saves["froze"].to_numpy(dtype=float)
    sh = saves["strength"].eq("SH").to_numpy(dtype=float)
    pp = saves["strength"].eq("PP").to_numpy(dtype=float)
    return np.column_stack([froze, froze * sh, froze * pp])


def main() -> None:
    VAL.mkdir(parents=True, exist_ok=True)
    shots = _load_saves_and_shots()
    saves = shots[shots["on_net"] & ~shots["is_goal"] & shots["froze"].notna()].copy()
    y = window_xga(shots, saves, window_s=30)
    # base features already carry pp/sh main effects, so the interactions are
    # identified; froze main = EV freeze effect, froze_sh/froze_pp = deltas
    X = np.hstack([build_features(saves).to_numpy(), freeze_strength_design(saves)])
    penalty = np.full(X.shape[1], 1.0)
    penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
    penalty[-3:] = 1e-6
    beta, se = ridge_linear(X, y.astype(float), penalty)
    names = ("froze_ev", "froze_x_sh", "froze_x_pp")
    est = {n: {"coef": float(beta[i]), "se": float(se[i])}
           for n, i in zip(names, (-3, -2, -1))}
    counts = (saves.groupby(["strength", "froze"]).size()
              .rename("n").reset_index().to_dict("records"))
    lines = [f"{n}: coef={e['coef']:+.5f} se={e['se']:.5f}" for n, e in est.items()]
    lines.append(f"PK freeze total = froze_ev + froze_x_sh = "
                 f"{est['froze_ev']['coef'] + est['froze_x_sh']['coef']:+.5f}")
    lines.append(f"saves by strength/froze: {counts}")
    lines.append("SE caveat: iid ridge SEs; clustering makes true uncertainty "
                 "larger (plausibly 2-5x), same as the headline freeze study.")
    report = "\n".join(lines)
    (VAL / "freeze_by_strength.txt").write_text(report + "\n")
    (VAL / "freeze_by_strength.json").write_text(json.dumps(est, indent=2))
    print(report)


if __name__ == "__main__":
    main()
