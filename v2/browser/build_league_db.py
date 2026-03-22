"""
Build a league-wide SQLite database for the NHL Data Browser.

Creates 6 tables:
  - competition:      all rows from data/<season>/generated/competition/*.csv
  - players:          from data/<season>/generated/players/csv/players.csv
  - games:            from data/<season>/generated/flatboxscores/boxscores.csv
  - points_5v5:       5v5 goals/assists from flatplays CSVs
  - elite_forwards:   per-team elite forward classification (tTOI%, iTOI%, P/60 model)
  - player_metrics:   PPI, PPI+, wPPI, wPPI+, avg_toi_share per eligible skater (GP >= 5)

After building elite_forwards, pct_vs_top_fwd in the competition table is
overwritten with the fraction of opposing forwards who are in the elite set.

Usage:
    python v2/browser/build_league_db.py          # defaults to 2025
    python v2/browser/build_league_db.py 2024      # builds 2024 database
"""

import csv
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
SCORED_SITUATIONS = {"1551", "0651", "1560"}  # 5v5 + empty-net situations


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


def build_elite_forwards_table(conn):
    """Identify elite forwards per team based on TOI share, ice-time profile, and 5v5 scoring rate.

    Criteria:
      - GP >= 20
      - tTOI% >= 28  (team time-on-ice share — top-six usage)
      - iTOI% < 83   (individual 5v5 share — excludes 5v5-only specialists)
      - P/60 >= 1.0   (minimum 5v5 scoring rate)

    Within each team, forwards are ranked by P/60.  The top 3 qualify automatically.
    A 4th slot is added if that player's P/60 >= 1.7.

    Traded players who are elite on one team also appear as carry-over rows
    (is_carryover=1) on every other team they played for.
    """
    stats_sql = """
    WITH team_totals AS (
        SELECT gameId, team, SUM(toi_seconds) as team_total
        FROM competition WHERE position IN ('F','D')
        GROUP BY gameId, team
    ),
    player_points AS (
        SELECT playerId, SUM(points) as total_pts
        FROM points_5v5 GROUP BY playerId
    )
    SELECT
        c.playerId, c.team,
        COUNT(DISTINCT c.gameId) as gp,
        ROUND(SUM(c.toi_seconds) * 1.0 / COUNT(DISTINCT c.gameId) / 60, 2) as toi_min_gp,
        AVG(5.0 * c.toi_seconds / tt.team_total) * 100 as ttoi_pct,
        SUM(c.toi_seconds) * 100.0 / SUM(c.total_toi_seconds) as itoi_pct,
        COALESCE(pp.total_pts, 0) * 3600.0 / SUM(c.toi_seconds) as p60
    FROM competition c
    JOIN team_totals tt ON tt.gameId = c.gameId AND tt.team = c.team
    LEFT JOIN player_points pp ON pp.playerId = c.playerId
    WHERE c.position = 'F'
    GROUP BY c.playerId, c.team
    HAVING gp >= 20
    """
    df = pd.read_sql_query(stats_sql, conn)
    if df.empty:
        print("  elite_forwards: 0 rows (no qualifying forwards)")
        return

    # Apply threshold filters
    df = df[
        (df["ttoi_pct"] >= 28)
        & (df["itoi_pct"] < 83)
        & (df["p60"] >= 1.0)
    ].copy()

    if df.empty:
        print("  elite_forwards: 0 rows (no forwards pass filters)")
        return

    # Rank by P/60 within each team (1 = highest)
    df["rank"] = df.groupby("team")["p60"].rank(ascending=False, method="first").astype(int)

    # Keep top 3 + optional 4th slot (P/60 >= 1.7)
    df = df[(df["rank"] <= 3) | ((df["rank"] == 4) & (df["p60"] >= 1.7))].copy()

    if df.empty:
        print("  elite_forwards: 0 rows (no forwards in top slots)")
        return

    df["is_carryover"] = 0

    # Detect traded elites: players elite on one team who also appear on another
    elite_pids = set(df["playerId"].unique())
    all_teams_for_pid = pd.read_sql_query(
        "SELECT DISTINCT playerId, team FROM competition WHERE position = 'F'",
        conn,
    )

    carryover_rows = []
    for pid in elite_pids:
        elite_teams = set(df[df["playerId"] == pid]["team"])
        all_teams = set(all_teams_for_pid[all_teams_for_pid["playerId"] == pid]["team"])
        other_teams = all_teams - elite_teams
        if other_teams:
            # Use the elite row with the highest GP as the source
            source = df[df["playerId"] == pid].sort_values("gp", ascending=False).iloc[0]
            for team in other_teams:
                carry = source.to_dict()
                carry["team"] = team
                carry["rank"] = 0
                carry["is_carryover"] = 1
                carryover_rows.append(carry)

    if carryover_rows:
        df = pd.concat([df, pd.DataFrame(carryover_rows)], ignore_index=True)

    out_cols = ["playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct", "p60", "rank", "is_carryover"]
    df[out_cols].to_sql("elite_forwards", conn, if_exists="replace", index=False)
    print(f"  elite_forwards: {len(df)} rows ({len(df[df['is_carryover'] == 0])} primary, {len(df[df['is_carryover'] == 1])} carry-over)")


