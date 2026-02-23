# v2/browser/pages/game.py
import dash
from dash import html, dash_table

from db import league_query
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/game/<game_id>", name="Game")

_META_SQL = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games WHERE gameId = ?
"""

_HEAVINESS_SQL = """
SELECT team,
       MAX(weighted_forward_heaviness) AS fwd_heaviness,
       MAX(weighted_defense_heaviness) AS def_heaviness,
       MAX(weighted_team_heaviness)    AS team_heaviness
FROM competition
WHERE gameId = ?
GROUP BY team
"""

_PLAYERS_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    c.team,
    c.position,
    c.toi_seconds,
    c.comp_fwd,
    c.comp_def,
    c.pct_vs_top_fwd,
    c.pct_vs_top_def
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
WHERE c.gameId = ? AND c.position IN ('F', 'D')
ORDER BY c.toi_seconds DESC
"""


def _make_player_table(df):
    """Build a DataTable with F/D group headers, sorted by TOI desc within each group."""
    df = df.copy().sort_values("toi_seconds", ascending=False)
    df["toi_display"]      = df["toi_seconds"].apply(seconds_to_mmss)
    df["comp_fwd_display"] = df["comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"] = df["comp_def"].apply(seconds_to_mmss)
    df["pct_vs_top_fwd"]   = df["pct_vs_top_fwd"].round(4)
    df["pct_vs_top_def"]   = df["pct_vs_top_def"].round(4)

    columns = [
        {"name": "Player",       "id": "playerName"},
        {"name": "5v5 TOI",      "id": "toi_display"},
        {"name": "OPP F TOI",    "id": "comp_fwd_display"},
        {"name": "OPP D TOI",    "id": "comp_def_display"},
        {"name": "vs Top Fwd %", "id": "pct_vs_top_fwd", "type": "numeric"},
        {"name": "vs Top Def %", "id": "pct_vs_top_def", "type": "numeric"},
    ]
    display_cols = [
        "playerName", "toi_display", "comp_fwd_display",
        "comp_def_display", "pct_vs_top_fwd", "pct_vs_top_def",
    ]

    # Build rows with position group separators
    rows = []
    header_indices = []
    for pos, label in [("F", "Forwards"), ("D", "Defensemen")]:
        pos_df = df[df["position"] == pos]
        if pos_df.empty:
            continue
        header_indices.append(len(rows))
        rows.append({col["id"]: (label if col["id"] == "playerName" else "") for col in columns})
        rows.extend(pos_df[display_cols].to_dict("records"))

    return dash_table.DataTable(
        columns=columns,
        data=rows,
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8f9fa", "fontWeight": "bold",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_cell={
            "textAlign": "left", "padding": "6px 10px",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
            *[
                {
                    "if": {"row_index": i},
                    "backgroundColor": "#e9ecef",
                    "fontWeight": "bold",
                    "color": "#495057",
                }
                for i in header_indices
            ],
        ],
    )


def layout(game_id=None):
    if not game_id:
        return html.Div("No game specified.")

    try:
        gid = int(game_id)
    except (TypeError, ValueError):
        return html.Div(f"Invalid game ID: {game_id}")

    meta_df    = league_query(_META_SQL, params=(gid,))
    heavy_df   = league_query(_HEAVINESS_SQL, params=(gid,))
    players_df = league_query(_PLAYERS_SQL, params=(gid,))

    if meta_df.empty:
        return html.Div(f"Game {gid} not found.")

    meta       = meta_df.iloc[0]
    away       = meta["awayTeam_abbrev"]
    home       = meta["homeTeam_abbrev"]
    away_score = int(meta["awayTeam_score"] or 0)
    home_score = int(meta["homeTeam_score"] or 0)

    # Score display: winner first
    if home_score > away_score:
        score_str = f"{home} {home_score}\u2013{away_score} {away}"
    else:
        score_str = f"{away} {away_score}\u2013{home_score} {home}"

    # Heaviness summary table
    heavy = {}
    for _, row in heavy_df.iterrows():
        heavy[row["team"]] = row

    def _h(team, col):
        val = heavy.get(team, {}).get(col, None)
        return round(float(val), 4) if val is not None else "\u2014"

    th_style = {
        "textAlign": "left", "padding": "6px 10px",
        "borderBottom": "2px solid #dee2e6", "fontSize": "13px", "fontWeight": "bold",
    }
    td_style = {"padding": "6px 10px", "borderBottom": "1px solid #dee2e6", "fontSize": "14px"}

    heaviness_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Team",           style=th_style),
            html.Th("Fwd Heaviness",  style=th_style),
            html.Th("Def Heaviness",  style=th_style),
            html.Th("Team Heaviness", style=th_style),
        ])),
        html.Tbody([
            html.Tr([
                html.Td(away, style=td_style),
                html.Td(_h(away, "fwd_heaviness"),  style=td_style),
                html.Td(_h(away, "def_heaviness"),  style=td_style),
                html.Td(_h(away, "team_heaviness"), style=td_style),
            ]),
            html.Tr([
                html.Td(home, style=td_style),
                html.Td(_h(home, "fwd_heaviness"),  style=td_style),
                html.Td(_h(home, "def_heaviness"),  style=td_style),
                html.Td(_h(home, "team_heaviness"), style=td_style),
            ]),
        ]),
    ], style={"borderCollapse": "collapse", "marginBottom": "1.5rem"})

    # Player tables by team
    if players_df.empty:
        away_table = html.Div("No player data.")
        home_table = html.Div("No player data.")
    else:
        away_df = players_df[players_df["team"] == away]
        home_df = players_df[players_df["team"] == home]
        away_table = _make_player_table(away_df) if not away_df.empty else html.Div("No player data.")
        home_table = _make_player_table(home_df) if not home_df.empty else html.Div("No player data.")

    return html.Div([
        html.H2(f"Game {gid}"),
        html.P(
            f"{meta['gameDate']}  |  {score_str}",
            style={"fontSize": "1.1rem", "marginBottom": "1rem"},
        ),
        heaviness_table,
        html.Div([
            html.Div([
                html.H4(f"{away} (Away)"),
                away_table,
            ], style={"flex": "1", "minWidth": "0", "marginRight": "1rem"}),
            html.Div([
                html.H4(f"{home} (Home)"),
                home_table,
            ], style={"flex": "1", "minWidth": "0", "marginLeft": "1rem"}),
        ], style={"display": "flex", "alignItems": "flex-start", "gap": "1rem"}),
    ])
