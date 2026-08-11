# v2/browser/tests/test_utils.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import seconds_to_mmss


def test_zero():
    assert seconds_to_mmss(0) == "00:00"


def test_one_minute():
    assert seconds_to_mmss(60) == "01:00"


def test_typical():
    """856 seconds = 14 minutes 16 seconds."""
    assert seconds_to_mmss(856) == "14:16"


def test_single_digit_seconds():
    """Seconds < 10 must be zero-padded."""
    assert seconds_to_mmss(65) == "01:05"


def test_none_is_missing_data_not_zero():
    """None/NaN mean "no data" (e.g. a goalie-game with no timeline) and must
    not render as a measured 00:00 — that is the NaN-vs-0 distinction the
    5v5 TOI pipeline preserves everywhere else."""
    assert seconds_to_mmss(None) == "—"


def test_nan_is_missing_data_not_zero():
    assert seconds_to_mmss(float("nan")) == "—"


def test_float_rounds_down():
    """Float input is truncated to int."""
    assert seconds_to_mmss(856.9) == "14:16"
