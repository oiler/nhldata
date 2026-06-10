# v2/browser/pages/home.py
import dash
from dash import html, dcc

dash.register_page(__name__, path="/", name="Home")

layout = html.Div([
    html.H2("Welcome to the NHL Data Browser"),
    html.P("Select a view from the navigation above, or jump directly to a section:"),
    html.Ul([
        html.Li(dcc.Link("Skaters Leaderboard", href="/skaters")),
        html.Li(dcc.Link("Games", href="/games")),
        html.Li(dcc.Link("Teams", href="/teams")),
    ], style={"lineHeight": "2", "marginBottom": "1.5rem"}),
    html.P("Or jump straight to an example page:"),
    html.Div([
        dcc.Link([
            html.Span("Team", className="example-card-eyebrow"),
            html.Span("Edmonton Oilers", className="example-card-title"),
            html.Span("/team/EDM", className="example-card-path"),
        ], href="/team/EDM", className="example-card"),
        dcc.Link([
            html.Span("Game", className="example-card-eyebrow"),
            html.Span("Game Boxscore", className="example-card-title"),
            html.Span("/game/2025020871", className="example-card-path"),
        ], href="/game/2025020871", className="example-card"),
        dcc.Link([
            html.Span("Skater", className="example-card-eyebrow"),
            html.Span("Connor McDavid", className="example-card-title"),
            html.Span("/player/8478402", className="example-card-path"),
        ], href="/player/8478402", className="example-card"),
    ], className="example-cards"),
])
