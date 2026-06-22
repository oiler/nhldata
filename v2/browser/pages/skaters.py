# v2/browser/pages/skaters.py
from datetime import date

import dash
import pandas as pd
from dash import html, dash_table, callback, Input, Output
from dash.dash_table import FormatTemplate
from dash.dash_table.Format import Format, Scheme

from burst_data import load_bursts
from db import league_query
from filters import make_filter_bar, register_home_away_callback, register_season_callback, compute_deployment_metrics
from metrics import events_per60, points_per100_shots
from table_style import table_styles
from utils import seconds_to_mmss

dash.register_page(__name__, path="/skaters", name="Skaters")
register_home_away_callback("skaters")
register_season_callback("skaters")

# NHL convention: integer age as of Sept 15 of the season's start year.
_AGE_CUTOFFS = {"2025": date(2025, 9, 15)}


def _age_on(birth_date_str, cutoff: date):
    if not birth_date_str or pd.isna(birth_date_str):
        return None
    birth = date.fromisoformat(birth_date_str)
    age = cutoff.year - birth.year
    if (cutoff.month, cutoff.day) < (birth.month, birth.day):
        age -= 1
    return age


_BURSTS_DF = load_bursts("2025").set_index("playerId")

_COMP_SQL = """
SELECT c.playerId,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
       c.position, p.shootsCatches, c.team, c.gameId, c.toi_seconds, c.total_toi_seconds,
       c.pct_any_elite_fwd, c.pct_any_elite_def,
       c.comp_fwd, c.comp_def, c.deployment_score, c.line_number,
       g.gameDate, g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
JOIN games g ON c.gameId = g.gameId
WHERE c.position IN ('F', 'D')
  AND g.gameDate BETWEEN ? AND ?
"""

_HA_HOME = " AND c.team = g.homeTeam_abbrev"
_HA_AWAY = " AND c.team = g.awayTeam_abbrev"

_PPI_SQL = "SELECT playerId, ppi, ppi_plus, wppi, wppi_plus FROM player_metrics"

_POINTS_SQL = "SELECT playerId, gameId, goals, assists, points FROM points_5v5"

_EVENTS_SQL = "SELECT gameId, playerId, hits, blocks, takeaways, giveaways, ishots FROM events_5v5"
ISA_RANK_MIN = 50  # min 5v5 individual shot attempts in window to show P/100iSA on the leaderboard


def layout():
    return html.Div([
        html.H2("Skaters"),
        html.A("Jump to glossary ↓", href="#glossary",
               style={"fontSize": "0.85rem", "color": "#6c757d", "textDecoration": "none",
                      "display": "inline-block", "marginBottom": "0.5rem"}),
        make_filter_bar("skaters", include_home_away=True),
        html.Div(id="skaters-content"),
    ])


