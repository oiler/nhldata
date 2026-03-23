"""
Build a league-wide SQLite database for the NHL Data Browser.

Creates 7 tables:
  - competition:      all rows from data/<season>/generated/competition/*.csv
  - players:          from data/<season>/generated/players/csv/players.csv
  - games:            from data/<season>/generated/flatboxscores/boxscores.csv
  - points_5v5:       5v5 goals/assists from flatplays CSVs
  - elite_forwards:   per-team elite forward classification (tTOI%, iTOI%, P/60 model)
  - elite_defensemen: per-team elite defensemen (production + deployment designations)
  - player_metrics:   PPI, PPI+, wPPI, wPPI+, avg_toi_share per eligible skater (GP >= 5)

After building elite_forwards, pct_vs_top_fwd in the competition table is
overwritten with the fraction of opposing forwards who are in the elite set.
After building elite_defensemen, pct_vs_top_def is similarly recomputed.

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
from datetime import date
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
      - P/60 >= 2.0   (minimum 5v5 scoring rate)

    All forwards passing the thresholds qualify. Ranked by P/60 within each team.

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
        & (df["p60"] >= 2.0)
    ].copy()

    if df.empty:
        print("  elite_forwards: 0 rows (no forwards pass filters)")
        return

    # Rank by P/60 within each team (1 = highest)
    df["rank"] = df.groupby("team")["p60"].rank(ascending=False, method="first").astype(int)

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
    """Replace pct_vs_top_fwd with fraction of opposing forwards who are elite.

    Also computes pct_any_elite_fwd — a binary metric: for each second, 1 if any
    elite forward is on the opposing side, 0 otherwise.  Averaged per game per player.
    """
    elite_rows = conn.execute("SELECT playerId FROM elite_forwards").fetchall()
    if not elite_rows:
        print("  pct_vs_elite_fwd: skipped (no elite forwards)")
        return
    elite_set = {r[0] for r in elite_rows}

    # Ensure pct_any_elite_fwd column exists
    cols = {r[1] for r in conn.execute("PRAGMA table_info(competition)").fetchall()}
    if "pct_any_elite_fwd" not in cols:
        conn.execute("ALTER TABLE competition ADD COLUMN pct_any_elite_fwd REAL DEFAULT 0.0")
        conn.commit()

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
    frac_updates = []
    binary_updates = []

    for game_id in sorted(game_ids):
        timeline_path = os.path.join(timelines_dir, f"{game_id}.csv")
        if not os.path.exists(timeline_path):
            continue

        positions = game_positions.get(game_id, {})
        frac_accum = {}    # playerId → [fraction, fraction, ...]
        binary_accum = {}  # playerId → [0 or 1, ...]

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
                    frac_accum.setdefault(player_id, []).append(elite_count / len(opp_fwds))
                    binary_accum.setdefault(player_id, []).append(1 if elite_count > 0 else 0)

        for pid, fracs in frac_accum.items():
            frac_updates.append((round(sum(fracs) / len(fracs), 4), game_id, pid))
        for pid, bins in binary_accum.items():
            binary_updates.append((round(sum(bins) / len(bins), 4), game_id, pid))

    if frac_updates:
        conn.executemany(
            "UPDATE competition SET pct_vs_top_fwd = ? WHERE gameId = ? AND playerId = ?",
            frac_updates,
        )
    if binary_updates:
        conn.executemany(
            "UPDATE competition SET pct_any_elite_fwd = ? WHERE gameId = ? AND playerId = ?",
            binary_updates,
        )
    conn.commit()

    print(f"  pct_vs_elite_fwd: updated {len(frac_updates)} rows across {len(game_ids)} games")


def build_elite_defensemen_table(conn):
    """Identify elite defensemen per team with two designations:

    Production elite (talent-driven):
      - GP >= 20, tTOI% >= 33, iTOI% < 83, P/60 >= 1.25
      - Ranked by P/60 within team, keep only rank 1 (max 1 per team)

    Deployment elite (coaching-driven):
      - GP >= 20, tTOI% >= 33, iTOI% < 90
      - Per team, the D with the highest avg pct_vs_top_fwd (vs elite forwards)

    Full elite: a production elite whose vs_ef gap to the team's deployment
    elite is < 1.5 percentage points (indicating they play as a pair).
    A player who is both production and deployment elite is also full elite.
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
        COALESCE(pp.total_pts, 0) * 3600.0 / SUM(c.toi_seconds) as p60,
        AVG(c.pct_any_elite_fwd) as vs_ef_pct
    FROM competition c
    JOIN team_totals tt ON tt.gameId = c.gameId AND tt.team = c.team
    LEFT JOIN player_points pp ON pp.playerId = c.playerId
    WHERE c.position = 'D'
    GROUP BY c.playerId, c.team
    HAVING gp >= 20
    """
    df = pd.read_sql_query(stats_sql, conn)
    if df.empty:
        print("  elite_defensemen: 0 rows (no qualifying defensemen)")
        return

    # --- Production elite ---
    prod = df[
        (df["ttoi_pct"] >= 33)
        & (df["itoi_pct"] < 83)
        & (df["p60"] >= 1.25)
    ].copy()

    if not prod.empty:
        prod["rank"] = prod.groupby("team")["p60"].rank(
            ascending=False, method="first"
        ).astype(int)
        prod = prod[prod["rank"] == 1].copy()
        prod["is_production"] = 1
    else:
        prod = pd.DataFrame()

    # --- Deployment elite ---
    dep = df[(df["ttoi_pct"] >= 33) & (df["itoi_pct"] < 90)].copy()
    if not dep.empty:
        dep = dep.loc[dep.groupby("team")["vs_ef_pct"].idxmax()].copy()
        dep["is_deployment"] = 1
    else:
        dep = pd.DataFrame()

    if prod.empty and dep.empty:
        print("  elite_defensemen: 0 rows (no defensemen pass filters)")
        return

    # --- Combine ---
    key_cols = ["playerId", "team"]
    if not prod.empty and not dep.empty:
        combined = pd.merge(
            prod[key_cols + ["gp", "toi_min_gp", "ttoi_pct", "itoi_pct", "p60",
                             "vs_ef_pct", "rank", "is_production"]],
            dep[key_cols + ["is_deployment"]],
            on=key_cols, how="outer",
        )
        # Fill stats for deployment-only players from df
        dep_only = combined["gp"].isna()
        if dep_only.any():
            dep_pids = combined.loc[dep_only, key_cols]
            dep_stats = pd.merge(dep_pids, df, on=key_cols)
            for col in ["gp", "toi_min_gp", "ttoi_pct", "itoi_pct", "p60", "vs_ef_pct"]:
                combined.loc[dep_only, col] = dep_stats[col].values
            combined.loc[dep_only, "rank"] = 0
    elif not prod.empty:
        combined = prod[key_cols + ["gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
                                     "p60", "vs_ef_pct", "rank", "is_production"]].copy()
        combined["is_deployment"] = 0
    else:
        combined = dep.copy()
        for col in ["gp", "toi_min_gp", "ttoi_pct", "itoi_pct", "p60", "vs_ef_pct"]:
            if col not in combined.columns:
                dep_stats = pd.merge(combined[key_cols], df, on=key_cols)
                for c in ["gp", "toi_min_gp", "ttoi_pct", "itoi_pct", "p60", "vs_ef_pct"]:
                    combined[c] = dep_stats[c].values
                break
        combined["is_production"] = 0
        combined["rank"] = 0

    combined["is_production"] = combined.get("is_production", 0).fillna(0).astype(int)
    combined["is_deployment"] = combined.get("is_deployment", 0).fillna(0).astype(int)

    # Full elite: production + deployment, OR production with vs_ef gap < 1.5pp to team's deployment elite
    dep_vs_ef = combined[combined["is_deployment"] == 1].set_index("team")["vs_ef_pct"].to_dict()

    def _is_full_elite(row):
        if row["is_production"] == 1 and row["is_deployment"] == 1:
            return 1
        if row["is_production"] == 1 and row["team"] in dep_vs_ef:
            gap = abs(row["vs_ef_pct"] - dep_vs_ef[row["team"]])
            if gap < 0.015:
                return 1
        return 0

    combined["is_full_elite"] = combined.apply(_is_full_elite, axis=1)
    combined["rank"] = combined["rank"].fillna(0).astype(int)
    combined["is_carryover"] = 0

    # --- Trade carry-over (production elites only) ---
    prod_pids = set(combined[combined["is_production"] == 1]["playerId"].unique())
    if prod_pids:
        all_teams_for_pid = pd.read_sql_query(
            "SELECT DISTINCT playerId, team FROM competition WHERE position = 'D'",
            conn,
        )
        carryover_rows = []
        for pid in prod_pids:
            elite_teams = set(combined[combined["playerId"] == pid]["team"])
            all_teams = set(all_teams_for_pid[all_teams_for_pid["playerId"] == pid]["team"])
            other_teams = all_teams - elite_teams
            if other_teams:
                source = combined[combined["playerId"] == pid].sort_values("gp", ascending=False).iloc[0]
                for team in other_teams:
                    carry = source.to_dict()
                    carry["team"] = team
                    carry["rank"] = 0
                    carry["is_carryover"] = 1
                    carryover_rows.append(carry)
        if carryover_rows:
            combined = pd.concat([combined, pd.DataFrame(carryover_rows)], ignore_index=True)

    out_cols = ["playerId", "team", "gp", "toi_min_gp", "ttoi_pct", "itoi_pct",
                "p60", "vs_ef_pct", "is_production", "is_deployment", "is_full_elite",
                "rank", "is_carryover"]
    combined[out_cols].to_sql("elite_defensemen", conn, if_exists="replace", index=False)

    n_prod = int(combined["is_production"].sum())
    n_dep = int(combined["is_deployment"].sum())
    n_full = int(combined["is_full_elite"].sum())
    print(f"  elite_defensemen: {len(combined)} rows ({n_prod} production, {n_dep} deployment, {n_full} full elite)")


def recompute_pct_vs_elite_def(conn):
    """Replace pct_vs_top_def with fraction of opposing defensemen who are deployment elite.

    Also computes pct_any_elite_def — a binary metric: for each second, 1 if any
    elite D is on the opposing side, 0 otherwise.  Averaged per game per player.
    """
    elite_rows = conn.execute(
        "SELECT playerId FROM elite_defensemen WHERE is_deployment = 1"
    ).fetchall()
    if not elite_rows:
        print("  pct_vs_elite_def: skipped (no elite defensemen)")
        return
    elite_set = {r[0] for r in elite_rows}

    # Ensure pct_any_elite_def column exists
    cols = {r[1] for r in conn.execute("PRAGMA table_info(competition)").fetchall()}
    if "pct_any_elite_def" not in cols:
        conn.execute("ALTER TABLE competition ADD COLUMN pct_any_elite_def REAL DEFAULT 0.0")
        conn.commit()

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
    frac_updates = []
    binary_updates = []

    for game_id in sorted(game_ids):
        timeline_path = os.path.join(timelines_dir, f"{game_id}.csv")
        if not os.path.exists(timeline_path):
            continue

        positions = game_positions.get(game_id, {})
        frac_accum = {}    # playerId → [fraction, fraction, ...]
        binary_accum = {}  # playerId → [0 or 1, ...]

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

                    opp_defs = [p for p in opponents if positions.get(p) == "D"]
                    if not opp_defs:
                        continue

                    elite_count = sum(1 for p in opp_defs if p in elite_set)
                    frac_accum.setdefault(player_id, []).append(elite_count / len(opp_defs))
                    binary_accum.setdefault(player_id, []).append(1 if elite_count > 0 else 0)

        for pid, fracs in frac_accum.items():
            frac_updates.append((round(sum(fracs) / len(fracs), 4), game_id, pid))
        for pid, bins in binary_accum.items():
            binary_updates.append((round(sum(bins) / len(bins), 4), game_id, pid))

    if frac_updates:
        conn.executemany(
            "UPDATE competition SET pct_vs_top_def = ? WHERE gameId = ? AND playerId = ?",
            frac_updates,
        )
    if binary_updates:
        conn.executemany(
            "UPDATE competition SET pct_any_elite_def = ? WHERE gameId = ? AND playerId = ?",
            binary_updates,
        )
    conn.commit()

    print(f"  pct_vs_elite_def: updated {len(frac_updates)} rows across {len(game_ids)} games")


def backfill_vs_elite_def_to_forwards(conn):
    """Add vs_ed_pct to elite_forwards: avg pct_any_elite_def per forward."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(elite_forwards)").fetchall()}
    if "vs_ed_pct" not in cols:
        conn.execute("ALTER TABLE elite_forwards ADD COLUMN vs_ed_pct REAL DEFAULT 0.0")
        conn.commit()

    updates = conn.execute(
        "SELECT c.playerId, c.team, AVG(c.pct_any_elite_def) "
        "FROM competition c "
        "JOIN elite_forwards e ON c.playerId = e.playerId AND c.team = e.team "
        "WHERE c.position = 'F' "
        "GROUP BY c.playerId, c.team"
    ).fetchall()

    if updates:
        conn.executemany(
            "UPDATE elite_forwards SET vs_ed_pct = ? WHERE playerId = ? AND team = ?",
            [(round(r[2], 4), r[0], r[1]) for r in updates],
        )
        conn.commit()
    print(f"  vs_elite_def → elite_forwards: backfilled {len(updates)} rows")


