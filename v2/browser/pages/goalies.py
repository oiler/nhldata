# v2/browser/pages/goalies.py
import dash
from dash import html, dash_table, callback, Input, Output
from dash.dash_table.Format import Format, Scheme

from db import goalies_query
from table_style import table_styles
from utils import seconds_to_mmss

dash.register_page(__name__, path="/goalies", name="Goalies")

_CAVEAT = ("GSAx describes results; it is weakly repeatable year-to-year (r ≈ 0.1) "
           "and did not predict post-team-switch performance in our validation. "
           "Read it as what happened, not who is best.")

_SQL = """
SELECT goalie_id, name, teams, gp, toi_s, shots_faced, ga, xga, gsax, gsax_per100,
       freeze_rate, freeze_pct, mean_difficulty_pct, mean_perf_z
FROM goalie_seasons WHERE season = ? AND situation = ? ORDER BY gsax DESC
"""

_CUT_NOTE = ("Strict 5v5 (situationCode 1551): shot metrics count 5v5 play only. "
             "GP and TOI/GP remain all-situations.")


def layout():
    return html.Div([
        html.H2("Goalies"),
        html.P(_CAVEAT, style={"fontSize": "0.85rem", "color": "#6c757d",
                               "maxWidth": "48rem"}),
        html.Div(id="goalies-content"),
    ])


@callback(
    Output("goalies-content", "children"),
    Input("store-season", "data"),
    Input("goalie-situation", "value"),
)
def update_goalies(season, situation):
    season = season or "2025"
    situation = situation if situation in ("all", "5v5") else "all"
    df = goalies_query(_SQL, params=(int(season), situation))
    if df.empty:
        return html.P("No goalie data for this season.")
    df["goalie_link"] = df.apply(lambda r: f"[{r['name']}](/goalie/{r['goalie_id']})", axis=1)
    df["toi_display"] = (df["toi_s"] / df["gp"].where(df["gp"] > 0)).apply(seconds_to_mmss)
    _ci = {"case": "insensitive"}
    toi_name = "TOI/GP (all sit)" if situation == "5v5" else "TOI/GP"
    columns = [
        {"name": "Goalie", "id": "goalie_link", "presentation": "markdown", "filter_options": _ci},
        {"name": "Team", "id": "teams", "filter_options": _ci},
        {"name": "GP", "id": "gp", "type": "numeric"},
        {"name": toi_name, "id": "toi_display", "filter_options": _ci},
        {"name": "Shots", "id": "shots_faced", "type": "numeric"},
        {"name": "GA", "id": "ga", "type": "numeric"},
        {"name": "xGA", "id": "xga", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "GSAx", "id": "gsax", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "GSAx/100", "id": "gsax_per100", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Freeze rate", "id": "freeze_rate", "type": "numeric", "format": Format(precision=3, scheme=Scheme.fixed)},
        {"name": "Freeze pct", "id": "freeze_pct", "type": "numeric", "format": Format(precision=0, scheme=Scheme.fixed)},
        {"name": "Difficulty faced", "id": "mean_difficulty_pct", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "Perf (season z̄)", "id": "mean_perf_z", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
    ]
    display = [c["id"] for c in columns]
    note = ([html.P(_CUT_NOTE, style={"fontSize": "0.8rem", "color": "#6c757d"})]
            if situation == "5v5" else [])
    return html.Div(note + [html.Div(
        dash_table.DataTable(
            columns=columns,
            data=df[display].to_dict("records"),
            markdown_options={"link_target": "_self"},
            sort_action="native", filter_action="native",
            page_action="native", page_size=50,
            **table_styles(),
        ),
        className="table-wrap",
    )])
