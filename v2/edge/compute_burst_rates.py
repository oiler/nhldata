"""Compute per-player bursts-over-20mph per 60 minutes of all-strengths TOI.

Inputs: cached EDGE skater-detail JSONs + league.db competition table.
Output: data/2025/generated/edge/player_bursts.csv
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd


def list_skater_ids(db_path: Path) -> list[int]:
    """Return distinct playerIds from the competition table."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT DISTINCT playerId FROM competition ORDER BY playerId"
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def get_player_season_totals(db_path: Path) -> dict[int, dict]:
    """Return per-player season totals: GP, total_toi_seconds, name, position.

    Joins competition with players for human-readable name and roster position.
    """
    con = sqlite3.connect(db_path)
    try:
        sql = """
        SELECT c.playerId,
               COUNT(*) AS gp,
               SUM(c.total_toi_seconds) AS total_toi_seconds,
               COALESCE(p.firstName || ' ' || p.lastName, '?') AS name,
               COALESCE(p.position, '?') AS position
        FROM competition c
        LEFT JOIN players p ON p.playerId = c.playerId
        GROUP BY c.playerId
        """
        rows = con.execute(sql).fetchall()
    finally:
        con.close()
    return {
        pid: {"gp": gp, "total_toi_seconds": toi, "name": name, "position": pos}
        for pid, gp, toi, name, pos in rows
    }


def extract_edge_fields(payload: dict) -> dict:
    """Pull the fields we care about out of a skater-detail JSON payload.

    Returns None for any field that's missing — the EDGE endpoint occasionally
    omits sub-blocks for players with very little ice time.
    """
    skating = payload.get("skatingSpeed") or {}
    bursts = skating.get("burstsOver20") or {}
    speed_max = skating.get("speedMax") or {}
    distance = payload.get("totalDistanceSkated") or {}
    team = (payload.get("player") or {}).get("team") or {}

    return {
        "bursts_over_20":   bursts.get("value"),
        "speed_max_mph":    speed_max.get("imperial"),
        "distance_miles":   distance.get("imperial"),
        "current_team":     team.get("abbrev"),
    }


def bursts_per_60(bursts: int | None, total_toi_seconds: int | None) -> float | None:
    """Convert season bursts + season TOI into a per-60-minute rate."""
    if bursts is None or total_toi_seconds is None or total_toi_seconds == 0:
        return None
    return bursts * 3600.0 / total_toi_seconds


def build_burst_table(db_path: Path, edge_dir: Path) -> pd.DataFrame:
    """Join cached EDGE payloads with league.db season totals into one table.

    Players present in league.db but missing an EDGE JSON file are included
    with None for EDGE-derived fields. This makes coverage gaps visible.
    """
    totals = get_player_season_totals(db_path)
    rows = []
    for pid, totals_row in totals.items():
        edge_path = edge_dir / f"{pid}.json"
        if edge_path.exists():
            payload = json.loads(edge_path.read_text())
            edge_fields = extract_edge_fields(payload)
        else:
            edge_fields = {
                "bursts_over_20": None, "speed_max_mph": None,
                "distance_miles": None, "current_team": None,
            }
        rows.append({
            "playerId":          pid,
            "name":              totals_row["name"],
            "position":          totals_row["position"],
            "current_team":      edge_fields["current_team"],
            "gp":                totals_row["gp"],
            "total_toi_seconds": totals_row["total_toi_seconds"],
            "bursts_over_20":    edge_fields["bursts_over_20"],
            "speed_max_mph":     edge_fields["speed_max_mph"],
            "distance_miles":    edge_fields["distance_miles"],
            "bursts_per_60":     bursts_per_60(
                                    edge_fields["bursts_over_20"],
                                    totals_row["total_toi_seconds"],
                                 ),
        })
    return pd.DataFrame(rows)


DB_PATH        = Path("data/2025/generated/browser/league.db")
EDGE_DIR       = Path("data/2025/edge/skater_detail")
OUTPUT_DIR     = Path("data/2025/generated/edge")
OUTPUT_CSV     = OUTPUT_DIR / "player_bursts.csv"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"league.db not found at {DB_PATH}")
    if not EDGE_DIR.exists():
        raise SystemExit(
            f"EDGE cache dir not found at {EDGE_DIR}. "
            f"Run v2/edge/fetch_skater_detail.py first."
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = build_burst_table(DB_PATH, EDGE_DIR)
    df = df.sort_values("bursts_per_60", ascending=False, na_position="last")
    df.to_csv(OUTPUT_CSV, index=False)

    n = len(df)
    n_with_edge = df["bursts_over_20"].notna().sum()
    print(f"Wrote {n} players to {OUTPUT_CSV} ({n_with_edge} with EDGE data).")


if __name__ == "__main__":
    main()
