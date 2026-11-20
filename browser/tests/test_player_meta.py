import sqlite3

import pandas as pd

from browser.db import player_meta


def _players_db(root, season, rows):
    path = root / season / "league.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    pd.DataFrame(rows).to_sql("players", conn, index=False)
    conn.close()


def _row(pid, team):
    return {"playerId": pid, "firstName": "A", "lastName": "B",
            "currentTeamAbbrev": team, "position": "C"}


def test_player_meta_prefers_newest_season(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _players_db(tmp_path, "2025", [_row(1, "EDM"), _row(3, "EDM")])
    _players_db(tmp_path, "2026", [_row(1, "VAN"), _row(2, "CGY")])
    assert player_meta(1)["currentTeamAbbrev"] == "VAN"
    assert player_meta(2)["currentTeamAbbrev"] == "CGY"
    # In 2025 only, while the 2026 DB exists: falls back to the older season.
    assert player_meta(3)["currentTeamAbbrev"] == "EDM"


def test_player_meta_unknown_player(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _players_db(tmp_path, "2025", [_row(1, "EDM")])
    assert player_meta(999) is None
