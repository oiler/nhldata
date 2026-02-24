# v2/browser/pages/teams.py
import dash
from dash import html, dcc

from db import all_teams

dash.register_page(__name__, path="/teams", name="Teams")

def layout():
    teams = all_teams()
    return html.Div([
        html.H2("Teams"),
        html.Div(
            [
                dcc.Link(t, href=f"/team/{t}", style={"display": "block", "padding": "4px 0"})
                for t in teams
            ],
            style={"columnCount": 4, "columnGap": "2rem", "maxWidth": "480px"},
        ),
    ])
