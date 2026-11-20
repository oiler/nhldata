"""Structure features for the layered difficulty models.

All columns float64; base categories: wrist shot, EV strength, tied score.
distance_adj is clamped to >= 0 (known -0.099 floor from quantile tail extension).
"""

import numpy as np
import pandas as pd

STRUCTURE_COLS = [
    "intercept", "dist", "log1p_dist", "angle",
    "snap", "slap", "backhand", "tip_deflect", "other_type",
    "pp", "sh", "trail2", "trail1", "lead1", "lead2",
    "is_rebound", "is_rush", "is_crossice_quick", "is_home",
]

CORSI_PREV = {"goal", "shot-on-goal", "missed-shot", "blocked-shot"}
OTHER_TYPES = {"wrap-around", "bat", "poke", "between-legs", "cradle"}


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    d = np.maximum(df["distance_adj"].to_numpy(dtype=float), 0.0)
    same = df["prev_same_team"].fillna(False).astype(bool).to_numpy()
    dt = df["dt_prev"].to_numpy(dtype=float)
    prev_x = df["prev_x_norm"].to_numpy(dtype=float)
    cross = df["prev_y_norm"].to_numpy(dtype=float) * df["y_norm"].to_numpy(dtype=float)
    prev_y_abs = np.abs(df["prev_y_norm"].to_numpy(dtype=float))
    prev_corsi = df["prev_type"].isin(CORSI_PREV).to_numpy()

    out = pd.DataFrame({
        "intercept": 1.0,
        "dist": d,
        "log1p_dist": np.log1p(d),
        "angle": df["angle"].to_numpy(dtype=float),
        "snap": df["shot_type"].eq("snap"),
        "slap": df["shot_type"].eq("slap"),
        "backhand": df["shot_type"].eq("backhand"),
        "tip_deflect": df["shot_type"].isin(["tip-in", "deflected"]),
        "other_type": df["shot_type"].isin(OTHER_TYPES),
        "pp": df["strength"].eq("PP"),
        "sh": df["strength"].eq("SH"),
        "trail2": df["score_diff"].le(-2),
        "trail1": df["score_diff"].eq(-1),
        "lead1": df["score_diff"].eq(1),
        "lead2": df["score_diff"].ge(2),
        "is_rebound": (dt <= 3) & same & prev_corsi,
        "is_rush": (dt <= 4) & (prev_x < 25),
        "is_crossice_quick": (dt <= 3) & same & (cross < 0) & (prev_y_abs >= 5),
        "is_home": df["goalie_is_home"].astype(bool),
    }, index=df.index)
    return out.astype("float64")[STRUCTURE_COLS]
