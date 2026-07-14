"""Game Difficulty Index: how hard was each goalie-game's workload?

difficulty_pct = percentile of xG-faced-per-60 among all goalie-games
(toi >= 20 min), pooled across seasons. Components reported alongside.
Per spec addendum 6b: no idle-gap term (probed null 2026-07-14).

Usage: python3 v2/goalies/game_difficulty.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.gsax_baseline import blind_shot_xg  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")

# Same-team prior CORSI event (features.py:17); is_rebound is dt_prev <= 3 (features.py:46).
CORSI_PREV = {"goal", "shot-on-goal", "missed-shot", "blocked-shot"}


def game_rows(shots: pd.DataFrame, xg: np.ndarray, toi: pd.DataFrame) -> pd.DataFrame:
    s = shots.assign(
        xg=xg,
        hd=(np.maximum(shots["distance_adj"], 0) < 15),
        rush=(shots["dt_prev"] <= 4) & (shots["prev_x_norm"] < 25),
        rebound=(shots["dt_prev"] <= 3) & shots["prev_same_team"].fillna(False)
                & shots["prev_type"].isin(CORSI_PREV),
        crossice=(shots["dt_prev"] <= 3) & shots["prev_same_team"].fillna(False)
                 & (shots["prev_y_norm"] * shots["y_norm"] < 0)
                 & (shots["prev_y_norm"].abs() >= 5),
    )
    g = s.groupby(["season", "game_id", "goalie_id"]).agg(
        shots_faced=("xg", "size"), xg_faced=("xg", "sum"),
        hd_shots=("hd", "sum"), rush_shots=("rush", "sum"),
        rebound_shots=("rebound", "sum"), crossice_shots=("crossice", "sum"),
    ).reset_index()
    merged = g.merge(toi[["season", "game_id", "goalie_id", "toi_s"]].assign(
        season=toi["season"].astype(g["season"].dtype)),
        on=["season", "game_id", "goalie_id"], how="inner")
    dropped = len(g) - len(merged)
    if dropped:
        print(f"note: {dropped} goalie-games had shots but no TOI row (dropped)")
    merged["xg_per60"] = merged["xg_faced"] * 3600 / merged["toi_s"]
    merged["hd_share"] = merged["hd_shots"] / merged["shots_faced"]
    return merged


def add_difficulty_pct(games: pd.DataFrame, min_toi_s: int = 1200) -> pd.DataFrame:
    out = games.copy()
    eligible = out["toi_s"] >= min_toi_s
    out["difficulty_pct"] = np.nan
    out.loc[eligible, "difficulty_pct"] = out.loc[eligible, "xg_per60"].rank(pct=True) * 100
    return out


def main() -> None:
    frames = []
    for season in SEASONS:
        shots = pd.read_csv(GEN / f"shots_{season}.csv")
        toi = pd.read_csv(GEN / f"goalie_games_{season}.csv")
        frames.append(game_rows(shots, blind_shot_xg(shots), toi))
    games = add_difficulty_pct(pd.concat(frames, ignore_index=True))
    games.to_csv(GEN / "game_difficulty.csv", index=False)
    e = games[games["difficulty_pct"].notna()]
    print(f"{len(games)} goalie-games ({len(e)} eligible); "
          f"xg_per60 median {e['xg_per60'].median():.2f}, "
          f"p10 {e['xg_per60'].quantile(.1):.2f}, p90 {e['xg_per60'].quantile(.9):.2f}")


if __name__ == "__main__":
    main()
