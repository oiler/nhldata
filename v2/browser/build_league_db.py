"""
Build a league-wide SQLite database for the NHL Data Browser.

Creates 4 tables:
  - competition:     all rows from data/<season>/generated/competition/*.csv
  - players:         from data/<season>/generated/players/csv/players.csv
  - games:           from data/<season>/generated/flatboxscores/boxscores.csv
  - player_metrics:  PPI, PPI+, wPPI, wPPI+, avg_toi_share per eligible skater (GP >= 5)

Usage:
    python v2/browser/build_league_db.py          # defaults to 2025
    python v2/browser/build_league_db.py 2024      # builds 2024 database
"""

import glob
import os
import sqlite3
import sys as _sys

import pandas as pd

_season = _sys.argv[1] if len(_sys.argv) > 1 else "2025"
SEASON_DIR = f"data/{_season}"
OUTPUT_DB = os.path.join(SEASON_DIR, "generated", "browser", "league.db")
COMPETITION_DIR = os.path.join(SEASON_DIR, "generated", "competition")
PLAYERS_CSV = os.path.join(SEASON_DIR, "generated", "players", "csv", "players.csv")
FLATBOXSCORES_CSV = os.path.join(SEASON_DIR, "generated", "flatboxscores", "boxscores.csv")


def build_competition_table(conn):
    """Load all competition CSVs into the competition table."""
    frames = []
    for path in sorted(glob.glob(os.path.join(COMPETITION_DIR, "*.csv"))):
        df = pd.read_csv(path)
        frames.append(df)
    if not frames:
        print("  competition: 0 rows (no CSVs found)")
        return
    out = pd.concat(frames, ignore_index=True)
    out.to_sql("competition", conn, if_exists="replace", index=False)
    print(f"  competition: {len(out)} rows from {len(frames)} games")


def build_players_table(conn):
    """Load players CSV into the players table (key columns only)."""
    if not os.path.exists(PLAYERS_CSV):
        print(f"  players: SKIPPED (file not found: {PLAYERS_CSV})")
        return
    keep = [
        "playerId", "firstName", "lastName",
        "currentTeamAbbrev", "position",
        "heightInInches", "weightInPounds",
    ]
    df = pd.read_csv(PLAYERS_CSV, usecols=keep)
    df.to_sql("players", conn, if_exists="replace", index=False)
    print(f"  players: {len(df)} rows")


def build_games_table(conn):
    """Load flat boxscores CSV into the games table (key columns only)."""
    if not os.path.exists(FLATBOXSCORES_CSV):
        print(f"  games: SKIPPED (file not found: {FLATBOXSCORES_CSV})")
        return
    keep = [
        "id", "gameDate",
        "awayTeam_abbrev", "homeTeam_abbrev",
        "awayTeam_score", "homeTeam_score",
        "periodDescriptor_number",
    ]
    df = pd.read_csv(FLATBOXSCORES_CSV, usecols=keep)
    df = df.rename(columns={"id": "gameId"})
    df.to_sql("games", conn, if_exists="replace", index=False)
    print(f"  games: {len(df)} rows")


def build_player_metrics_table(conn):
    """Compute PPI, PPI+, wPPI, wPPI+, avg_toi_share for eligible skaters and write to player_metrics."""
    comp = pd.read_sql_query(
        "SELECT playerId, team, gameId, position, toi_seconds, height_in, weight_lbs"
        " FROM competition WHERE position IN ('F', 'D')",
        conn,
    )
    if comp.empty:
        print("  player_metrics: 0 rows (no competition data)")
        return

    # Games played per player
    gp = comp.groupby("playerId")["gameId"].nunique().rename("games_played")

    # Physical data per player (all rows for a player have the same height/weight)
    phys = comp.groupby("playerId")[["height_in", "weight_lbs"]].max()
    phys["ppi"] = phys["weight_lbs"] / phys["height_in"]

    # Eligible: GP >= 5, non-null PPI
    player_df = gp.to_frame().join(phys[["ppi"]])
    eligible = player_df[(player_df["games_played"] >= 5) & player_df["ppi"].notna()].copy()

    if eligible.empty:
        print("  player_metrics: 0 rows (no eligible players)")
        return

    # PPI+
    mean_ppi = eligible["ppi"].mean()
    eligible["ppi_plus"] = 100.0 * eligible["ppi"] / mean_ppi

    # wPPI: PPI × games-weighted average TOI share across team stints.
    # Weighted average (not sum) ensures traded players aren't double-counted
    # relative to single-team players with identical per-game deployment.
    eligible_comp = comp[comp["playerId"].isin(eligible.index)]
    player_team_toi   = eligible_comp.groupby(["playerId", "team"])["toi_seconds"].sum()
    player_team_games = eligible_comp.groupby(["playerId", "team"])["gameId"].nunique()
    player_avg_toi    = player_team_toi / player_team_games  # avg seconds/game per stint

    team_total_toi    = eligible_comp.groupby("team")["toi_seconds"].sum()
    team_unique_games = eligible_comp.groupby("team")["gameId"].nunique()
    team_avg_toi      = team_total_toi / team_unique_games   # team avg eligible-seconds/game

    share_numerator: dict[int, float] = {}
    share_denominator: dict[int, int] = {}
    for (pid, team), avg_toi in player_avg_toi.items():
        team_avg = team_avg_toi.get(team, 0)
        if team_avg == 0:
            continue
        share = avg_toi / team_avg
        games = int(player_team_games[(pid, team)])
        share_numerator[pid] = share_numerator.get(pid, 0.0) + share * games
        share_denominator[pid] = share_denominator.get(pid, 0) + games

    wppi_map: dict[int, float] = {}
    for pid, numerator in share_numerator.items():
        denom = share_denominator.get(pid, 0)
        if denom == 0:
            continue
        weighted_avg_share = numerator / denom
        wppi_map[pid] = eligible.loc[pid, "ppi"] * weighted_avg_share

    eligible["wppi"] = pd.Series(wppi_map)
    eligible = eligible[eligible["wppi"].notna()]

    # wPPI+
    mean_wppi = eligible["wppi"].mean()
    eligible["wppi_plus"] = 100.0 * eligible["wppi"] / mean_wppi

    # avg_toi_share: mean of per-game (5 × player_toi / team_toi) across player's games.
    # team_toi uses full comp (all skaters, not just eligible), matching real game deployment totals.
    game_team_toi = comp.groupby(["team", "gameId"])["toi_seconds"].transform("sum")
    comp_share = comp.copy()
    comp_share["toi_share"] = 5.0 * comp_share["toi_seconds"] / game_team_toi.where(game_team_toi > 0)
    avg_toi_share = (
        comp_share[comp_share["playerId"].isin(eligible.index)]
        .groupby("playerId")["toi_share"]
        .mean()
        .rename("avg_toi_share")
    )
    eligible = eligible.join(avg_toi_share)

    out = eligible[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]].reset_index()
    out.to_sql("player_metrics", conn, if_exists="replace", index=False)
    print(f"  player_metrics: {len(out)} rows")


def main():
    os.makedirs(os.path.dirname(OUTPUT_DB), exist_ok=True)
    if os.path.exists(OUTPUT_DB):
        os.remove(OUTPUT_DB)
        print(f"Removed existing {OUTPUT_DB}")
    conn = sqlite3.connect(OUTPUT_DB)
    try:
        print(f"Building {OUTPUT_DB} ...\n")
        build_competition_table(conn)
        build_players_table(conn)
        build_games_table(conn)
        build_player_metrics_table(conn)
    finally:
        conn.close()
    size_mb = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print(f"\nDone. Database: {OUTPUT_DB} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
