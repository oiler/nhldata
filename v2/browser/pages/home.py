# v2/browser/pages/home.py
import dash
from dash import html

dash.register_page(__name__, path="/", name="Home")

layout = html.Div([
    html.H2("Welcome to the NHL Data Browser"),
    html.P("Select a season and team using the filters above, then choose a view:"),
    html.Ul([
        html.Li(html.A("Games", href="/games")),
    ], style={"lineHeight": "2"}),
])
