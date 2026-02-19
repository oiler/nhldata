# NHL Data Browser App — Basic Scaffold

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Scaffold a multi-page Plotly Dash app in `v2/browser/` with season/team filter controls, clean URLs via Dash's pages system, and a read-only Games DataTable as the first data view.

**Architecture:** Multi-page Dash app (`use_pages=True`) that lives in `v2/browser/`. A shared season toggle (RadioItems) and team dropdown (Dropdown) live in the root layout; their values are stored in `dcc.Store` components so every page can read them. A flat `db.py` module handles SQLite queries against the existing per-season databases. Initial data comes from `data/2025/generated/browser/edm.db`; the DB builder will be extended to league-wide in a future plan.

**Tech Stack:** Python 3.11+, Dash 3.x, dash-bootstrap-components, pandas, SQLite, uv

---

## File Map

```
v2/browser/
├── app.py                   ← multi-page entry point, nav, filters, stores
├── db.py                    ← SQLite query helpers
├── requirements.txt         ← updated deps
├── assets/
│   └── style.css            ← minimal custom CSS
├── pages/
│   ├── home.py              ← landing page  (path: /)
│   └── games.py             ← games table   (path: /games)
└── tests/
    └── test_smoke.py        ← import + registry smoke tests
```

The existing `build_edm_db.py` is not touched.

---

## Task 1: Update requirements and verify install

**Files:**
- Modify: `v2/browser/requirements.txt`

**Step 1: Replace the contents of requirements.txt**

```
dash>=3.0
dash-bootstrap-components>=1.6
pandas
gunicorn
gevent
```

**Step 2: Install**

```bash
uv pip install -r v2/browser/requirements.txt
```

Expected: all packages install with no errors.

**Step 3: Verify key imports**

```bash
python -c "import dash, dash_bootstrap_components, pandas; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add v2/browser/requirements.txt
git commit -m "chore: add Dash deps to browser requirements"
```

---

## Task 2: Create db.py — SQLite query helper

**Files:**
- Create: `v2/browser/db.py`

**Step 1: Write the failing test**

Create `v2/browser/tests/__init__.py` (empty) and `v2/browser/tests/test_smoke.py`:

```python
# v2/browser/tests/test_smoke.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_db_import():
    """db module is importable."""
    import db  # noqa: F401


def test_query_returns_dataframe():
    """query() always returns a DataFrame, even for missing DB."""
    import pandas as pd
    from db import query
    result = query("2099", "SELECT 1")  # season with no DB
    assert isinstance(result, pd.DataFrame)
```

**Step 2: Run test to confirm failure**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_db_import -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'db'`

**Step 3: Create db.py**

```python
# v2/browser/db.py
from pathlib import Path
import sqlite3
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # nhl/

_DB_PATHS = {
    "2025": _PROJECT_ROOT / "data" / "2025" / "generated" / "browser" / "edm.db",
    "2024": _PROJECT_ROOT / "data" / "2024" / "generated" / "browser" / "edm.db",
}


def query(season: str, sql: str) -> pd.DataFrame:
    """Run sql against the season DB. Returns empty DataFrame if DB is missing."""
    db_path = _DB_PATHS.get(season)
    if db_path is None or not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def available_teams(season: str) -> list[str]:
    """Return sorted list of team abbreviations found in the season DB."""
    df = query(season, "SELECT DISTINCT opponent FROM games ORDER BY opponent")
    if df.empty:
        return []
    return df["opponent"].tolist()
```

**Step 4: Run tests**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py -v
```

Expected: both tests PASS.

**Step 5: Commit**

```bash
git add v2/browser/db.py v2/browser/tests/__init__.py v2/browser/tests/test_smoke.py
git commit -m "feat: add db.py SQLite query helper with tests"
```

---

## Task 3: Create app.py — scaffold, nav, and shared filters

**Files:**
- Create: `v2/browser/app.py`
- Create: `v2/browser/assets/style.css`

**Step 1: Add test to test_smoke.py**

Append these two tests to `v2/browser/tests/test_smoke.py`:

