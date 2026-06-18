"""
Build a league-wide SQLite database for the NHL Data Browser.

Creates 8 tables:
  - competition:      all rows from data/<season>/generated/competition/*.csv
  - players:          from data/<season>/generated/players/csv/players.csv
  - games:            from data/<season>/generated/flatboxscores/boxscores.csv
  - points_5v5:       5v5 goals/assists from flatplays CSVs
  - elite_forwards:   per-team elite forward classification (tTOI%, iTOI%, P/60 model)
  - elite_defensemen: per-team elite defensemen (production + deployment designations)
  - player_metrics:   PPI, PPI+, wPPI, wPPI+, avg_toi_share per eligible skater (GP >= 5)
  - constants:        scalar league-wide values used as fixed denominators in the browser
                      (e.g. league_mean_team_wppi — the full-season baseline for team wPPI+)

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


def count_5v5_events(df, game_id):
    """Count per-player 5v5 hits/blocks/takeaways/giveaways for one game's flatplays."""
    five_v_five = df[df["situationCode"].astype(str).isin(FIVE_V_FIVE)]
    counts = {}  # playerId -> dict

    def _bump(pid_val, key):
        if pd.notna(pid_val):
            pid = int(pid_val)
            row = counts.setdefault(pid, {"hits": 0, "blocks": 0, "takeaways": 0, "giveaways": 0})
            row[key] += 1

    for _, r in five_v_five.iterrows():
        t = r["typeDescKey"]
        if t == "hit":
            _bump(r.get("details.hittingPlayerId"), "hits")
        elif t == "blocked-shot":
            _bump(r.get("details.blockingPlayerId"), "blocks")
        elif t == "takeaway":
            _bump(r.get("details.playerId"), "takeaways")
        elif t == "giveaway":
            _bump(r.get("details.playerId"), "giveaways")

    records = [{"gameId": game_id, "playerId": pid, **vals} for pid, vals in counts.items()]
    return pd.DataFrame(records, columns=["gameId", "playerId", "hits", "blocks", "takeaways", "giveaways"])


def build_events_5v5_table(conn):
    """Per-game 5v5 individual event counts from flattened plays."""
    frames = []
    for path in sorted(glob.glob(os.path.join(FLATPLAYS_DIR, "*.csv"))):
        game_id = int(os.path.basename(path).replace(".csv", ""))
        df = pd.read_csv(path, low_memory=False)
        game_df = count_5v5_events(df, game_id)
        if not game_df.empty:
            frames.append(game_df)
    if not frames:
        pd.DataFrame(columns=["gameId", "playerId", "hits", "blocks", "takeaways", "giveaways"]).to_sql(
            "events_5v5", conn, if_exists="replace", index=False
        )
        print("  events_5v5: 0 rows (no flatplays found)")
        return
    out = pd.concat(frames, ignore_index=True)
    out.to_sql("events_5v5", conn, if_exists="replace", index=False)
    print(f"  events_5v5: {len(out)} rows from {len(frames)} games")


