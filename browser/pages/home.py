# browser/pages/home.py
from datetime import date

import dash
import pandas as pd
from dash import dash_table, dcc, html
from dash.dash_table.Format import Format, Scheme

from browser.db import league_query
from browser.filters import season_not_ready
from browser.seasons import DEFAULT_SEASON, season_label
from browser.table_style import table_styles

dash.register_page(__name__, path="/", name="Home")

# Same eligibility as the skaters leaderboard: at least 5 games played.
MIN_GP = 5

_LATEST_SQL = """
SELECT gameId, gameDate, periodDescriptor_number,
       awayTeam_abbrev, awayTeam_score, homeTeam_abbrev, homeTeam_score
FROM games
WHERE awayTeam_score IS NOT NULL
  AND gameDate = (SELECT MAX(gameDate) FROM games WHERE awayTeam_score IS NOT NULL)
ORDER BY gameId
"""

_LEADERS_SQL = """
SELECT pm.playerId,
       p.firstName || ' ' || p.lastName AS playerName,
       p.currentTeamAbbrev               AS team,
       c.position,
       c.gp,
       pm.wppi_plus
FROM player_metrics pm
JOIN players p ON p.playerId = pm.playerId
JOIN (
    SELECT playerId, COUNT(DISTINCT gameId) AS gp, MAX(position) AS position
    FROM competition
    WHERE position IN ('F', 'D')
    GROUP BY playerId
) c ON c.playerId = pm.playerId
WHERE c.gp >= ? AND c.position = ? AND pm.wppi_plus IS NOT NULL
ORDER BY pm.wppi_plus DESC
LIMIT ?
"""


def latest_games(season):
    """(date, games) for the latest date with a scored game; (None, empty) when there's none."""
    df = league_query(_LATEST_SQL, season=season)
    if df.empty:
        return None, df
    return df.iloc[0]["gameDate"], df


def wppi_leaders(season, position, n=5):
    """Top `n` skaters at `position` ('F' or 'D') by season wPPI+.

    Split by position because defensemen play more 5v5 minutes, so a combined list
    is all defensemen.
    """
    return league_query(_LEADERS_SQL, params=(MIN_GP, position, n), season=season)


def score_line(row):
    """'CAR 3–2 NYR': winner first, as on the game page."""
    away, home = row["awayTeam_abbrev"], row["homeTeam_abbrev"]
    a, h = int(row["awayTeam_score"]), int(row["homeTeam_score"])
    if h > a:
        return f"{home} {h}–{a} {away}"
    return f"{away} {a}–{h} {home}"


def result_label(row):
    periods = row["periodDescriptor_number"]
    p = 3 if periods is None or pd.isna(periods) else int(periods)
    return "SO" if p >= 5 else "OT" if p == 4 else "Final"


def _long_date(iso):
    d = date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def _latest_section(season):
    game_date, games = latest_games(season)
    if game_date is None:
        return html.P("No games have been played yet.")
    cards = [
        dcc.Link([
            html.Span(result_label(g), className="example-card-eyebrow"),
            html.Span(score_line(g), className="example-card-title"),
        ], href=f"/game/{g['gameId']}", className="example-card")
        for g in games.to_dict("records")
    ]
    return html.Section([
        html.H4(f"Latest games: {_long_date(game_date)}", className="home-heading"),
        html.Div(cards, className="example-cards"),
    ])


def _leaders_table(season, position):
    df = wppi_leaders(season, position)
    if df.empty:
        return html.P(f"No one has played {MIN_GP} games yet.")
    df.insert(0, "rank", range(1, len(df) + 1))
    df["player_link"] = df.apply(lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1)
    columns = [
        {"name": "#", "id": "rank", "type": "numeric"},
        {"name": "Player", "id": "player_link", "presentation": "markdown"},
        {"name": "Team", "id": "team"},
        {"name": "GP", "id": "gp", "type": "numeric"},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    styles = table_styles(columns)
    # Long names wrap, so the wPPI+ column stays in view on a phone.
    styles["style_cell_conditional"] = styles["style_cell_conditional"] + [
        {"if": {"column_id": "player_link"}, "whiteSpace": "normal"},
    ]
    return html.Div(
        dash_table.DataTable(
            columns=columns,
            data=df[[c["id"] for c in columns]].to_dict("records"),
            markdown_options={"link_target": "_self"},
            **styles,
        ),
        className="table-wrap",
    )


def _leaders_section(season):
    return html.Section([
        html.H4("wPPI+ leaders", className="home-heading", style={"marginTop": "2rem"}),
        html.P(f"Season wPPI+, among skaters with at least {MIN_GP} games: build and 5v5 deployment, "
               "indexed to the league average of 100."),
        html.Div([
            html.Div([html.H5("Forwards"), _leaders_table(season, "F")]),
            html.Div([html.H5("Defensemen"), _leaders_table(season, "D")]),
        ], className="home-leaders"),
        html.P(dcc.Link("Full skaters leaderboard →", href="/skaters"), style={"marginTop": "0.75rem"}),
    ])


def layout(**_query):
    season = DEFAULT_SEASON
    intro = html.P(
        "5v5 stats for every NHL game, built from a second-by-second record of who was on the ice "
        f"and at what strength. Showing {season_label(season)}."
    )
    not_ready = season_not_ready(season)
    if not_ready:
        return html.Div([html.H2("NHL Data"), intro, not_ready])
    return html.Div([
        html.H2("NHL Data"),
        intro,
        _latest_section(season),
        _leaders_section(season),
    ])
