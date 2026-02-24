# v2/browser/pages/games.py
import dash
from dash import html, dash_table

from db import league_query

dash.register_page(__name__, path="/games", name="Games")


_SQL = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
ORDER BY gameDate DESC
"""


def layout():
    df = league_query(_SQL)
    if df.empty:
        return html.Div([html.H2("Games"), html.P("No game data available.")])

    df["game_link"] = df["gameId"].apply(lambda gid: f"[{gid}](/game/{gid})")

    df["score"] = (
        df["awayTeam_score"].fillna(0).astype(int).astype(str)
        + "\u2013"
        + df["homeTeam_score"].fillna(0).astype(int).astype(str)
    )

    def _result(periods):
        try:
            p = int(periods or 3)
        except (TypeError, ValueError):
            p = 3
        if p == 4:
            return "OT"
        if p >= 5:
            return "SO"
        return "REG"

    df["result"] = df["periodDescriptor_number"].apply(_result)

    columns = [
        {"name": "Game",   "id": "game_link",        "presentation": "markdown"},
        {"name": "Date",   "id": "gameDate",          "type": "text"},
        {"name": "Away",   "id": "awayTeam_abbrev",   "type": "text"},
        {"name": "Home",   "id": "homeTeam_abbrev",   "type": "text"},
        {"name": "Score",  "id": "score",             "type": "text"},
        {"name": "Result", "id": "result",            "type": "text"},
    ]
    display_cols = ["game_link", "gameDate", "awayTeam_abbrev", "homeTeam_abbrev", "score", "result"]

    return html.Div([
        html.H2("Games"),
        dash_table.DataTable(
            columns=columns,
            data=df[display_cols].to_dict("records"),
            markdown_options={"link_target": "_self"},
            sort_action="native",
            filter_action="native",
            filter_options={"case": "insensitive"},
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
            ],
        ),
    ])
