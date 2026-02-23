# v2/browser/pages/games.py
import dash
from dash import html, dash_table, callback, Input, Output
from dash.exceptions import PreventUpdate
from db import query

dash.register_page(__name__, path="/games", name="Games")

_COLUMNS = [
    {"name": "Game ID",   "id": "gameId",      "type": "numeric"},
    {"name": "Date",      "id": "gameDate",     "type": "text"},
    {"name": "Opponent",  "id": "opponent",     "type": "text"},
    {"name": "H/A",       "id": "homeAway",     "type": "text"},
    {"name": "For",       "id": "edmGoals",     "type": "numeric"},
    {"name": "Against",   "id": "oppGoals",     "type": "numeric"},
    {"name": "Result",    "id": "result",       "type": "text"},
    {"name": "Periods",   "id": "periodCount",  "type": "numeric"},
]

_PAGE_SIZE = 25

layout = html.Div([
    html.H2("Games"),
    dash_table.DataTable(
        id="games-table",
        columns=_COLUMNS,
        data=[],
        page_current=0,
        page_size=_PAGE_SIZE,
        page_action="custom",
        sort_action="custom",
        sort_mode="multi",
        sort_by=[],
        filter_action="custom",
        filter_query="",
        fixed_rows={"headers": True},
        style_table={"overflowX": "auto", "minWidth": "100%"},
        style_header={
            "backgroundColor": "#f8f9fa",
            "fontWeight": "bold",
            "border": "1px solid #dee2e6",
            "fontSize": "13px",
        },
        style_cell={
            "textAlign": "left",
            "padding": "8px 12px",
            "border": "1px solid #dee2e6",
            "fontSize": "14px",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    ),
    html.Div(id="games-info", style={"marginTop": "0.5rem", "color": "#6c757d", "fontSize": "13px"}),
])


# --- filter parsing (standard Dash pattern) ---

_OPERATORS = [
    ["ge ", ">="], ["le ", "<="], ["lt ", "<"], ["gt ", ">"],
    ["ne ", "!="], ["eq ", "="],
    ["contains "],
    ["datestartswith "],
]


def _parse_filter(filter_part: str):
    for op_type in _OPERATORS:
        for op in op_type:
            if op in filter_part:
                name_part, value_part = filter_part.split(op, 1)
                name = name_part[name_part.find("{") + 1: name_part.rfind("}")]
                value_part = value_part.strip()
                v0 = value_part[0] if value_part else ""
                if v0 and v0 == value_part[-1] and v0 in ("'", '"', "`"):
                    value = value_part[1:-1].replace("\\" + v0, v0)
                else:
                    try:
                        value = float(value_part)
                    except ValueError:
                        value = value_part
                return name, op_type[0].strip(), value
    return None, None, None


@callback(
    Output("games-table", "data"),
    Output("games-table", "page_count"),
    Output("games-info", "children"),
    Input("games-table", "page_current"),
    Input("games-table", "page_size"),
    Input("games-table", "sort_by"),
    Input("games-table", "filter_query"),
    Input("store-season", "data"),
    Input("store-team", "data"),
)
def update_games_table(page_current, page_size, sort_by, filter_query, season, team):
    if not season:
        raise PreventUpdate

    dff = query(season, "SELECT * FROM games ORDER BY gameDate")

    if dff.empty:
        return [], 1, f"No game data available for {season}."

    # Team filter — when DB is league-wide this column will need rework
    if team and team != "ALL":
        dff = dff[dff["opponent"] == team]

    # Column filter
    if filter_query:
        for expr in filter_query.split(" && "):
            col_name, operator, value = _parse_filter(expr)
            if col_name is None or col_name not in dff.columns:
                continue
            col = dff[col_name].astype(str) if operator in ("contains", "datestartswith") else dff[col_name]
            if operator == "contains":
                dff = dff[col.str.contains(str(value), case=False, na=False)]
            elif operator == "datestartswith":
                dff = dff[col.str.startswith(str(value))]
            elif operator == "=":
                dff = dff[dff[col_name] == value]
            elif operator == "!=":
                dff = dff[dff[col_name] != value]
            elif operator in (">", ">=", "<", "<="):
                op_map = {">": "__gt__", ">=": "__ge__", "<": "__lt__", "<=": "__le__"}
                dff = dff[getattr(dff[col_name], op_map[operator])(value)]

    # Sort
    if sort_by:
        dff = dff.sort_values(
            [c["column_id"] for c in sort_by],
            ascending=[c["direction"] == "asc" for c in sort_by],
        )

    total = len(dff)
    page_count = max(1, -(-total // page_size))
    start = page_current * page_size
    end = min(start + page_size, total)
    info = f"Showing {start + 1}–{end} of {total} games"
    return dff.iloc[start:end].to_dict("records"), page_count, info
