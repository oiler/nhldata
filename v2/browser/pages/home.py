# v2/browser/pages/home.py
import dash
from dash import html, dcc

dash.register_page(__name__, path="/", name="Home")

layout = html.Div([
    html.H2("Welcome to the NHL Data Browser"),
    html.P("Select a view from the navigation above, or jump directly to a team:"),
    html.Ul([
        html.Li(dcc.Link("Skaters Leaderboard", href="/skaters")),
        html.Li(dcc.Link("Games", href="/games")),
        html.Li(dcc.Link("Teams", href="/teams")),
    ], style={"lineHeight": "2", "marginBottom": "1rem"}),
    html.P("Navigate to a specific team or game:"),
    html.Ul([
        html.Li([
            "Team page example: ",
            dcc.Link("/team/EDM", href="/team/EDM"),
        ]),
        html.Li([
            "Game page example: ",
            dcc.Link("/game/2025020871", href="/game/2025020871"),
        ]),
    ], style={"lineHeight": "2", "fontFamily": "monospace"}),
])
