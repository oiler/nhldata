# v2/browser/pages/skaters.py
from urllib.parse import parse_qs, urlencode

import dash
from dash import Input, Output, callback, dcc, dash_table, html

from db import league_query
from utils import seconds_to_mmss

dash.register_page(__name__, path="/skaters", name="Skaters")

_PAGE_SIZES = [50, 100, 250]

_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    COALESCE(p.currentTeamAbbrev, c.team)                               AS team,
    SUM(c.toi_seconds)                                                   AS total_toi,
    MAX(c.heaviness)                                                     AS heaviness,
    CAST(SUM(c.pct_vs_top_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_fwd,
    CAST(SUM(c.pct_vs_top_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_def,
    CAST(SUM(c.comp_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_fwd,
    CAST(SUM(c.comp_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_def
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
WHERE c.position IN ('F', 'D')
GROUP BY c.playerId
ORDER BY total_toi DESC
"""

layout = html.Div([
    dcc.Location(id="skaters-location", refresh=False),
    html.H2("Skaters"),
    html.Div(id="skaters-size-links", style={"marginBottom": "0.5rem"}),
    html.Div(id="skaters-table-container"),
    html.Div(id="skaters-page-links", style={"marginTop": "0.75rem"}),
])


@callback(
    Output("skaters-table-container", "children"),
    Output("skaters-page-links", "children"),
    Output("skaters-size-links", "children"),
    Input("skaters-location", "search"),
)
def update_skaters(search):
    params = parse_qs((search or "").lstrip("?"))
    page = int(params.get("page", ["1"])[0])
    size = int(params.get("size", ["50"])[0])
    if size not in _PAGE_SIZES:
        size = 50
    if page < 1:
        page = 1

    df = league_query(_SQL)
    if df.empty:
        return html.Div("No data available."), "", ""

    total = len(df)
    total_pages = max(1, -(-total // size))
    if page > total_pages:
        page = total_pages

    start = (page - 1) * size
    end = min(start + size, total)
    page_df = df.iloc[start:end].copy()

    page_df["toi_display"]        = page_df["total_toi"].apply(seconds_to_mmss)
    page_df["comp_fwd_display"]   = page_df["avg_comp_fwd"].apply(seconds_to_mmss)
    page_df["comp_def_display"]   = page_df["avg_comp_def"].apply(seconds_to_mmss)
    page_df["heaviness"]          = page_df["heaviness"].round(4)
    page_df["avg_pct_vs_top_fwd"] = page_df["avg_pct_vs_top_fwd"].round(4)
    page_df["avg_pct_vs_top_def"] = page_df["avg_pct_vs_top_def"].round(4)

    columns = [
        {"name": "Player",        "id": "playerName"},
        {"name": "Team",          "id": "team"},
        {"name": "5v5 TOI",       "id": "toi_display"},
        {"name": "Heaviness",     "id": "heaviness",           "type": "numeric"},
        {"name": "vs Top Fwd %",  "id": "avg_pct_vs_top_fwd",  "type": "numeric"},
        {"name": "vs Top Def %",  "id": "avg_pct_vs_top_def",  "type": "numeric"},
        {"name": "OPP F TOI",     "id": "comp_fwd_display"},
        {"name": "OPP D TOI",     "id": "comp_def_display"},
    ]
    display_cols = [
        "playerName", "team", "toi_display", "heaviness",
        "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
        "comp_fwd_display", "comp_def_display",
    ]

    table = dash_table.DataTable(
        columns=columns,
        data=page_df[display_cols].to_dict("records"),
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8f9fa", "fontWeight": "bold",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_cell={
            "textAlign": "left", "padding": "8px 12px",
            "border": "1px solid #dee2e6", "fontSize": "14px",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    )

    def _link(p, label=None):
        label = label or str(p)
        qs = urlencode({"page": p, "size": size})
        weight = "bold" if p == page else "normal"
        return dcc.Link(label, href=f"/skaters?{qs}",
                        style={"fontWeight": weight, "marginRight": "8px"})

    page_links = html.Div([
        html.Span(
            f"Page {page} of {total_pages}  —  {start + 1}–{end} of {total} skaters",
            style={"marginRight": "16px", "color": "#6c757d", "fontSize": "13px"},
        ),
        _link(1, "« First") if page > 2 else None,
        _link(page - 1, "‹ Prev") if page > 1 else None,
        _link(page + 1, "Next ›") if page < total_pages else None,
        _link(total_pages, "Last »") if page < total_pages - 1 else None,
    ])

    size_links = html.Div([
        html.Span("Rows per page: ", style={"color": "#6c757d", "fontSize": "13px"}),
        *[
            dcc.Link(
                str(s),
                href=f"/skaters?page=1&size={s}",
                style={
                    "fontWeight": "bold" if s == size else "normal",
                    "marginRight": "8px", "fontSize": "13px",
                },
            )
            for s in _PAGE_SIZES
        ],
    ])

    return table, page_links, size_links
