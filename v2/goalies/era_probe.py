"""Era probe: did froze/rebound_generated CODING shift at the 2023 tracking era?

Fits the structure model on saves with an unpenalized era_b dummy; the dummy's
logit coefficient is the feature-conditional era shift. Pre-registered rule
(spec 6c): |coef| <= 0.05 stable; > 0.15 normalize; else sensitivity.

Usage: python3 v2/goalies/era_probe.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.features import STRUCTURE_COLS, build_features  # noqa: E402
from v2.goalies.irls import fit_penalized_logistic  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
ERA_B = {2023, 2024, 2025}


def era_shift(shots: pd.DataFrame, outcome: str) -> dict:
    frame = shots[shots["on_net"] & ~shots["is_goal"]]
    frame = frame[frame[outcome].notna()]
    y = frame[outcome].to_numpy(dtype=float)
    era_b = frame["season"].isin(ERA_B).to_numpy(dtype=float)
    X = np.hstack([build_features(frame).to_numpy(), era_b[:, None]])
    penalty = np.full(X.shape[1], 1.0)
    penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
    penalty[-1] = 1e-6
    fit = fit_penalized_logistic(X, y, penalty)
    return {
        "coef": float(fit.coef[-1]), "se": float(fit.se[-1]),
        "rate_a": float(y[era_b == 0].mean()), "rate_b": float(y[era_b == 1].mean()),
    }


def verdict(coef: float) -> str:
    if abs(coef) <= 0.05:
        return "stable"
    if abs(coef) > 0.15:
        return "normalize"
    return "sensitivity"


def main() -> None:
    VAL.mkdir(parents=True, exist_ok=True)
    shots = pd.concat([pd.read_csv(GEN / f"shots_{s}.csv") for s in SEASONS],
                      ignore_index=True)
    lines, verdicts, coefs = [], {}, {}
    for outcome in ("froze", "rebound_generated"):
        r = era_shift(shots, outcome)
        verdicts[outcome] = verdict(r["coef"])
        coefs[outcome] = r
        lines.append(f"{outcome}: era_b coef={r['coef']:+.4f} se={r['se']:.4f} "
                     f"raw rates A={r['rate_a']:.4f} B={r['rate_b']:.4f} "
                     f"-> verdict {verdicts[outcome]}")
    saves = shots[shots["on_net"] & ~shots["is_goal"]].copy()
    saves["era"] = np.where(saves["season"].isin(ERA_B), "B", "A")
    saves["dist_band"] = pd.cut(np.maximum(saves["distance_adj"], 0),
                                [0, 15, 30, 50, 200], right=False)
    binned = saves.groupby(["era", "dist_band", "shot_type"], observed=True)["froze"].agg(
        ["mean", "size"])
    lines.append("\nfroze rate by era x distance band x shot type (n >= 2000 cells):")
    lines.append(binned[binned["size"] >= 2000].to_string())
    (VAL / "era_probe_verdict.json").write_text(json.dumps(
        {"froze": verdicts["froze"], "rebound_generated": verdicts["rebound_generated"],
         "coefs": coefs}, indent=2))
    report = "\n".join(lines)
    (VAL / "era_probe_report.txt").write_text(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
