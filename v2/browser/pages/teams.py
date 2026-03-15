# v2/browser/pages/teams.py
import pandas as pd
import dash
from dash import html, dash_table, callback, Input, Output
from dash.dash_table.Format import Format, Scheme

from db import league_query
from filters import make_filter_bar, register_home_away_callback, register_season_callback, compute_deployment_metrics

dash.register_page(__name__, path="/teams", name="Teams")
register_home_away_callback("teams")
register_season_callback("teams")

_GAMES_SQL = """
SELECT gameId, gameDate, homeTeam_abbrev, awayTeam_abbrev,
       homeTeam_score, awayTeam_score, periodDescriptor_number
FROM games
WHERE awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
"""

_COMP_SQL = """
SELECT c.playerId, c.position, c.team, c.gameId, c.toi_seconds,
       g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
JOIN games g ON c.gameId = g.gameId
WHERE c.position IN ('F', 'D')
  AND g.gameDate BETWEEN ? AND ?
"""

_PPI_SQL = "SELECT playerId, ppi, ppi_plus FROM player_metrics"
_POINTS_SQL = "SELECT playerId, gameId, goals FROM points_5v5"

_DIVISIONS = {
    "BOS": "ATL", "BUF": "ATL", "DET": "ATL", "FLA": "ATL",
    "MTL": "ATL", "OTT": "ATL", "TBL": "ATL", "TOR": "ATL",
    "CAR": "MET", "CBJ": "MET", "NJD": "MET", "NYI": "MET",
    "NYR": "MET", "PHI": "MET", "PIT": "MET", "WSH": "MET",
    "CHI": "CEN", "COL": "CEN", "DAL": "CEN", "MIN": "CEN",
    "NSH": "CEN", "STL": "CEN", "WPG": "CEN", "UTA": "CEN",
    "ANA": "PAC", "CGY": "PAC", "EDM": "PAC", "LAK": "PAC",
    "SJS": "PAC", "SEA": "PAC", "VAN": "PAC", "VGK": "PAC",
}
_CONFERENCES = {"ATL": "East", "MET": "East", "CEN": "West", "PAC": "West"}


def layout():
    return html.Div([
        html.H2("Teams"),
        make_filter_bar("teams", include_home_away=True),
        html.Div(id="teams-content"),
    ])


