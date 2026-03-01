# v2/browser/filters.py
"""Shared filter bar components for browser pages."""

import pandas as pd
from dash import html, dcc, callback, Input, Output, ctx
from db import league_query


def season_date_range(season: str = "2025") -> tuple[str, str]:
    """Return (min_date, max_date) from the games table."""
    df = league_query(
        "SELECT MIN(gameDate) AS min_d, MAX(gameDate) AS max_d FROM games WHERE awayTeam_score IS NOT NULL",
        season=season,
    )
    if df.empty or df.iloc[0]["min_d"] is None:
        return ("2025-10-01", "2026-06-30")
    return (df.iloc[0]["min_d"], df.iloc[0]["max_d"])


def make_filter_bar(page_id: str, include_home_away: bool = True) -> html.Div:
    """Build a filter bar with date pickers and optional home/away toggle.

    Component IDs are namespaced by page_id to avoid collisions:
      - f"{page_id}-date-start"
      - f"{page_id}-date-end"
      - f"{page_id}-home-away"  (only if include_home_away=True)
    """
    min_date, max_date = season_date_range()

    date_start = dcc.DatePickerSingle(
        id=f"{page_id}-date-start",
        date=min_date,
        min_date_allowed=min_date,
        max_date_allowed=max_date,
        display_format="MMM D, YYYY",
        style={"marginRight": "1rem"},
    )
    date_end = dcc.DatePickerSingle(
        id=f"{page_id}-date-end",
        date=max_date,
        min_date_allowed=min_date,
        max_date_allowed=max_date,
        display_format="MMM D, YYYY",
        style={"marginRight": "1rem"},
    )

    children = [
        html.Label("From", style={"marginRight": "0.5rem", "fontWeight": "bold", "fontSize": "0.9rem"}),
        date_start,
        html.Label("To", style={"marginRight": "0.5rem", "fontWeight": "bold", "fontSize": "0.9rem"}),
        date_end,
    ]

    if include_home_away:
        btn_style = {
            "padding": "6px 16px", "border": "1px solid #dee2e6",
            "backgroundColor": "#fff", "cursor": "pointer",
            "fontSize": "0.85rem",
        }
        active_style = {**btn_style, "backgroundColor": "#0d6efd", "color": "#fff", "borderColor": "#0d6efd"}

        children.append(
            html.Div([
                html.Button("All", id=f"{page_id}-ha-all", n_clicks=0,
                            style={**active_style, "borderRadius": "4px 0 0 4px"}),
                html.Button("Home", id=f"{page_id}-ha-home", n_clicks=0,
                            style={**btn_style, "borderLeft": "none"}),
                html.Button("Away", id=f"{page_id}-ha-away", n_clicks=0,
                            style={**btn_style, "borderLeft": "none", "borderRadius": "0 4px 4px 0"}),
                dcc.Store(id=f"{page_id}-home-away", data="all"),
            ], style={"display": "inline-flex", "marginLeft": "1rem"})
        )

    return html.Div(
        children,
        style={
            "display": "flex", "alignItems": "center", "padding": "0.75rem 0",
            "marginBottom": "1rem", "flexWrap": "wrap", "gap": "0.5rem",
        },
    )


def register_home_away_callback(page_id: str):
    """Register a callback that syncs the H/A toggle buttons with the store."""

    btn_style = {
        "padding": "6px 16px", "border": "1px solid #dee2e6",
        "backgroundColor": "#fff", "cursor": "pointer",
        "fontSize": "0.85rem",
    }
    active_style = {**btn_style, "backgroundColor": "#0d6efd", "color": "#fff", "borderColor": "#0d6efd"}

    @callback(
        Output(f"{page_id}-home-away", "data"),
        Output(f"{page_id}-ha-all", "style"),
        Output(f"{page_id}-ha-home", "style"),
        Output(f"{page_id}-ha-away", "style"),
        Input(f"{page_id}-ha-all", "n_clicks"),
        Input(f"{page_id}-ha-home", "n_clicks"),
        Input(f"{page_id}-ha-away", "n_clicks"),
    )
    def toggle_home_away(n_all, n_home, n_away):
        triggered = ctx.triggered_id or f"{page_id}-ha-all"
        styles = {
            f"{page_id}-ha-all": {**btn_style, "borderRadius": "4px 0 0 4px"},
            f"{page_id}-ha-home": {**btn_style, "borderLeft": "none"},
            f"{page_id}-ha-away": {**btn_style, "borderLeft": "none", "borderRadius": "0 4px 4px 0"},
        }
        value_map = {
            f"{page_id}-ha-all": "all",
            f"{page_id}-ha-home": "home",
            f"{page_id}-ha-away": "away",
        }
        styles[triggered] = {**styles[triggered], "backgroundColor": "#0d6efd", "color": "#fff", "borderColor": "#0d6efd"}
        value = value_map.get(triggered, "all")
        return value, styles[f"{page_id}-ha-all"], styles[f"{page_id}-ha-home"], styles[f"{page_id}-ha-away"]


