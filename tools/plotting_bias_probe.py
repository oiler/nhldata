"""Probe for handedness-linked lateral plotting displacement in shot coordinates.

Exploratory follow-up to offwing_splits.py (no test file by design). Question:
is the recorded shot location displaced toward the shooter's blade side — either
because scorers plot the puck (true release point, offset from the body) or
because of systematic plotting bias? From pbp alone the two sources are not
separable; these tests measure the SIZE of the combined offset. A uniform
displacement cancels in pooled marginals under mirrored deployment, so each
test conditions on something that breaks the cancellation:

1. Within-shooter mirror: for shooters with enough shots on both wings, compare
   their mean |y| on strong side vs off-wing. Combined displacement + behavior;
   removes who-plays-where selection.
2. Same-side D point shots: L-shot vs R-shot defensemen shooting from the same
   recorded side at long range. Difference of mean y ~ 2*delta (+ behavior).
3. Center-line discontinuity: body positioning is smooth through y=0, but a
   blade-side offset steps the handedness mix exactly at the center line.
   L shots displace +y, R shots -y, so the L-share of shots just above 0 should
   exceed the smooth trend, and fall short just below 0.

Reads data/2025/generated/offwing/shots.csv (built by offwing_splits.py).
Usage: python3 tools/plotting_bias_probe.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

SHOTS_CSV = Path(__file__).resolve().parents[1] / "data" / "2025" / "generated" / "offwing" / "shots.csv"


def _shooter_gap(sub: pd.DataFrame, min_per_wing: int) -> dict | None:
    """Within-shooter mean |y| gap (strong minus off) averaged across qualifying shooters."""
    per = sub.assign(abs_y=sub["y_norm"].abs()).pivot_table(
        index="shooter_id", columns="wing", values="abs_y", aggfunc=["mean", "count"]
    )
    per.columns = [f"{a}_{b}" for a, b in per.columns]
    per = per.dropna()
    per = per[(per["count_off"] >= min_per_wing) & (per["count_strong"] >= min_per_wing)]
    if len(per) < 5:
        return None
    gap = per["mean_strong"] - per["mean_off"]
    dist = sub.pivot_table(index="shooter_id", columns="wing", values="distance", aggfunc="mean").loc[per.index]
    return {
        "shooters": len(per),
        "mean_gap_ft": gap.mean(),
        "se_ft": gap.std(ddof=1) / math.sqrt(len(gap)),
        "median_gap_ft": gap.median(),
        "pct_positive": 100 * (gap > 0).mean(),
        "dist_gap_ft": (dist["strong"] - dist["off"]).mean(),
    }


def within_shooter_mirror(df: pd.DataFrame, min_per_wing: int = 8) -> pd.DataFrame:
    out = []
    for label, sub in [("all", df)] + [(b, df[df["dist_band"] == b]) for b in sorted(df["dist_band"].unique())]:
        row = _shooter_gap(sub, min_per_wing)
        if row:
            out.append({"scope": label, **row})
    return pd.DataFrame(out)


def gap_by_shot_type(df: pd.DataFrame, min_per_wing: int = 5) -> pd.DataFrame:
    """Discriminator: release-point recording predicts gap(slap) >> gap(snap) > gap(wrist)
    at fixed distance (windup size sets the blade-to-body offset); positional behavior
    predicts near-equal gaps across shot types at the same distance."""
    out = []
    for band in ("15-30ft", "30-45ft", "45ft+"):
        for stype in ("wrist", "snap", "slap", "backhand"):
            row = _shooter_gap(df[(df["dist_band"] == band) & (df["shot_type"] == stype)], min_per_wing)
            if row:
                out.append({"band": band, "shot_type": stype, **row})
    return pd.DataFrame(out)


def gap_by_position(df: pd.DataFrame, min_per_wing: int = 5) -> pd.DataFrame:
    """Second discriminator: at the same distance, F and D share shot mechanics but not
    deployment roles, so positional stories allow F/D differences a release offset can't."""
    out = []
    for band in ("30-45ft", "45ft+"):
        for pos in ("F", "D"):
            row = _shooter_gap(df[(df["dist_band"] == band) & (df["position"] == pos)], min_per_wing)
            if row:
                out.append({"band": band, "position": pos, **row})
    return pd.DataFrame(out)


