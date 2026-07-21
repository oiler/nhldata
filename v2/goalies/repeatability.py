"""P6 secondary suite: component repeatability + tandem sanity table.

Repeatability uses term_indep (independent per-season fits) — chained terms
carry information across seasons by construction and would inflate r.
Anchors (report, don't assert): freeze ~ 0.58+, stopping ~ 0.12.

Usage: python3 v2/goalies/repeatability.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.portability import weighted_r  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
LAYER_LIST = ("onnet", "freeze", "goal", "rebound")


def component_repeatability(terms: dict[int, pd.DataFrame],
                            min_shots: int = 500) -> pd.DataFrame:
    rows = []
    seasons = sorted(terms)
    for layer in LAYER_LIST:
        for a, b in zip(seasons, seasons[1:]):
            ta = terms[a][(terms[a]["layer"] == layer)
                          & (terms[a]["n_shots"] >= min_shots)]
            tb = terms[b][(terms[b]["layer"] == layer)
                          & (terms[b]["n_shots"] >= min_shots)]
            m = ta.merge(tb, on="goalie_id", suffixes=("_a", "_b"))
            if len(m) < 3:
                continue
            w = np.minimum(m["n_shots_a"], m["n_shots_b"])
            rows.append({"layer": layer, "pair": f"{a}-{b}",
                         "r": weighted_r(m["term_indep_a"], m["term_indep_b"], w),
                         "n_goalies": len(m)})
    return pd.DataFrame(rows)


def tandem_table(gg: pd.DataFrame, shots_xg: pd.DataFrame,
                 terms: dict[int, pd.DataFrame], min_fenwick: int = 600) -> pd.DataFrame:
    fen = shots_xg[shots_xg["fenwick_flag"]]
    per_goalie = fen.groupby(["season", "goalie_id"]).agg(
        n=("xg", "size"), xga=("xg", "sum"), ga=("is_goal", "sum")).reset_index()
    per_goalie["gsax_rate"] = (per_goalie["xga"] - per_goalie["ga"]) / per_goalie["n"]
    team_of = gg.groupby(["season", "goalie_id"])["team_abbrev"].agg(
        lambda s: s.mode().iloc[0]).rename("team").reset_index()
    per_goalie = per_goalie.merge(team_of, on=["season", "goalie_id"])
    rows = []
    for (season, team), grp in per_goalie.groupby(["season", "team"]):
        grp = grp[grp["n"] >= min_fenwick].sort_values("n", ascending=False)
        if len(grp) < 2:
            continue
        pair = grp.head(2).sort_values("gsax_rate", ascending=False)
        hi, lo = pair.iloc[0], pair.iloc[1]
        tframe = terms.get(season)
        goal_terms = (tframe[tframe["layer"] == "goal"].set_index("goalie_id")
                      if tframe is not None else None)

        def _term(gid):
            if goal_terms is None or gid not in goal_terms.index:
                return np.nan
            return -float(goal_terms.loc[gid, "term_indep"])   # orient: higher=better

        team_dates = set(gg[(gg["season"] == season)
                            & (gg["team_abbrev"] == team)]["game_date"])

        def _b2b_share(gid):
            mine = gg[(gg["season"] == season) & (gg["goalie_id"] == gid)
                      & (gg["team_abbrev"] == team)]["game_date"]
            prev = (pd.to_datetime(mine) - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
            return float(prev.isin(team_dates).mean()) if len(mine) else np.nan

        rows.append({"season": season, "team": team,
                     "goalie_hi": int(hi["goalie_id"]), "goalie_lo": int(lo["goalie_id"]),
                     "gsax_gap": float(hi["gsax_rate"] - lo["gsax_rate"]),
                     "term_gap": _term(int(hi["goalie_id"])) - _term(int(lo["goalie_id"])),
                     "b2b_share_hi": _b2b_share(int(hi["goalie_id"])),
                     "b2b_share_lo": _b2b_share(int(lo["goalie_id"]))})
    return pd.DataFrame(rows)


def main() -> None:
    from v2.goalies.cut import gen_dir, parse_situation
    from v2.goalies.portability import build_shots_xg, load_terms
    situation = parse_situation()
    val = gen_dir(situation) / "validation"
    val.mkdir(parents=True, exist_ok=True)
    terms = load_terms(situation)
    rep = component_repeatability(terms)
    rep.to_csv(val / "repeatability.csv", index=False)
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    tandem = tandem_table(gg, build_shots_xg(situation), terms)
    tandem.to_csv(val / "tandem_table.csv", index=False)
    print(rep.to_string(index=False))
    print(f"\ntandem pairs: {len(tandem)}; "
          f"corr(gsax_gap, term_gap) = "
          f"{weighted_r(tandem['gsax_gap'], tandem['term_gap'], np.ones(len(tandem))):+.3f}")


if __name__ == "__main__":
    main()
