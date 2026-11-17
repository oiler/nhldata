"""Spec Testing row 1: a full build in main() order on a season's first game."""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import build_league_db as b

_COMP_COLS = ["gameId", "playerId", "team", "position", "toi_seconds", "total_toi_seconds",
              "comp_fwd", "comp_def", "pct_vs_top_fwd", "pct_vs_top_def", "height_in", "weight_lbs",
              "heaviness", "weighted_forward_heaviness", "weighted_defense_heaviness",
              "weighted_team_heaviness", "line_number", "deployment_score"]
_SKATERS = [(1, "EDM", "C"), (2, "EDM", "D"), (3, "VAN", "C"), (4, "VAN", "D")]


def _opening_night(tmp_path, monkeypatch):
    """One game, four skaters, no flatplays (so no 5v5 goals), no timelines."""
    season = tmp_path / "2026"
    comp = season / "generated" / "competition"
    comp.mkdir(parents=True)
    pd.DataFrame([
        dict(zip(_COMP_COLS, [2026020004, pid, team, "D" if pos == "D" else "F", 900, 1100,
                              800.0, 900.0, 0.5, 0.5, 72, 198, 2.75, 2.7, 2.8, 2.75, 1, 100]))
        for pid, team, pos in _SKATERS
    ]).to_csv(comp / "2026020004.csv", index=False)
    (season / "generated" / "flatplays").mkdir(parents=True)
    (season / "generated" / "timelines" / "csv").mkdir(parents=True)
    box = season / "generated" / "flatboxscores"
    box.mkdir(parents=True)
    pd.DataFrame([{"id": 2026020004, "gameDate": "2026-09-29", "awayTeam_abbrev": "VAN",
                   "homeTeam_abbrev": "EDM", "awayTeam_score": 1, "homeTeam_score": 2,
                   "periodDescriptor_number": 3}]).to_csv(box / "boxscores.csv", index=False)
    (season / "players").mkdir()
    pcsv = season / "generated" / "players" / "csv" / "players.csv"
    pcsv.parent.mkdir(parents=True)
    pd.DataFrame([{"playerId": pid, "firstName": "F", "lastName": "L", "currentTeamAbbrev": team,
                   "position": pos, "shootsCatches": "L", "heightInInches": 72,
                   "weightInPounds": 198, "birthDate": "2000-01-01"}
                  for pid, team, pos in _SKATERS]).to_csv(pcsv, index=False)
    for name, val in [("SEASON_DIR", season), ("COMPETITION_DIR", comp), ("PLAYERS_CSV", pcsv),
                      ("FLATBOXSCORES_CSV", box / "boxscores.csv"),
                      ("FLATPLAYS_DIR", season / "generated" / "flatplays")]:
        monkeypatch.setattr(b, name, str(val))


def test_opening_night_build_creates_every_page_table(tmp_path, monkeypatch):
    _opening_night(tmp_path, monkeypatch)
    conn = sqlite3.connect(":memory:")
    for step in (b.build_competition_table, b.build_players_table, b._recover_missing_players,
                 b.build_games_table, b.build_points_5v5_table, b.build_events_5v5_table,
                 b.build_onice_5v5_table, b.build_elite_forwards_table, b.recompute_pct_vs_elite_fwd,
                 b.build_elite_defensemen_table, b.recompute_pct_vs_elite_def,
                 b.build_player_metrics_table, b.build_constants_table):
        step(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"competition", "players", "games", "points_5v5", "events_5v5", "onice_5v5",
            "elite_forwards", "elite_defensemen", "player_metrics", "constants"} <= tables
    cols = {r[1] for r in conn.execute("PRAGMA table_info(competition)")}
    assert {"pct_any_elite_fwd", "pct_any_elite_def"} <= cols
