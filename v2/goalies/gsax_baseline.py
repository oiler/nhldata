"""Vanilla GSAx baseline: goalie-blind xG minus goals against, per goalie-season.

The comparator the spec's validation design requires (portability and
repeatability must be judged against this, not against raw save%).

Usage: python3 v2/goalies/gsax_baseline.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from v2.goalies.features import STRUCTURE_COLS, build_features  # noqa: E402
from v2.goalies.irls import fit_penalized_logistic, predict_proba  # noqa: E402
from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def blind_shot_xg(df: pd.DataFrame) -> np.ndarray:
    """Per-shot goalie-blind goal probability (the model behind gsax_table)."""
    X = build_features(df).to_numpy()
    y = df["is_goal"].to_numpy(dtype=float)
    penalty = np.full(len(STRUCTURE_COLS), 1.0)
    penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
    fit = fit_penalized_logistic(X, y, penalty)
    return predict_proba(X, fit.coef)


def gsax_table(df: pd.DataFrame) -> pd.DataFrame:
    xg = blind_shot_xg(df)
    agg = df.assign(xg=xg).groupby("goalie_id").agg(
        shots=("is_goal", "size"), xga=("xg", "sum"), ga=("is_goal", "sum"))
    agg["gsax"] = agg["xga"] - agg["ga"]
    agg["gsax_per100"] = 100 * agg["gsax"] / agg["shots"]
    return agg.reset_index()


def main() -> None:
    situation = parse_situation()
    out = gen_dir(situation)
    out.mkdir(parents=True, exist_ok=True)
    for season in SEASONS:
        df = load_shots(season, situation)
        table = gsax_table(df)
        table.to_csv(out / f"gsax_{season}.csv", index=False)
        print(f"{season}: gsax for {len(table)} goalies "
              f"(league xga {table['xga'].sum():.0f} vs ga {table['ga'].sum()})")


if __name__ == "__main__":
    main()
