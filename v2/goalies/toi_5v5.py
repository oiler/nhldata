"""Per-goalie 5v5 time on ice, reconstructed from the per-second timelines.

Boxscore TOI (v2/goalies/toi.py) is all-situations and has no 5v5 variant, so
every per-60 in the 5v5 cut divided a 5v5 numerator by an all-situations
denominator. This module supplies the missing denominator.

Usage: python3 v2/goalies/toi_5v5.py
"""

import csv
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.cut import STRICT_5V5, gen_dir  # noqa: E402

SEASONS = ("2021", "2022", "2023", "2024", "2025")
GOALIE_COLS = ("awayGoalie", "homeGoalie")


def timelines_dir(season: str) -> Path:
    return ROOT / "data" / season / "generated" / "timelines" / "csv"


def count_5v5_seconds(rows) -> dict[int, int]:
    """Strict-5v5 seconds per goalie for one game's timeline rows.

    Goalies who appear in the game but never at 1551 get an explicit 0, so a
    caller can tell "played, saw no 5v5" apart from "no timeline at all".

    Strict 1551 only. compute_competition.py:24 uses
    SCORED_SITUATIONS = {"1551", "0651", "1560"} for skaters; the latter two are
    goalie-pulled states, and counting them would credit the remaining goalie
    with ice time while the other net is empty.
    """
    seconds: Counter[int] = Counter()
    seen: set[int] = set()
    for row in rows:
        at_5v5 = row["situationCode"] == STRICT_5V5
        for col in GOALIE_COLS:
            raw = row.get(col)
            if not raw:
                continue
            gid = int(raw)
            seen.add(gid)
            if at_5v5:
                seconds[gid] += 1
    return {gid: seconds.get(gid, 0) for gid in sorted(seen)}


def season_frame(season: str, tl_dir: Path) -> pd.DataFrame:
    paths = sorted(tl_dir.glob("*.csv"))
    if not paths:
        raise RuntimeError(
            f"no timelines for {season} at {tl_dir} — run "
            f"'python v2/timelines/generate_timeline.py 1 1312 {season}' first. "
            "Writing an empty file here would blank every 5v5 rate for the "
            "season while each downstream stage still reported success.")
    rows = []
    for path in paths:
        with path.open(newline="") as f:
            counts = count_5v5_seconds(list(csv.DictReader(f)))
        game_id = int(path.stem)
        rows.extend({"season": int(season), "game_id": game_id,
                     "goalie_id": gid, "toi_5v5_s": secs}
                    for gid, secs in counts.items())
    return pd.DataFrame(
        rows, columns=["season", "game_id", "goalie_id", "toi_5v5_s"]
    ).astype("int64")


def main() -> None:
    out_dir = gen_dir("5v5")
    out_dir.mkdir(parents=True, exist_ok=True)
    for season in SEASONS:
        df = season_frame(season, timelines_dir(season))
        df.to_csv(out_dir / f"goalie_toi_{season}.csv", index=False)
        zeros = int((df["toi_5v5_s"] == 0).sum())
        print(f"{season}: {len(df)} goalie-games, "
              f"{df['goalie_id'].nunique()} goalies, "
              f"5v5 TOI {df['toi_5v5_s'].sum() / 3600:.0f} h, "
              f"{zeros} with zero 5v5 seconds")


if __name__ == "__main__":
    main()
