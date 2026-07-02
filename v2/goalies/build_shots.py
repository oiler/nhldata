"""Build data/generated/goalies/shots_<season>.csv from raw plays. Rebuildable, raw untouched.

Usage: python3 v2/goalies/build_shots.py <season>   # e.g. 2021
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from v2.goalies.extract import extract_goalie_shots  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent


def build_season(plays_dir: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(plays_dir.glob("*.json")):
        rows.extend(extract_goalie_shots(json.loads(f.read_text())))
    df = pd.DataFrame(rows)
    df["season"] = plays_dir.parent.name
    # None/True/False mixed columns round-trip badly through CSV; store as nullable floats
    for c in ("froze", "rebound_generated"):
        df[c] = df[c].map({True: 1.0, False: 0.0})
    return df


def main() -> None:
    season = sys.argv[1]
    df = build_season(ROOT / "data" / season / "plays")
    out_dir = ROOT / "data" / "generated" / "goalies"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"shots_{season}.csv"
    df.to_csv(out, index=False)
    print(f"{season}: {len(df)} shots, {df['goalie_id'].nunique()} goalies, "
          f"{int(df['is_goal'].sum())} goals -> {out}")


if __name__ == "__main__":
    main()
