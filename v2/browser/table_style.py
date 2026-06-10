# v2/browser/table_style.py
"""Shared DataTable styling for the NHL Data design system. Source: /DESIGN.md

Single source of truth so every page's DataTable renders identically. Behavioral
props (columns, data, sort_action, filter_action, page_action) stay per-page;
this module owns only the visual style kwargs.
"""

STYLE_TABLE = {"overflowX": "auto"}

STYLE_HEADER = {
    "backgroundColor": "#ffffff",
    "color": "#00205B",
    "fontWeight": "600",
    "fontSize": "0.78rem",
    "letterSpacing": "0.04em",
    "textAlign": "left",
    "border": "none",
    "borderBottom": "1px solid #ebebeb",
    "padding": "8px 12px",
}

# Header alignment follows its column's data: numeric headers right-aligned so
# the label sits directly above the right-aligned numbers. `style_header` sets the
# default (left, for text columns); this conditional overrides it for numerics
# (header_conditional outranks header in DataTable's precedence order).
STYLE_HEADER_CONDITIONAL = [
    {"if": {"column_type": "numeric"}, "textAlign": "right"},
]

STYLE_CELL = {
    "fontFamily": '"Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    "fontSize": "0.88rem",
    "color": "#171717",
    "textAlign": "left",
    "padding": "8px 12px",
    "border": "none",
    "borderBottom": "1px solid #f0f0f0",
}

# Numeric columns get tabular mono, right-aligned. `column_type` matches any
# column whose definition sets "type": "numeric" (all numeric columns do).
STYLE_CELL_CONDITIONAL = [
    {
        "if": {"column_type": "numeric"},
        "fontFamily": '"Geist Mono", ui-monospace, "SF Mono", Menlo, monospace',
        "fontFeatureSettings": '"tnum" 1, "zero" 1',
        "textAlign": "right",
    },
]

STYLE_DATA_CONDITIONAL = [
    {
        "if": {"state": "active"},
        "backgroundColor": "rgba(0, 32, 91, 0.06)",
        "border": "1px solid #00205B",
    },
    {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
]

# Hide the case-sensitivity filter toggle (preserves prior behavior).
CSS = [{"selector": ".dash-filter--case", "rule": "display: none"}]


def table_styles() -> dict:
    """Style kwargs to splat into dash_table.DataTable(**table_styles(), ...)."""
    return {
        "style_table": STYLE_TABLE,
        "style_header": STYLE_HEADER,
        "style_header_conditional": STYLE_HEADER_CONDITIONAL,
        "style_cell": STYLE_CELL,
        "style_cell_conditional": STYLE_CELL_CONDITIONAL,
        "style_data_conditional": STYLE_DATA_CONDITIONAL,
        "css": CSS,
    }
