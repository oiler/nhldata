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
from v2.goalies.leverage import MIN_CELL  # noqa: E402

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


def _wp_lut(wp: pd.DataFrame) -> dict:
    """(score_diff_c, period_c, time_bucket) -> wp, or NaN if n < MIN_CELL."""
    return {(int(r.score_diff_c), int(r.period_c), int(r.time_bucket)):
            (float(r.wp) if r.n >= MIN_CELL else np.nan)
            for r in wp.itertuples()}


def leverage_weight_vectorized(shots: pd.DataFrame, wp: pd.DataFrame) -> np.ndarray:
    """Vectorized equivalent of leverage.leverage_weight applied per-row.

    The naive per-row loop calls `_cell`, which filters the whole wp_table
    on every invocation — O(shots * wp_table) and far too slow across
    ~560k shots. This builds the (score_diff_c, period_c, time_bucket) -> wp
    lookup once and vectorizes the same clip/bucket logic, including the
    n < MIN_CELL guard and the max(-3, sd - 1) clip for the "after" cell.
    Missing keys map to NaN just like sub-threshold cells (pd.Series.map
    default), so both cases fall through to the same 0.0 guard.
    """
    lut = _wp_lut(wp)
    sd = shots["score_diff"].clip(-3, 3).astype(int)
    p = shots["period"].clip(1, 4).astype(int)
    tb = (shots["time_s"] // 300).astype(int)
    sd_after = (sd - 1).clip(lower=-3)

    before = pd.Series(list(zip(sd, p, tb)), index=shots.index).map(lut)
    after = pd.Series(list(zip(sd_after, p, tb)), index=shots.index).map(lut)
    return (before - after).fillna(0.0).to_numpy()


def main() -> None:
    wp = pd.read_csv(GEN / "wp_table.csv")
    frames = []
    for season in SEASONS:
        shots = pd.read_csv(GEN / f"shots_{season}.csv")
        xg = blind_shot_xg(shots)
        lev = leverage_weight_vectorized(shots, wp)
        frames.append(ledger_rows(shots, xg, lev))
    ledger = pd.concat(frames, ignore_index=True)
    diff = pd.read_csv(GEN / "game_difficulty.csv")[
        ["season", "game_id", "goalie_id", "difficulty_pct", "xg_per60", "toi_s"]]
    ledger = ledger.merge(diff, on=["season", "game_id", "goalie_id"], how="left")
    ledger["gsax_per60"] = ledger["gsax_game"] * 3600 / ledger["toi_s"]
    ledger.to_csv(GEN / "game_ledger.csv", index=False)
    print(f"{len(ledger)} goalie-games; mean perf_z {ledger['perf_z'].mean():+.3f} "
          f"(should be ~0); mean lev_value {ledger['lev_value'].mean():+.4f}")


if __name__ == "__main__":
    main()
