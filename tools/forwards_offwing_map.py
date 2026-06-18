"""Forwards-only off-wing shooting map in natural forward territory.

Question (docs/ideas/2026-05-10-shooters.md): for forwards, in the areas they
naturally occupy (below the tops of the circles, x_norm >= 54), where — if
anywhere — is off-wing shooting more accurate, and do one-timer-ish shots
(quick release after a same-team event, especially a cross-ice one) drive it?

Frame: u = handedness-mirrored cross-ice coordinate; u > 0 is always the
shooter's off-wing side, so the cell at (x band, u band) compares directly
against its mirror (x band, -u band) — same ice geometry, opposite wing.

Caution: the map has 16 cells x 2 metrics; expect ~1-2 nominal p<0.05 cells by
chance. Trust coherent patterns and the within-shooter check, not lone cells.

Usage: python3 tools/forwards_offwing_map.py  (needs shots.csv from offwing_splits.py)
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from offwing_splits import two_prop_z

SHOTS_CSV = Path(__file__).resolve().parents[1] / "data" / "2025" / "generated" / "offwing" / "shots.csv"

X_BANDS = ((84, 89, "net-front 84-89"), (74, 84, "low-circles 74-84"),
           (64, 74, "dot-line 64-74"), (54, 64, "top-circles 54-64"))
U_BANDS = ((0, 8, "slot-lane <8"), (8, 16, "mid-lane 8-16"),
           (16, 24, "dot-wide 16-24"), (24, 43, "boards 24+"))


def mirrored_u(shoots: str, y_norm: float) -> float:
    """Cross-ice coordinate in a handedness-mirrored frame: u > 0 = off-wing side."""
    return y_norm if shoots == "R" else -y_norm


def wing_stats(off: pd.DataFrame, strong: pd.DataFrame) -> dict | None:
    """Fenwick sh% and goal-given-on-net comparison between mirrored subsets."""
    if len(off) < 50 or len(strong) < 50:
        return None
    og, sg = int(off["is_goal"].sum()), int(strong["is_goal"].sum())
    z, p = two_prop_z(og, len(off), sg, len(strong))
    off_net, strong_net = int(off["on_net"].sum()), int(strong["on_net"].sum())
    zn, pn = two_prop_z(og, off_net, sg, strong_net) if off_net and strong_net else (0.0, 1.0)
    return {
        "off_n": len(off), "off_g": og, "off_sh%": 100 * og / len(off),
        "str_n": len(strong), "str_g": sg, "str_sh%": 100 * sg / len(strong),
        "diff_pp": 100 * (og / len(off) - sg / len(strong)), "z": z, "p": p,
        "off_g|net%": 100 * og / off_net if off_net else float("nan"),
        "str_g|net%": 100 * sg / strong_net if strong_net else float("nan"),
        "z_net": zn, "p_net": pn,
    }


def cell_map(nat: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for xlo, xhi, xname in X_BANDS:
        xcell = nat[(nat["x_norm"] >= xlo) & (nat["x_norm"] < xhi)]
        for ulo, uhi, uname in U_BANDS:
            band = xcell[(xcell["u"].abs() > ulo) & (xcell["u"].abs() <= uhi)]
            stats = wing_stats(band[band["u"] > 0], band[band["u"] < 0])
            if stats:
                rows.append({"x_band": xname, "u_band": uname, **stats})
    return pd.DataFrame(rows)


def proxy_splits(nat: pd.DataFrame) -> pd.DataFrame:
    """One-timer-ish proxy groups: cross-ice quick plays vs other quick plays vs the rest."""
    royal = (nat["dt_prev"] <= 3) & nat["prev_same_team"].fillna(False) \
        & (nat["prev_y_norm"] * nat["y_norm"] < 0) & (nat["prev_y_norm"].abs() >= 5)
    quick = (nat["dt_prev"] <= 2) & nat["prev_same_team"].fillna(False) & ~royal
    fo = (nat["prev_type"] == "faceoff") & (nat["dt_prev"] <= 3) & nat["prev_same_team"].fillna(False)
    groups = [
        ("cross-ice quick (royal road-ish, dt<=3)", royal),
        ("other quick same-team (dt<=2)", quick),
        ("off faceoff win (dt<=3)", fo),
        ("everything else", ~royal & ~quick),
    ]
    rows = []
    for name, mask in groups:
        sub = nat[mask]
        stats = wing_stats(sub[sub["u"] > 0], sub[sub["u"] < 0])
        if stats:
            off_share = 100 * mask[nat["u"] > 0].mean()
            str_share = 100 * mask[nat["u"] < 0].mean()
            rows.append({"group": name, "off_share%": off_share, "str_share%": str_share, **stats})
    return pd.DataFrame(rows)


def within_shooter_conversion(nat: pd.DataFrame, min_per_wing: int = 15) -> dict | None:
    """Per-shooter off-minus-strong sh% gap — guards against shooter-quality selection."""
    per = nat.pivot_table(index="shooter_id", columns="wing", values="is_goal", aggfunc=["mean", "count"])
    per.columns = [f"{a}_{b}" for a, b in per.columns]
    per = per.dropna()
    per = per[(per["count_off"] >= min_per_wing) & (per["count_strong"] >= min_per_wing)]
    if len(per) < 10:
        return None
    gap = 100 * (per["mean_off"] - per["mean_strong"])
    return {"shooters": len(per), "mean_gap_pp": gap.mean(),
            "se_pp": gap.std(ddof=1) / math.sqrt(len(gap)), "pct_positive": 100 * (gap > 0).mean()}


def fmt(table: pd.DataFrame) -> str:
    return table.to_string(index=False, float_format=lambda v: f"{v:.2f}")


def main() -> None:
    df = pd.read_csv(SHOTS_CSV)
    fw = df[df["position"] == "F"].copy()
    fw["u"] = [mirrored_u(s, y) for s, y in zip(fw["shoots"], fw["y_norm"])]
    assert ((fw["u"] > 0) == (fw["wing"] == "off")).all(), "mirror frame disagrees with wing labels"
    fw["on_net"] = fw["event"].isin(("goal", "shot-on-goal"))

    nat = fw[(fw["x_norm"] >= 54) & (fw["x_norm"] <= 89)]
    print(f"Forwards: {len(fw)} shots; natural territory (54 <= x <= 89): {len(nat)} "
          f"({100 * len(nat) / len(fw):.1f}%); excluded: {int((fw['x_norm'] < 54).sum())} point-area, "
          f"{int((fw['x_norm'] > 89).sum())} behind-net")

    overall = wing_stats(nat[nat["u"] > 0], nat[nat["u"] < 0])
    print("\n=== Overall: forwards in natural territory, off-wing vs strong-side ===")
    print(fmt(pd.DataFrame([overall])))

    print("\n=== Spatial map: off-wing vs mirrored strong-side cell (Fenwick sh% and goal|on-net) ===")
    print("(16 cells: expect 1-2 chance significances; read patterns, not lone cells)")
    print(fmt(cell_map(nat)))

    print("\n=== One-timer-ish proxy splits (share = % of that wing's shots in group) ===")
    print(fmt(proxy_splits(nat)))

    ws = within_shooter_conversion(nat)
    print("\n=== Within-shooter check (same player, off minus strong sh%, n>=15 per wing) ===")
    print(ws if ws else "insufficient qualifying shooters")


if __name__ == "__main__":
    main()
