# v2/browser/pages/team.py
import dash
import pandas as pd
from dash import html, dash_table

from db import league_query
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/team/<abbrev>", name="Team")

_PLAYER_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
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
WHERE c.position IN ('F', 'D') AND c.team = ?
GROUP BY c.playerId
ORDER BY total_toi DESC
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


def _make_player_table(df):
    df = df.copy()
    df["toi_display"]        = df["total_toi"].apply(seconds_to_mmss)
    df["comp_fwd_display"]   = df["avg_comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"]   = df["avg_comp_def"].apply(seconds_to_mmss)
    df["heaviness"]          = df["heaviness"].round(4)
    df["avg_pct_vs_top_fwd"] = df["avg_pct_vs_top_fwd"].round(4)
    df["avg_pct_vs_top_def"] = df["avg_pct_vs_top_def"].round(4)

    columns = [
        {"name": "Player",        "id": "playerName"},
        {"name": "5v5 TOI",       "id": "toi_display"},
        {"name": "Heaviness",     "id": "heaviness",           "type": "numeric"},
        {"name": "vs Top Fwd %",  "id": "avg_pct_vs_top_fwd",  "type": "numeric"},
        {"name": "vs Top Def %",  "id": "avg_pct_vs_top_def",  "type": "numeric"},
        {"name": "OPP F TOI",     "id": "comp_fwd_display"},
        {"name": "OPP D TOI",     "id": "comp_def_display"},
    ]
    display_cols = [
        "playerName", "toi_display", "heaviness",
        "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
        "comp_fwd_display", "comp_def_display",
    ]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
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
        _make_player_table(player_df) if not player_df.empty else html.Div("No player data."),
        html.H3("Game Log", style={"marginTop": "2rem"}),
        game_table,
    ])