def build_elite_forwards_table(conn):
    """League-wide elite forwards: production gate + 2-of-3 deployment, 80/20 blend.

    Production gate (required):
      - weighted P/60 ≥ 2.3

    Deployment qualification (2-of-3 required):
      - DPL    ≤ 2.5  (avg line assignment — lower is better)
      - tTOI%  ≥ 28%  (share of team 5v5 ice time)
      - iTOI%  < 83%  (fraction of total TOI at 5v5 — plays special teams)

    Three-phase logic based on total GP (across all teams):
      Phase 1 (GP < 10):   no designation
      Phase 2 (10–19 GP):  full-season values only, l20_* stored as NULL
      Phase 3 (≥ 20 GP):   80/20 blend: metric = fs_metric * 0.8 + l20_metric * 0.2

    "Last 20 games" is player-specific (their last 20 games played, across all teams).
    """
    # ---- Load per-game forward data with per-game team totals ----
    comp = pd.read_sql_query(
        """
        WITH tt AS (
            SELECT gameId, team, SUM(toi_seconds) AS team_total
            FROM competition WHERE position IN ('F', 'D')
            GROUP BY gameId, team
        )
        SELECT c.playerId, c.team, c.gameId,
               c.toi_seconds, c.total_toi_seconds, c.line_number,
               COALESCE(c.deployment_score, 0) AS deployment_score,
               5.0 * c.toi_seconds / tt.team_total AS ttoi_frac
        FROM competition c
        JOIN tt ON tt.gameId = c.gameId AND tt.team = c.team
        WHERE c.position = 'F'
        """,
        conn,
    )
    _COLS = [
        "playerId", "team", "gp", "toi_min_gp",
        "fs_p60", "l20_p60", "weighted_p60",
        "fs_dpl", "l20_dpl", "weighted_dpl",
        "fs_ttoi_pct", "l20_ttoi_pct", "weighted_ttoi_pct",
        "fs_itoi_pct", "l20_itoi_pct", "weighted_itoi_pct",
        "weighted_dps_plus",
    ]
    if comp.empty:
        print("  elite_forwards: 0 rows (no forward competition data)")
        pd.DataFrame(columns=_COLS).to_sql(
            "elite_forwards", conn, if_exists="replace", index=False
        )
        return

    pts = pd.read_sql_query(
        "SELECT playerId, gameId, SUM(points) AS points FROM points_5v5 GROUP BY playerId, gameId",
        conn,
    )

    # Merge points into per-game data (one row per player per game per team)
    gd = comp.merge(pts, on=["playerId", "gameId"], how="left")
    gd["points"] = gd["points"].fillna(0)
    gd = gd.sort_values(["playerId", "gameId"]).reset_index(drop=True)

    # Pre-index player's full game sequence for last-20 slicing
    player_games = (
        gd.groupby("playerId")["gameId"]
        .apply(lambda s: sorted(s.unique()))
        .to_dict()
    )

    records = []
    for (pid, team), grp in gd.groupby(["playerId", "team"]):
        gp = grp["gameId"].nunique()
        if gp < 10:  # Phase 1
            continue

        # Full-season metrics for this (player, team)
        fs_toi     = grp["toi_seconds"].sum()
        fs_all_toi = grp["total_toi_seconds"].sum()
        fs_pts     = grp["points"].sum()
        fs_p60        = fs_pts * 3600.0 / fs_toi if fs_toi > 0 else 0.0
        fs_ttoi_pct   = float(grp["ttoi_frac"].mean()) * 100.0
        fs_itoi_pct   = fs_toi * 100.0 / fs_all_toi if fs_all_toi > 0 else 0.0
        fs_dpl_raw    = grp["line_number"].dropna()
        fs_dpl        = float(fs_dpl_raw.mean()) if not fs_dpl_raw.empty else None
        fs_depl_raw   = grp["deployment_score"].dropna()
        fs_depl       = float(fs_depl_raw.mean()) if not fs_depl_raw.empty else None

        toi_min_gp = fs_toi / gp / 60.0

        # Last-20-games metrics (player-specific across all teams)
        all_player_game_ids = player_games.get(pid, [])
        total_player_gp = len(all_player_game_ids)  # player-wide, across all teams

        l20_p60 = l20_ttoi_pct = l20_itoi_pct = l20_dpl = l20_depl = None

        if total_player_gp >= 20:
            last20 = set(all_player_game_ids[-20:])
            l20_rows = gd[(gd["playerId"] == pid) & (gd["gameId"].isin(last20))]
            l20_toi     = l20_rows["toi_seconds"].sum()
            l20_all_toi = l20_rows["total_toi_seconds"].sum()
            l20_pts     = l20_rows["points"].sum()
            l20_p60       = l20_pts * 3600.0 / l20_toi if l20_toi > 0 else 0.0
            l20_ttoi_pct  = float(l20_rows["ttoi_frac"].mean()) * 100.0
            l20_itoi_pct  = l20_toi * 100.0 / l20_all_toi if l20_all_toi > 0 else 0.0
            l20_dpl_raw   = l20_rows["line_number"].dropna()
            l20_dpl       = float(l20_dpl_raw.mean()) if not l20_dpl_raw.empty else None
            l20_depl_raw  = l20_rows["deployment_score"].dropna()
            l20_depl      = float(l20_depl_raw.mean()) if not l20_depl_raw.empty else None

        # Weighted metrics
        if total_player_gp >= 20:
            weighted_p60      = fs_p60 * 0.8 + l20_p60 * 0.2
            weighted_ttoi_pct = fs_ttoi_pct * 0.8 + l20_ttoi_pct * 0.2
            weighted_itoi_pct = fs_itoi_pct * 0.8 + l20_itoi_pct * 0.2
            if fs_dpl is not None and l20_dpl is not None:
                weighted_dpl = fs_dpl * 0.8 + l20_dpl * 0.2
            else:
                weighted_dpl = fs_dpl  # fall back to full-season if l20 unavailable
            if fs_depl is not None and l20_depl is not None:
                weighted_depl = fs_depl * 0.8 + l20_depl * 0.2
            else:
                weighted_depl = fs_depl
        else:
            # Phase 2: full-season only
            weighted_p60      = fs_p60
            weighted_ttoi_pct = fs_ttoi_pct
            weighted_itoi_pct = fs_itoi_pct
            weighted_dpl      = fs_dpl
            weighted_depl     = fs_depl

        # Production gate
        if weighted_p60 < 2.3:
            continue

        # 2-of-3 deployment
        dpl_ok   = weighted_dpl is not None and weighted_dpl <= 2.5
        ttoi_ok  = weighted_ttoi_pct >= 28.0
        itoi_ok  = weighted_itoi_pct < 83.0

        if sum([dpl_ok, ttoi_ok, itoi_ok]) < 2:
            continue

        records.append({
            "playerId":          pid,
            "team":              team,
            "gp":                gp,
            "toi_min_gp":        round(toi_min_gp, 2),
            "fs_p60":            round(fs_p60, 4),
            "l20_p60":           round(l20_p60, 4) if l20_p60 is not None else None,
            "weighted_p60":      round(weighted_p60, 4),
            "fs_dpl":            round(fs_dpl, 4) if fs_dpl is not None else None,
            "l20_dpl":           round(l20_dpl, 4) if l20_dpl is not None else None,
            "weighted_dpl":      round(weighted_dpl, 4) if weighted_dpl is not None else None,
            "fs_ttoi_pct":       round(fs_ttoi_pct, 4),
            "l20_ttoi_pct":      round(l20_ttoi_pct, 4) if l20_ttoi_pct is not None else None,
            "weighted_ttoi_pct": round(weighted_ttoi_pct, 4),
            "fs_itoi_pct":       round(fs_itoi_pct, 4),
            "l20_itoi_pct":      round(l20_itoi_pct, 4) if l20_itoi_pct is not None else None,
            "weighted_itoi_pct": round(weighted_itoi_pct, 4),
            "weighted_depl":     round(weighted_depl, 4) if weighted_depl is not None else None,
        })

    if not records:
        print("  elite_forwards: 0 rows (no qualifying forwards)")
        pd.DataFrame(columns=_COLS).to_sql(
            "elite_forwards", conn, if_exists="replace", index=False
        )
        return

    out = pd.DataFrame(records)
    # Normalize weighted_dps_plus to league avg = 100 across qualifying forwards.
    # Forwards with all-null deployment_score get weighted_depl=0.0 (from COALESCE in SQL),
    # so weighted_dps_plus is 0/league_avg*100 — low but not NaN.
    fwd_league_avg = out["weighted_depl"].dropna().mean()
    if fwd_league_avg and fwd_league_avg > 0:
        out["weighted_dps_plus"] = out["weighted_depl"] / fwd_league_avg * 100
    else:
        out["weighted_dps_plus"] = None
    out[_COLS].to_sql("elite_forwards", conn, if_exists="replace", index=False)
    print(f"  elite_forwards: {len(out)} rows")


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
    """Identify elite defensemen using a league-wide threshold model.

    Gate (all required, GP >= 20):
      P/60   > 1.2   — production
      tTOI%  > 35%   — top-pair usage
      DPS+   > 120   — deployment difficulty (100 = league avg)

    Full-season stats only — no last-20 blend (points streaks unreliable for D).

    DPS+ normalization:
      avg_deploy = SUM(deployment_score) / gp   per player
      league_avg = mean(avg_deploy) across all D with GP >= 20
      dps_plus   = avg_deploy / league_avg * 100

    Output columns: playerId, team, gp, toi_min_gp, p60, ttoi_pct, dps_plus
    """
    _COLS = ["playerId", "team", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus", "dpl"]

    comp = pd.read_sql_query("""
        WITH tt AS (
            SELECT gameId, team, SUM(toi_seconds) AS team_total
            FROM competition WHERE position IN ('F', 'D')
            GROUP BY gameId, team
        )
        SELECT c.playerId, c.team, c.gameId,
               c.toi_seconds,
               COALESCE(c.deployment_score, 0) AS deployment_score,
               COALESCE(c.line_number, 4) AS line_number,
               5.0 * c.toi_seconds / tt.team_total AS ttoi_frac
        FROM competition c
        JOIN tt ON tt.gameId = c.gameId AND tt.team = c.team
        WHERE c.position = 'D'
    """, conn)

    pts = pd.read_sql_query(
        "SELECT playerId, gameId, SUM(points) AS points FROM points_5v5 GROUP BY playerId, gameId",
        conn,
    )

    def _empty():
        pd.DataFrame(columns=_COLS).to_sql(
            "elite_defensemen", conn, if_exists="replace", index=False
        )

    if comp.empty:
        _empty()
        print("  elite_defensemen: 0 rows (no competition data)")
        return

    gd = comp.merge(pts, on=["playerId", "gameId"], how="left")
    gd["points"] = gd["points"].fillna(0)

    rows = []
    for pid, grp in gd.groupby("playerId"):
        gp = grp["gameId"].nunique()
        if gp < 20:
            continue

        # Team = whichever team they played the most games for
        team = grp.groupby("team")["gameId"].nunique().idxmax()

        total_toi = grp["toi_seconds"].sum()
        total_pts = grp["points"].sum()

        p60        = total_pts * 3600.0 / total_toi if total_toi > 0 else 0.0
        ttoi_pct   = grp["ttoi_frac"].mean() * 100
        avg_deploy = grp["deployment_score"].mean()

        avg_pair = grp["line_number"].mean()
        rows.append({
            "playerId": pid, "team": team, "gp": gp,
            "toi_min_gp": round(total_toi / gp / 60, 2),
            "p60": p60, "ttoi_pct": ttoi_pct, "avg_deploy": avg_deploy,
            "dpl": round(avg_pair, 2),
        })

    if not rows:
        _empty()
        print("  elite_defensemen: 0 rows (no qualifying defensemen)")
        return

    df = pd.DataFrame(rows)

    # Normalize deployment scores → DPS+ (100 = league average)
    league_avg = df["avg_deploy"].mean()
    if league_avg and league_avg > 0:
        # Normalized against all qualifying D (GP >= 20), before elite gates.
        # The elite subset (dps_plus > 120) will have a mean well above 100 by design.
        df["dps_plus"] = df["avg_deploy"] / league_avg * 100
    else:
        df["dps_plus"] = 100.0

    # Apply gates (all three required)
    elite = df[
        (df["p60"] > 1.2) &
        (df["ttoi_pct"] > 35.0) &
        (df["dps_plus"] > 120.0)
    ].copy()

    if elite.empty:
        _empty()
        print("  elite_defensemen: 0 rows (no defensemen pass gates)")
        return

    elite[_COLS].to_sql("elite_defensemen", conn, if_exists="replace", index=False)
    print(f"  elite_defensemen: {len(elite)} rows")


def recompute_pct_vs_elite_def(conn):
    """Replace pct_vs_top_def with fraction of opposing defensemen who are deployment elite.

    Also computes pct_any_elite_def — a binary metric: for each second, 1 if any
    elite D is on the opposing side, 0 otherwise.  Averaged per game per player.
    """
    elite_rows = conn.execute(
        "SELECT playerId FROM elite_defensemen"
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



def build_constants_table(conn):
    """Compute and store league-wide scalar constants used as fixed denominators in the browser.

    league_mean_team_wppi:
        For each team-game, sums (ppi_plus × toi_seconds) across all eligible skaters.
        Averages that raw score across each team's games → team wPPI.
        Takes the mean across all 32 teams → the fixed denominator for team wPPI+.

    Stored as key/value rows in the constants table.
    """
    comp = pd.read_sql_query(
        "SELECT playerId, team, gameId, toi_seconds FROM competition WHERE position IN ('F', 'D')",
        conn,
    )
    metrics = pd.read_sql_query("SELECT playerId, ppi_plus FROM player_metrics", conn)
    if comp.empty or metrics.empty:
        print("  constants: SKIPPED (no competition or player_metrics data)")
        return

    comp = comp.merge(metrics, on="playerId", how="inner")
    comp["raw_score"] = comp["ppi_plus"] * comp["toi_seconds"]

    # Per team-game: sum of raw scores. Per team: mean across games.
    team_game = comp.groupby(["team", "gameId"])["raw_score"].sum().reset_index()
    team_wppi = team_game.groupby("team")["raw_score"].mean()
    league_mean = float(team_wppi.mean())

    pd.DataFrame([{"key": "league_mean_team_wppi", "value": round(league_mean, 4)}]).to_sql(
        "constants", conn, if_exists="replace", index=False
    )
    print(f"  constants: league_mean_team_wppi = {league_mean:.2f}")


def _read_old_elites(db_path):
    """Read current elite sets from an existing league.db before it is deleted.

    Returns (fwd_df, def_df) — primary rows only (excludes carry-overs if schema has them).
    Each DataFrame has columns: playerId, playerName, team.
    def_df also has a 'type' column: Full Elite / Production / Deployment.
    Returns empty DataFrames if the DB doesn't exist or tables are missing.
    """
    if not os.path.exists(db_path):
        return pd.DataFrame(columns=["playerId", "playerName", "team"]), \
               pd.DataFrame(columns=["playerId", "playerName", "team", "type"])
    try:
        old = sqlite3.connect(db_path)
        try:
            # Check if old schema has is_carryover (v1) or not (v2)
            fwd_cols = {row[1] for row in old.execute("PRAGMA table_info(elite_forwards)").fetchall()}
            carryover_filter = "WHERE e.is_carryover = 0" if "is_carryover" in fwd_cols else ""
            fwd = pd.read_sql_query(
                f"SELECT e.playerId, "
                f"  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
                f"  e.team "
                f"FROM elite_forwards e "
                f"LEFT JOIN players p ON e.playerId = p.playerId "
                f"{carryover_filter}",
                old,
            )
            def_cols = {row[1] for row in old.execute("PRAGMA table_info(elite_defensemen)").fetchall()}
            def_carryover = "WHERE e.is_carryover = 0" if "is_carryover" in def_cols else ""
            if "is_full_elite" in def_cols:
                type_expr = (
                    "CASE WHEN e.is_full_elite = 1 THEN 'Full Elite' "
                    "     WHEN e.is_production = 1 THEN 'Production' "
                    "     ELSE 'Deployment' END"
                )
            else:
                type_expr = "'Elite'"
            def_ = pd.read_sql_query(
                f"SELECT e.playerId, "
                f"  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
                f"  e.team, "
                f"  {type_expr} AS type "
                f"FROM elite_defensemen e "
                f"LEFT JOIN players p ON e.playerId = p.playerId "
                f"{def_carryover}",
                old,
            )
            return fwd, def_
        finally:
            old.close()
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
    # v2 schema: no is_carryover column for elite_forwards
    new_fwd = pd.read_sql_query(
        "SELECT e.playerId, "
        "  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
        "  e.team "
        "FROM elite_forwards e "
        "LEFT JOIN players p ON e.playerId = p.playerId",
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
    # Check whether the new DB's elite_defensemen has type-designation columns (v1 schema)
    # or uses the single-tier v2 schema. Use CASE only if the columns exist.
    new_def_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(elite_defensemen)").fetchall()
    }
    if "is_full_elite" in new_def_cols:
        def_type_expr = (
            "CASE WHEN e.is_full_elite = 1 THEN 'Full Elite' "
            "     WHEN e.is_production = 1 THEN 'Production' "
            "     ELSE 'Deployment' END"
        )
    else:
        def_type_expr = "'Elite'"
    new_def = pd.read_sql_query(
        "SELECT e.playerId, "
        "  COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName, "
        f"  e.team, {def_type_expr} AS type "
        "FROM elite_defensemen e "
        "LEFT JOIN players p ON e.playerId = p.playerId",
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
        build_events_5v5_table(conn)
        build_elite_forwards_table(conn)
        recompute_pct_vs_elite_fwd(conn)
        build_elite_defensemen_table(conn)
        recompute_pct_vs_elite_def(conn)
        build_player_metrics_table(conn)
        build_constants_table(conn)
        _log_elite_changes(old_fwd, old_def, conn)
    finally:
        conn.close()
    size_mb = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print(f"\nDone. Database: {OUTPUT_DB} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
