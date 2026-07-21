"""Situation-cut plumbing for the parallel strict-5v5 pipeline.

The all-situations pipeline is the default; `--situation 5v5` filters the
shared shots CSVs to situationCode 1551 and redirects outputs to GEN/5v5.
Shared inputs that are not shot-derived (goalie_games TOI, wp_table) always
come from the parent GEN dir regardless of cut.
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
