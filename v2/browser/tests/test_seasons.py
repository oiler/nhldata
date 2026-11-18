import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from seasons import DEFAULT_SEASON, SEASONS, age_cutoff, normalize_season, season_label


def test_seasons_and_default():
    assert SEASONS == ["2025", "2026"]
    assert DEFAULT_SEASON == "2026"


def test_normalize_season_keeps_known_values():
    assert normalize_season("2025") == "2025"
    assert normalize_season("2026") == "2026"


def test_normalize_season_rejects_unknown_values():
    for bad in ("2024", "2019", "../x", "", None, 2026):
        assert normalize_season(bad) == DEFAULT_SEASON


def test_season_label():
    assert season_label("2025") == "2025-26"
    assert season_label("2026") == "2026-27"
    assert season_label("2099") == "2099-00"


def test_age_cutoff():
    assert age_cutoff("2026") == date(2026, 9, 15)
