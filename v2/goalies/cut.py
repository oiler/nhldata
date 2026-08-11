"""Situation-cut plumbing for the parallel strict-5v5 pipeline.

The all-situations pipeline is the default; `--situation 5v5` filters the
shared shots CSVs to situationCode 1551 and redirects outputs to GEN/5v5.
Goalie TOI is cut-aware as of 2026-07-30 (see
docs/plans/2026-07-30-goalie-5v5-toi-design.md): `load_toi` serves boxscore TOI
for the all cut and timeline-derived 5v5 TOI for the 5v5 cut. It previously came
from the parent GEN dir regardless of cut, which made every 5v5 per-60 a 5v5
numerator over an all-situations denominator. `wp_table` remains genuinely
shared — it is a game-state object, not an exposure measure.
"""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
STRICT_5V5 = "1551"


def parse_situation(argv: list[str] | None = None) -> str:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--situation", choices=("all", "5v5"), default="all")
    return p.parse_known_args(argv)[0].situation


def gen_dir(situation: str) -> Path:
    return GEN / "5v5" if situation == "5v5" else GEN


def filter_cut(df: pd.DataFrame, situation: str) -> pd.DataFrame:
    if situation == "all":
        return df
    mask = df["situation_code"].astype(str) == STRICT_5V5
    return df[mask].reset_index(drop=True)


def load_shots(season: str, situation: str,
               usecols: list[str] | None = None) -> pd.DataFrame:
    cols = usecols
    if cols is not None and situation == "5v5" and "situation_code" not in cols:
        cols = [*cols, "situation_code"]
    df = pd.read_csv(GEN / f"shots_{season}.csv", usecols=cols,
                     dtype={"situation_code": str})
    df = filter_cut(df, situation)
    if usecols is not None and "situation_code" not in usecols:
        df = df.drop(columns="situation_code", errors="ignore")
    return df[usecols] if usecols is not None else df


def load_toi(season: str, situation: str) -> pd.DataFrame:
    """Goalie-game rows whose `toi_s` is the exposure denominator for `situation`.

    Returns the whole goalie_games frame rather than a bare TOI series:
    consumers also read team_abbrev, game_date, opp_abbrev, is_home and starter
    off it, and preserving them is what lets game_ledger.py and environment.py
    inherit the corrected denominator without edits.

    A goalie-game with no timeline gets NaN, which is distinct from the 0 that
    toi_5v5.py writes for a goalie who played but saw no 5v5.
    """
    gg = pd.read_csv(GEN / f"goalie_games_{season}.csv")
    if situation == "all":
        return gg
    toi5 = pd.read_csv(gen_dir("5v5") / f"goalie_toi_{season}.csv")
    merged = (gg.drop(columns="toi_s")
              .merge(toi5, on=["season", "game_id", "goalie_id"], how="left")
              .rename(columns={"toi_5v5_s": "toi_s"}))
    missing = int(merged["toi_s"].isna().sum())
    if missing:
        print(f"note: {missing} {season} goalie-games have no timeline; "
              "their 5v5 rates will be NaN")
    return merged