def compute_deployment_metrics(comp_df: pd.DataFrame, ppi_df: pd.DataFrame) -> pd.DataFrame:
    """Compute wPPI, wPPI+, avg_toi_share from filtered competition data.

    Args:
        comp_df: Filtered competition rows with columns:
                 playerId, team, gameId, toi_seconds, position
        ppi_df:  Player metrics with columns: playerId, ppi, ppi_plus
                 (full-season, not filtered)

    Returns:
        DataFrame indexed by playerId with columns:
        ppi, ppi_plus, wppi, wppi_plus, avg_toi_share
    """
    if comp_df.empty or ppi_df.empty:
        return pd.DataFrame()

    ppi = ppi_df.set_index("playerId")[["ppi", "ppi_plus"]]

    # Games played per player in filtered window
    gp = comp_df.groupby("playerId")["gameId"].nunique().rename("games_played")
    eligible = ppi.join(gp, how="inner")
    eligible = eligible[eligible["games_played"] >= 5].copy()
    if eligible.empty:
        return pd.DataFrame()

    # wPPI: PPI x games-weighted average TOI share across team stints
    eligible_comp = comp_df[comp_df["playerId"].isin(eligible.index)]
    player_team_toi   = eligible_comp.groupby(["playerId", "team"])["toi_seconds"].sum()
    player_team_games = eligible_comp.groupby(["playerId", "team"])["gameId"].nunique()
    player_avg_toi    = player_team_toi / player_team_games

    team_total_toi    = eligible_comp.groupby("team")["toi_seconds"].sum()
    team_unique_games = eligible_comp.groupby("team")["gameId"].nunique()
    team_avg_toi      = team_total_toi / team_unique_games

    share_num: dict[int, float] = {}
    share_den: dict[int, int] = {}
    for (pid, team), avg_toi in player_avg_toi.items():
        t_avg = team_avg_toi.get(team, 0)
        if t_avg == 0:
            continue
        share = avg_toi / t_avg
        games = int(player_team_games[(pid, team)])
        share_num[pid] = share_num.get(pid, 0.0) + share * games
        share_den[pid] = share_den.get(pid, 0) + games

    wppi_map = {}
    for pid, num in share_num.items():
        den = share_den.get(pid, 0)
        if den == 0:
            continue
        wppi_map[pid] = eligible.loc[pid, "ppi"] * (num / den)

    eligible["wppi"] = pd.Series(wppi_map)
    eligible = eligible[eligible["wppi"].notna()]
    if eligible.empty:
        return pd.DataFrame()

    mean_wppi = eligible["wppi"].mean()
    eligible["wppi_plus"] = 100.0 * eligible["wppi"] / mean_wppi

    # avg_toi_share
    game_team_toi = comp_df.groupby(["team", "gameId"])["toi_seconds"].transform("sum")
    cs = comp_df.copy()
    cs["toi_share"] = 5.0 * cs["toi_seconds"] / game_team_toi.where(game_team_toi > 0)
    avg_share = (
        cs[cs["playerId"].isin(eligible.index)]
        .groupby("playerId")["toi_share"]
        .mean()
        .rename("avg_toi_share")
    )
    eligible = eligible.join(avg_share)

    return eligible[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]]
