# v2/browser/pages/elites.py
import dash
import pandas as pd
from dash import html, dash_table
from dash.dash_table.Format import Format, Scheme

from db import league_query

dash.register_page(__name__, path="/elites", name="Elites")

_FWD_SQL = """
SELECT e.playerId, e.team, e.gp, e.toi_min_gp,
       e.weighted_p60, e.weighted_dpl, e.weighted_ttoi_pct, e.weighted_itoi_pct,
       e.weighted_dps_plus,
       e.fs_p60, e.fs_dpl, e.fs_ttoi_pct, e.fs_itoi_pct,
       e.l20_p60, e.l20_dpl, e.l20_ttoi_pct, e.l20_itoi_pct,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName
FROM elite_forwards e
LEFT JOIN players p ON e.playerId = p.playerId
ORDER BY e.weighted_p60 DESC
"""

_DEF_SQL = """
SELECT e.playerId, e.team, e.gp, e.toi_min_gp,
       e.p60, e.ttoi_pct, e.dps_plus, e.dpl,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName
FROM elite_defensemen e
LEFT JOIN players p ON e.playerId = p.playerId
ORDER BY e.p60 DESC
"""

_TABLE_STYLE_HEADER = {
    "backgroundColor": "#f8f9fa", "fontWeight": "bold",
    "border": "1px solid #dee2e6", "fontSize": "13px",
}
_TABLE_STYLE_CELL = {
    "textAlign": "left", "padding": "8px 12px",
    "border": "1px solid #dee2e6", "fontSize": "14px",
}
_CI = {"case": "insensitive"}


def _build_fwd_table(df):
    """Build the forwards DataTable."""
    df = df.copy()
    df["player_link"] = df.apply(
        lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1,
    )
    df["team_link"] = df["team"].apply(lambda t: f"[{t}](/team/{t})")

    columns = [
        {"name": "Player",  "id": "player_link",       "presentation": "markdown", "filter_options": _CI},
        {"name": "Team",    "id": "team_link",          "presentation": "markdown", "filter_options": _CI},
        {"name": "GP",      "id": "gp",                 "type": "numeric"},
        {"name": "TOI/GP",  "id": "toi_min_gp",         "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "P/60",    "id": "weighted_p60",       "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "DPL",     "id": "weighted_dpl",       "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "tTOI%",   "id": "weighted_ttoi_pct",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "iTOI%",   "id": "weighted_itoi_pct",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "DPS+",    "id": "weighted_dps_plus",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "team_link", "gp", "toi_min_gp",
        "weighted_p60", "weighted_dpl", "weighted_ttoi_pct", "weighted_itoi_pct",
        "weighted_dps_plus",
    ]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        markdown_options={"link_target": "_self"},
        sort_action="native",
        filter_action="native",
        css=[{"selector": ".dash-filter--case", "rule": "display: none"}],
        page_action="none",
        style_table={"overflowX": "auto"},
        style_header=_TABLE_STYLE_HEADER,
        style_cell=_TABLE_STYLE_CELL,
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    )


def _build_def_table(df):
    """Build the defensemen DataTable."""
    df = df.copy()
    df["player_link"] = df.apply(
        lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1,
    )
    df["team_link"] = df["team"].apply(lambda t: f"[{t}](/team/{t})")
    df["dps_plus"] = pd.to_numeric(df["dps_plus"], errors="coerce").round(1)
    df["dpl"] = pd.to_numeric(df["dpl"], errors="coerce").round(1)

    columns = [
        {"name": "Player",  "id": "player_link",  "presentation": "markdown", "filter_options": _CI},
        {"name": "Team",    "id": "team_link",     "presentation": "markdown", "filter_options": _CI},
        {"name": "GP",      "id": "gp",            "type": "numeric"},
        {"name": "TOI/GP",  "id": "toi_min_gp",    "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "P/60",    "id": "p60",           "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "tTOI%",   "id": "ttoi_pct",      "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "DPS+",    "id": "dps_plus",      "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "DPL",     "id": "dpl",           "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = ["player_link", "team_link", "gp", "toi_min_gp", "p60", "ttoi_pct", "dps_plus", "dpl"]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        markdown_options={"link_target": "_self"},
        sort_action="native",
        filter_action="native",
        css=[{"selector": ".dash-filter--case", "rule": "display: none"}],
        page_action="none",
        style_table={"overflowX": "auto"},
        style_header=_TABLE_STYLE_HEADER,
        style_cell=_TABLE_STYLE_CELL,
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    )


def layout(season=None):
    season = season or "2025"
    children = []

    # --- Forwards ---
    fwd_df = league_query(_FWD_SQL, season=season)
    children.append(html.H2("Elite Forwards"))
    if fwd_df.empty:
        children.append(html.P("No elite forwards data available."))
    else:
        children.append(_build_fwd_table(fwd_df))

    # --- Defensemen ---
    children.append(html.H2("Elite Defensemen", style={"marginTop": "2rem"}))
    try:
        def_df = league_query(_DEF_SQL, season=season)
    except Exception:
        def_df = pd.DataFrame()
    if def_df.empty:
        children.append(html.P("No elite defensemen data available."))
    else:
        children.append(_build_def_table(def_df))

    return html.Div(children)
