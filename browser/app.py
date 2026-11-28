# browser/app.py
import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc

from browser.filters import data_through
from browser.glossary import GOALIES, SKATERS, TEAMS_AND_GAMES
from browser.seasons import DEFAULT_SEASON, SEASONS, normalize_season, season_label

# Dash loads each page straight into sys.modules as browser.pages.<name>
# without importing the parent package, so import it here: then
# `import browser.pages.<name>` finds the loaded page instead of failing.
import browser.pages  # noqa: E402,F401

# Name the app after its package, not this module: Dash 4 prefixes page module
# names with the app's name only when that name is a package. With "browser",
# pages load as browser.pages.<name>, the same name their own imports use, so
# no page is imported (and its callbacks registered) twice. The root folder,
# and with it pages/ and assets/, is browser/ either way.
app = dash.Dash(
    "browser",
    use_pages=True,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
server = app.server  # for gunicorn

app.index_string = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    <style>
      @font-face {
        font-family: "Geist";
        src: url("/assets/fonts/geist-latin.woff2") format("woff2");
        font-weight: 100 900;
        font-display: swap;
      }
      @font-face {
        font-family: "Geist Mono";
        src: url("/assets/fonts/geist-mono-latin.woff2") format("woff2");
        font-weight: 100 900;
        font-display: swap;
      }
    </style>
    {%css%}
  </head>
  <body>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
  </body>
</html>"""

from browser.healthz import healthz_bp
server.register_blueprint(healthz_bp)

import os
if os.environ.get("DASH_ENABLE_SECURITY_HEADERS") == "1":
    from browser.security import install as install_security
    install_security(server)

from browser.canonical_host import install as install_canonical_host
install_canonical_host(server)

def _nav_links():
    """The header's page links. Built per call: a component can sit in only one place."""
    return [
        dbc.NavLink(page["name"], href=page["relative_path"], active="exact")
        for page in dash.page_registry.values()
        if page["path_template"] is None and page["relative_path"] != "/elites"
    ]


def _definition_list(entries):
    return [el for term, definition in entries for el in (html.Dt(term), html.Dd(definition))]


app.layout = html.Div([
    # Shared season state. store-season is memory-only; it follows the
    # filter-season radio, whose session persistence carries the choice across
    # full page loads (DataTable links reload the page).
    dcc.Store(id="store-season", storage_type="memory", data=DEFAULT_SEASON),
    dcc.Location(id="url", refresh=False),

    # Header + nav. Below 640px the link row is hidden and the Menu button shows
    # the same links as a dropdown (style.css); <details> opens without JS.
    html.Div([
        html.H1(dcc.Link("NHL Data", href="/", className="app-wordmark"), id="top"),
        dbc.Nav(_nav_links(), className="app-nav app-nav-wide"),
        html.Details([
            html.Summary("Menu", className="app-menu-button"),
            dbc.Nav(_nav_links(), vertical=True, className="app-menu-list"),
        ], id="app-menu", className="app-menu"),
    ], className="app-header"),

    # Season filter. Starts hidden like goalie-situation-bar; toggle_season_bar
    # shows it on season-aware pages, which avoids a flash on the others.
    html.Div([
        html.Fieldset([
            html.Legend("Season", className="filter-bar-label"),
            dbc.RadioItems(
                id="filter-season",
                options=[{"label": season_label(s), "value": s} for s in SEASONS],
                value=DEFAULT_SEASON,
                inline=True,
                persistence=True,
                persistence_type="session",
                class_name="season-options",
            ),
        ], className="season-fieldset"),
        html.Span(id="season-data-date", className="season-data-date"),
    ], id="season-bar", className="filter-bar", style={"display": "none"}),

    # Goalie situation filter — visible only on goalie-bearing pages (toggled
    # below). Session-persisted so the choice follows the user across views.
    html.Div([
        html.Div([
            html.Label("Situations", className="filter-bar-label"),
            dcc.Dropdown(
                id="goalie-situation",
                options=[{"label": "All situations", "value": "all"},
                         {"label": "5v5 (1551)", "value": "5v5"}],
                value="all", clearable=False, searchable=False,
                persistence=True, persistence_type="session",
                style={"width": "200px"},
            ),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
    ], id="goalie-situation-bar", className="filter-bar",
       style={"display": "none"}),

    # Page content
    html.Div(dash.page_container, className="page-content"),

    # Glossary footer
    html.Footer([
        html.Div([
            html.H6("Stat Glossary", id="glossary", className="glossary-heading"),
            html.A("↑ Back to top", href="#top", className="glossary-backtotop"),
        ], className="glossary-header"),
        html.Div([
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
            className="glossary-note",
        ),
        html.H6("Skaters", className="glossary-subheading"),
        html.Dl(_definition_list(SKATERS), className="glossary"),
        html.H6("Teams and games", className="glossary-subheading"),
        html.Dl(_definition_list(TEAMS_AND_GAMES), className="glossary"),
        html.H6("Goalies", className="glossary-subheading"),
        html.P(
            [
                "Goalie stats cover ",
                html.B("all strength states"),
                " by default; the situation filter on goalie pages switches every "
                "goalie stat to the strict ",
                html.B("5v5"),
                " cut (situationCode 1551 — both goalies in net, five skaters each; "
                "4v4 and 3v3 excluded), including TOI and every per-60 rate. GP "
                "counts appearances in all situations. "
                "Seasons 2021-22 through 2025-26. These are descriptive "
                "measurements: our validation found goalie results are dominated by "
                "environment and sample noise, so read them as what happened, not as "
                "talent rankings.",
            ],
            className="glossary-note",
        ),
        html.Dl(_definition_list(GOALIES), className="glossary"),
        ], className="glossary-card"),
    ], id="glossary-footer", className="app-footer"),
])


@callback(Output("store-season", "data"), Input("filter-season", "value"))
def sync_season(season):
    return normalize_season(season)


@callback(Output("season-data-date", "children"), Input("store-season", "data"))
def show_data_date(season):
    return data_through(season)


_SEASON_PAGES = ("/games", "/teams", "/skaters", "/goalies")
_SEASON_PAGE_PREFIXES = ("/team/", "/player/")


@callback(Output("season-bar", "style"), Input("url", "pathname"))
def toggle_season_bar(pathname):
    p = pathname or ""
    show = p in _SEASON_PAGES or p.startswith(_SEASON_PAGE_PREFIXES)
    return {} if show else {"display": "none"}


# The glossary footer lives in the global layout (shows on every page). Hide it on
# the home page only, which has its own intro content and doesn't need the glossary.
@callback(Output("glossary-footer", "style"), Input("url", "pathname"))
def toggle_glossary_footer(pathname):
    return {"display": "none"} if pathname == "/" else {}


@callback(Output("goalie-situation-bar", "style"), Input("url", "pathname"))
def toggle_goalie_situation_bar(pathname):
    p = pathname or ""
    show = p == "/goalies" or p.startswith("/goalie/") or p.startswith("/team/")
    return {} if show else {"display": "none"}


if __name__ == "__main__":
    app.run(debug=True)
