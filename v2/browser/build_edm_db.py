"""
Build a SQLite database of Edmonton Oilers 2025 season data for Datasette browsing.

Creates 6 tables:
  - games: one row per EDM game with result
  - players: current EDM roster
  - player_game_stats: per-game stats for EDM players (skaters + goalies)
  - plays: flat play-by-play events for EDM games
  - shifts: shift-level data for EDM games
  - timelines: second-by-second situation timelines for EDM games

Usage:
    python v2/browser/build_edm_db.py
"""

import json
import os
import sqlite3
import glob

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TEAM_ABBREV = "EDM"
SEASON_DIR = "data/2025"
OUTPUT_DB = os.path.join(SEASON_DIR, "generated", "browser", "edm.db")
FLAT_BOXSCORES = os.path.join(SEASON_DIR, "generated", "flatboxscores", "boxscores.csv")
PLAYERS_CSV = os.path.join(SEASON_DIR, "generated", "players", "csv", "players.csv")
BOXSCORES_DIR = os.path.join(SEASON_DIR, "boxscores")
FLATPLAYS_DIR = os.path.join(SEASON_DIR, "generated", "flatplays")
SHIFTS_DIR = os.path.join(SEASON_DIR, "shifts")
TIMELINES_DIR = os.path.join(SEASON_DIR, "generated", "timelines", "csv")


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def build_games_table(conn):
    """Build the games table from flat boxscores. Returns set of EDM game IDs."""
    df = pd.read_csv(FLAT_BOXSCORES)
    edm = df[(df["awayTeam_abbrev"] == TEAM_ABBREV) | (df["homeTeam_abbrev"] == TEAM_ABBREV)].copy()

    # Already one row per game. periodDescriptor_number is the max period played.
    edm["gameId"] = edm["id"]
    edm["periodCount"] = edm["periodDescriptor_number"].astype(int)

    edm["homeAway"] = edm.apply(
        lambda r: "home" if r["homeTeam_abbrev"] == TEAM_ABBREV else "away", axis=1
    )
    edm["opponent"] = edm.apply(
        lambda r: r["awayTeam_abbrev"] if r["homeAway"] == "home" else r["homeTeam_abbrev"], axis=1
    )
    edm["edmGoals"] = edm.apply(
        lambda r: int(r["homeTeam_score"]) if r["homeAway"] == "home" else int(r["awayTeam_score"]), axis=1
    )
    edm["oppGoals"] = edm.apply(
        lambda r: int(r["awayTeam_score"]) if r["homeAway"] == "home" else int(r["homeTeam_score"]), axis=1
    )

    def result(r):
        if r["edmGoals"] > r["oppGoals"]:
            return "W"
        elif r["periodCount"] > 3:
            return "OTL"
        else:
            return "L"

    edm["result"] = edm.apply(result, axis=1)

    out = edm[["gameId", "gameDate", "opponent", "homeAway", "edmGoals", "oppGoals", "result", "periodCount"]]
    out.to_sql("games", conn, if_exists="replace", index=False)
    print(f"  games: {len(out)} rows")
    return set(out["gameId"].astype(int))


def build_players_table(conn):
    """Build the players table from the players CSV (EDM roster only)."""
    df = pd.read_csv(PLAYERS_CSV)
    edm = df[df["currentTeamAbbrev"] == TEAM_ABBREV].copy()

    keep = [
        "playerId", "firstName", "lastName", "sweaterNumber", "position",
        "heightInInches", "weightInPounds", "birthDate", "birthCountry",
        "shootsCatches", "draftYear", "draftTeam", "draftRound", "draftPick", "draftOverall",
    ]
    out = edm[keep]
    out.to_sql("players", conn, if_exists="replace", index=False)
    print(f"  players: {len(out)} rows")