@callback(
    Output("teams-content", "children"),
    Input("teams-date-start", "date"),
    Input("teams-date-end", "date"),
    Input("teams-home-away", "data"),
    Input("store-season", "data"),
)
def update_teams(date_start, date_end, home_away, season):
    season = season or "2025"
    if not date_start or not date_end:
        return html.P("Select a date range.")

    games_df = league_query(_GAMES_SQL, params=(date_start, date_end), season=season)
    if games_df.empty:
        return html.P("No games found for this range.")

    comp_df = league_query(_COMP_SQL, params=(date_start, date_end), season=season)
    pts_df = league_query(_POINTS_SQL, season=season)
    ppi_df = league_query(_PPI_SQL, season=season)

    # --- Records (GP, P%, RW) ---
    # Unpivot games to team-game rows
    home = games_df[["gameId", "homeTeam_abbrev", "homeTeam_score",
                      "awayTeam_score", "periodDescriptor_number"]].copy()
    home.columns = ["gameId", "team", "own_score", "opp_score", "period"]
    home["ha"] = "home"

    away = games_df[["gameId", "awayTeam_abbrev", "awayTeam_score",
                      "homeTeam_score", "periodDescriptor_number"]].copy()
    away.columns = ["gameId", "team", "own_score", "opp_score", "period"]
    away["ha"] = "away"

    tg = pd.concat([home, away])
    if home_away == "home":
        tg = tg[tg["ha"] == "home"]
    elif home_away == "away":
        tg = tg[tg["ha"] == "away"]

    # Compute results
    tg["win"] = tg["own_score"] > tg["opp_score"]
    tg["reg_win"] = tg["win"] & (tg["period"] <= 3)
    tg["otl"] = (~tg["win"]) & (tg["period"] > 3)
    tg["pts"] = tg["win"].astype(int) * 2 + tg["otl"].astype(int)

    records = tg.groupby("team").agg(
        gp=("gameId", "nunique"),
        wins=("win", "sum"),
        rw=("reg_win", "sum"),
        total_pts=("pts", "sum"),
    ).astype(int)
    records["pct"] = records["total_pts"] / (2 * records["gp"])

    # --- 5v5 Goal Differential ---
    relevant = tg[["team", "gameId"]].drop_duplicates()

    if not comp_df.empty and not pts_df.empty:
        pts_team = pts_df.merge(
            comp_df[["playerId", "gameId", "team"]].drop_duplicates(),
            on=["playerId", "gameId"], how="inner",
        )
        team_game_goals = pts_team.groupby(["team", "gameId"])["goals"].sum().reset_index()
        game_total = pts_team.groupby("gameId")["goals"].sum().reset_index()
        game_total.columns = ["gameId", "game_total"]

        tgg = team_game_goals.merge(game_total, on="gameId")
        tgg["ga"] = tgg["game_total"] - tgg["goals"]
        tgg = tgg.merge(relevant, on=["team", "gameId"], how="inner")

        goal_agg = tgg.groupby("team").agg(gf=("goals", "sum"), ga=("ga", "sum"))
        goal_agg["gd_5v5"] = goal_agg["gf"] - goal_agg["ga"]
    else:
        goal_agg = pd.DataFrame(columns=["gd_5v5"])

    # --- PPI+ — TOI-weighted team average ---
    if home_away == "home":
        ha_comp = comp_df[comp_df["team"] == comp_df["homeTeam_abbrev"]]
    elif home_away == "away":
        ha_comp = comp_df[comp_df["team"] == comp_df["awayTeam_abbrev"]]
    else:
        ha_comp = comp_df

    metrics = compute_deployment_metrics(ha_comp, ppi_df)

    if not metrics.empty:
        pt_toi = ha_comp.groupby(["playerId", "team"])["toi_seconds"].sum().reset_index()
        pt_toi = pt_toi.merge(
            metrics[["ppi_plus"]].reset_index(),
            on="playerId", how="inner",
        )
        pt_toi["w_ppi"] = pt_toi["ppi_plus"] * pt_toi["toi_seconds"]

        team_ppi = pt_toi.groupby("team").agg(
            w_ppi_sum=("w_ppi", "sum"),
            total_toi=("toi_seconds", "sum"),
        )
        team_ppi["ppi_plus"] = team_ppi["w_ppi_sum"] / team_ppi["total_toi"]
    else:
        team_ppi = pd.DataFrame(columns=["ppi_plus"])

    # --- Combine all metrics ---
    df = records[["gp", "pct", "rw"]].copy()
    if not team_ppi.empty:
        df = df.join(team_ppi[["ppi_plus"]], how="left")
    if not goal_agg.empty:
        df = df.join(goal_agg[["gf", "ga", "gd_5v5"]], how="left")
    for col in ["ppi_plus", "gf", "ga", "gd_5v5"]:
        if col not in df.columns:
            df[col] = None
    for col in ["gf", "ga", "gd_5v5"]:
        df[col] = df[col].fillna(0).astype(int)

    df = df.reset_index()
    df["division"] = df["team"].map(_DIVISIONS)
    df["conference"] = df["division"].map(_CONFERENCES)
    df = df.sort_values("pct", ascending=False)
    df["team_link"] = df["team"].apply(lambda t: f"[{t}](/team/{t})")

    # --- Tercile coloring ---
    _TOP = "#d4edda"      # green tint
    _MID = "#fff3cd"      # yellow tint
    _BOT = "#f8d7da"      # red tint
    _TOP_ODD = "#c5e4cd"
    _MID_ODD = "#f5e9be"
    _BOT_ODD = "#eecacd"

    def _tercile_styles(col_id, higher_is_better=True):
        """Generate conditional styles for top/mid/bottom thirds of a column."""
        series = df[col_id].dropna()
        if series.empty:
            return []
        t1 = series.quantile(1 / 3)
        t2 = series.quantile(2 / 3)
        if higher_is_better:
            top_q, bot_q = f"{{{col_id}}} >= {t2}", f"{{{col_id}}} < {t1}"
            mid_q = f"{{{col_id}}} >= {t1} && {{{col_id}}} < {t2}"
        else:
            top_q, bot_q = f"{{{col_id}}} <= {t1}", f"{{{col_id}}} > {t2}"
            mid_q = f"{{{col_id}}} > {t1} && {{{col_id}}} <= {t2}"
        return [
            {"if": {"filter_query": top_q, "column_id": col_id}, "backgroundColor": _TOP},
            {"if": {"filter_query": mid_q, "column_id": col_id}, "backgroundColor": _MID},
            {"if": {"filter_query": bot_q, "column_id": col_id}, "backgroundColor": _BOT},
            {"if": {"filter_query": top_q, "column_id": col_id, "row_index": "odd"}, "backgroundColor": _TOP_ODD},
            {"if": {"filter_query": mid_q, "column_id": col_id, "row_index": "odd"}, "backgroundColor": _MID_ODD},
            {"if": {"filter_query": bot_q, "column_id": col_id, "row_index": "odd"}, "backgroundColor": _BOT_ODD},
        ]

    tercile_cond = []
    for col_id, higher in [("pct", True), ("rw", True), ("ppi_plus", True),
                            ("gf", True), ("ga", False), ("gd_5v5", True)]:
        tercile_cond.extend(_tercile_styles(col_id, higher))

    _ci = {"case": "insensitive"}
    columns = [
        {"name": "Team",   "id": "team_link", "presentation": "markdown", "filter_options": _ci},
        {"name": "Div",   "id": "division",   "filter_options": _ci},
        {"name": "Conf",  "id": "conference",  "filter_options": _ci},
        {"name": "GP",     "id": "gp",        "type": "numeric"},
        {"name": "P%",     "id": "pct",       "type": "numeric",
         "format": Format(precision=3, scheme=Scheme.fixed)},
        {"name": "RW",     "id": "rw",        "type": "numeric"},
        {"name": "PPI+",   "id": "ppi_plus",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "5v5 GF", "id": "gf",       "type": "numeric"},
        {"name": "5v5 GA", "id": "ga",       "type": "numeric"},
        {"name": "5v5 GD", "id": "gd_5v5",   "type": "numeric"},
    ]
    display_cols = ["team_link", "division", "conference", "gp", "pct", "rw", "ppi_plus", "gf", "ga", "gd_5v5"]

    return dash_table.DataTable(
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
        ] + tercile_cond,
    )
