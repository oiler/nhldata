import sqlite3

from browser.filters import season_date_range, season_not_ready


def test_fallback_range_for_missing_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert season_date_range("2026") == ("2026-09-01", "2027-06-30")


def test_fallback_range_when_no_scored_games(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    db = tmp_path / "2026" / "league.db"
    db.parent.mkdir()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE games (gameDate TEXT, awayTeam_score INTEGER)")
    conn.execute("INSERT INTO games VALUES ('2026-09-29', NULL)")
    conn.commit()
    conn.close()
    assert season_date_range("2026") == ("2026-09-01", "2027-06-30")


def test_not_ready_message(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    msg = season_not_ready("2026")
    assert msg is not None
    assert msg.children == "2026-27 data isn't available yet."


def test_ready_season_has_no_message(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "2026").mkdir()
    (tmp_path / "2026" / "league.db").write_bytes(b"x")
    (tmp_path / "2026" / "player_bursts.csv").write_text("playerId\n1\n")
    assert season_not_ready("2026") is None