def build_player_game_stats_table(conn, edm_game_ids):
    """Build per-game player stats for EDM players from raw boxscore JSONs."""
    rows = []
    for game_id in sorted(edm_game_ids):
        path = os.path.join(BOXSCORES_DIR, f"{game_id}.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)

        # Determine which side is EDM
        if data["homeTeam"]["abbrev"] == TEAM_ABBREV:
            side = "homeTeam"
        elif data["awayTeam"]["abbrev"] == TEAM_ABBREV:
            side = "awayTeam"
        else:
            continue

        stats = data["playerByGameStats"][side]

        # Process skaters (forwards + defense)
        for group in ("forwards", "defense"):
            for p in stats.get(group, []):
                rows.append({
                    "gameId": game_id,
                    "playerId": p["playerId"],
                    "name": p["name"]["default"],
                    "position": p["position"],
                    "goals": p.get("goals"),
                    "assists": p.get("assists"),
                    "points": p.get("points"),
                    "plusMinus": p.get("plusMinus"),
                    "pim": p.get("pim"),
                    "hits": p.get("hits"),
                    "powerPlayGoals": p.get("powerPlayGoals"),
                    "sog": p.get("sog"),
                    "faceoffWinningPctg": p.get("faceoffWinningPctg"),
                    "toi": p.get("toi"),
                    "blockedShots": p.get("blockedShots"),
                    "shifts": p.get("shifts"),
                    "giveaways": p.get("giveaways"),
                    "takeaways": p.get("takeaways"),
                    # Goalie-specific fields null for skaters
                    "goalsAgainst": None,
                    "savePctg": None,
                    "saveShotsAgainst": None,
                })

        # Process goalies
        for p in stats.get("goalies", []):
            rows.append({
                "gameId": game_id,
                "playerId": p["playerId"],
                "name": p["name"]["default"],
                "position": p["position"],
                # Skater-specific fields null for goalies
                "goals": None,
                "assists": None,
                "points": None,
                "plusMinus": None,
                "hits": None,
                "powerPlayGoals": None,
                "sog": None,
                "faceoffWinningPctg": None,
                "blockedShots": None,
                "shifts": None,
                "giveaways": None,
                "takeaways": None,
                # Shared
                "pim": p.get("pim"),
                "toi": p.get("toi"),
                # Goalie-specific
                "goalsAgainst": p.get("goalsAgainst"),
                "savePctg": p.get("savePctg"),
                "saveShotsAgainst": p.get("saveShotsAgainst"),
            })

    df = pd.DataFrame(rows)
    df.to_sql("player_game_stats", conn, if_exists="replace", index=False)
    print(f"  player_game_stats: {len(df)} rows")


def build_plays_table(conn, edm_game_ids):
    """Load flat play CSVs for EDM games into the plays table."""
    frames = []
    for game_id in sorted(edm_game_ids):
        path = os.path.join(FLATPLAYS_DIR, f"{game_id}.csv")
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, dtype=str)
        df.insert(0, "gameId", str(game_id))
        frames.append(df)

    if frames:
        out = pd.concat(frames, ignore_index=True)
        out.to_sql("plays", conn, if_exists="replace", index=False)
        print(f"  plays: {len(out)} rows")
    else:
        print("  plays: 0 rows (no data found)")


def build_shifts_table(conn, edm_game_ids):
    """Parse shift JSONs for EDM games into the shifts table."""
    rows = []
    for game_id in sorted(edm_game_ids):
        for suffix in ("home", "away"):
            path = os.path.join(SHIFTS_DIR, f"{game_id}_{suffix}.json")
            if not os.path.exists(path):
                continue
            with open(path) as f:
                data = json.load(f)

            team_abbrev = data.get("team", {}).get("abbrev", "")
            team_type = data.get("teamType", "")

            for player in data.get("players", []):
                sweater_number = player.get("number")
                player_name = player.get("name")
                for shift in player.get("shifts", []):
                    rows.append({
                        "gameId": game_id,
                        "teamAbbrev": team_abbrev,
                        "teamType": team_type,
                        "sweaterNumber": sweater_number,
                        "playerName": player_name,
                        "shiftNumber": shift.get("shiftNumber"),
                        "period": shift.get("period"),
                        "startTime": shift.get("startTime"),
                        "endTime": shift.get("endTime"),
                        "duration": shift.get("duration"),
                        "event": shift.get("event"),
                    })

    df = pd.DataFrame(rows)
    df.to_sql("shifts", conn, if_exists="replace", index=False)
    print(f"  shifts: {len(df)} rows")


def build_timelines_table(conn, edm_game_ids):
    """Load timeline CSVs for EDM games into the timelines table."""
    frames = []
    for game_id in sorted(edm_game_ids):
        path = os.path.join(TIMELINES_DIR, f"{game_id}.csv")
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, dtype=str)
        df.insert(0, "gameId", str(game_id))
        frames.append(df)

    if frames:
        out = pd.concat(frames, ignore_index=True)
        out.to_sql("timelines", conn, if_exists="replace", index=False)
        print(f"  timelines: {len(out)} rows")
    else:
        print("  timelines: 0 rows (no data found)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Create output directory
    os.makedirs(os.path.dirname(OUTPUT_DB), exist_ok=True)

    # Remove existing database
    if os.path.exists(OUTPUT_DB):
        os.remove(OUTPUT_DB)
        print(f"Removed existing {OUTPUT_DB}")

    conn = sqlite3.connect(OUTPUT_DB)
    print(f"Building {OUTPUT_DB} ...\n")

    edm_game_ids = build_games_table(conn)
    build_players_table(conn)
    build_player_game_stats_table(conn, edm_game_ids)
    build_plays_table(conn, edm_game_ids)
    build_shifts_table(conn, edm_game_ids)
    build_timelines_table(conn, edm_game_ids)

    conn.close()
    size_mb = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print(f"\nDone. Database: {OUTPUT_DB} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
