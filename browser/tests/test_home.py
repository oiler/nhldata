"""The home page's latest games and wPPI+ leaders."""

import sqlite3

from browser import app  # noqa: F401 — registers pages so they can be imported
import browser.pages.home as home


def _league_db(root):
    (root / "2026").mkdir()
    conn = sqlite3.connect(root / "2026" / "league.db")
    conn.execute("CREATE TABLE games (gameId INTEGER, gameDate TEXT, periodDescriptor_number INTEGER,"
                 " awayTeam_abbrev TEXT, awayTeam_score INTEGER, homeTeam_abbrev TEXT, homeTeam_score INTEGER)")
    conn.executemany("INSERT INTO games VALUES (?,?,?,?,?,?,?)", [
        (1, "2026-11-24", 3, "EDM", 4, "CGY", 1),
        (2, "2026-11-25", 4, "NYR", 2, "CAR", 3),
        (3, "2026-11-25", 3, "BOS", 5, "TOR", 2),
        (4, "2026-11-26", None, "MTL", None, "OTT", None),  # scheduled, no score yet
    ])
    conn.execute("CREATE TABLE players (playerId INTEGER, firstName TEXT, lastName TEXT, currentTeamAbbrev TEXT)")
    conn.execute("CREATE TABLE player_metrics (playerId INTEGER, wppi_plus REAL)")
    conn.execute("CREATE TABLE competition (gameId INTEGER, playerId INTEGER, position TEXT)")
    for pid, pos, wppi, gp in [(10, "F", 130.0, 5), (11, "F", 150.0, 4), (12, "F", 110.0, 6),
                               (13, "F", 120.0, 5), (14, "D", 170.0, 9)]:
        conn.execute("INSERT INTO players VALUES (?,?,?,?)", (pid, "P", str(pid), "EDM"))
        conn.execute("INSERT INTO player_metrics VALUES (?,?)", (pid, wppi))
        conn.executemany("INSERT INTO competition VALUES (?,?,?)",
                         [(g, pid, pos) for g in range(100, 100 + gp)])
    conn.commit()
    conn.close()


def test_latest_games_are_the_last_scored_date(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _league_db(tmp_path)
    date, games = home.latest_games("2026")
    assert date == "2026-11-25"
    assert sorted(games["gameId"]) == [2, 3]


def test_leaders_need_five_games_and_sort_by_wppi_plus(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _league_db(tmp_path)
    leaders = home.wppi_leaders("2026", "F", n=2)
    assert list(leaders["playerId"]) == [10, 13]  # 11 has the top forward wPPI+ but only 4 games
    assert list(leaders["gp"]) == [5, 5]


def test_leaders_are_split_by_position(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _league_db(tmp_path)
    assert list(home.wppi_leaders("2026", "D")["playerId"]) == [14]


def test_score_line_puts_the_winner_first():
    row = {"awayTeam_abbrev": "NYR", "awayTeam_score": 2, "homeTeam_abbrev": "CAR",
           "homeTeam_score": 3, "periodDescriptor_number": 4}
    assert home.score_line(row) == "CAR 3–2 NYR"
    assert home.result_label(row) == "OT"
