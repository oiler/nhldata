"""Per-game goalie ledger: results, difficulty-adjusted z, leverage-weighted value.

A game is its own story: raw GA/xGA, difficulty-adjusted perf_z, and
leverage-weighted value are reported side by side with the game's
difficulty percentile — never collapsed into one number.

Usage: python3 v2/goalies/game_ledger.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.gsax_baseline import blind_shot_xg  # noqa: E402
from v2.goalies.leverage import leverage_weight_vectorized  # noqa: E402
from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def ledger_rows(shots: pd.DataFrame, xg: np.ndarray, lev: np.ndarray) -> pd.DataFrame:
    s = shots.assign(xg=xg, lev=lev,
                     var=xg * (1 - xg),
                     lev_delta=lev * (xg - shots["is_goal"].astype(float)))
    g = s.groupby(["season", "game_id", "goalie_id"]).agg(
        ga=("is_goal", "sum"), xga=("xg", "sum"),
        var_sum=("var", "sum"), lev_value=("lev_delta", "sum"),
    ).reset_index()
    g["gsax_game"] = g["xga"] - g["ga"]
    g["perf_z"] = np.where(g["var_sum"] > 0, g["gsax_game"] / np.sqrt(g["var_sum"]), np.nan)
    return g.drop(columns=["var_sum"])


def main() -> None:
    situation = parse_situation()
    out = gen_dir(situation)
    out.mkdir(parents=True, exist_ok=True)
    wp = pd.read_csv(GEN / "wp_table.csv")   # WP is a game-state object: shared across cuts
    frames = []
    for season in SEASONS:
        shots = load_shots(season, situation)
        xg = blind_shot_xg(shots)
        lev = leverage_weight_vectorized(shots, wp)
        frames.append(ledger_rows(shots, xg, lev))
    ledger = pd.concat(frames, ignore_index=True)
    diff = pd.read_csv(out / "game_difficulty.csv")[
        ["season", "game_id", "goalie_id", "difficulty_pct", "xg_per60", "toi_s"]]
    ledger = ledger.merge(diff, on=["season", "game_id", "goalie_id"], how="left")
    ledger["gsax_per60"] = ledger["gsax_game"] * 3600 / ledger["toi_s"]
    ledger.to_csv(out / "game_ledger.csv", index=False)
    print(f"{len(ledger)} goalie-games; mean perf_z {ledger['perf_z'].mean():+.3f} "
          f"(should be ~0); mean lev_value {ledger['lev_value'].mean():+.4f}")


if __name__ == "__main__":
    main()
