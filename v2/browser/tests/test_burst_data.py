import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from burst_data import load_bursts, BURST_COLUMNS

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
