# v2/browser/pages/team.py
import dash
import pandas as pd
from dash import html, dash_table
from dash.dash_table import FormatTemplate
from dash.dash_table.Format import Format, Scheme

from db import league_query
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/team/<abbrev>", name="Team")

_PLAYER_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    c.position,
    COUNT(DISTINCT c.gameId)                                             AS games_played,
    CAST(SUM(c.toi_seconds) AS REAL)
        / NULLIF(COUNT(DISTINCT c.gameId), 0)                           AS toi_per_game,
    MAX(pm.ppi)                                                          AS ppi,
    MAX(pm.ppi_plus)                                                     AS ppi_plus,
    MAX(pm.wppi)                                                         AS wppi,
    MAX(pm.wppi_plus)                                                    AS wppi_plus,
    MAX(pm.avg_toi_share)                                                AS avg_toi_share,
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
WHERE c.position IN ('F', 'D') AND c.team = ?
GROUP BY c.playerId
ORDER BY toi_per_game DESC
"""

_GAMES_SQL = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
WHERE homeTeam_abbrev = ? OR awayTeam_abbrev = ?
ORDER BY gameDate ASC
"""

_HEAVINESS_SQL = """
SELECT gameId, team, MAX(weighted_team_heaviness) AS wth
FROM competition
WHERE gameId IN ({placeholders})
GROUP BY gameId, team
"""


def _make_position_table(df):
    """Build a single sortable DataTable for one position group."""
    df = df.copy()
    df["player_link"]      = df.apply(lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1)
    df["toi_display"]      = df["toi_per_game"].apply(seconds_to_mmss)
    df["comp_fwd_display"] = df["avg_comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"] = df["avg_comp_def"].apply(seconds_to_mmss)
    columns = [
        {"name": "Player",       "id": "player_link",        "presentation": "markdown"},
        {"name": "GP",           "id": "games_played",       "type": "numeric"},
        {"name": "5v5 TOI/GP",   "id": "toi_display"},
        {"name": "TOI%",         "id": "avg_toi_share", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "vs Top Fwd %", "id": "avg_pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Top Def %", "id": "avg_pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "OPP F TOI",    "id": "comp_fwd_display"},
        {"name": "OPP D TOI",    "id": "comp_def_display"},
        {"name": "PPI",   "id": "ppi",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "wPPI",  "id": "wppi",      "type": "numeric", "format": Format(precision=4, scheme=Scheme.fixed)},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "games_played", "toi_display", "avg_toi_share",
        "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
        "comp_fwd_display", "comp_def_display",
        "ppi", "ppi_plus", "wppi", "wppi_plus",
    ]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        markdown_options={"link_target": "_self"},
        sort_action="native",
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


def _make_player_tables(df):
    """Return an html.Div with separate sortable Forwards and Defensemen tables."""
    sections = []
    for pos, label in [("F", "Forwards"), ("D", "Defensemen")]:
        pos_df = df[df["position"] == pos]
        if pos_df.empty:
            continue
        sections.append(html.H4(label, style={"marginTop": "1.5rem", "marginBottom": "0.25rem"}))
        sections.append(_make_position_table(pos_df))
    return html.Div(sections) if sections else html.Div("No player data.")


def layout(abbrev=None):
    if not abbrev:
        return html.Div("No team specified.")

    abbrev = abbrev.upper()

    player_df = league_query(_PLAYER_SQL, params=(abbrev,))
    games_df  = league_query(_GAMES_SQL, params=(abbrev, abbrev))

    if games_df.empty:
        return html.Div(f"No data found for team {abbrev}.")

    # Build heaviness lookup: {game_id: {team: value}}
    game_ids = games_df["gameId"].tolist()
    if game_ids:
        placeholders = ",".join("?" * len(game_ids))
        heaviness_df = league_query(
            _HEAVINESS_SQL.format(placeholders=placeholders),
            params=tuple(game_ids),
        )
    else:
        heaviness_df = pd.DataFrame()
    heaviness_map = {}
    for _, row in heaviness_df.iterrows():
        gid = row["gameId"]
        if gid not in heaviness_map:
            heaviness_map[gid] = {}
        heaviness_map[gid][row["team"]] = row["wth"]

    # Build game log rows
    game_rows = []
    for _, row in games_df.iterrows():
        is_home   = row["homeTeam_abbrev"] == abbrev
        opponent  = row["awayTeam_abbrev"] if is_home else row["homeTeam_abbrev"]
        own_score = int(row["homeTeam_score"] or 0) if is_home else int(row["awayTeam_score"] or 0)
        opp_score = int(row["awayTeam_score"] or 0) if is_home else int(row["homeTeam_score"] or 0)

        if own_score > opp_score:
            result = "W"
        elif int(row["periodDescriptor_number"] or 0) > 3:
            result = "OTL"
        else:
            result = "L"

        gid  = row["gameId"]
        gmap = heaviness_map.get(gid, {})
        game_rows.append({
            "gameDate":      row["gameDate"],
            "opponent":      opponent,
            "homeAway":      "Home" if is_home else "Away",
            "score":         f"{own_score}–{opp_score}",
            "result":        result,
            "opp_heaviness": round(gmap.get(opponent, 0.0), 4),
            "own_heaviness": round(gmap.get(abbrev, 0.0), 4),
            "gameId":        gid,
        })

    result_color = {"W": "green", "OTL": "darkorange", "L": "crimson"}

    th_style = {
        "textAlign": "left", "padding": "6px 10px",
        "borderBottom": "2px solid #dee2e6", "fontSize": "13px",
        "fontWeight": "bold", "color": "#495057",
    }
    td_style = {
        "padding": "6px 10px", "borderBottom": "1px solid #dee2e6", "fontSize": "14px",
    }

    game_table_rows = [
        html.Tr([
            html.Td(r["gameDate"],  style=td_style),
            html.Td(r["opponent"],  style=td_style),
            html.Td(r["homeAway"],  style=td_style),
            html.Td(r["score"],     style=td_style),
            html.Td(r["result"],    style={**td_style, "color": result_color.get(r["result"], "black")}),
            html.Td(r["opp_heaviness"], style=td_style),
            html.Td(r["own_heaviness"], style=td_style),
            html.Td(html.A("View", href=f"/game/{r['gameId']}"), style=td_style),
        ])
        for r in game_rows
    ]

    game_table = html.Table(
        [
            html.Thead(html.Tr([
                html.Th("Date",          style=th_style),
                html.Th("Opponent",      style=th_style),
                html.Th("H/A",           style=th_style),
                html.Th("Score",         style=th_style),
                html.Th("Result",        style=th_style),
                html.Th("OPP Heaviness", style=th_style),
                html.Th("Team Heaviness", style=th_style),
                html.Th("",              style=th_style),
            ])),
            html.Tbody(game_table_rows),
        ],
        style={"width": "100%", "borderCollapse": "collapse"},
    )

    return html.Div([
        html.H2(f"{abbrev} — Season Overview"),
        html.H3("Players"),
        _make_player_tables(player_df) if not player_df.empty else html.Div("No player data."),
        html.H3("Game Log", style={"marginTop": "2rem"}),
        game_table,
    ])
