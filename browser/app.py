# browser/app.py
import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc

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

app.layout = html.Div([
    # Shared season state. store-season is memory-only; it follows the
    # filter-season radio, whose session persistence carries the choice across
    # full page loads (DataTable links reload the page).
    dcc.Store(id="store-season", storage_type="memory", data=DEFAULT_SEASON),
    dcc.Location(id="url", refresh=False),

    # Header + nav
    html.Div([
        html.H1("NHL Data", id="top"),
        dbc.Nav(
            [
                dbc.NavLink(
                    page["name"],
                    href=page["relative_path"],
                    active="exact",
                )
                for page in dash.page_registry.values()
                if page["path_template"] is None
                and page["relative_path"] != "/elites"
            ],
            className="app-nav",
        ),
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
        html.Dl([
            html.Dt("Age"),
            html.Dd("Player's age in years as of Sept 15 of the season's start year (Sept 15, 2025 for the 2025-26 season)."),
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
                "high values indicate explosive skaters. Among 2025-26 skaters with 500+ minutes, "
                "forwards had a median near 5 and the top 10% above 10.7; defensemen had a median "
                "near 1.7 and the top 10% above 3.5. Computed from season totals, so it doesn't "
                "change with the date filter."
            ),
            html.Dt("Max MPH"),
            html.Dd(
                "Top season skating speed in mph, recorded by the NHL EDGE tracking system. "
                "A single peak value across one season's regular-season ice time."
            ),
            html.Dt("G, A, P"),
            html.Dd("5v5 goals, assists, and points."),
            html.Dt("P/60"),
            html.Dd("5v5 points per 60 minutes of 5v5 ice time."),
            html.Dt("iSA/60"),
            html.Dd(
                "Individual shot attempts per 60 minutes of 5v5 ice time — shots on goal, "
                "missed shots, and the player's own attempts that were blocked, plus goals. "
                "Measures how much shot volume a skater generates himself."
            ),
            html.Dt("P/100iSA"),
            html.Dd(
                "5v5 points (goals + assists) per 100 individual shot attempts. Measures how "
                "productive each attempt is; playmakers score high. On the leaderboard, shown "
                "only for skaters with at least 50 attempts in the window so small samples "
                "don't distort the sort."
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
            html.Dt("5v5 TOI"),
            html.Dd("5-on-5 time on ice in one game."),
            html.Dt("Line / Pair"),
            html.Dd(
                "The forward line (1–4) or defense pair a skater played on in one game, detected from "
                "the 5v5 combinations that played together most. 1 is the top unit."
            ),
            html.Dt("Dep Score"),
            html.Dd(
                "Raw deployment score for one game, the input to DPS+. Each 5v5 second adds points for "
                "the opposition faced: a defenseman gets 12 minus the line numbers of the three opposing "
                "forwards, and a forward gets 8 minus the pair numbers of the two opposing defensemen. "
                "More ice time against top units gives a higher score."
            ),
            html.Dt("DPS+"),
            html.Dd("Deployment Score Plus — a skater's raw deployment score (Dep Score) indexed to the league average for their position (100 = average). For a defenseman the raw score reflects the opposing forward lines faced; for a forward, the opposing defense pairs. 110 means 10% tougher deployment than average."),
            html.Dt("DPL"),
            html.Dd("Deployment Line — a skater's average line (forwards) or pair (defensemen) across games played, where 1 is the top unit. Lower values indicate higher deployment; 1.0 means used only on the top unit."),
        ], className="glossary"),
        html.H6("Teams and games", className="glossary-subheading"),
        html.Dl([
            html.Dt("P%"),
            html.Dd(
                "Points percentage — standings points (2 for a win, 1 for an overtime or shootout loss) "
                "divided by the maximum possible, 2 per game played."
            ),
            html.Dt("RW"),
            html.Dd("Regulation wins — wins decided in the first three periods."),
            html.Dt("5v5 GF, GA, GD"),
            html.Dd("Goals for, goals against, and goal differential with both goalies in at 5v5 (situation 1551)."),
            html.Dt("FWD, DEF, Team PPI"),
            html.Dd("Average PPI of a team's forwards, defensemen, or all skaters in one game, weighted by their 5v5 ice time."),
            html.Dt("FWD, DEF, Team wPPI"),
            html.Dd("Average season PPI+ of a team's forwards, defensemen, or all skaters, weighted by their 5v5 ice time in one game."),
            html.Dt("Team Heaviness, OPP Heaviness"),
            html.Dd("Team PPI for a team and for its opponent in one game, on the team page's game log."),
            html.Dt("Game wPPI+"),
            html.Dd(
                "A skater's wPPI+ for one game: PPI+ times that game's 5v5 ice time, divided by the "
                "league mean wPPI, times 100. It uses the season's league mean, so it compares directly "
                "with season wPPI+."
            ),
        ], className="glossary"),
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
        html.Dl([
            html.Dt("Shots"),
            html.Dd("Unblocked shot attempts faced (shots on goal plus misses), all strength states by default."),
            html.Dt("xGA"),
            html.Dd(
                "Expected goals against — the sum of each shot's goal probability from our "
                "goalie-blind shot model (rink-adjusted location, shot type, strength, score "
                "state, pre-shot context). What an average goalie would concede on the same shots."
            ),
            html.Dt("xGA/60"),
            html.Dd(
                "Expected goals against per 60 minutes — how much danger the team in front "
                "served up. This is the term that makes GSAx/100 and GSAx/60 disagree."
            ),
            html.Dt("GSAx"),
            html.Dd(
                "Goals Saved Above Expected: xGA − GA. Positive means fewer goals conceded than "
                "the shot mix predicted. Descriptive, not predictive — it is weakly repeatable "
                "year over year (r ≈ 0.1) and did not predict goalies' post-trade results in our "
                "validation."
            ),
            html.Dt("GSAx/100"),
            html.Dd("GSAx per 100 unblocked shots faced — the workload-independent rate form."),
            html.Dt("GSAx/60"),
            html.Dd(
                "GSAx per 60 minutes of ice time — the workload-dependent rate form. Read it "
                "against GSAx/100: a goalie who rates well per shot but poorly per 60 faced a "
                "light shot load, and one who rates well per 60 but poorly per shot was busy."
            ),
            html.Dt("Freeze rate"),
            html.Dd(
                "Share of saves frozen for a stoppage within 5 seconds. The most repeatable goalie "
                "skill in our data (year-over-year r ≈ 0.6–0.7) — it travels with the goalie, not "
                "the team."
            ),
            html.Dt("Freeze pct"),
            html.Dd("League percentile (0–100) of freeze rate within the season, among goalies with 500+ saves."),
            html.Dt("Freeze impact"),
            html.Dd(
                "Goals per starter season attributable to freeze skill, relative to the "
                "league-median freeze rate. From our pricing study: each freeze suppresses "
                "≈ 0.02 expected goals over the next 30 seconds of play versus playing the puck on."
            ),
            html.Dt("Difficulty"),
            html.Dd(
                "Per-game workload percentile (0–100): the game's xG faced per 60 ranked against "
                "all goalie-games of 20+ minutes league-wide. 90 means a harder night than 90% of "
                "goalie starts. In 5v5 mode, the rate is 5v5 xG faced per 60 of total ice time."
            ),
            html.Dt("Difficulty faced"),
            html.Dd("Season average of per-game Difficulty — how hard this goalie's slate of games actually was."),
            html.Dt("Perf z"),
            html.Dd(
                "Difficulty-adjusted single-game score: (xGA − GA) scaled by the game's "
                "shot-quality variance. 0 = as expected for that workload; +2 is an excellent "
                "night. Noisy for short relief stints."
            ),
            html.Dt("Perf (season z̄)"),
            html.Dd("Season mean of per-game Perf z. Compare goalies on this aggregate, not on single games."),
            html.Dt("Leverage"),
            html.Dd(
                "Win-probability value added: each shot outcome weighted by how much win "
                "probability a goal would have swung in that game state — a save in a tied third "
                "period counts more than one up 5-0. Descriptive by design."
            ),
            html.Dt("Difficulty served"),
            html.Dd(
                "Team page — the average per-game Difficulty a team hands its own goalies, the "
                "“o-line grade.” Measures workload served, not goalie quality."
            ),
            html.Dt("xG faced/60"),
            html.Dd("Team page — expected goals against per 60 minutes served to the team's goalies."),
            html.Dt("High-danger share"),
            html.Dd("Team page — share of shots faced from inside 15 feet (rink-adjusted)."),
            html.Dt("Cross-ice/60"),
            html.Dd(
                "Team page — cross-ice quick plays against per 60: shots within 3 seconds of a "
                "same-team attempt from the other side of the ice, the highest-conversion pattern "
                "we measure."
            ),
            html.Dt("Back-to-backs"),
            html.Dd("Team page — games played on the second night of consecutive team game days."),
        ], className="glossary"),
        ], className="glossary-card"),
    ], id="glossary-footer", className="app-footer"),
])


@callback(Output("store-season", "data"), Input("filter-season", "value"))
def sync_season(season):
    return normalize_season(season)


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
