# v2/browser/app.py
import dash
from dash import Dash, html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
from db import available_teams

SEASONS = ["2024", "2025"]
DEFAULT_SEASON = "2025"

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
server = app.server  # for gunicorn

app.layout = html.Div([
    # Shared state
    dcc.Store(id="store-season", storage_type="session", data=DEFAULT_SEASON),
    dcc.Store(id="store-team", storage_type="session", data="ALL"),

    # Header + nav
    html.Div([
        html.H1("NHL Data Browser"),
        html.Div([
            dcc.Link(page["name"], href=page["relative_path"])
            for page in dash.page_registry.values()
        ], className="app-nav"),
    ], className="app-header"),

    # Filter bar
    html.Div([
        html.Div([
            html.Label("Season"),
            dcc.RadioItems(
                id="filter-season",
                options=[{"label": s, "value": s} for s in SEASONS],
                value=DEFAULT_SEASON,
                inline=True,
                inputStyle={"marginRight": "4px"},
                labelStyle={"marginRight": "16px", "fontWeight": "normal",
                            "fontSize": "0.9rem", "color": "#212529"},
            ),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div([
            html.Label("Team"),
            dcc.Dropdown(
                id="filter-team",
                options=[{"label": "All Teams", "value": "ALL"}],
                value="ALL",
                clearable=False,
                style={"minWidth": "160px", "fontSize": "0.9rem"},
            ),
        ], style={"display": "flex", "alignItems": "center"}),
    ], className="filter-bar"),

    # Page content
    html.Div(dash.page_container, className="page-content"),
])


@callback(Output("store-season", "data"), Input("filter-season", "value"))
def sync_season(season):
    return season


@callback(
    Output("filter-team", "options"),
    Output("filter-team", "value"),
    Input("store-season", "data"),
)
def update_team_options(season):
    """Repopulate team dropdown when season changes. Resetting value triggers sync_team."""
    teams = available_teams(season)
    options = [{"label": "All Teams", "value": "ALL"}] + [
        {"label": t, "value": t} for t in teams
    ]
    return options, "ALL"


@callback(Output("store-team", "data"), Input("filter-team", "value"))
def sync_team(team):
    """Write selected team into store. Fires whenever dropdown value changes (including season reset)."""
    return team


if __name__ == "__main__":
    app.run(debug=True)
