# v2/browser/pages/elites.py
import dash
from dash import html, dash_table
from dash.dash_table.Format import Format, Scheme

from db import league_query

dash.register_page(__name__, path="/elites", name="Elite Forwards")

_SQL = """
SELECT e.playerId, e.team, e.gp, e.toi_min_gp, e.ttoi_pct, e.itoi_pct,
       e.p60, e.rank, e.is_carryover,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName
FROM elite_forwards e
LEFT JOIN players p ON e.playerId = p.playerId
ORDER BY e.team, e.rank
"""


def layout(season=None):
    season = season or "2025"
    df = league_query(_SQL, season=season)
    if df.empty:
        return html.Div([
            html.H2("Elite Forwards"),
            html.P("No elite forwards data available."),
        ])

    df["player_link"] = df.apply(
        lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1,
    )
    df["team_link"] = df["team"].apply(lambda t: f"[{t}](/team/{t})")
    df["carry"] = df["is_carryover"].apply(lambda v: "Yes" if v else "")

    _ci = {"case": "insensitive"}
    columns = [
        {"name": "Player", "id": "player_link", "presentation": "markdown", "filter_options": _ci},
        {"name": "Team",   "id": "team_link",    "presentation": "markdown", "filter_options": _ci},
        {"name": "GP",     "id": "gp",           "type": "numeric"},
        {"name": "TOI/GP", "id": "toi_min_gp",   "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "tTOI%",  "id": "ttoi_pct",     "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "iTOI%",  "id": "itoi_pct",     "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "P/60",   "id": "p60",          "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Rank",   "id": "rank",         "type": "numeric"},
        {"name": "Carry-over", "id": "carry",    "filter_options": _ci},
    ]
    display_cols = [
        "player_link", "team_link", "gp", "toi_min_gp",
        "ttoi_pct", "itoi_pct", "p60", "rank", "carry",
    ]

    # Carry-over rows get light gray background
    carryover_ids = df.index[df["is_carryover"] == 1].tolist()
    carryover_cond = [
        {"if": {"row_index": i}, "backgroundColor": "#e9ecef"}
        for i in carryover_ids
    ]

    return html.Div([
        html.H2("Elite Forwards"),
        dash_table.DataTable(
            columns=columns,
            data=df[display_cols].to_dict("records"),
            markdown_options={"link_target": "_self"},
            sort_action="native",
            filter_action="native",
            css=[{"selector": ".dash-filter--case", "rule": "display: none"}],
            page_action="none",
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
            ] + carryover_cond,
        ),
    ])
