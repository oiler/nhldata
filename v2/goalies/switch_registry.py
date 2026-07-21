"""Switch registry: real team-change cases + non-switch pseudo-cases.

A stint is a maximal date-ordered run of games with one team. Every stint
boundary with a team change is a candidate case; floors (600 fenwick each
side) and min(pre, post) weights per spec 6c. Pre window = everything before
switch_date; post window = the new stint only. Non-switch pseudo-cases
(same team, consecutive seasons) exist ONLY to freeze the baseline K and
composite weights before any real case is scored.

Usage: python3 v2/goalies/switch_registry.py
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
FLOOR = 600


def fenwick_by_game(shots: pd.DataFrame) -> pd.DataFrame:
    fen = shots[shots["event"] != "blocked-shot"]
    return (fen.groupby(["season", "game_id", "goalie_id"]).size()
            .rename("fenwick").reset_index())


def stint_table(gg: pd.DataFrame, fenwick: pd.DataFrame) -> pd.DataFrame:
    g = gg.sort_values(["goalie_id", "game_date", "game_id"]).merge(
        fenwick, on=["season", "game_id", "goalie_id"], how="left")
    g["fenwick"] = g["fenwick"].fillna(0)
    changed = (g["team_abbrev"] != g.groupby("goalie_id")["team_abbrev"].shift())
    g["stint_id"] = changed.cumsum()
    return (g.groupby(["goalie_id", "stint_id"]).agg(
        team=("team_abbrev", "first"), start=("game_date", "min"),
        end=("game_date", "max"), first_season=("season", "min"),
        last_season=("season", "max"), fenwick=("fenwick", "sum"))
        .reset_index().sort_values(["goalie_id", "start"], ignore_index=True))


def _case_row(prev_rows, cur, case_id, switch_type):
    pre_fenwick = int(prev_rows["fenwick"].sum())
    return {
        "case_id": case_id, "goalie_id": cur["goalie_id"],
        "switch_type": switch_type, "switch_date": cur["start"],
        "pre_team": prev_rows.iloc[-1]["team"], "post_team": cur["team"],
        "pre_fenwick": pre_fenwick, "post_fenwick": int(cur["fenwick"]),
        "weight": min(pre_fenwick, int(cur["fenwick"])),
        "last_pre_season": int(prev_rows.iloc[-1]["last_season"]),
        "first_post_season": int(cur["first_season"]),
    }


def switch_cases(stints: pd.DataFrame, floor: int = FLOOR) -> pd.DataFrame:
    rows = []
    for _, grp in stints.groupby("goalie_id"):
        grp = grp.reset_index(drop=True)
        for i in range(1, len(grp)):
            prev_rows, cur = grp.iloc[:i], grp.iloc[i]
            if prev_rows["fenwick"].sum() < floor or cur["fenwick"] < floor:
                continue
            switch_type = ("offseason"
                           if prev_rows.iloc[-1]["last_season"] != cur["first_season"]
                           else "midseason")
            rows.append(_case_row(prev_rows, cur,
                                  f"S{cur['goalie_id']}-{cur['start']}", switch_type))
    return pd.DataFrame(rows)


def nonswitch_pseudo_cases(stints: pd.DataFrame, gg: pd.DataFrame,
                           fenwick: pd.DataFrame, floor: int = FLOOR) -> pd.DataFrame:
    """Same-team consecutive-season pseudo-cases, for frozen-param fitting only."""
    g = gg.merge(fenwick, on=["season", "game_id", "goalie_id"], how="left")
    g["fenwick"] = g["fenwick"].fillna(0)
    rows = []
    for _, st in stints.iterrows():
        for t in range(int(st["first_season"]), int(st["last_season"])):
            mine = g[g["goalie_id"] == st["goalie_id"]].sort_values("game_date")
            post = mine[(mine["season"] == t + 1)
                        & (mine["team_abbrev"] == st["team"])]
            if post.empty:
                continue
            switch_date = post["game_date"].min()
            pre = mine[mine["game_date"] < switch_date]
            if pre["fenwick"].sum() < floor or post["fenwick"].sum() < floor:
                continue
            last_pre_season = int(pre["season"].max())
            rows.append({
                "case_id": f"N{st['goalie_id']}-{switch_date}",
                "goalie_id": st["goalie_id"], "switch_type": "nonswitch",
                "switch_date": switch_date, "pre_team": st["team"],
                "post_team": st["team"],
                "pre_fenwick": int(pre["fenwick"].sum()),
                "post_fenwick": int(post["fenwick"].sum()),
                "weight": int(min(pre["fenwick"].sum(), post["fenwick"].sum())),
                "last_pre_season": last_pre_season, "first_post_season": t + 1,
            })
    cols = ["case_id", "goalie_id", "switch_type", "switch_date", "pre_team",
            "post_team", "pre_fenwick", "post_fenwick", "weight",
            "last_pre_season", "first_post_season"]
    return pd.DataFrame(rows, columns=cols)


def main() -> None:
    situation = parse_situation()
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--floor", type=int, default=FLOOR)
    floor = p.parse_known_args()[0].floor
    val = gen_dir(situation) / "validation"
    val.mkdir(parents=True, exist_ok=True)
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    shots = pd.concat([load_shots(s, situation,
                                  usecols=["season", "game_id", "goalie_id", "event"])
                       for s in SEASONS], ignore_index=True)
    fw = fenwick_by_game(shots)
    stints = stint_table(gg, fw)
    real = switch_cases(stints, floor=floor)
    pseudo = nonswitch_pseudo_cases(stints, gg, fw, floor=floor)
    registry = pd.concat([real, pseudo], ignore_index=True)
    registry.to_csv(val / "switch_registry.csv", index=False)
    counts = real.groupby("switch_type").size().to_dict()
    print(f"registry [{situation}, floor {floor}]: {len(real)} real cases {counts}, "
          f"{len(pseudo)} nonswitch pseudo; weights p10/p50/p90 = "
          f"{real['weight'].quantile(.1):.0f}/{real['weight'].median():.0f}/"
          f"{real['weight'].quantile(.9):.0f}")


if __name__ == "__main__":
    main()
