# v2/browser/app.py
import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc

SEASONS = ["2024", "2025"]
DEFAULT_SEASON = "2025"

app = dash.Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
server = app.server  # for gunicorn

app.layout = html.Div([
    # Shared state
    dcc.Store(id="store-season", storage_type="session", data=DEFAULT_SEASON),

    # Header + nav
    html.Div([
        html.H1("NHL Data Browser"),
        html.Div([
            dcc.Link(page["name"], href=page["relative_path"])
            for page in dash.page_registry.values()
            if page["path_template"] is None
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
    ], className="filter-bar"),

    # Page content
    html.Div(dash.page_container, className="page-content"),

    # Glossary footer
    html.Footer([
        html.Hr(style={"borderColor": "#dee2e6", "marginBottom": "1rem"}),
        html.H6("Stat Glossary", style={"fontWeight": "bold", "marginBottom": "0.75rem", "color": "#495057"}),
        html.Dl([
            html.Dt("PPI"),
            html.Dd("Pounds Per Inch — a player's weight (lbs) divided by height (inches). A purely physical build metric."),
            html.Dt("PPI+"),
            html.Dd("PPI indexed to the league average (100 = average). 110 means 10% heavier build than average; 90 means 10% lighter."),
            html.Dt("wPPI"),
            html.Dd("Weighted PPI — PPI scaled by a player's average 5v5 TOI share relative to their team. Measures deployment-adjusted physical presence per game."),
            html.Dt("wPPI+"),
            html.Dd("wPPI indexed to the league average (100 = average). Accounts for both build and 5v5 deployment rate."),
            html.Dt("TOI%"),
            html.Dd(
                "Share of the team's 5v5 ice time played by this skater per game. "
                "Computed as 5 × player_toi / team_total_5v5_toi per game, then averaged "
                "across the season. 20% means the skater played 1/5 of all available 5v5 ice time."
            ),
            html.Dt("5v5 TOI/GP"),
            html.Dd("Average 5-on-5 time on ice per game played."),
            html.Dt("vs Top Fwd % / vs Top Def %"),
            html.Dd("Fraction of a player's 5v5 TOI spent against the opposing team's top forwards or defensemen (by TOI)."),
            html.Dt("OPP F TOI / OPP D TOI"),
            html.Dd("TOI-weighted average ice time of opposing forwards and defensemen faced. Higher values mean facing heavier-used opponents."),
        ], style={
            "display": "grid",
            "gridTemplateColumns": "max-content 1fr",
            "columnGap": "1.5rem",
            "rowGap": "0.35rem",
            "fontSize": "0.82rem",
            "color": "#6c757d",
        }),
    ], style={
        "maxWidth": "860px",
        "margin": "3rem auto 2rem auto",
        "padding": "0 1rem",
    }),
])


@callback(Output("store-season", "data"), Input("filter-season", "value"))
def sync_season(season):
    return season




if __name__ == "__main__":
    app.run(debug=True)
