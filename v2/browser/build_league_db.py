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
import json
import os
import sqlite3
import sys as _sys
from pathlib import Path

import pandas as pd

_sys.path.insert(0, str(Path(__file__).parent))

from metrics import compute_wppi_and_toi_share

_season = _sys.argv[1] if len(_sys.argv) > 1 else "2025"
SEASON_DIR = f"data/{_season}"
OUTPUT_DB = os.path.join(SEASON_DIR, "generated", "browser", "league.db")
COMPETITION_DIR = os.path.join(SEASON_DIR, "generated", "competition")
PLAYERS_CSV = os.path.join(SEASON_DIR, "generated", "players", "csv", "players.csv")
FLATBOXSCORES_CSV = os.path.join(SEASON_DIR, "generated", "flatboxscores", "boxscores.csv")
FLATPLAYS_DIR = os.path.join(SEASON_DIR, "generated", "flatplays")
FIVE_V_FIVE = {"1551"}  # true 5v5 only (both goalies in, 5 skaters per side)


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
        "currentTeamAbbrev", "position", "shootsCatches",
        "heightInInches", "weightInPounds",
    ]
    df = pd.read_csv(PLAYERS_CSV, usecols=keep)
    df.to_sql("players", conn, if_exists="replace", index=False)
    print(f"  players: {len(df)} rows")


def _recover_missing_players(conn):
    """Fill gaps in the players table from raw JSON files."""
    missing = pd.read_sql_query(
        "SELECT DISTINCT c.playerId FROM competition c"
        " LEFT JOIN players p ON c.playerId = p.playerId"
        " WHERE p.playerId IS NULL AND c.position IN ('F','D')",
        conn,
    )
    if missing.empty:
        return

    players_dir = os.path.join(SEASON_DIR, "players")
    recovered = []
    for pid in missing["playerId"]:
        path = os.path.join(players_dir, f"{pid}.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            d = json.load(f)

        def _name(val):
            return val.get("default", "") if isinstance(val, dict) else (val or "")

        recovered.append({
            "playerId": pid,
            "firstName": _name(d.get("firstName", "")),
            "lastName": _name(d.get("lastName", "")),
            "currentTeamAbbrev": d.get("currentTeamAbbrev", ""),
            "position": d.get("position", ""),
            "shootsCatches": d.get("shootsCatches", ""),
            "heightInInches": d.get("heightInInches"),
            "weightInPounds": d.get("weightInPounds"),
        })

    if recovered:
        pd.DataFrame(recovered).to_sql("players", conn, if_exists="append", index=False)
        print(f"  players: recovered {len(recovered)} from raw JSON")


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

    eligible = compute_wppi_and_toi_share(eligible, comp)

    if eligible.empty:
        print("  player_metrics: 0 rows (no valid wPPI)")
        return

    out = eligible[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]].reset_index()
    out.to_sql("player_metrics", conn, if_exists="replace", index=False)
    print(f"  player_metrics: {len(out)} rows")


def build_points_5v5_table(conn):
    """Extract 5v5 goals and assists from flattened plays, write per-game player point counts."""
    frames = []
    for path in sorted(glob.glob(os.path.join(FLATPLAYS_DIR, "*.csv"))):
        game_id = int(os.path.basename(path).replace(".csv", ""))
        df = pd.read_csv(path, low_memory=False)
        goals = df[
            (df["typeDescKey"] == "goal")
            & (df["situationCode"].astype(str).isin(FIVE_V_FIVE))
        ]
        if goals.empty:
            continue

        records = []
        for _, g in goals.iterrows():
            scorer = g.get("details.scoringPlayerId")
            a1 = g.get("details.assist1PlayerId")
            a2 = g.get("details.assist2PlayerId")
            if pd.notna(scorer):
                records.append({"gameId": game_id, "playerId": int(scorer), "goals": 1, "assists": 0})
            if pd.notna(a1):
                records.append({"gameId": game_id, "playerId": int(a1), "goals": 0, "assists": 1})
            if pd.notna(a2):
                records.append({"gameId": game_id, "playerId": int(a2), "goals": 0, "assists": 1})
        if records:
            frames.append(pd.DataFrame(records))

    if not frames:
        print("  points_5v5: 0 rows (no 5v5 goals found)")
        return
    out = pd.concat(frames, ignore_index=True)
    out = out.groupby(["gameId", "playerId"]).agg(
        goals=("goals", "sum"),
        assists=("assists", "sum"),
    ).reset_index()
    out["points"] = out["goals"] + out["assists"]
    out.to_sql("points_5v5", conn, if_exists="replace", index=False)
    print(f"  points_5v5: {len(out)} rows from {len(frames)} games")


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
        _recover_missing_players(conn)
        build_games_table(conn)
        build_points_5v5_table(conn)
        build_player_metrics_table(conn)
    finally:
        conn.close()
    size_mb = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print(f"\nDone. Database: {OUTPUT_DB} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
