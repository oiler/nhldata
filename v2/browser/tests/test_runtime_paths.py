import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime_paths import league_db, edm_db, player_bursts_csv, data_root, season_ready


def test_data_root_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert data_root() == tmp_path


def test_data_root_falls_back_to_repo_layout(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    root = data_root()
    assert root.name == "data"
    assert root.is_absolute()
    # The parents[N] lookup must land on the repository root (D57).
    assert (root.parent / "pyproject.toml").exists()


def test_league_db_path_per_season(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert league_db("2025") == tmp_path / "2025" / "league.db"
    assert league_db("2024") == tmp_path / "2024" / "league.db"


def test_edm_db_path(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert edm_db("2025") == tmp_path / "2025" / "edm.db"


def test_player_bursts_csv_path(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert player_bursts_csv("2025") == tmp_path / "2025" / "player_bursts.csv"


def test_fallback_layout_matches_existing_db_path(monkeypatch):
    """Fallback must produce the same paths the legacy db.py used."""
    monkeypatch.delenv("DATA_DIR", raising=False)
    root = data_root()
    assert league_db("2025") == root / "2025" / "generated" / "browser" / "league.db"


def test_season_ready_production_needs_both_files(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "2026").mkdir()
    assert season_ready("2026") is False
    (tmp_path / "2026" / "player_bursts.csv").write_text("playerId\n1\n")
    assert season_ready("2026") is False  # CSV alone isn't enough
    (tmp_path / "2026" / "player_bursts.csv").unlink()
    (tmp_path / "2026" / "league.db").write_bytes(b"x")
    assert season_ready("2026") is False  # league.db alone isn't enough
    (tmp_path / "2026" / "player_bursts.csv").write_text("playerId\n1\n")
    assert season_ready("2026") is True


def test_season_ready_local_dev_needs_only_league_db(monkeypatch, tmp_path):
    import runtime_paths
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setattr(runtime_paths, "data_root", lambda: tmp_path)
    assert season_ready("2026") is False
    db = tmp_path / "2026" / "generated" / "browser" / "league.db"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"x")
    assert season_ready("2026") is True
