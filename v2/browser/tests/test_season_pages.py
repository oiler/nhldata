import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import burst_data
import app  # noqa: F401 — registers pages so they can be imported
import pages.elites as elites
import pages.game as game
import pages.games as games
import pages.goalies as goalies
import pages.player as player
import pages.skaters as skaters
import pages.team as team
import pages.teams as teams

NOT_READY = "2026-27 data isn't available yet."


@pytest.mark.parametrize("call", [
    lambda d0, d1: games.update_games(d0, d1, "2026"),
    lambda d0, d1: teams.update_teams(d0, d1, "all", "2026"),
    lambda d0, d1: team.update_team(d0, d1, "all", "EDM", "2026", "all"),
    lambda d0, d1: player.update_player(d0, d1, "all", 1, "F", "2026"),
], ids=["games", "teams", "team", "player"])
def test_season_aware_page_says_not_ready(call, monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert call("2026-10-01", "2026-10-31").children == NOT_READY


def _goalies_db(root, season_rows):
    conn = sqlite3.connect(root / "goalies.db")
    pd.DataFrame(season_rows).to_sql("team_environment", conn, index=False)
    pd.DataFrame(columns=["goalie_id", "name", "teams", "gp", "toi_s", "shots_faced", "ga",
                          "xga", "gsax", "gsax_per100", "freeze_rate", "freeze_pct",
                          "mean_difficulty_pct", "mean_perf_z", "season", "situation"]
                 ).to_sql("goalie_seasons", conn, index=False)
    conn.close()


_ENV_ROW = {"season": 2025, "team_abbrev": "EDM", "situation": "all",
            "mean_difficulty_pct": 50.0, "mean_xg_faced_per60": 2.5, "hd_share": 0.2,
            "crossice_per60": 1.0, "b2b_games": 10}


def test_goalies_page_message_for_season_without_goalie_data(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _goalies_db(tmp_path, [_ENV_ROW])
    out = goalies.update_goalies("2026", "all")
    assert out.children == "2026-27 goalie data isn't available yet."


def test_team_goalie_section_season_absent_shows_message(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _goalies_db(tmp_path, [_ENV_ROW])
    section = team._goalie_environment_section("2026", "EDM", "all")
    assert "2026-27 goalie data isn't available yet." in str(section)


def test_team_goalie_section_team_absent_is_omitted(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _goalies_db(tmp_path, [_ENV_ROW])
    assert team._goalie_environment_section("2025", "XXX", "all") is None
    assert team._goalie_environment_section("2025", "EDM", "all") is not None


def test_elites_normalizes_query_string_season(monkeypatch):
    seen = []

    def fake_query(sql, params=(), season=None):
        seen.append(season)
        return pd.DataFrame()

    monkeypatch.setattr(elites, "league_query", fake_query)
    for bad in ("../x", "2024", None):
        elites.layout(season=bad)
    assert set(seen) == {"2025"}


def test_skaters_not_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert skaters.update_skaters("2026-10-01", "2026-10-31", "all", "2026").children == NOT_READY


def test_attach_bursts_and_age_uses_the_seasons_own_bursts(monkeypatch, tmp_path):
    monkeypatch.delenv("DATA_DIR", raising=False)
    pd.DataFrame({"playerId": [1], "bursts_per_60": [3.0], "speed_max_mph": [23.0],
                  "birth_date": ["2000-01-01"]}).to_csv(tmp_path / "2025.csv", index=False)
    monkeypatch.setattr(burst_data, "player_bursts_csv", lambda s: tmp_path / f"{s}.csv")
    burst_data.bursts_for.cache_clear()
    grouped = pd.DataFrame({"birthDate": ["2000-09-16", None, ""]},
                           index=pd.Index([1, 2, 3], name="playerId"))

    out26 = skaters.attach_bursts_and_age(grouped, "2026")  # no 2026 CSV
    assert out26["bursts_per_60"].isna().all()
    assert out26["speed_max_mph"].isna().all()
    assert out26.loc[1, "age"] == 25
    assert pd.isna(out26.loc[2, "age"]) and pd.isna(out26.loc[3, "age"])

    out25 = skaters.attach_bursts_and_age(grouped, "2025")
    assert out25.loc[1, "speed_max_mph"] == 23.0
    assert out25.loc[1, "age"] == 24
    burst_data.bursts_for.cache_clear()


def test_game_league_mean_wppi_is_none_while_metrics_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    db = tmp_path / "2026" / "league.db"
    db.parent.mkdir()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE player_metrics (playerId INTEGER, wppi REAL)")
    conn.commit()
    conn.close()
    assert game._league_mean_wppi("2026") is None
