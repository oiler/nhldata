# v2/browser/build_goalies_db.py
"""Build the cross-season goalies.db sidecar from the goalie pipeline CSVs.

Usage: python3 v2/browser/build_goalies_db.py
Sources: data/generated/goalies/*.csv + data/<season>/players/<id>.json
Output:  data/generated/browser/goalies.db
"""

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
GOALIES = REPO / "data" / "generated" / "goalies"
OUT = REPO / "data" / "generated" / "browser" / "goalies.db"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
MIN_SAVES_FOR_PCT = 500
_NAME_CACHE: dict[int, str] = {}


def freeze_percentile(rates: pd.DataFrame, min_saves: int = MIN_SAVES_FOR_PCT) -> pd.Series:
    out = pd.Series(np.nan, index=rates.index)
    eligible = rates["n_saves"] >= min_saves
    out[eligible] = rates.loc[eligible, "freeze_rate"].rank(pct=True) * 100
    return out


def resolve_name(goalie_id: int, seasons: tuple[str, ...], root: Path) -> str:
    """Resolve goalie name from players JSON across multiple seasons.

    Tries each season in order until finding a players/<id>.json file.
    Returns "Goalie <id>" if not found in any season.
    Pure function — no caching.
    """
    for season in seasons:
        f = root / season / "players" / f"{goalie_id}.json"
        if f.exists():
            j = json.loads(f.read_text())
            return f"{j['firstName']['default']} {j['lastName']['default']}"
    return f"Goalie {goalie_id}"


def _teams_joined(team_series: pd.Series) -> str:
    seen = []
    for t in team_series:
        if t not in seen:
            seen.append(t)
    return "/".join(seen)


def build_goalie_seasons(gg, gsax, shots, terms, ledger) -> pd.DataFrame:
    base = gg.sort_values("game_date").groupby(["season", "goalie_id"]).agg(
        teams=("team_abbrev", _teams_joined),
        gp=("game_id", "nunique"), toi_s=("toi_s", "sum")).reset_index()

    saves = shots[shots["on_net"] & ~shots["is_goal"] & shots["froze"].notna()]
    fr = saves.groupby(["season", "goalie_id"])["froze"].agg(
        freeze_rate="mean", n_saves="size").reset_index()
    pct_frames = []
    for season, grp in fr.groupby("season"):
        grp = grp.copy()
        grp["freeze_pct"] = freeze_percentile(grp)
        pct_frames.append(grp)
    fr = pd.concat(pct_frames, ignore_index=True) if pct_frames else fr.assign(freeze_pct=np.nan)

    reb = terms[terms["layer"] == "rebound"][["goalie_id", "term_indep"]].copy()
    reb["rebound_term_indep"] = -reb.pop("term_indep")

    led = ledger.groupby(["season", "goalie_id"]).agg(
        mean_difficulty_pct=("difficulty_pct", "mean"),
        mean_perf_z=("perf_z", "mean"),
        lev_value_sum=("lev_value", "sum")).reset_index()

    out = (base.merge(gsax.rename(columns={"shots": "shots_faced"}),
                      on="goalie_id", how="left")
           .merge(fr[["season", "goalie_id", "freeze_rate", "freeze_pct"]],
                  on=["season", "goalie_id"], how="left")
           .merge(reb[["goalie_id", "rebound_term_indep"]], on="goalie_id", how="left")
           .merge(led, on=["season", "goalie_id"], how="left"))
    return out


def _name(season: str, goalie_id: int) -> str:
    """Resolve goalie name with cross-season lookup and caching."""
    if goalie_id not in _NAME_CACHE:
        # Try the given season first, then other seasons in SEASONS order
        search_order = (season,) + tuple(s for s in SEASONS if s != season)
        _NAME_CACHE[goalie_id] = resolve_name(goalie_id, search_order, REPO / "data")
    return _NAME_CACHE[goalie_id]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ledger = pd.read_csv(GOALIES / "game_ledger.csv")
    season_frames, game_frames = [], []
    for season in SEASONS:
        gg = pd.read_csv(GOALIES / f"goalie_games_{season}.csv")
        gsax = pd.read_csv(GOALIES / f"gsax_{season}.csv")
        shots = pd.read_csv(GOALIES / f"shots_{season}.csv",
                            usecols=["season", "goalie_id", "on_net", "is_goal", "froze"])
        terms = pd.read_csv(GOALIES / f"goalie_terms_{season}.csv")
        led = ledger[ledger["season"] == int(season)]
        gs = build_goalie_seasons(gg, gsax, shots, terms, led)
        gs["name"] = [(_name(season, g)) for g in gs["goalie_id"]]
        season_frames.append(gs)

        games = led.merge(
            gg[["season", "game_id", "goalie_id", "game_date", "opp_abbrev"]],
            on=["season", "game_id", "goalie_id"], how="left")
        game_frames.append(games)

    conn = sqlite3.connect(str(OUT))
    try:
        pd.concat(season_frames, ignore_index=True).to_sql(
            "goalie_seasons", conn, if_exists="replace", index=False)
        pd.concat(game_frames, ignore_index=True).to_sql(
            "goalie_games", conn, if_exists="replace", index=False)
        pd.read_csv(GOALIES / "team_environment.csv").to_sql(
            "team_environment", conn, if_exists="replace", index=False)
        fv_path = GOALIES / "validation" / "freeze_value.json"
        fv = json.loads(fv_path.read_text()) if fv_path.exists() else {"per_freeze_xga_delta": None}
        rows = ([] if fv.get("per_freeze_xga_delta") is None
                else [{"per_freeze_xga_delta": fv["per_freeze_xga_delta"],
                       "window_s": fv.get("window_s", 30)}])
        pd.DataFrame(rows, columns=["per_freeze_xga_delta", "window_s"]).to_sql(
            "freeze_value", conn, if_exists="replace", index=False)
    finally:
        conn.close()
    print(f"goalies.db: {sum(len(f) for f in season_frames)} goalie-seasons, "
          f"{sum(len(f) for f in game_frames)} goalie-games, freeze_value rows={len(rows)}")


if __name__ == "__main__":
    main()
