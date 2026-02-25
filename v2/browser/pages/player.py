# v2/browser/pages/player.py
import dash
from dash import html, dash_table
from dash.dash_table import FormatTemplate

from db import league_query
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/player/<player_id>", name="Player")

_META_SQL = """
SELECT firstName, lastName, currentTeamAbbrev, position
FROM players WHERE playerId = ?
"""

_GAMES_SQL = """
SELECT c.gameId, g.gameDate, c.team,
       g.awayTeam_abbrev, g.homeTeam_abbrev,
       g.awayTeam_score, g.homeTeam_score,
       g.periodDescriptor_number,
       c.toi_seconds,
       5.0 * c.toi_seconds / NULLIF(tt.team_total, 0) AS toi_share,
       c.comp_fwd, c.comp_def,
       c.pct_vs_top_fwd, c.pct_vs_top_def
FROM competition c
JOIN games g ON c.gameId = g.gameId
JOIN (
    SELECT gameId, team, SUM(toi_seconds) AS team_total
    FROM competition
    WHERE position IN ('F', 'D')
    GROUP BY gameId, team
) tt ON c.gameId = tt.gameId AND c.team = tt.team
WHERE c.playerId = ?
ORDER BY g.gameDate ASC
"""


def layout(player_id=None):
    if player_id is None:
        return html.Div("No player specified.")

    try:
        pid = int(player_id)
    except (TypeError, ValueError):
        return html.Div(f"Invalid player ID: {player_id}")

    meta_df  = league_query(_META_SQL, params=(pid,))
    games_df = league_query(_GAMES_SQL, params=(pid,))

    if meta_df.empty:
        name = f"Player {pid}"
        subtitle = ""
    else:
        m = meta_df.iloc[0]
        name = f"{m['firstName']} {m['lastName']}"
        subtitle = f"{m['currentTeamAbbrev']} · {m['position']}"

    if games_df.empty:
        return html.Div([html.H2(name), html.P("No game data available.")])

    rows = []
    for _, r in games_df.iterrows():
        is_home  = r["team"] == r["homeTeam_abbrev"]
        opponent = r["awayTeam_abbrev"] if is_home else r["homeTeam_abbrev"]
        own_score = int(r["homeTeam_score"] or 0) if is_home else int(r["awayTeam_score"] or 0)
        opp_score = int(r["awayTeam_score"] or 0) if is_home else int(r["homeTeam_score"] or 0)

        if own_score > opp_score:
            result = "W"
        elif int(r["periodDescriptor_number"] or 0) > 3:
            result = "OTL"
        else:
            result = "L"

        rows.append({
            "game_link":      f"[{r['gameId']}](/game/{r['gameId']})",
            "gameDate":       r["gameDate"],
            "team":           r["team"],
            "homeAway":       "Home" if is_home else "Away",
            "opponent":       opponent,
            "score":          f"{own_score}\u2013{opp_score}",
            "result":         result,
            "toi_display":    seconds_to_mmss(r["toi_seconds"]),
            "toi_share":      round(float(r["toi_share"]), 4) if r["toi_share"] is not None else None,
            "comp_fwd":       seconds_to_mmss(r["comp_fwd"]),
            "comp_def":       seconds_to_mmss(r["comp_def"]),
            "pct_vs_top_fwd": round(float(r["pct_vs_top_fwd"]), 4) if r["pct_vs_top_fwd"] is not None else None,
            "pct_vs_top_def": round(float(r["pct_vs_top_def"]), 4) if r["pct_vs_top_def"] is not None else None,
        })

    _ci = {"case": "insensitive"}
    columns = [
        {"name": "Game",         "id": "game_link",      "presentation": "markdown", "filter_options": _ci},
        {"name": "Date",         "id": "gameDate",        "type": "text",    "filter_options": _ci},
        {"name": "Team",         "id": "team",            "type": "text",    "filter_options": _ci},
        {"name": "H/A",          "id": "homeAway",        "type": "text",    "filter_options": _ci},
        {"name": "Opp",          "id": "opponent",        "type": "text",    "filter_options": _ci},
        {"name": "Score",        "id": "score",           "type": "text",    "filter_options": _ci},
        {"name": "Result",       "id": "result",          "type": "text",    "filter_options": _ci},
        {"name": "5v5 TOI",      "id": "toi_display",     "type": "text",    "filter_options": _ci},
        {"name": "TOI%",         "id": "toi_share",        "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "OPP F TOI",    "id": "comp_fwd",        "type": "text",    "filter_options": _ci},
        {"name": "OPP D TOI",    "id": "comp_def",        "type": "text",    "filter_options": _ci},
        {"name": "vs Top Fwd %", "id": "pct_vs_top_fwd",  "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Top Def %", "id": "pct_vs_top_def",  "type": "numeric", "format": FormatTemplate.percentage(2)},
    ]

    return html.Div([
        html.H2(name),
        html.P(subtitle, style={"color": "#6c757d", "marginTop": "-0.5rem", "marginBottom": "1rem"}),
        dash_table.DataTable(
            columns=columns,
            data=rows,
            markdown_options={"link_target": "_self"},
            sort_action="native",
            filter_action="native",
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
                {"if": {"filter_query": '{result} = "W"', "column_id": "result"}, "color": "green"},
                {"if": {"filter_query": '{result} = "OTL"', "column_id": "result"}, "color": "darkorange"},
                {"if": {"filter_query": '{result} = "L"', "column_id": "result"}, "color": "crimson"},
            ],
        ),
    ])
