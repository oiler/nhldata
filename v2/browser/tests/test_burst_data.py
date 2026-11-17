import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import burst_data
from burst_data import load_bursts, BURST_COLUMNS, bursts_for, preload_ready_seasons

_SOURCE_COLS = ["playerId", "name", "position", "speed_max_mph", "birth_date", "bursts_per_60"]
_VALID_ROW = {
    "playerId": 8478402, "name": "Connor McDavid", "position": "C",
    "speed_max_mph": 24.6, "birth_date": "1997-01-13", "bursts_per_60": 21.7,
}


def _write_csv(path, rows):
    df = pd.DataFrame(rows, columns=_SOURCE_COLS) if rows else pd.DataFrame(columns=_SOURCE_COLS)
    df.to_csv(path, index=False)
    return path


def test_loads_valid_csv(tmp_path, monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    csv = _write_csv(tmp_path / "b.csv", [_VALID_ROW])
    df = load_bursts(csv_path=csv)
    assert list(df.columns) == BURST_COLUMNS
    assert df.loc[0, "bursts_per_60"] == 21.7


def test_missing_csv_raises_in_production(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="not found"):
        load_bursts(csv_path=tmp_path / "nope.csv")


def test_empty_csv_raises_in_production(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    csv = _write_csv(tmp_path / "b.csv", [])  # header only, zero data rows
    with pytest.raises(RuntimeError, match="no data rows"):
        load_bursts(csv_path=csv)


def test_missing_csv_degrades_in_dev(tmp_path, monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    df = load_bursts(csv_path=tmp_path / "nope.csv")
    assert df.empty
    assert list(df.columns) == BURST_COLUMNS


def test_empty_csv_degrades_in_dev(tmp_path, monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    csv = _write_csv(tmp_path / "b.csv", [])
    df = load_bursts(csv_path=csv)
    assert df.empty


@pytest.fixture
def clear_bursts_cache():
    bursts_for.cache_clear()
    yield
    bursts_for.cache_clear()


def test_bursts_for_missing_season_is_empty_in_dev(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setattr(burst_data, "player_bursts_csv", lambda s: tmp_path / f"{s}.csv")
    df = bursts_for("2026")
    assert df.empty
    assert df.index.name == "playerId"
    assert {"bursts_per_60", "speed_max_mph"} <= set(df.columns)


def test_bursts_for_reads_each_seasons_own_csv(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.delenv("DATA_DIR", raising=False)
    _write_csv(tmp_path / "2025.csv", [_VALID_ROW])
    _write_csv(tmp_path / "2026.csv", [{**_VALID_ROW, "speed_max_mph": 25.1}])
    monkeypatch.setattr(burst_data, "player_bursts_csv", lambda s: tmp_path / f"{s}.csv")
    assert bursts_for("2025").loc[8478402, "speed_max_mph"] == 24.6
    assert bursts_for("2026").loc[8478402, "speed_max_mph"] == 25.1


def test_preload_fails_boot_on_empty_csv_for_ready_season(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "2026").mkdir()
    (tmp_path / "2026" / "league.db").write_bytes(b"x")
    _write_csv(tmp_path / "2026" / "player_bursts.csv", [])  # header only
    with pytest.raises(RuntimeError):
        preload_ready_seasons(["2026"])


def test_preload_skips_season_not_in_image(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    preload_ready_seasons(["2026"])  # no files: skipped with a warning, no raise


def test_preload_does_nothing_in_local_dev(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setattr(burst_data, "player_bursts_csv", lambda s: tmp_path / f"{s}.csv")
    preload_ready_seasons(["2026"])
    assert bursts_for.cache_info().currsize == 0