def _read_old_elites(db_path):
    """Read current elite sets from an existing league.db before it is deleted.

    Returns (fwd_df, def_df) — primary rows only (excludes carry-overs).
    Each DataFrame has columns: playerId, playerName, team.
    def_df also has a 'type' column: Full Elite / Production / Deployment.
    Returns empty DataFrames if the DB doesn't exist or tables are missing.
    """
    if not os.path.exists(db_path):
        return pd.DataFrame(columns=["playerId", "playerName", "team"]), \
               pd.DataFrame(columns=["playerId", "playerName", "team", "type"])
    try:
        old = sqlite3.connect(db_path)
        fwd = pd.read_sql_query(
            "SELECT e.playerId, "
            "  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
            "  e.team "
            "FROM elite_forwards e "
            "LEFT JOIN players p ON e.playerId = p.playerId "
            "WHERE e.is_carryover = 0",
            old,
        )
        def_ = pd.read_sql_query(
            "SELECT e.playerId, "
            "  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
            "  e.team, "
            "  CASE WHEN e.is_full_elite = 1 THEN 'Full Elite' "
            "       WHEN e.is_production = 1 THEN 'Production' "
            "       ELSE 'Deployment' END AS type "
            "FROM elite_defensemen e "
            "LEFT JOIN players p ON e.playerId = p.playerId "
            "WHERE e.is_carryover = 0",
            old,
        )
        old.close()
        return fwd, def_
    except Exception:
        return pd.DataFrame(columns=["playerId", "playerName", "team"]), \
               pd.DataFrame(columns=["playerId", "playerName", "team", "type"])


