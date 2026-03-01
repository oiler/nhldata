# v2/browser/pages/team.py
import dash
import pandas as pd
from dash import html, dash_table, callback, Input, Output, dcc
from dash.dash_table import FormatTemplate
from dash.dash_table.Format import Format, Scheme

from db import league_query
from filters import make_filter_bar, register_home_away_callback, compute_deployment_metrics
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/team/<abbrev>", name="Team")
register_home_away_callback("team")

_COMP_SQL = """
SELECT c.playerId,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
       c.position, c.team, c.gameId, c.toi_seconds,
       c.pct_vs_top_fwd, c.pct_vs_top_def,
       c.comp_fwd, c.comp_def,
       g.gameDate, g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
JOIN games g ON c.gameId = g.gameId
WHERE c.position IN ('F', 'D') AND c.team = ?
  AND g.gameDate BETWEEN ? AND ?
"""

_HA_HOME = " AND c.team = g.homeTeam_abbrev"
_HA_AWAY = " AND c.team = g.awayTeam_abbrev"

_GAMES_SQL = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
WHERE (homeTeam_abbrev = ? OR awayTeam_abbrev = ?)
  AND awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
ORDER BY gameDate ASC
"""

_GAMES_HA_HOME = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
WHERE homeTeam_abbrev = ?
  AND awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
ORDER BY gameDate ASC
"""

_GAMES_HA_AWAY = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
WHERE awayTeam_abbrev = ?
  AND awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
ORDER BY gameDate ASC
"""

_HEAVINESS_SQL = """
SELECT gameId, team, MAX(weighted_team_heaviness) AS wth
FROM competition
WHERE gameId IN ({placeholders})
GROUP BY gameId, team
"""

_PPI_SQL = "SELECT playerId, ppi, ppi_plus FROM player_metrics"

_POINTS_SQL = "SELECT playerId, gameId, goals, assists, points FROM points_5v5"


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
        {"name": "G",     "id": "total_goals",   "type": "numeric"},
        {"name": "A",     "id": "total_assists",  "type": "numeric"},
        {"name": "P",     "id": "total_points",   "type": "numeric"},
        {"name": "P/60",  "id": "p_per_60",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
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
        "player_link", "games_played",
        "total_goals", "total_assists", "total_points", "p_per_60",
        "toi_display", "avg_toi_share",
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
    return html.Div([
        html.H2(f"{abbrev} — Season Overview"),
        dcc.Store(id="team-abbrev", data=abbrev),
        make_filter_bar("team", include_home_away=True),
        html.Div(id="team-content"),
    ])


@callback(
    Output("team-content", "children"),
    Input("team-date-start", "date"),
    Input("team-date-end", "date"),
    Input("team-home-away", "data"),
    Input("team-abbrev", "data"),
)
def update_team(date_start, date_end, home_away, abbrev):
    if not date_start or not date_end or not abbrev:
        return html.P("Select a date range.")

    # Player stats
    sql = _COMP_SQL
    if home_away == "home":
        sql += _HA_HOME
    elif home_away == "away":
        sql += _HA_AWAY

    comp_df = league_query(sql, params=(abbrev, date_start, date_end))
    ppi_df = league_query(_PPI_SQL)

    # Aggregate per player
    if not comp_df.empty:
        grouped = comp_df.groupby("playerId").agg(
            playerName=("playerName", "first"),
            position=("position", "first"),
            games_played=("gameId", "nunique"),
            total_toi=("toi_seconds", "sum"),
            weighted_pct_fwd=("pct_vs_top_fwd", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
            weighted_pct_def=("pct_vs_top_def", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
            weighted_comp_fwd=("comp_fwd", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
            weighted_comp_def=("comp_def", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
        )
        grouped["toi_per_game"] = grouped["total_toi"] / grouped["games_played"]
        grouped["avg_pct_vs_top_fwd"] = grouped["weighted_pct_fwd"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
        grouped["avg_pct_vs_top_def"] = grouped["weighted_pct_def"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
        grouped["avg_comp_fwd"] = grouped["weighted_comp_fwd"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
        grouped["avg_comp_def"] = grouped["weighted_comp_def"] / grouped["total_toi"].where(grouped["total_toi"] > 0)

        metrics = compute_deployment_metrics(comp_df, ppi_df)
        if not metrics.empty:
            grouped = grouped.join(metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]])
        else:
            for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]:
                grouped[col] = None

        # 5v5 points
        pts_df = league_query(_POINTS_SQL)
        if not pts_df.empty:
            valid_games = comp_df[["playerId", "gameId"]].drop_duplicates()
            pts_filtered = pts_df.merge(valid_games, on=["playerId", "gameId"], how="inner")
            pts_agg = pts_filtered.groupby("playerId").agg(
                total_goals=("goals", "sum"),
                total_assists=("assists", "sum"),
                total_points=("points", "sum"),
            )
            grouped = grouped.join(pts_agg)
        for c in ["total_goals", "total_assists", "total_points"]:
            grouped[c] = grouped[c].fillna(0).astype(int) if c in grouped.columns else 0
        grouped["p_per_60"] = grouped["total_points"] * 3600 / grouped["total_toi"].where(grouped["total_toi"] > 0)

        player_df = grouped.reset_index().sort_values("toi_per_game", ascending=False)
        for col, dec in [("ppi", 2), ("ppi_plus", 1), ("wppi", 4), ("wppi_plus", 1)]:
            player_df[col] = pd.to_numeric(player_df[col], errors="coerce").round(dec)
    else:
        player_df = pd.DataFrame()

    # Game log
    if home_away == "home":
        games_df = league_query(_GAMES_HA_HOME, params=(abbrev, date_start, date_end))
    elif home_away == "away":
        games_df = league_query(_GAMES_HA_AWAY, params=(abbrev, date_start, date_end))
    else:
        games_df = league_query(_GAMES_SQL, params=(abbrev, abbrev, date_start, date_end))

    # Heaviness lookup
    game_ids = games_df["gameId"].tolist() if not games_df.empty else []
    heaviness_map = {}
    if game_ids:
        placeholders = ",".join("?" * len(game_ids))
        heaviness_df = league_query(
            _HEAVINESS_SQL.format(placeholders=placeholders),
            params=tuple(game_ids),
        )
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
            "score":         f"{own_score}\u2013{opp_score}",
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
        html.H3("Players"),
        _make_player_tables(player_df) if not player_df.empty else html.Div("No player data."),
        html.H3("Game Log", style={"marginTop": "2rem"}),
        game_table if game_rows else html.P("No games found in this range."),
    ])
