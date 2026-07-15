"""Empirical win-probability table and per-shot leverage weights.

State from the GOALIE team's perspective; wp = P(goalie's team wins),
OT/SO wins included. Leverage of a shot = win probability its goal would cost.

Usage: python3 v2/goalies/leverage.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
MIN_CELL = 200


def wp_table(states: pd.DataFrame) -> pd.DataFrame:
    s = states.assign(
        score_diff_c=states["score_diff"].clip(-3, 3),
        period_c=states["period"].clip(1, 4),
        time_bucket=states["time_s"] // 300,
    )
    return (s.groupby(["score_diff_c", "period_c", "time_bucket"])
            .agg(wp=("won", "mean"), n=("won", "size")).reset_index())


def _cell(table: pd.DataFrame, sd: int, p: int, tb: int):
    hit = table[(table.score_diff_c == sd) & (table.period_c == p) & (table.time_bucket == tb)]
    if len(hit) == 0 or hit.iloc[0]["n"] < MIN_CELL:
        return None
    return float(hit.iloc[0]["wp"])


def leverage_weight(row, table: pd.DataFrame) -> float:
    sd = int(max(-3, min(3, row["score_diff"])))
    p = int(max(1, min(4, row["period"])))
    tb = int(row["time_s"] // 300)
    before = _cell(table, sd, p, tb)
    after = _cell(table, max(-3, sd - 1), p, tb)
    if before is None or after is None:
        return 0.0
    return before - after


def _wp_lut(wp: pd.DataFrame) -> dict:
    """(score_diff_c, period_c, time_bucket) -> wp, or NaN if n < MIN_CELL."""
    return {(int(r.score_diff_c), int(r.period_c), int(r.time_bucket)):
            (float(r.wp) if r.n >= MIN_CELL else np.nan)
            for r in wp.itertuples()}


def leverage_weight_vectorized(shots: pd.DataFrame, wp: pd.DataFrame) -> np.ndarray:
    """Vectorized equivalent of leverage_weight applied per-row.

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


def game_winners(season: str) -> pd.DataFrame:
    rows = []
    for f in sorted((ROOT / "data" / season / "boxscores").glob("*.json")):
        b = json.loads(f.read_text())
        rows.append({"game_id": b["id"], "home_won": b["homeTeam"]["score"] > b["awayTeam"]["score"]})
    return pd.DataFrame(rows)


def main() -> None:
    frames = []
    for season in SEASONS:
        shots = pd.read_csv(GEN / f"shots_{season}.csv",
                            usecols=["game_id", "goalie_is_home", "score_diff", "period", "time_s"])
        winners = game_winners(season)
        m = shots.merge(winners, on="game_id")
        m["won"] = (m["goalie_is_home"] == m["home_won"]).astype(float)
        frames.append(m[["score_diff", "period", "time_s", "won"]])
    table = wp_table(pd.concat(frames, ignore_index=True))
    table.to_csv(GEN / "wp_table.csv", index=False)
    tied3 = table[(table.score_diff_c == 0) & (table.period_c == 3)]
    print(f"wp_table: {len(table)} cells; tied-3rd wp by bucket:\n{tied3.to_string(index=False)}")


if __name__ == "__main__":
    main()
