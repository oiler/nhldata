"""Arena scorer-bias correction via distance quantile mapping.

Each arena's recorded shot-distance distribution is mapped onto the pooled
distribution of shots recorded at all OTHER arenas (leave-one-out reference).
This is the load-bearing correction for every downstream repeatability claim.

Usage: python3 v2/goalies/rink_adjust.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

QUANTILES = np.linspace(0.01, 0.99, 99)
ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"


def fit_quantile_map(arena_distances: np.ndarray, reference_distances: np.ndarray) -> np.ndarray:
    a_q = np.quantile(arena_distances, QUANTILES)
    r_q = np.quantile(reference_distances, QUANTILES)
    return np.column_stack([a_q, r_q])


def apply_quantile_map(distances: np.ndarray, qmap: np.ndarray) -> np.ndarray:
    a_q, r_q = qmap[:, 0], qmap[:, 1]
    out = np.interp(distances, a_q, r_q)
    # np.interp clamps out-of-range inputs to the endpoint VALUE, collapsing
    # everything below q01 (the closest, most dangerous shots) to a constant.
    # Extend by the endpoint DELTA instead so ordering/spacing is preserved.
    out = np.where(distances < a_q[0], distances + (r_q[0] - a_q[0]), out)
    out = np.where(distances > a_q[-1], distances + (r_q[-1] - a_q[-1]), out)
    return out


def fit_all_arenas(df: pd.DataFrame) -> dict[str, np.ndarray]:
    maps = {}
    for arena in sorted(df["home_abbrev"].unique()):
        at_arena = df.loc[df["home_abbrev"] == arena, "distance"].to_numpy()
        elsewhere = df.loc[df["home_abbrev"] != arena, "distance"].to_numpy()
        maps[arena] = fit_quantile_map(at_arena, elsewhere)
    return maps


def main() -> None:
    files = sorted(GEN.glob("shots_*.csv"))
    pooled = pd.concat([pd.read_csv(f, usecols=["home_abbrev", "distance"]) for f in files])
    maps = fit_all_arenas(pooled)

    long = [{"arena": a, "q": q, "arena_dist": row[0], "ref_dist": row[1]}
            for a, m in maps.items() for q, row in zip(QUANTILES, m)]
    pd.DataFrame(long).to_csv(GEN / "arena_adjustments.csv", index=False)

    for f in files:
        df = pd.read_csv(f)
        # Vectorized per-arena adjustment: one apply_quantile_map call per arena
        for arena, group in df.groupby("home_abbrev"):
            df.loc[group.index, "distance_adj"] = apply_quantile_map(
                group["distance"].to_numpy(), maps[arena]
            )
        df.to_csv(f, index=False)
        shift = (df["distance_adj"] - df["distance"]).abs().mean()
        print(f"{f.name}: mean |adjustment| = {shift:.2f} ft")


if __name__ == "__main__":
    main()
