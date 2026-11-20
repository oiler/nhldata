from pathlib import Path

from pipeline.paths import data_dir, repo_root, season_dir


def test_repo_root_holds_pyproject():
    assert (repo_root() / "pyproject.toml").exists()


def test_data_dir_defaults_to_repo_data(monkeypatch):
    monkeypatch.delenv("NHL_DATA_DIR", raising=False)
    assert data_dir() == repo_root() / "data"


def test_data_dir_honors_override(monkeypatch, tmp_path):
    monkeypatch.setenv("NHL_DATA_DIR", str(tmp_path))
    assert data_dir() == tmp_path
    assert season_dir("2026") == tmp_path / "2026"


def test_data_dir_ignores_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("NHL_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert data_dir() == repo_root() / "data"
    assert data_dir().is_absolute()


def test_empty_override_falls_back(monkeypatch):
    monkeypatch.setenv("NHL_DATA_DIR", "")
    assert data_dir() == repo_root() / "data"
