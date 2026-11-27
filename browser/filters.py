# browser/filters.py
"""Shared filter bar components for browser pages."""

from datetime import date

import pandas as pd
from dash import html, dcc, callback, Input, Output, ctx
from browser.db import league_query
from browser.runtime_paths import season_ready
from browser.seasons import DEFAULT_SEASON, normalize_season, season_label


def season_date_range(season: str = DEFAULT_SEASON) -> tuple[str, str]:
    """Return (min_date, max_date) from the games table.

    Falls back to Sept 1 of the start year through June 30 of the next when the
    season has no scored games yet. Sept 1 covers a late-September opener.
    """
    season = normalize_season(season)
    df = league_query(
        "SELECT MIN(gameDate) AS min_d, MAX(gameDate) AS max_d FROM games WHERE awayTeam_score IS NOT NULL",
        season=season,
    )
    if df.empty or pd.isna(df.iloc[0]["min_d"]):
        yr = int(season)
        return (f"{yr}-09-01", f"{yr + 1}-06-30")
    return (df.iloc[0]["min_d"], df.iloc[0]["max_d"])


def data_through(season: str) -> str:
    """'Games through Nov 22, 2026' for the season's latest scored game, or ''.

    The deployed image is rebuilt by hand, so this tells readers how old its data is.
    """
    df = league_query(
        "SELECT MAX(gameDate) AS max_d FROM games WHERE awayTeam_score IS NOT NULL",
        season=normalize_season(season),
    )
    if df.empty or pd.isna(df.iloc[0]["max_d"]):
        return ""
    d = date.fromisoformat(df.iloc[0]["max_d"])
    return f"Games through {d:%b} {d.day}, {d.year}"


def season_not_ready(season: str):
    """The not-available message when `season` has no data to show, else None."""
    if season_ready(season):
        return None
    return html.P(f"{season_label(season)} data isn't available yet.")


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


def register_season_callback(page_id: str):
    """Register a callback that resets date pickers when the season changes."""

    @callback(
        Output(f"{page_id}-date-start", "date"),
        Output(f"{page_id}-date-start", "min_date_allowed"),
        Output(f"{page_id}-date-start", "max_date_allowed"),
        Output(f"{page_id}-date-end", "date"),
        Output(f"{page_id}-date-end", "min_date_allowed"),
        Output(f"{page_id}-date-end", "max_date_allowed"),
        Input("store-season", "data"),
    )
    def update_dates(season):
        min_d, max_d = season_date_range(season)
        return min_d, min_d, max_d, max_d, min_d, max_d


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
    """Return per-player deployment metrics using stored wPPI/wPPI+ from the database.

    wPPI and wPPI+ are the full-season values stored in player_metrics — the filtered
    window determines which players are shown (GP >= 5 in window) and their avg_toi_share,
    but does not shift the wPPI+ baseline. This mirrors how wRC+ uses year-to-date league
    constants as a stable denominator rather than recomputing per filtered view.

    Args:
        comp_df: Filtered competition rows with columns:
                 playerId, team, gameId, toi_seconds, position
                 (deployment_score column optional — if absent, deployment_rate = NaN)
        ppi_df:  Player metrics with columns: playerId, ppi, ppi_plus, wppi, wppi_plus
                 (full-season, not filtered)

    Returns:
        DataFrame indexed by playerId with columns:
        ppi, ppi_plus, wppi, wppi_plus, avg_toi_share, deployment_rate, fwd_deployment_rate
    """
    if comp_df.empty or ppi_df.empty:
        return pd.DataFrame()

    ppi = ppi_df.set_index("playerId")[["ppi", "ppi_plus", "wppi", "wppi_plus"]]

    # Games played per player in filtered window
    gp = comp_df.groupby("playerId")["gameId"].nunique().rename("games_played")
    eligible = ppi.join(gp, how="inner")
    eligible = eligible[eligible["games_played"] >= 5].copy()
    if eligible.empty:
        return pd.DataFrame()

    # avg_toi_share: computed from filtered window.
    # Denominator uses full comp (all skaters), matching real per-game deployment totals.
    game_team_toi = comp_df.groupby(["team", "gameId"])["toi_seconds"].transform("sum")
    cs = comp_df.copy()
    cs["toi_share"] = 5.0 * cs["toi_seconds"] / game_team_toi.where(game_team_toi > 0)
    avg_toi_share = (
        cs[cs["playerId"].isin(eligible.index)]
        .groupby("playerId")["toi_share"]
        .mean()
        .rename("avg_toi_share")
    )
    eligible = eligible.join(avg_toi_share)
    eligible = eligible[eligible["avg_toi_share"].notna()]
    if eligible.empty:
        return pd.DataFrame()

    # Deployment rate — D only, requires deployment_score column in comp_df
    if "deployment_score" in comp_df.columns:
        d_comp = comp_df[comp_df["position"] == "D"].copy()
        if not d_comp.empty:
            d_comp["deployment_score"] = pd.to_numeric(d_comp["deployment_score"], errors="coerce")
            d_agg = d_comp.groupby("playerId").agg(
                total_score=("deployment_score", "sum"),
                d_gp=("gameId", "nunique"),
            )
            d_agg["avg_score"] = d_agg["total_score"] / d_agg["d_gp"]
            league_avg = d_agg["avg_score"].mean()
            if league_avg and league_avg > 0:
                d_agg["deployment_rate"] = d_agg["avg_score"] / league_avg * 100
            else:
                d_agg["deployment_rate"] = None
            eligible = eligible.join(d_agg[["deployment_rate"]])
        else:
            eligible["deployment_rate"] = None
    else:
        eligible["deployment_rate"] = None

    # Forward deployment rate — F only, requires deployment_score column in comp_df
    if "deployment_score" in comp_df.columns:
        f_comp = comp_df[comp_df["position"] == "F"].copy()
        if not f_comp.empty:
            f_comp["deployment_score"] = pd.to_numeric(f_comp["deployment_score"], errors="coerce")
            f_agg = f_comp.groupby("playerId").agg(
                total_score=("deployment_score", "sum"),
                f_gp=("gameId", "nunique"),
            )
            f_agg["avg_score"] = f_agg["total_score"] / f_agg["f_gp"]
            fwd_league_avg = f_agg["avg_score"].mean()
            if fwd_league_avg and fwd_league_avg > 0:
                f_agg["fwd_deployment_rate"] = f_agg["avg_score"] / fwd_league_avg * 100
            else:
                f_agg["fwd_deployment_rate"] = None
            eligible = eligible.join(f_agg[["fwd_deployment_rate"]])
        else:
            eligible["fwd_deployment_rate"] = None
    else:
        eligible["fwd_deployment_rate"] = None

    return eligible[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate", "fwd_deployment_rate"]]
