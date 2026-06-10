# v2/browser/tests/test_table_style.py
"""Tests for the shared DataTable styling in table_style.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from table_style import (
    STYLE_CELL_CONDITIONAL,
    STYLE_HEADER,
    STYLE_HEADER_CONDITIONAL,
    table_styles,
)


def test_header_is_navy_on_white():
    assert STYLE_HEADER["color"] == "#00205B"
    assert STYLE_HEADER["backgroundColor"] == "#ffffff"


def test_numeric_columns_use_mono_tnum_right_aligned():
    rule = next(
        r for r in STYLE_CELL_CONDITIONAL
        if r["if"].get("column_type") == "numeric"
    )
    assert "Geist Mono" in rule["fontFamily"]
    assert rule["textAlign"] == "right"
    assert "tnum" in rule["fontFeatureSettings"]


def test_numeric_headers_right_aligned_to_match_data():
    # Header alignment must follow its column's data: numeric headers right-aligned
    # so the label sits directly over the right-aligned numbers (no horizontal gap).
    rule = next(
        r for r in STYLE_HEADER_CONDITIONAL
        if r["if"].get("column_type") == "numeric"
    )
    assert rule["textAlign"] == "right"


def test_table_styles_exposes_all_kwargs():
    kw = table_styles()
    for key in (
        "style_table", "style_header", "style_header_conditional", "style_cell",
        "style_cell_conditional", "style_data_conditional", "css",
    ):
        assert key in kw
