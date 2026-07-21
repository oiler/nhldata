# v2/browser/pages/goalie.py
import dash
import pandas as pd
from dash import html, dash_table, dcc, callback, Input, Output
from dash.dash_table.Format import Format, Scheme

from db import goalies_query
from table_style import table_styles
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/goalie/<goalie_id>", name="Goalie")

_SEASONS_SQL = """
SELECT season, name, teams, gp, toi_s, gsax, gsax_per100, freeze_rate, freeze_pct,
       mean_difficulty_pct
FROM goalie_seasons WHERE goalie_id = ? AND situation = ? ORDER BY season DESC
"""

_GAMES_SQL = """
SELECT season, game_date, opp_abbrev, ga, xga, gsax_game, difficulty_pct,
       perf_z, lev_value, toi_s
FROM goalie_games WHERE goalie_id = ? AND situation = ? ORDER BY game_date DESC
"""

_FREEZE_SQL = "SELECT per_freeze_xga_delta FROM freeze_value WHERE situation = ?"

_FREEZE_MEDIAN_SQL = """
SELECT freeze_rate FROM goalie_seasons
WHERE season = ? AND situation = ? AND freeze_pct IS NOT NULL
"""

# Typical starter workload ~= 1,550 saves/season; matches the freeze-value
# study's conversion constant in v2/goalies/freeze_value.py (SAVES_PER_SEASON).
STARTER_SEASON_SAVES = 1550


def _season_card(r, situation="all"):
    # Each fragment guards only itself: the freeze fragment (rate + pct) renders
    # when freeze_rate is present; the difficulty fragment appends independently
    # when mean_difficulty_pct is present. A NaN in one must not blank the other.
    freeze_parts = []
    if pd.notna(r["freeze_rate"]):
        frag = f"Freeze {r['freeze_rate']:.3f}"
        if pd.notna(r["freeze_pct"]):
            frag += f" (p{r['freeze_pct']:.0f})"
        freeze_parts.append(frag)
    if pd.notna(r["mean_difficulty_pct"]):
        freeze_parts.append(f"Difficulty faced {r['mean_difficulty_pct']:.1f}")

    toi_label = "TOI/GP (all sit)" if situation == "5v5" else "TOI/GP"
    gp_line = f"GP {r['gp']} · {toi_label} {seconds_to_mmss(r['toi_s'] / max(r['gp'], 1))}"
    # gsax/gsax_per100 are null for at least one edge-case single-game season
    # (no shots faced modeled); guard so that row doesn't crash the format spec.
    if pd.notna(r["gsax"]) and pd.notna(r["gsax_per100"]):
        gp_line += f" · GSAx {r['gsax']:+.1f} ({r['gsax_per100']:+.2f}/100)"

    card_children = [
        html.H4(f"{r['season']} — {r['teams']}"),
        html.P(gp_line),
    ]
    if freeze_parts:
        card_children.append(html.P(" · ".join(freeze_parts)))

    return html.Div(card_children, className="card", style={"display": "inline-block", "verticalAlign": "top",
                                "margin": "0 0.75rem 0.75rem 0", "padding": "0.5rem 0.75rem",
                                "border": "1px solid #dee2e6", "borderRadius": "6px"})


def layout(goalie_id=None):
    try:
        gid = int(goalie_id)
    except (TypeError, ValueError):
        return html.Div(html.P("Unknown goalie."))
    return html.Div([
        dcc.Store(id="goalie-gid", data=gid),
        html.Div(id="goalie-content"),
    ])


@callback(
    Output("goalie-content", "children"),
    Input("goalie-gid", "data"),
    Input("goalie-situation", "value"),
)
def render_goalie(gid, situation):
    situation = situation if situation in ("all", "5v5") else "all"
    seasons = goalies_query(_SEASONS_SQL, params=(gid, situation))
    if seasons.empty:
        return html.P("No goalie data for this cut.")
    games = goalies_query(_GAMES_SQL, params=(gid, situation))
    games["toi_display"] = games["toi_s"].apply(seconds_to_mmss)

    children = [html.H2(seasons.iloc[0]["name"]),
                html.Div([_season_card(r, situation) for _, r in seasons.iterrows()])]
    if situation == "5v5":
        children.insert(1, html.P(
            "Strict 5v5 (situationCode 1551). GP and TOI are all-situations; "
            "shot metrics count 5v5 play only.",
            style={"fontSize": "0.8rem", "color": "#6c757d"}))

    fv = goalies_query(_FREEZE_SQL, params=(situation,))
    if not fv.empty:
        delta = float(fv.iloc[0]["per_freeze_xga_delta"])
        latest = seasons.iloc[0]
        if pd.notna(latest["freeze_rate"]) and pd.notna(latest["freeze_pct"]):
            median_df = goalies_query(_FREEZE_MEDIAN_SQL,
                                      params=(int(latest["season"]), situation))
            if not median_df.empty:
                median_rate = median_df["freeze_rate"].median()
                goals_vs_median = -delta * STARTER_SEASON_SAVES * (float(latest["freeze_rate"]) - median_rate)
                children.append(html.P(
                    f"Freeze impact vs the league-median freeze rate: {goals_vs_median:+.1f} "
                    f"goals per starter season (this goalie: p{latest['freeze_pct']:.0f} freeze "
                    f"rate; validated pathway estimate).",
                    style={"fontSize": "0.9rem", "color": "#495057"}))

    toi_name = "TOI (all sit)" if situation == "5v5" else "TOI"
    columns = [
        {"name": "Date", "id": "game_date"},
        {"name": "Opp", "id": "opp_abbrev"},
        {"name": toi_name, "id": "toi_display"},
        {"name": "GA", "id": "ga", "type": "numeric"},
        {"name": "xGA", "id": "xga", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "GSAx", "id": "gsax_game", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Difficulty", "id": "difficulty_pct", "type": "numeric", "format": Format(precision=0, scheme=Scheme.fixed)},
        {"name": "Perf z", "id": "perf_z", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Leverage", "id": "lev_value", "type": "numeric", "format": Format(precision=3, scheme=Scheme.fixed)},
    ]
    display = [c["id"] for c in columns]
    children.append(html.Div(
        dash_table.DataTable(
            columns=columns,
            data=games[display].to_dict("records"),
            sort_action="native", page_action="native", page_size=41,
            **table_styles(),
        ),
        className="table-wrap",
    ))
    return html.Div(children)