def recompute_pct_vs_elite_fwd(conn):
    """Replace pct_vs_top_fwd with fraction of opposing forwards who are elite."""
    elite_rows = conn.execute("SELECT playerId FROM elite_forwards").fetchall()
    if not elite_rows:
        print("  pct_vs_elite_fwd: skipped (no elite forwards)")
        return
    elite_set = {r[0] for r in elite_rows}

    # Build per-game lookups from competition table
    pos_rows = conn.execute(
        "SELECT gameId, playerId, position FROM competition"
    ).fetchall()
    game_positions = {}
    game_ids = set()
    for gid, pid, pos in pos_rows:
        game_ids.add(gid)
        game_positions.setdefault(gid, {})[pid] = pos

    timelines_dir = os.path.join(SEASON_DIR, "generated", "timelines", "csv")
    updates = []

    for game_id in sorted(game_ids):
        timeline_path = os.path.join(timelines_dir, f"{game_id}.csv")
        if not os.path.exists(timeline_path):
            continue

        positions = game_positions.get(game_id, {})
        accum = {}  # playerId → [fraction, fraction, ...]

        with open(timeline_path, newline="") as f:
            for row in csv.DictReader(f):
                if row["situationCode"] not in SCORED_SITUATIONS:
                    continue

                away = [int(p) for p in row["awaySkaters"].split("|")] if row.get("awaySkaters") else []
                home = [int(p) for p in row["homeSkaters"].split("|")] if row.get("homeSkaters") else []

                for player_id, opponents in (
                    [(p, home) for p in away] + [(p, away) for p in home]
                ):
                    if positions.get(player_id) == "G":
                        continue

                    opp_fwds = [p for p in opponents if positions.get(p) == "F"]
                    if not opp_fwds:
                        continue

                    elite_count = sum(1 for p in opp_fwds if p in elite_set)
                    accum.setdefault(player_id, []).append(elite_count / len(opp_fwds))

        for pid, fracs in accum.items():
            updates.append((round(sum(fracs) / len(fracs), 4), game_id, pid))

    if updates:
        conn.executemany(
            "UPDATE competition SET pct_vs_top_fwd = ? WHERE gameId = ? AND playerId = ?",
            updates,
        )
        conn.commit()

    print(f"  pct_vs_elite_fwd: updated {len(updates)} rows across {len(game_ids)} games")


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
        build_elite_forwards_table(conn)
        recompute_pct_vs_elite_fwd(conn)
        build_player_metrics_table(conn)
    finally:
        conn.close()
    size_mb = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print(f"\nDone. Database: {OUTPUT_DB} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
