# v2/goalies/verify_foundation.py
"""Cross-season sanity report for the goalie-shot foundation (P0-P2 exit gate).

Usage: python3 v2/goalies/verify_foundation.py
"""

from pathlib import Path

import pandas as pd

GEN = Path(__file__).resolve().parent.parent.parent / "data" / "generated" / "goalies"

lines = []
for f in sorted(GEN.glob("shots_*.csv")):
    df = pd.read_csv(f)
    saves = df[(df["on_net"]) & (~df["is_goal"])]
    lines.append(
        f"{f.stem}: shots={len(df)} goalies={df['goalie_id'].nunique()} "
        f"goals={int(df['is_goal'].sum())} "
        f"sv%={1 - df['is_goal'].sum() / max(df['on_net'].sum(), 1):.4f} "
        f"freeze%={saves['froze'].mean():.3f} rebound%={saves['rebound_generated'].mean():.3f} "
        f"EV/PP/SH={df['strength'].value_counts(normalize=True).round(3).to_dict()} "
        f"arenas={df['home_abbrev'].nunique()} "
        f"mean|adj|={(df['distance_adj'] - df['distance']).abs().mean():.2f}ft"
    )
report = "\n".join(lines)
print(report)
(GEN / "foundation_report.txt").write_text(report + "\n")