def same_side_d_points(df: pd.DataFrame) -> pd.DataFrame:
    """L vs R defensemen long-range shots from the same recorded side; diff ~ 2*delta."""
    d = df[(df["position"] == "D") & (df["dist_band"] == "45ft+")].copy()
    d["side"] = np.where(d["y_norm"] > 0, "left", "right")
    rows = []
    for side, sub in d.groupby("side"):
        cell = sub.groupby("shoots")["y_norm"].agg(["mean", "count", "std"])
        if not {"L", "R"}.issubset(cell.index):
            continue
        diff = cell.loc["L", "mean"] - cell.loc["R", "mean"]
        se = math.hypot(cell.loc["L", "std"] / math.sqrt(cell.loc["L", "count"]),
                        cell.loc["R", "std"] / math.sqrt(cell.loc["R", "count"]))
        rows.append({
            "side": side,
            "n_L": int(cell.loc["L", "count"]), "mean_y_L": cell.loc["L", "mean"],
            "n_R": int(cell.loc["R", "count"]), "mean_y_R": cell.loc["R", "mean"],
            "L_minus_R_ft": diff, "se_ft": se, "implied_delta_ft": diff / 2,
        })
    return pd.DataFrame(rows)


def center_discontinuity(df: pd.DataFrame, fit_range: tuple[int, int] = (4, 12),
                         step_range: tuple[int, int] = (1, 3)) -> dict:
    """Step in L-shooter share at y=0 vs the smooth trend fitted away from it."""
    lo_f, hi_f = fit_range
    lo_s, hi_s = step_range
    sub = df[df["y_norm"].abs().between(1, hi_f)].copy()
    sub["bin"] = sub["y_norm"].round().astype(int)
    per_bin = sub.groupby("bin").agg(n=("shoots", "size"), l_share=("shoots", lambda s: (s == "L").mean()))

    fit_bins = per_bin[(per_bin.index.to_series().abs() >= lo_f) & (per_bin.index.to_series().abs() <= hi_f)]
    slope, intercept = np.polyfit(fit_bins.index, fit_bins["l_share"], 1, w=fit_bins["n"])

    def excess(side_sign: int) -> tuple[float, float]:
        bins = per_bin[(per_bin.index * side_sign >= lo_s) & (per_bin.index * side_sign <= hi_s)]
        n = bins["n"].sum()
        obs = (bins["l_share"] * bins["n"]).sum() / n
        pred = (( slope * bins.index + intercept) * bins["n"]).sum() / n
        return obs - pred, math.sqrt(obs * (1 - obs) / n)

    above, se_above = excess(+1)   # y in [+1,+3]: displacement predicts L excess
    below, se_below = excess(-1)   # y in [-3,-1]: displacement predicts L deficit
    step = above - below
    se_step = math.hypot(se_above, se_below)
    return {
        "per_bin": per_bin,
        "excess_above": above, "excess_below": below,
        "step": step, "se_step": se_step, "z": step / se_step,
    }


def main() -> None:
    df = pd.read_csv(SHOTS_CSV)
    print(f"Shots: {len(df)} from {SHOTS_CSV}\n")

    print("=== 1. Within-shooter mirror: mean |y| strong-side minus off-wing ===")
    print("(positive = same player's shots plot wider on strong side / more central off-wing;")
    print(" displacement of delta ft toward the blade predicts gap ~ 2*delta; behavior adds same sign)")
    print(within_shooter_mirror(df).to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    print("\n=== 1b. Gap by shot type at fixed distance (release-offset discriminator) ===")
    print(gap_by_shot_type(df).to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    print("\n=== 1c. Gap by position at fixed distance ===")
    print(gap_by_position(df).to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    print("\n=== 2. Defensemen 45ft+ shots, same recorded side, L vs R shooters ===")
    print("(L minus R mean y ~ 2*delta on both sides if body positions match)")
    print(same_side_d_points(df).to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    print("\n=== 3. Center-line discontinuity in L-shooter share ===")
    res = center_discontinuity(df)
    print(res["per_bin"].to_string(float_format=lambda v: f"{v:.3f}"))
    print(f"\nL-share excess just above center (y +1..+3): {100 * res['excess_above']:+.2f}pp")
    print(f"L-share excess just below center (y -3..-1): {100 * res['excess_below']:+.2f}pp")
    print(f"Step at y=0: {100 * res['step']:+.2f}pp (se {100 * res['se_step']:.2f}, z = {res['z']:+.2f})")
    print("(blade-side displacement predicts a positive step: L excess above, L deficit below)")


if __name__ == "__main__":
    main()
