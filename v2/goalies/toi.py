"""Goalie games (TOI, box counts) from raw boxscores.

Usage: python3 v2/goalies/toi.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def parse_toi(mmss: str) -> int:
    m, s = mmss.split(":")
    return int(m) * 60 + int(s)


def extract_goalie_games(box: dict) -> list[dict]:
    rows = []
    for side, opp in (("homeTeam", "awayTeam"), ("awayTeam", "homeTeam")):
        for g in box["playerByGameStats"][side]["goalies"]:
            toi_s = parse_toi(g["toi"])
            if toi_s == 0:
                continue
            rows.append({
                "game_id": box["id"],
                "game_date": box["gameDate"],
                "goalie_id": g["playerId"],
                "team_abbrev": box[side]["abbrev"],
                "opp_abbrev": box[opp]["abbrev"],
                "is_home": side == "homeTeam",
                "starter": bool(g["starter"]),
                "toi_s": toi_s,
                "shots_against": g["shotsAgainst"],
                "goals_against": g["goalsAgainst"],
                "box_saves": g["saves"],
            })
    return rows


def main() -> None:
    for season in SEASONS:
        rows = []
        for f in sorted((ROOT / "data" / season / "boxscores").glob("*.json")):
            rows.extend(extract_goalie_games(json.loads(f.read_text())))
        df = pd.DataFrame(rows).assign(season=season)
        df.to_csv(GEN / f"goalie_games_{season}.csv", index=False)
        print(f"{season}: {len(df)} goalie-games, {df['goalie_id'].nunique()} goalies, "
              f"total TOI {df['toi_s'].sum() / 3600:.0f} h")


if __name__ == "__main__":
    main()
