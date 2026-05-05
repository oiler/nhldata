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
        html.P(
            [
                "All metrics are computed at ",
                html.B("5v5"),
                " unless otherwise noted. Any stat ending in ",
                html.Code("/a60"),
                " is computed across ",
                html.B("all-situation"),
                " ice time (5v5, PP, PK, OT).",
            ],
            style={"fontSize": "0.82rem", "color": "#6c757d", "marginBottom": "0.6rem"},
        ),
        html.Dl([
            html.Dt("PPI"),
            html.Dd("Pounds Per Inch — a player's weight (lbs) divided by height (inches). A purely physical build metric."),
            html.Dt("PPI+"),
            html.Dd("PPI indexed to the league average (100 = average). 110 means 10% heavier build than average; 90 means 10% lighter."),
            html.Dt("wPPI"),
            html.Dd("Weighted PPI — PPI scaled by a player's average 5v5 TOI share relative to their team. Measures deployment-adjusted physical presence per game."),
            html.Dt("wPPI+"),
            html.Dd("wPPI indexed to the league average (100 = average). Accounts for both build and 5v5 deployment rate."),
            html.Dt("SB/a60"),
            html.Dd(
                "Speed Bursts per all-situation 60 — count of NHL EDGE skating bursts above 20 mph "
                "per 60 minutes of total ice time (all strengths). A pure speed-attribute metric; "
                "high values indicate explosive skaters. Top-line forwards typically sit in the 5–10 range; "
                "defensemen usually 1–4."
            ),
            html.Dt("tTOI%"),
            html.Dd(
                "Share of the team's 5v5 ice time played by this skater per game. "
                "Computed as 5 × player_toi / team_total_5v5_toi per game, then averaged "
                "across the season. 20% means the skater played 1/5 of all available 5v5 ice time."
            ),
            html.Dt("iTOI%"),
            html.Dd(
                "Fraction of a player's total ice time (all situations) spent at 5v5. "
                "Lower values indicate power play or penalty kill specialists."
            ),
            html.Dt("5v5 TOI/GP"),
            html.Dd("Average 5-on-5 time on ice per game played."),
            html.Dt("DPS+"),
            html.Dd("Deployment Score Plus — a defenseman's raw deployment score indexed to the league average (100 = average). The raw score accumulates points each 5v5 second based on the opposing forward line faced (line 1 opponents score highest). DPS+ normalizes across the league so 110 means a defenseman faces 10% tougher forward deployment than average."),
            html.Dt("DPL"),
            html.Dd("Deployment Line — a forward's average line assignment (1–4) across games played, where line 1 is the top line. Lower values indicate higher deployment; 1.0 means exclusively used as a first-line forward, 4.0 exclusively as a fourth-liner."),
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
