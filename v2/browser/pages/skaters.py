# v2/browser/pages/skaters.py
import dash
from dash import dash_table, html
from dash.dash_table import FormatTemplate
from dash.dash_table.Format import Format, Scheme

from db import league_query
from utils import seconds_to_mmss

dash.register_page(__name__, path="/skaters", name="Skaters")

_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    GROUP_CONCAT(DISTINCT c.team)                                        AS teams_raw,
    c.position,
    COUNT(DISTINCT c.gameId)                                             AS games_played,
    CAST(SUM(c.toi_seconds) AS REAL)
        / NULLIF(COUNT(DISTINCT c.gameId), 0)                           AS toi_per_game,
    MAX(pm.ppi)                                                          AS ppi,
    MAX(pm.ppi_plus)                                                     AS ppi_plus,
    MAX(pm.wppi)                                                         AS wppi,
    MAX(pm.wppi_plus)                                                    AS wppi_plus,
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
LEFT JOIN player_metrics pm ON c.playerId = pm.playerId
WHERE c.position IN ('F', 'D')
GROUP BY c.playerId
ORDER BY toi_per_game DESC
"""


def layout():
    df = league_query(_SQL)
    if df.empty:
        return html.Div([html.H2("Skaters"), html.P("No data available.")])

    df["team"] = df["teams_raw"].apply(lambda s: "/".join(sorted(s.split(","))) if s else "")
    df["player_link"] = df.apply(lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1)
    df["toi_display"]      = df["toi_per_game"].apply(seconds_to_mmss)
    df["comp_fwd_display"] = df["avg_comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"] = df["avg_comp_def"].apply(seconds_to_mmss)

    columns = [
        {"name": "Player",       "id": "player_link",       "presentation": "markdown"},
        {"name": "Team",         "id": "team"},
        {"name": "Pos",          "id": "position"},
        {"name": "GP",           "id": "games_played",       "type": "numeric"},
        {"name": "5v5 TOI/GP",   "id": "toi_display"},
        {"name": "PPI",   "id": "ppi",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "wPPI",  "id": "wppi",      "type": "numeric", "format": Format(precision=4, scheme=Scheme.fixed)},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "vs Top Fwd %", "id": "avg_pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Top Def %", "id": "avg_pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "OPP F TOI",    "id": "comp_fwd_display"},
        {"name": "OPP D TOI",    "id": "comp_def_display"},
    ]
    display_cols = [
        "player_link", "team", "position", "games_played", "toi_display",
        "ppi", "ppi_plus", "wppi", "wppi_plus",
        "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
        "comp_fwd_display", "comp_def_display",
    ]

    return html.Div([
        html.H2("Skaters"),
        dash_table.DataTable(
            columns=columns,
            data=df[display_cols].to_dict("records"),
            markdown_options={"link_target": "_self"},
            sort_action="native",
            filter_action="native",
            filter_options={"case": "insensitive"},
            page_action="native",
            page_size=50,
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
        ),
    ])