@callback(
    Output("skaters-content", "children"),
    Input("skaters-date-start", "date"),
    Input("skaters-date-end", "date"),
    Input("skaters-home-away", "data"),
    Input("store-season", "data"),
)
def update_skaters(date_start, date_end, home_away, season):
    season = season or "2025"
    if not date_start or not date_end:
        return html.P("Select a date range.")

    sql = _COMP_SQL
    if home_away == "home":
        sql += _HA_HOME
    elif home_away == "away":
        sql += _HA_AWAY

    comp_df = league_query(sql, params=(date_start, date_end), season=season)
    if comp_df.empty:
        return html.P("No data found for this range.")

    ppi_df = league_query(_PPI_SQL, season=season)

    # Aggregate per player
    grouped = comp_df.groupby("playerId").agg(
        playerName=("playerName", "first"),
        teams_raw=("team", lambda x: ",".join(sorted(x.unique()))),
        position=("position", "first"),
        shoots=("shootsCatches", "first"),
        games_played=("gameId", "nunique"),
        total_toi=("toi_seconds", "sum"),
        total_all_toi=("total_toi_seconds", "sum"),
        weighted_pct_fwd=("pct_any_elite_fwd", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
        weighted_pct_def=("pct_any_elite_def", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
        weighted_comp_fwd=("comp_fwd", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
        weighted_comp_def=("comp_def", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
        avg_line=("line_number", "mean"),
    )
    grouped["toi_per_game"] = grouped["total_toi"] / grouped["games_played"]
    grouped["avg_pct_any_elite_fwd"] = grouped["weighted_pct_fwd"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
    grouped["avg_pct_any_elite_def"] = grouped["weighted_pct_def"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
    grouped["avg_comp_fwd"] = grouped["weighted_comp_fwd"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
    grouped["avg_comp_def"] = grouped["weighted_comp_def"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
    grouped["avg_itoi_pct"] = grouped["total_toi"] / grouped["total_all_toi"].where(grouped["total_all_toi"] > 0)

    # Deployment metrics (wPPI, wPPI+, avg_toi_share) from filtered data
    metrics = compute_deployment_metrics(comp_df, ppi_df)
    if not metrics.empty:
        grouped = grouped.join(metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate", "fwd_deployment_rate"]])
    else:
        for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share", "deployment_rate", "fwd_deployment_rate"]:
            grouped[col] = None

    # 5v5 points
    pts_df = league_query(_POINTS_SQL, season=season)
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

    # Individual shot attempts (iSA/60) and shot efficiency (P/100iSA), 5v5
    events_df = league_query(_EVENTS_SQL, season=season)
    valid_games = comp_df[["playerId", "gameId"]].drop_duplicates()
    toi_frame = comp_df[["gameId", "playerId", "toi_seconds"]]
    if not events_df.empty:
        ev = events_df.merge(valid_games, on=["playerId", "gameId"], how="inner")
        grouped = grouped.join(events_per60(ev, toi_frame)[["ishots_per60"]])
        pts_for_eff = (
            pts_df.merge(valid_games, on=["playerId", "gameId"], how="inner")
            if not pts_df.empty else pd.DataFrame(columns=["gameId", "playerId", "points"])
        )
        grouped = grouped.join(
            points_per100_shots(pts_for_eff, ev, min_attempts=ISA_RANK_MIN)[["p_per100_ranked"]]
        )
    for col in ["ishots_per60", "p_per100_ranked"]:
        if col not in grouped.columns:
            grouped[col] = None

    grouped = grouped.join(_BURSTS_DF)
    cutoff = _AGE_CUTOFFS.get(season)
    if cutoff is not None:
        grouped["age"] = grouped["birth_date"].apply(lambda b: _age_on(b, cutoff))
    else:
        grouped["age"] = None

    df = grouped.reset_index()
    df = df.sort_values("total_points", ascending=False)

    # Display formatting
    for col, decimals in [("ppi", 2), ("ppi_plus", 1), ("wppi_plus", 1), ("deployment_rate", 1), ("fwd_deployment_rate", 1), ("avg_line", 2)]:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(decimals)
    df["team"] = df["teams_raw"].apply(lambda s: "/".join(sorted(s.split(","))) if s else "")
    df["player_link"] = df.apply(lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1)
    df["toi_display"]      = df["toi_per_game"].apply(seconds_to_mmss)
    df["comp_fwd_display"] = df["avg_comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"] = df["avg_comp_def"].apply(seconds_to_mmss)
    df["dps_plus"] = df.apply(
        lambda r: r["deployment_rate"] if r["position"] == "D" else r["fwd_deployment_rate"], axis=1
    )

    _ci = {"case": "insensitive"}
    columns = [
        {"name": "Player",       "id": "player_link",       "presentation": "markdown", "filter_options": _ci},
        {"name": "Team",         "id": "team",               "filter_options": _ci},
        {"name": "Shoots",      "id": "shoots",              "filter_options": _ci},
        {"name": "Pos",          "id": "position",           "filter_options": _ci},
        {"name": "Age",          "id": "age",                "type": "numeric"},
        {"name": "GP",           "id": "games_played",       "type": "numeric"},
        {"name": "G",     "id": "total_goals",   "type": "numeric"},
        {"name": "A",     "id": "total_assists",  "type": "numeric"},
        {"name": "P",     "id": "total_points",   "type": "numeric"},
        {"name": "P/60",  "id": "p_per_60",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "iSA/60", "id": "ishots_per60", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "P/100iSA", "id": "p_per100_ranked", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "5v5 TOI/GP",   "id": "toi_display",        "filter_options": _ci},
        {"name": "tTOI%",        "id": "avg_toi_share", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "iTOI%",        "id": "avg_itoi_pct", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "SB/a60", "id": "bursts_per_60", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Max MPH", "id": "speed_max_mph", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "DPL",  "id": "avg_line",  "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "DPS+", "id": "dps_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "team", "shoots", "position", "age", "games_played",
        "total_goals", "total_assists", "total_points", "p_per_60", "ishots_per60", "p_per100_ranked",
        "toi_display",
        "avg_toi_share", "avg_itoi_pct",
        "ppi_plus", "wppi_plus", "bursts_per_60", "speed_max_mph", "avg_line", "dps_plus",
    ]

    return html.Div(
        dash_table.DataTable(
            columns=columns,
            data=df[display_cols].to_dict("records"),
            markdown_options={"link_target": "_self"},
            sort_action="native",
            filter_action="native",
            page_action="native",
            page_size=50,
            **table_styles(),
        ),
        className="table-wrap",
    )
