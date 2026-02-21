#!/usr/bin/env python3
"""
NHL Competition Score Generator

Computes per-skater competition scores for a single game based on
the mean game 5v5 TOI of opposing forwards and defensemen.

Usage:
    python v2/competition/compute_competition.py <game_number> <season>

Example:
    python v2/competition/compute_competition.py 1 2025
    → writes data/2025/generated/competition/2025020001.csv
"""

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

DATA_DIR = Path("data")
SCORED_SITUATIONS = {"1551", "0651", "1560"}
GAME_TYPE = "02"

_POSITION_MAP = {"C": "F", "L": "F", "R": "F", "D": "D", "G": "G"}


def build_lookups(plays_data: dict) -> Tuple[Dict[int, str], Dict[int, str]]:
    """
    Build position and team lookups from plays JSON rosterSpots.

    Returns:
        positions: {playerId: 'F', 'D', or 'G'}
        teams:     {playerId: teamAbbrev}
    """
    team_map = {
        plays_data["homeTeam"]["id"]: plays_data["homeTeam"]["abbrev"],
        plays_data["awayTeam"]["id"]: plays_data["awayTeam"]["abbrev"],
    }

    positions: Dict[int, str] = {}
    teams: Dict[int, str] = {}

    for spot in plays_data.get("rosterSpots", []):
        pid = spot["playerId"]
        code = spot.get("positionCode", "")
        positions[pid] = _POSITION_MAP.get(code, "F")  # unknown → F per design
        teams[pid] = team_map.get(spot["teamId"], "")

    return positions, teams


def compute_game_toi(rows: List[dict]) -> Dict[int, int]:
    """
    Count 5v5 seconds on ice per skater.

    Args:
        rows: list of timeline row dicts (all rows, not pre-filtered)

    Returns:
        {playerId: seconds}
    """
    toi: Dict[int, int] = {}
    for row in rows:
        if row["situationCode"] not in SCORED_SITUATIONS:
            continue
        for col in ("awaySkaters", "homeSkaters"):
            raw = row.get(col, "")
            if not raw:
                continue
            for pid_str in raw.split("|"):
                pid = int(pid_str)
                toi[pid] = toi.get(pid, 0) + 1
    return toi


def score_game(
    rows: List[dict],
    toi: Dict[int, int],
    positions: Dict[int, str],
) -> Dict[int, dict]:
    """
    For every skater in every 5v5 second, accumulate the mean opposing
    forward and defense TOI.

    Returns:
        {playerId: {"side": "home"|"away", "comp_fwd": float, "comp_def": float}}
    """
    # accum[playerId] = {"side": str, "fwd_vals": [...], "def_vals": [...]}
    accum: Dict[int, dict] = {}

    for row in rows:
        if row["situationCode"] not in SCORED_SITUATIONS:
            continue

        away = [int(p) for p in row["awaySkaters"].split("|")] if row.get("awaySkaters") else []
        home = [int(p) for p in row["homeSkaters"].split("|")] if row.get("homeSkaters") else []

        for player_id, opponents, side in (
            [(p, home, "away") for p in away] +
            [(p, away, "home") for p in home]
        ):
            if positions.get(player_id, "F") == "G":
                continue  # skip goalies that appear in skater columns (data quality guard)

            if player_id not in accum:
                accum[player_id] = {"side": side, "fwd_vals": [], "def_vals": []}

            opp_fwd = [toi.get(p, 0) for p in opponents if positions.get(p, "F") == "F"]
            opp_def = [toi.get(p, 0) for p in opponents if positions.get(p, "F") == "D"]

            if opp_fwd:
                accum[player_id]["fwd_vals"].append(sum(opp_fwd) / len(opp_fwd))
            if opp_def:
                accum[player_id]["def_vals"].append(sum(opp_def) / len(opp_def))

    # Compute final means
    result: Dict[int, dict] = {}
    for pid, data in accum.items():
        fwd_vals = data["fwd_vals"]
        def_vals = data["def_vals"]
        result[pid] = {
            "side": data["side"],
            "comp_fwd": sum(fwd_vals) / len(fwd_vals) if fwd_vals else 0.0,
            "comp_def": sum(def_vals) / len(def_vals) if def_vals else 0.0,
        }

    return result


def load_timeline(season: str, game_id: str) -> List[dict]:
    """Load timeline CSV, return list of row dicts."""
    path = DATA_DIR / season / "generated" / "timelines" / "csv" / f"{game_id}.csv"
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_plays(season: str, game_id: str) -> dict:
    """Load plays JSON for a game."""
    path = DATA_DIR / season / "plays" / f"{game_id}.json"
    with open(path) as f:
        return json.load(f)


def write_output(game_id: str, season: str, scores: Dict[int, dict],
                 toi: Dict[int, int], positions: Dict[int, str],
                 teams: Dict[int, str]) -> Path:
    """Write per-player competition scores to CSV."""
    out_dir = DATA_DIR / season / "generated" / "competition"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{game_id}.csv"

    rows = []
    for pid, data in scores.items():
        rows.append({
            "gameId":      game_id,
            "playerId":    pid,
            "team":        teams.get(pid, ""),
            "position":    positions.get(pid, "F"),
            "toi_seconds": toi.get(pid, 0),
            "comp_fwd":    round(data["comp_fwd"], 2),
            "comp_def":    round(data["comp_def"], 2),
        })

    rows.sort(key=lambda r: r["toi_seconds"], reverse=True)

    fieldnames = ["gameId", "playerId", "team", "position", "toi_seconds", "comp_fwd", "comp_def"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return out_path


def run_game(game_number: int, season: str) -> Path:
    """Full pipeline for a single game. Returns path to output CSV."""
    game_id = f"{season}{GAME_TYPE}{game_number:04d}"

    plays_data = load_plays(season, game_id)
    positions, teams = build_lookups(plays_data)

    timeline_rows = load_timeline(season, game_id)
    toi = compute_game_toi(timeline_rows)
    scores = score_game(timeline_rows, toi, positions)

    return write_output(game_id, season, scores, toi, positions, teams)


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python v2/competition/compute_competition.py <game_number> <season>")
        print("  python v2/competition/compute_competition.py <start> <end> <season>")
        print("\nExamples:")
        print("  python v2/competition/compute_competition.py 1 2025")
        print("  python v2/competition/compute_competition.py 1 900 2025")
        sys.exit(1)

    if len(sys.argv) == 3:
        # Single game mode
        try:
            game_number = int(sys.argv[1])
        except ValueError:
            print("Error: game_number must be an integer")
            sys.exit(1)
        season = sys.argv[2]

        out_path = run_game(game_number, season)
        print(f"Written: {out_path}")
    else:
        # Batch mode
        start = int(sys.argv[1])
        end = int(sys.argv[2])
        season = sys.argv[3]

        succeeded = 0
        failed = 0

        for game_number in range(start, end + 1):
            try:
                out_path = run_game(game_number, season)
                print(f"Written: {out_path}")
                succeeded += 1
            except Exception as e:
                print(f"Error processing game {game_number}: {e}")
                failed += 1

        print(f"\nBatch complete: {succeeded} succeeded, {failed} failed")
        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
