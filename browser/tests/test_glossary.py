"""Column-header tooltips come from the glossary."""

from browser.glossary import COLUMN_TERMS, GOALIES, SKATERS, TEAMS_AND_GAMES, header_tooltips
from browser.table_style import table_styles

TERMS = {term for section in (SKATERS, TEAMS_AND_GAMES, GOALIES) for term, _ in section}
DEFS = dict(SKATERS + TEAMS_AND_GAMES + GOALIES)

COLUMNS = [
    {"name": "Player", "id": "player_link"},
    {"name": "wPPI+", "id": "wppi_plus"},
    {"name": "G", "id": "total_goals"},
    {"name": "5v5 GD", "id": "gd_5v5"},
]


def test_tooltips_cover_glossary_columns_only():
    tips = header_tooltips(COLUMNS)
    assert set(tips) == {"wppi_plus", "total_goals", "gd_5v5"}
    assert tips["wppi_plus"] == {"value": DEFS["wPPI+"], "type": "text"}


def test_combined_terms_reach_each_column():
    tips = header_tooltips(COLUMNS)
    assert tips["total_goals"]["value"] == DEFS["G, A, P"]
    assert tips["gd_5v5"]["value"] == DEFS["5v5 GF, GA, GD"]


def test_every_column_alias_names_a_glossary_term():
    assert set(COLUMN_TERMS.values()) <= TERMS


def test_table_styles_adds_tooltips_and_marks_their_headers():
    styles = table_styles(COLUMNS)
    assert set(styles["tooltip_header"]) == {"wppi_plus", "total_goals", "gd_5v5"}
    marked = {
        r["if"]["column_id"] for r in styles["style_header_conditional"]
        if r["if"].get("column_id") and "dotted" in r.get("textDecoration", "")
    }
    assert marked == {"wppi_plus", "total_goals", "gd_5v5"}


def test_table_styles_without_columns_has_no_tooltips():
    assert "tooltip_header" not in table_styles()