```python
def test_app_initializes():
    """App object exists and has a layout."""
    import app as app_module
    assert app_module.app is not None
    assert app_module.app.layout is not None


def test_pages_registered():
    """Home and Games pages are in the page registry."""
    import dash
    import app as _  # noqa: F401 — triggers page discovery
    paths = [p["relative_path"] for p in dash.page_registry.values()]
    assert "/" in paths, "Home page not registered"
    assert "/games" in paths, "Games page not registered"
```

**Step 2: Run the new tests to confirm failure**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_app_initializes -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

**Step 3: Create assets/style.css**

```css
/* v2/browser/assets/style.css */
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background-color: #f8f9fa;
    margin: 0;
}

.app-header {
    background-color: #212529;
    padding: 0.75rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.app-header h1 {
    color: #ffffff;
    margin: 0;
    font-size: 1.2rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}

.app-nav a {
    color: #adb5bd;
    text-decoration: none;
    margin-left: 1.25rem;
    font-size: 0.9rem;
}

.app-nav a:hover {
    color: #ffffff;
}

.filter-bar {
    background-color: #ffffff;
    border-bottom: 1px solid #dee2e6;
    padding: 0.6rem 1.5rem;
    display: flex;
    gap: 2rem;
    align-items: center;
}

.filter-bar label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #6c757d;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-right: 0.5rem;
}

.page-content {
    padding: 1.5rem;
}
```

**Step 4: Create app.py**

```python
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
```

**Step 5: Run all tests**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py -v
```

Expected: `test_app_initializes` and `test_pages_registered` will still fail because `pages/` directory doesn't exist yet. `test_db_import` and `test_query_returns_dataframe` should still pass.

> This is expected — we need pages before the registry tests pass. Continue to Task 4.

**Step 6: Commit what we have**

```bash
git add v2/browser/app.py v2/browser/assets/style.css
git commit -m "feat: add app.py scaffold with nav, season/team filters, and dcc.Store"
```

---

## Task 4: Create the Home page

**Files:**
- Create: `v2/browser/pages/__init__.py` (empty)
- Create: `v2/browser/pages/home.py`

**Step 1: Create pages/__init__.py**

Empty file — just marks the directory as a package.

**Step 2: Create pages/home.py**

```python
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
```

**Step 3: Run tests**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py -v
```

Expected: `test_pages_registered` still fails (only home is registered, not `/games`). Others pass.

**Step 4: Commit**

```bash
git add v2/browser/pages/__init__.py v2/browser/pages/home.py
git commit -m "feat: add home page"
```

---

## Task 5: Create the Games page with DataTable

**Files:**
- Create: `v2/browser/pages/games.py`

**Step 1: Create pages/games.py**

```python
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
            if col_name is None:
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
```

**Step 2: Run all tests**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py -v
```

Expected: all 4 tests PASS.

**Step 3: Start the app and verify**

```bash
cd v2/browser && python app.py
```

- Open http://127.0.0.1:8050/ → Home page with nav links
- Open http://127.0.0.1:8050/games → Games table
  - If 2025 EDM DB exists: rows are populated, sorting and filtering work
  - If 2024 selected: table shows "No game data available for 2024."
- Toggle the season RadioItems → team dropdown resets to "All Teams"

**Step 4: Commit**

```bash
git add v2/browser/pages/games.py
git commit -m "feat: add games page with server-side DataTable, sort, filter, and season/team wiring"
```

---

## Verification Checklist

After all tasks are done, confirm:

- [ ] `python -m pytest v2/browser/tests/ -v` — all green
- [ ] App starts with `python v2/browser/app.py`
- [ ] `/` loads the Home page
- [ ] `/games` loads the Games page
- [ ] Season toggle (2024 ↔ 2025) triggers team dropdown reset
- [ ] Sorting columns in Games table works
- [ ] Typing in a column filter box in Games table filters rows
- [ ] Paging controls work

---

## Notes for Future Plans

- The team filter currently filters EDM games by opponent. Once `build_edm_db.py` is extended to a league-wide DB builder, the team filter should filter `homeTeam` or `awayTeam`.
- Additional pages (Players, Plays, Shifts, Timelines) follow the same pattern: register at a clean path, read from `db.query()`, wire to the shared stores.
