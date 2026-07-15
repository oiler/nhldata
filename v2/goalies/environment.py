"""Team environment profile: how hard does each team make its goalies' lives?

The 'o-line grade': per team-season workload difficulty served to own goalies,
plus schedule burden and the arena freeze-timing check (spec addendum 6b).

Usage: python3 v2/goalies/environment.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
TIP_TYPES = {"tip-in", "deflected"}


def team_environment(games: pd.DataFrame, goalie_games: pd.DataFrame,
                     shots: pd.DataFrame) -> pd.DataFrame:
    key = ["season", "game_id", "goalie_id"]
    g = games.merge(goalie_games[key + ["team_abbrev", "game_date"]], on=key)

    shot_team = shots.merge(goalie_games[key + ["team_abbrev"]], on=key)
    shot_agg = shot_team.groupby(["season", "team_abbrev"]).agg(
        tip_share=("shot_type", lambda s: s.isin(TIP_TYPES).mean()),
        d_shot_share=("shooter_position", lambda s: s.eq("D").mean()),
    ).reset_index()

    team_games = (g.sort_values("game_date")
                  .drop_duplicates(["season", "team_abbrev", "game_id"]))
    team_games["prev_date"] = team_games.groupby(["season", "team_abbrev"])["game_date"].shift()
    team_games["b2b"] = (pd.to_datetime(team_games["game_date"])
                         - pd.to_datetime(team_games["prev_date"])).dt.days == 1

    env = g.groupby(["season", "team_abbrev"]).agg(
        gp=("game_id", "size"),
        mean_difficulty_pct=("difficulty_pct", "mean"),
        mean_xg_faced_per60=("xg_per60", "mean"),
        hd_share=("hd_share", "mean"),
        crossice_shots_sum=("crossice_shots", "sum"),
        toi_s_sum=("toi_s", "sum"),
    ).reset_index()
    env["crossice_per60"] = env["crossice_shots_sum"] * 3600 / env["toi_s_sum"]
    env = env.drop(columns=["crossice_shots_sum", "toi_s_sum"])

    b2b = team_games.groupby(["season", "team_abbrev"])["b2b"].sum().rename("b2b_games").reset_index()
    return env.merge(b2b, on=["season", "team_abbrev"]).merge(shot_agg, on=["season", "team_abbrev"])


def arena_freeze_offsets(shots: pd.DataFrame) -> pd.DataFrame:
    saves = shots[(shots["on_net"]) & (~shots["is_goal"]) & (~shots["goalie_is_home"])]
    per_goalie_arena = saves.groupby(["goalie_id", "home_abbrev"])["froze"].agg(["mean", "size"])
    overall = saves.groupby("goalie_id")["froze"].mean().rename("away_base")
    j = per_goalie_arena.reset_index().merge(overall, on="goalie_id")
    j["off"] = j["mean"] - j["away_base"]
    out = j.groupby("home_abbrev").apply(
        lambda x: pd.Series({"n_saves": x["size"].sum(),
                             "freeze_offset": (x["off"] * x["size"]).sum() / x["size"].sum()}),
        include_groups=False).reset_index()
    return out


def main() -> None:
    games = pd.read_csv(GEN / "game_difficulty.csv")
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS], ignore_index=True)
    shots = pd.concat([pd.read_csv(GEN / f"shots_{s}.csv") for s in SEASONS], ignore_index=True)
    env = team_environment(games, gg, shots)
    env.to_csv(GEN / "team_environment.csv", index=False)
    offs = arena_freeze_offsets(shots)
    offs.to_csv(GEN / "arena_freeze_offsets.csv", index=False)
    print(f"env rows: {len(env)}")
    print(f"b2b_games range: {env['b2b_games'].min()}-{env['b2b_games'].max()}")
    print(env.sort_values("mean_xg_faced_per60").tail(5).to_string(index=False))
    print(f"arena freeze offsets: max |offset| = {offs['freeze_offset'].abs().max():.3f}")
    over_03 = offs[offs["freeze_offset"].abs() > 0.03].sort_values(
        "freeze_offset", key=lambda s: s.abs(), ascending=False)
    if len(over_03):
        print("arenas with |offset| > 0.03:")
        print(over_03.to_string(index=False))


if __name__ == "__main__":
    main()
