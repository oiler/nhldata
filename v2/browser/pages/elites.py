# v2/browser/pages/elites.py
import dash
import pandas as pd
from dash import html, dash_table
from dash.dash_table.Format import Format, Scheme

from db import league_query

dash.register_page(__name__, path="/elites", name="Elites")

_FWD_SQL = """
SELECT e.playerId, e.team, e.gp, e.toi_min_gp, e.ttoi_pct, e.itoi_pct,
       e.p60, e.vs_ed_pct, e.is_carryover,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName
FROM elite_forwards e
LEFT JOIN players p ON e.playerId = p.playerId
ORDER BY e.team, e.p60 DESC
"""

_DEF_SQL = """
SELECT e.playerId, e.team, e.gp, e.toi_min_gp, e.ttoi_pct, e.itoi_pct,
       e.p60, e.vs_ef_pct, e.is_production, e.is_deployment, e.is_full_elite,
       e.is_carryover,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || e.playerId) AS playerName
FROM elite_defensemen e
LEFT JOIN players p ON e.playerId = p.playerId
ORDER BY e.team,
         CASE WHEN e.is_full_elite = 1 THEN 0
              WHEN e.is_production = 1 THEN 1
              ELSE 2 END
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


def _collapse_traded(df):
    """Merge multi-team rows into one row per player.

    The primary row (is_carryover=0) keeps its stats.  Carry-over teams
    are combined into the team column as "CGY/VGK".
    """
    teams_by_pid = df.groupby("playerId")["team"].apply(
        lambda ts: "/".join(ts.unique())
    )
    # Keep only the primary row (or first row if all carry-over)
    df = df.sort_values("is_carryover").drop_duplicates(subset="playerId", keep="first").copy()
    df["team"] = df["playerId"].map(teams_by_pid)
    df = df.reset_index(drop=True)
    return df


def _build_fwd_table(df):
    """Build the forwards DataTable."""
    df = _collapse_traded(df)
    df["player_link"] = df.apply(
        lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1,
    )
    df["team_link"] = df["team"].apply(
        lambda t: "/".join(f"[{x}](/team/{x})" for x in t.split("/"))
    )
    df["vs_ed_pct"] = df["vs_ed_pct"] * 100

    columns = [
        {"name": "Player", "id": "player_link", "presentation": "markdown", "filter_options": _CI},
        {"name": "Team",   "id": "team_link",    "presentation": "markdown", "filter_options": _CI},
        {"name": "GP",     "id": "gp",           "type": "numeric"},
        {"name": "TOI/GP", "id": "toi_min_gp",   "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "tTOI%",  "id": "ttoi_pct",     "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "iTOI%",  "id": "itoi_pct",     "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "P/60",   "id": "p60",          "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "vs Elite Def %", "id": "vs_ed_pct", "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "team_link", "gp", "toi_min_gp",
        "ttoi_pct", "itoi_pct", "p60", "vs_ed_pct",
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
    df = _collapse_traded(df)
    df["player_link"] = df.apply(
        lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1,
    )
    df["team_link"] = df["team"].apply(
        lambda t: "/".join(f"[{x}](/team/{x})" for x in t.split("/"))
    )
    df["vs_ef_pct"] = df["vs_ef_pct"] * 100
    df["type"] = df.apply(
        lambda r: "Full Elite" if r["is_full_elite"]
        else ("Production" if r["is_production"] else "Deployment"),
        axis=1,
    )

    columns = [
        {"name": "Player", "id": "player_link", "presentation": "markdown", "filter_options": _CI},
        {"name": "Team",   "id": "team_link",    "presentation": "markdown", "filter_options": _CI},
        {"name": "GP",     "id": "gp",           "type": "numeric"},
        {"name": "TOI/GP", "id": "toi_min_gp",   "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "tTOI%",  "id": "ttoi_pct",     "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "iTOI%",  "id": "itoi_pct",     "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "P/60",   "id": "p60",          "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "vs Elite Fwd %", "id": "vs_ef_pct", "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Type",   "id": "type",         "filter_options": _CI},
    ]
    display_cols = [
        "player_link", "team_link", "gp", "toi_min_gp",
        "ttoi_pct", "itoi_pct", "p60", "vs_ef_pct", "type",
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