def _log_elite_changes(old_fwd, old_def, conn, changelog_path=None):
    """Compare old vs new elite sets and append changes to a CSV changelog.

    Args:
        old_fwd: DataFrame with playerId, playerName, team from previous build
        old_def: DataFrame with playerId, playerName, team, type from previous build
        conn: connection to the newly built league.db
        changelog_path: path to CSV file (defaults to elite_changelog.csv next to OUTPUT_DB)
    """
    if changelog_path is None:
        changelog_path = os.path.join(os.path.dirname(OUTPUT_DB), "elite_changelog.csv")

    today = date.today().isoformat()
    changes = []

    # --- Forwards ---
    new_fwd = pd.read_sql_query(
        "SELECT e.playerId, "
        "  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
        "  e.team "
        "FROM elite_forwards e "
        "LEFT JOIN players p ON e.playerId = p.playerId "
        "WHERE e.is_carryover = 0",
        conn,
    )

    old_fwd_keys = set(zip(old_fwd["playerId"], old_fwd["team"])) if not old_fwd.empty else set()
    new_fwd_keys = set(zip(new_fwd["playerId"], new_fwd["team"])) if not new_fwd.empty else set()
    new_fwd_lookup = {(r["playerId"], r["team"]): r["playerName"] for _, r in new_fwd.iterrows()} if not new_fwd.empty else {}
    old_fwd_lookup = {(r["playerId"], r["team"]): r["playerName"] for _, r in old_fwd.iterrows()} if not old_fwd.empty else {}

    for pid, team in new_fwd_keys - old_fwd_keys:
        changes.append({"date": today, "playerId": pid, "playerName": new_fwd_lookup[(pid, team)],
                         "team": team, "position": "F", "type": "Elite", "action": "added"})
    for pid, team in old_fwd_keys - new_fwd_keys:
        changes.append({"date": today, "playerId": pid, "playerName": old_fwd_lookup[(pid, team)],
                         "team": team, "position": "F", "type": "Elite", "action": "removed"})

    # --- Defensemen ---
    new_def = pd.read_sql_query(
        "SELECT e.playerId, "
        "  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
        "  e.team, "
        "  CASE WHEN e.is_full_elite = 1 THEN 'Full Elite' "
        "       WHEN e.is_production = 1 THEN 'Production' "
        "       ELSE 'Deployment' END AS type "
        "FROM elite_defensemen e "
        "LEFT JOIN players p ON e.playerId = p.playerId "
        "WHERE e.is_carryover = 0",
        conn,
    )

    old_def_keys = set(zip(old_def["playerId"], old_def["team"])) if not old_def.empty else set()
    new_def_keys = set(zip(new_def["playerId"], new_def["team"])) if not new_def.empty else set()
    new_def_lookup = {(r["playerId"], r["team"]): (r["playerName"], r["type"]) for _, r in new_def.iterrows()} if not new_def.empty else {}
    old_def_lookup = {(r["playerId"], r["team"]): (r["playerName"], r["type"]) for _, r in old_def.iterrows()} if not old_def.empty else {}

    for pid, team in new_def_keys - old_def_keys:
        name, dtype = new_def_lookup[(pid, team)]
        changes.append({"date": today, "playerId": pid, "playerName": name,
                         "team": team, "position": "D", "type": dtype, "action": "added"})
    for pid, team in old_def_keys - new_def_keys:
        name, dtype = old_def_lookup[(pid, team)]
        changes.append({"date": today, "playerId": pid, "playerName": name,
                         "team": team, "position": "D", "type": dtype, "action": "removed"})
    # Type changes (same player+team, different designation)
    for pid, team in old_def_keys & new_def_keys:
        old_type = old_def_lookup[(pid, team)][1]
        new_name, new_type = new_def_lookup[(pid, team)]
        if old_type != new_type:
            changes.append({"date": today, "playerId": pid, "playerName": new_name,
                             "team": team, "position": "D", "type": new_type,
                             "action": f"{old_type} → {new_type}"})

    if not changes:
        return

    change_df = pd.DataFrame(changes, columns=["date", "playerId", "playerName",
                                                 "team", "position", "type", "action"])
    header = not os.path.exists(changelog_path)
    change_df.to_csv(changelog_path, mode="a", index=False, header=header)
    print(f"  elite_changelog: {len(changes)} changes logged to {changelog_path}")


def main():
    os.makedirs(os.path.dirname(OUTPUT_DB), exist_ok=True)

    # Snapshot old elite sets before deleting the DB
    old_fwd, old_def = _read_old_elites(OUTPUT_DB)

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
        build_elite_defensemen_table(conn)
        recompute_pct_vs_elite_def(conn)
        backfill_vs_elite_def_to_forwards(conn)
        build_player_metrics_table(conn)
        _log_elite_changes(old_fwd, old_def, conn)
    finally:
        conn.close()
    size_mb = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print(f"\nDone. Database: {OUTPUT_DB} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
