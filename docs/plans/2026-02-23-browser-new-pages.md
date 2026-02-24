# NHL Data Browser — New Pages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a league-wide SQLite database and three new Dash pages to `v2/browser/`: a Skaters Leaderboard, a Team Page, and a Game Page, built on the Basic Scaffold from `docs/plans/2026-02-18-data-browser-app.md`.

**Architecture:** A new `build_league_db.py` loads all 901 competition CSVs, the players CSV, and the flat boxscores CSV into `league.db`. A `league_query()` function in `db.py` serves all new pages. The Skaters page uses URL query params (`?page=N&size=M`) via `dcc.Location` for GET-parameter-driven pagination. The Team and Game pages use Dash `path_template` for clean URLs (`/team/<abbrev>` and `/game/<game_id>`). All TOI values (stored in seconds) are displayed as `MM:SS`. Path-template pages are excluded from the top nav.

**Tech Stack:** Python 3.11+, Dash 3.x, dash-bootstrap-components, pandas, SQLite, uv

---

## File Map

```
v2/browser/
├── app.py                         ← updated: filter path-template pages from nav
├── db.py                          ← updated: league_query(), all_teams()
├── utils.py                       ← new: seconds_to_mmss()
├── build_league_db.py             ← new: builds data/2025/generated/browser/league.db
├── requirements.txt
├── assets/style.css
├── pages/
│   ├── home.py                    ← updated: links to new pages
│   ├── games.py
│   ├── skaters.py                 ← new: leaderboard with GET-param pagination
│   ├── team.py                    ← new: team stats + game log (/team/<abbrev>)
│   └── game.py                    ← new: two-table game view (/game/<game_id>)
└── tests/
    ├── test_smoke.py              ← updated: league_query + new page registrations
    └── test_utils.py              ← new: seconds_to_mmss unit tests
```

**Key data files (read-only, do not modify):**
- `data/2025/generated/competition/*.csv` — 901 files, 15 columns each: `gameId, playerId, team, position, toi_seconds, comp_fwd, comp_def, pct_vs_top_fwd, pct_vs_top_def, height_in, weight_lbs, heaviness, weighted_forward_heaviness, weighted_defense_heaviness, weighted_team_heaviness`
- `data/2025/generated/players/csv/players.csv` — `playerId, firstName, lastName, currentTeamAbbrev, position, ...`
- `data/2025/generated/flatboxscores/boxscores.csv` — `id (gameId), gameDate, awayTeam_abbrev, homeTeam_abbrev, awayTeam_score, homeTeam_score, periodDescriptor_number, ...`

**`comp_fwd` / `comp_def` semantics:** These are in seconds. They represent the mean 5v5 TOI of opposing forwards/defensemen in a single game. Display these as MM:SS everywhere. For season aggregates, compute a TOI-weighted mean across games.

**`pct_vs_top_fwd` / `pct_vs_top_def` semantics:** Fraction (0.0–1.0) of seconds spent facing top-6 forwards / top-4 defensemen. For season aggregates, compute a TOI-weighted mean across games.

**`weighted_team_heaviness`:** All players on the same team in the same game share the same value; use `MAX()` to extract one value per (gameId, team) pair.

---

## Task 1: Implement the Basic Scaffold

**Files:** See `docs/plans/2026-02-18-data-browser-app.md` for exact code.

**Step 1: Read and follow the scaffold plan exactly**

Open `docs/plans/2026-02-18-data-browser-app.md` and complete Tasks 1–5 in sequence. That plan creates:
- `v2/browser/requirements.txt` (updated deps)
- `v2/browser/db.py`
- `v2/browser/app.py`
- `v2/browser/assets/style.css`
- `v2/browser/pages/__init__.py`
- `v2/browser/pages/home.py`
- `v2/browser/pages/games.py`
- `v2/browser/tests/__init__.py`
- `v2/browser/tests/test_smoke.py` (4 tests)

**Step 2: Verify all 4 scaffold tests pass**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py -v
```

Expected: 4 tests PASS.

**Step 3: Commit (the scaffold plan specifies individual commits per task — follow those)**

---

## Task 2: Build league.db

**Files:**
- Create: `v2/browser/build_league_db.py`

**Step 1: Write the failing test**

Append to `v2/browser/tests/test_smoke.py`:

```python
def test_league_db_exists():
    """league.db has been built and contains the three expected tables."""
    from pathlib import Path
    db_path = Path(__file__).resolve().parents[3] / "data" / "2025" / "generated" / "browser" / "league.db"
    assert db_path.exists(), f"league.db not found at {db_path}. Run build_league_db.py first."
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "competition" in tables
    assert "players" in tables
    assert "games" in tables
```

**Step 2: Run the test to confirm it fails**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_league_db_exists -v
```

Expected: FAIL — `league.db not found`.

**Step 3: Create build_league_db.py**

```python
"""
Build a league-wide SQLite database for the NHL Data Browser.

Creates 3 tables:
  - competition: all rows from data/2025/generated/competition/*.csv
  - players:     from data/2025/generated/players/csv/players.csv
  - games:       from data/2025/generated/flatboxscores/boxscores.csv

Usage:
    python v2/browser/build_league_db.py
"""

import glob
import os
import sqlite3

import pandas as pd

SEASON_DIR = "data/2025"
OUTPUT_DB = os.path.join(SEASON_DIR, "generated", "browser", "league.db")
COMPETITION_DIR = os.path.join(SEASON_DIR, "generated", "competition")
PLAYERS_CSV = os.path.join(SEASON_DIR, "generated", "players", "csv", "players.csv")
FLATBOXSCORES_CSV = os.path.join(SEASON_DIR, "generated", "flatboxscores", "boxscores.csv")


def build_competition_table(conn):
    """Load all competition CSVs into the competition table."""
    frames = []
    for path in sorted(glob.glob(os.path.join(COMPETITION_DIR, "*.csv"))):
        df = pd.read_csv(path)
        frames.append(df)
    if not frames:
        print("  competition: 0 rows (no CSVs found)")
        return
    out = pd.concat(frames, ignore_index=True)
    out.to_sql("competition", conn, if_exists="replace", index=False)
    print(f"  competition: {len(out)} rows from {len(frames)} games")


def build_players_table(conn):
    """Load players CSV into the players table (key columns only)."""
    keep = [
        "playerId", "firstName", "lastName",
        "currentTeamAbbrev", "position",
        "heightInInches", "weightInPounds",
    ]
    df = pd.read_csv(PLAYERS_CSV, usecols=keep)
    df.to_sql("players", conn, if_exists="replace", index=False)
    print(f"  players: {len(df)} rows")


def build_games_table(conn):
    """Load flat boxscores CSV into the games table (key columns only)."""
    keep = [
        "id", "gameDate",
        "awayTeam_abbrev", "homeTeam_abbrev",
        "awayTeam_score", "homeTeam_score",
        "periodDescriptor_number",
    ]
    df = pd.read_csv(FLATBOXSCORES_CSV, usecols=keep)
    df = df.rename(columns={"id": "gameId"})
    df.to_sql("games", conn, if_exists="replace", index=False)
    print(f"  games: {len(df)} rows")


def main():
    os.makedirs(os.path.dirname(OUTPUT_DB), exist_ok=True)
    if os.path.exists(OUTPUT_DB):
        os.remove(OUTPUT_DB)
        print(f"Removed existing {OUTPUT_DB}")
    conn = sqlite3.connect(OUTPUT_DB)
    print(f"Building {OUTPUT_DB} ...\n")
    build_competition_table(conn)
    build_players_table(conn)
    build_games_table(conn)
    conn.close()
    size_mb = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print(f"\nDone. Database: {OUTPUT_DB} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
```

**Step 4: Run the builder**

```bash
python v2/browser/build_league_db.py
```

Expected output (approximate):
```
Building data/2025/generated/browser/league.db ...

  competition: ~33000 rows from 901 games
  players: ~941 rows
  games: 902 rows

Done. Database: data/2025/generated/browser/league.db (X.X MB)
```

**Step 5: Run the test to confirm it passes**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_league_db_exists -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add v2/browser/build_league_db.py v2/browser/tests/test_smoke.py
git commit -m "feat: add build_league_db.py and league.db existence test"
```

---

## Task 3: Add league_query() to db.py and create utils.py

**Files:**
- Modify: `v2/browser/db.py`
- Create: `v2/browser/utils.py`
- Create: `v2/browser/tests/test_utils.py`

**Step 1: Write the failing tests**

Create `v2/browser/tests/test_utils.py`:

```python
# v2/browser/tests/test_utils.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import seconds_to_mmss


def test_zero():
    assert seconds_to_mmss(0) == "0:00"


def test_one_minute():
    assert seconds_to_mmss(60) == "1:00"


def test_typical():
    """856 seconds = 14 minutes 16 seconds."""
    assert seconds_to_mmss(856) == "14:16"


def test_single_digit_seconds():
    """Seconds < 10 must be zero-padded."""
    assert seconds_to_mmss(65) == "1:05"


def test_none_returns_zero():
    assert seconds_to_mmss(None) == "0:00"


def test_float_rounds_down():
    """Float input is truncated to int."""
    assert seconds_to_mmss(856.9) == "14:16"
```

Append to `v2/browser/tests/test_smoke.py`:

```python
def test_league_query_returns_dataframe():
    """league_query() always returns a DataFrame, even for missing DB."""
    import pandas as pd
    from db import league_query
    result = league_query("SELECT 1", season="2099")  # nonexistent season
    assert isinstance(result, pd.DataFrame)
```

**Step 2: Run to confirm failures**

```bash
cd v2/browser && python -m pytest tests/test_utils.py tests/test_smoke.py::test_league_query_returns_dataframe -v
```

Expected: all FAIL — `ModuleNotFoundError: No module named 'utils'` and `ImportError`.

**Step 3: Create utils.py**

```python
# v2/browser/utils.py


def seconds_to_mmss(seconds) -> str:
    """Convert numeric seconds to 'M:SS' string. Returns '0:00' for None/zero."""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "0:00"
    m, sec = divmod(abs(s), 60)
    return f"{m}:{sec:02d}"
```

**Step 4: Add league_query() and all_teams() to db.py**

Append the following to `v2/browser/db.py` (after the existing content):

```python
_LEAGUE_DB_PATHS = {
    "2025": _PROJECT_ROOT / "data" / "2025" / "generated" / "browser" / "league.db",
}


def league_query(sql: str, params=(), season: str = "2025") -> "pd.DataFrame":
    """Run parameterized sql against the league DB. Returns empty DataFrame if DB is missing."""
    db_path = _LEAGUE_DB_PATHS.get(season)
    if db_path is None or not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(sql, conn, params=list(params))
    finally:
        conn.close()


def all_teams(season: str = "2025") -> list[str]:
    """Return sorted list of all team abbreviations present in the competition table."""
    df = league_query("SELECT DISTINCT team FROM competition ORDER BY team", season=season)
    if df.empty:
        return []
    return df["team"].tolist()
```

**Step 5: Run all tests**

```bash
cd v2/browser && python -m pytest tests/ -v
```

Expected: all tests PASS (including the 6 new utils tests and league_query test).

**Step 6: Commit**

```bash
git add v2/browser/utils.py v2/browser/db.py v2/browser/tests/test_utils.py v2/browser/tests/test_smoke.py
git commit -m "feat: add utils.py with seconds_to_mmss and league_query to db.py"
```

---

## Task 4: Create pages/skaters.py — Leaderboard

**Files:**
- Create: `v2/browser/pages/skaters.py`

**Step 1: Write the failing test**

Append to `v2/browser/tests/test_smoke.py`:

```python
def test_skaters_page_registered():
    """Skaters page is registered at /skaters."""
    import dash
    import app as _  # noqa: F401
    paths = [p["relative_path"] for p in dash.page_registry.values()]
    assert "/skaters" in paths, "Skaters page not registered"
```

**Step 2: Run to confirm failure**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_skaters_page_registered -v
```

Expected: FAIL — `/skaters not in paths`.

**Step 3: Create pages/skaters.py**

```python
# v2/browser/pages/skaters.py
from urllib.parse import parse_qs, urlencode

import dash
from dash import Input, Output, callback, dcc, dash_table, html
from dash.exceptions import PreventUpdate

from db import league_query
from utils import seconds_to_mmss

dash.register_page(__name__, path="/skaters", name="Skaters")

_PAGE_SIZES = [50, 100, 250]

_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    COALESCE(p.currentTeamAbbrev, c.team)                               AS team,
    SUM(c.toi_seconds)                                                   AS total_toi,
    MAX(c.heaviness)                                                     AS heaviness,
    CAST(SUM(c.pct_vs_top_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_fwd,
    CAST(SUM(c.pct_vs_top_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_def,
    CAST(SUM(c.comp_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_fwd,
    CAST(SUM(c.comp_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_def
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
WHERE c.position IN ('F', 'D')
GROUP BY c.playerId
ORDER BY total_toi DESC
"""

layout = html.Div([
    dcc.Location(id="skaters-location", refresh=False),
    html.H2("Skaters"),
    html.Div(id="skaters-size-links", style={"marginBottom": "0.5rem"}),
    html.Div(id="skaters-table-container"),
    html.Div(id="skaters-page-links", style={"marginTop": "0.75rem"}),
])


@callback(
    Output("skaters-table-container", "children"),
    Output("skaters-page-links", "children"),
    Output("skaters-size-links", "children"),
    Input("skaters-location", "search"),
)
def update_skaters(search):
    params = parse_qs((search or "").lstrip("?"))
    page = int(params.get("page", ["1"])[0])
    size = int(params.get("size", ["50"])[0])
    if size not in _PAGE_SIZES:
        size = 50
    if page < 1:
        page = 1

    df = league_query(_SQL)
    if df.empty:
        return html.Div("No data available."), "", ""

    total = len(df)
    total_pages = max(1, -(-total // size))
    if page > total_pages:
        page = total_pages

    start = (page - 1) * size
    end = min(start + size, total)
    page_df = df.iloc[start:end].copy()

    page_df["toi_display"]        = page_df["total_toi"].apply(seconds_to_mmss)
    page_df["comp_fwd_display"]   = page_df["avg_comp_fwd"].apply(seconds_to_mmss)
    page_df["comp_def_display"]   = page_df["avg_comp_def"].apply(seconds_to_mmss)
    page_df["heaviness"]          = page_df["heaviness"].round(4)
    page_df["avg_pct_vs_top_fwd"] = page_df["avg_pct_vs_top_fwd"].round(4)
    page_df["avg_pct_vs_top_def"] = page_df["avg_pct_vs_top_def"].round(4)

    columns = [
        {"name": "Player",        "id": "playerName"},
        {"name": "Team",          "id": "team"},
        {"name": "5v5 TOI",       "id": "toi_display"},
        {"name": "Heaviness",     "id": "heaviness",           "type": "numeric"},
        {"name": "vs Top Fwd %",  "id": "avg_pct_vs_top_fwd",  "type": "numeric"},
        {"name": "vs Top Def %",  "id": "avg_pct_vs_top_def",  "type": "numeric"},
        {"name": "OPP F TOI",     "id": "comp_fwd_display"},
        {"name": "OPP D TOI",     "id": "comp_def_display"},
    ]
    display_cols = [
        "playerName", "team", "toi_display", "heaviness",
        "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
        "comp_fwd_display", "comp_def_display",
    ]

    table = dash_table.DataTable(
        columns=columns,
        data=page_df[display_cols].to_dict("records"),
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8f9fa", "fontWeight": "bold",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_cell={
            "textAlign": "left", "padding": "8px 12px",
            "border": "1px solid #dee2e6", "fontSize": "14px",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    )

    def _link(p, label=None):
        label = label or str(p)
        qs = urlencode({"page": p, "size": size})
        weight = "bold" if p == page else "normal"
        return dcc.Link(label, href=f"/skaters?{qs}",
                        style={"fontWeight": weight, "marginRight": "8px"})

    page_links = html.Div([
        html.Span(
            f"Page {page} of {total_pages}  —  {start + 1}–{end} of {total} skaters",
            style={"marginRight": "16px", "color": "#6c757d", "fontSize": "13px"},
        ),
        _link(1, "« First") if page > 2 else None,
        _link(page - 1, "‹ Prev") if page > 1 else None,
        _link(page + 1, "Next ›") if page < total_pages else None,
        _link(total_pages, "Last »") if page < total_pages - 1 else None,
    ])

    size_links = html.Div([
        html.Span("Rows per page: ", style={"color": "#6c757d", "fontSize": "13px"}),
        *[
            dcc.Link(
                str(s),
                href=f"/skaters?page=1&size={s}",
                style={
                    "fontWeight": "bold" if s == size else "normal",
                    "marginRight": "8px", "fontSize": "13px",
                },
            )
            for s in _PAGE_SIZES
        ],
    ])

    return table, page_links, size_links
```

**Step 4: Run the test**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_skaters_page_registered -v
```

Expected: PASS.

**Step 5: Start app and verify manually**

```bash
cd v2/browser && python app.py
```

- Navigate to `http://127.0.0.1:8050/skaters` — table loads with ~600+ skaters, sorted by 5v5 TOI descending
- Click "Next ›" — URL changes to `/skaters?page=2&size=50`, table updates
- Click "100" in rows-per-page — URL changes to `/skaters?page=1&size=100`
- All TOI columns display as `MM:SS` (e.g., `14:16` not `856`)
- `pct_vs_top_fwd` displays as 4-decimal fraction (e.g., `0.6716`)

**Step 6: Commit**

```bash
git add v2/browser/pages/skaters.py v2/browser/tests/test_smoke.py
git commit -m "feat: add skaters leaderboard page with GET-param pagination"
```

---

## Task 5: Create pages/team.py — Team Page

**Files:**
- Create: `v2/browser/pages/team.py`

**Step 1: Write the failing test**

Append to `v2/browser/tests/test_smoke.py`:

```python
def test_team_page_registered():
    """Team page is registered with path template /team/<abbrev>."""
    import dash
    import app as _  # noqa: F401
    templates = [p.get("path_template", "") for p in dash.page_registry.values()]
    assert "/team/<abbrev>" in templates, "Team page not registered"
```

**Step 2: Run to confirm failure**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_team_page_registered -v
```

Expected: FAIL.

**Step 3: Create pages/team.py**

```python
# v2/browser/pages/team.py
import dash
from dash import html, dash_table

from db import league_query
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/team/<abbrev>", name="Team")

_PLAYER_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    SUM(c.toi_seconds)                                                   AS total_toi,
    MAX(c.heaviness)                                                     AS heaviness,
    CAST(SUM(c.pct_vs_top_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_fwd,
    CAST(SUM(c.pct_vs_top_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_pct_vs_top_def,
    CAST(SUM(c.comp_fwd * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_fwd,
    CAST(SUM(c.comp_def * c.toi_seconds) AS REAL)
        / NULLIF(SUM(c.toi_seconds), 0)                                  AS avg_comp_def
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
WHERE c.position IN ('F', 'D') AND c.team = ?
GROUP BY c.playerId
ORDER BY total_toi DESC
"""

_GAMES_SQL = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
WHERE homeTeam_abbrev = ? OR awayTeam_abbrev = ?
ORDER BY gameDate ASC
"""

_HEAVINESS_SQL = """
SELECT gameId, team, MAX(weighted_team_heaviness) AS wth
FROM competition
WHERE gameId IN ({placeholders})
GROUP BY gameId, team
"""


def _make_player_table(df):
    df = df.copy()
    df["toi_display"]        = df["total_toi"].apply(seconds_to_mmss)
    df["comp_fwd_display"]   = df["avg_comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"]   = df["avg_comp_def"].apply(seconds_to_mmss)
    df["heaviness"]          = df["heaviness"].round(4)
    df["avg_pct_vs_top_fwd"] = df["avg_pct_vs_top_fwd"].round(4)
    df["avg_pct_vs_top_def"] = df["avg_pct_vs_top_def"].round(4)

    columns = [
        {"name": "Player",        "id": "playerName"},
        {"name": "5v5 TOI",       "id": "toi_display"},
        {"name": "Heaviness",     "id": "heaviness",           "type": "numeric"},
        {"name": "vs Top Fwd %",  "id": "avg_pct_vs_top_fwd",  "type": "numeric"},
        {"name": "vs Top Def %",  "id": "avg_pct_vs_top_def",  "type": "numeric"},
        {"name": "OPP F TOI",     "id": "comp_fwd_display"},
        {"name": "OPP D TOI",     "id": "comp_def_display"},
    ]
    display_cols = [
        "playerName", "toi_display", "heaviness",
        "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
        "comp_fwd_display", "comp_def_display",
    ]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8f9fa", "fontWeight": "bold",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_cell={
            "textAlign": "left", "padding": "8px 12px",
            "border": "1px solid #dee2e6", "fontSize": "14px",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    )


def layout(abbrev=None):
    if not abbrev:
        return html.Div("No team specified.")

    abbrev = abbrev.upper()

    player_df = league_query(_PLAYER_SQL, params=(abbrev,))
    games_df  = league_query(_GAMES_SQL, params=(abbrev, abbrev))

    if games_df.empty:
        return html.Div(f"No data found for team {abbrev}.")

    # Build heaviness lookup: {game_id: {team: value}}
    game_ids = games_df["gameId"].tolist()
    placeholders = ",".join("?" * len(game_ids))
    heaviness_df = league_query(
        _HEAVINESS_SQL.format(placeholders=placeholders),
        params=tuple(game_ids),
    )
    heaviness_map = {}
    for _, row in heaviness_df.iterrows():
        gid = row["gameId"]
        if gid not in heaviness_map:
            heaviness_map[gid] = {}
        heaviness_map[gid][row["team"]] = row["wth"]

    # Build game log rows
    game_rows = []
    for _, row in games_df.iterrows():
        is_home   = row["homeTeam_abbrev"] == abbrev
        opponent  = row["awayTeam_abbrev"] if is_home else row["homeTeam_abbrev"]
        own_score = int(row["homeTeam_score"]) if is_home else int(row["awayTeam_score"])
        opp_score = int(row["awayTeam_score"]) if is_home else int(row["homeTeam_score"])

        if own_score > opp_score:
            result = "W"
        elif int(row["periodDescriptor_number"]) > 3:
            result = "OTL"
        else:
            result = "L"

        gid  = row["gameId"]
        gmap = heaviness_map.get(gid, {})
        game_rows.append({
            "gameDate":      row["gameDate"],
            "opponent":      opponent,
            "homeAway":      "Home" if is_home else "Away",
            "score":         f"{own_score}–{opp_score}",
            "result":        result,
            "opp_heaviness": round(gmap.get(opponent, 0.0), 4),
            "own_heaviness": round(gmap.get(abbrev, 0.0), 4),
            "gameId":        gid,
        })

    result_color = {"W": "green", "OTL": "darkorange", "L": "crimson"}

    th_style = {
        "textAlign": "left", "padding": "6px 10px",
        "borderBottom": "2px solid #dee2e6", "fontSize": "13px",
        "fontWeight": "bold", "color": "#495057",
    }
    td_style = {
        "padding": "6px 10px", "borderBottom": "1px solid #dee2e6", "fontSize": "14px",
    }

    game_table_rows = [
        html.Tr([
            html.Td(r["gameDate"],  style=td_style),
            html.Td(r["opponent"],  style=td_style),
            html.Td(r["homeAway"],  style=td_style),
            html.Td(r["score"],     style=td_style),
            html.Td(r["result"],    style={**td_style, "color": result_color.get(r["result"], "black")}),
            html.Td(r["opp_heaviness"], style=td_style),
            html.Td(r["own_heaviness"], style=td_style),
            html.Td(html.A("View", href=f"/game/{r['gameId']}"), style=td_style),
        ])
        for r in game_rows
    ]

    game_table = html.Table(
        [
            html.Thead(html.Tr([
                html.Th("Date",          style=th_style),
                html.Th("Opponent",      style=th_style),
                html.Th("H/A",           style=th_style),
                html.Th("Score",         style=th_style),
                html.Th("Result",        style=th_style),
                html.Th("OPP Heaviness", style=th_style),
                html.Th("Team Heaviness", style=th_style),
                html.Th("",              style=th_style),
            ])),
            html.Tbody(game_table_rows),
        ],
        style={"width": "100%", "borderCollapse": "collapse"},
    )

    return html.Div([
        html.H2(f"{abbrev} — Season Overview"),
        html.H3("Players"),
        _make_player_table(player_df) if not player_df.empty else html.Div("No player data."),
        html.H3("Game Log", style={"marginTop": "2rem"}),
        game_table,
    ])
```

**Step 4: Run the test**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_team_page_registered -v
```

Expected: PASS.

**Step 5: Start app and verify manually**

```bash
cd v2/browser && python app.py
```

- Navigate to `http://127.0.0.1:8050/team/EDM`
- Player stats table loads: ~25 skaters, sorted by 5v5 TOI desc, all TOI in MM:SS
- Game log shows ~82 rows sorted by date ascending, with W/L/OTL colored
- Each "View" link goes to `/game/<game_id>`

**Step 6: Commit**

```bash
git add v2/browser/pages/team.py v2/browser/tests/test_smoke.py
git commit -m "feat: add team page with player stats and game log"
```

---

## Task 6: Create pages/game.py — Game Page

**Files:**
- Create: `v2/browser/pages/game.py`

**Step 1: Write the failing test**

Append to `v2/browser/tests/test_smoke.py`:

```python
def test_game_page_registered():
    """Game page is registered with path template /game/<game_id>."""
    import dash
    import app as _  # noqa: F401
    templates = [p.get("path_template", "") for p in dash.page_registry.values()]
    assert "/game/<game_id>" in templates, "Game page not registered"
```

**Step 2: Run to confirm failure**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_game_page_registered -v
```

Expected: FAIL.

**Step 3: Create pages/game.py**

```python
# v2/browser/pages/game.py
import dash
from dash import html, dash_table

from db import league_query
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/game/<game_id>", name="Game")

_META_SQL = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games WHERE gameId = ?
"""

_HEAVINESS_SQL = """
SELECT team,
       MAX(weighted_forward_heaviness) AS fwd_heaviness,
       MAX(weighted_defense_heaviness) AS def_heaviness,
       MAX(weighted_team_heaviness)    AS team_heaviness
FROM competition
WHERE gameId = ?
GROUP BY team
"""

_PLAYERS_SQL = """
SELECT
    c.playerId,
    COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
    c.team,
    c.position,
    c.toi_seconds,
    c.comp_fwd,
    c.comp_def,
    c.pct_vs_top_fwd,
    c.pct_vs_top_def
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
WHERE c.gameId = ? AND c.position IN ('F', 'D')
ORDER BY c.toi_seconds DESC
"""


def _make_player_table(df):
    """Build a DataTable with F/D group headers, sorted by TOI desc within each group."""
    df = df.copy().sort_values("toi_seconds", ascending=False)
    df["toi_display"]        = df["toi_seconds"].apply(seconds_to_mmss)
    df["comp_fwd_display"]   = df["comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"]   = df["comp_def"].apply(seconds_to_mmss)
    df["pct_vs_top_fwd"]     = df["pct_vs_top_fwd"].round(4)
    df["pct_vs_top_def"]     = df["pct_vs_top_def"].round(4)

    columns = [
        {"name": "Player",        "id": "playerName"},
        {"name": "5v5 TOI",       "id": "toi_display"},
        {"name": "OPP F TOI",     "id": "comp_fwd_display"},
        {"name": "OPP D TOI",     "id": "comp_def_display"},
        {"name": "vs Top Fwd %",  "id": "pct_vs_top_fwd",  "type": "numeric"},
        {"name": "vs Top Def %",  "id": "pct_vs_top_def",  "type": "numeric"},
    ]
    display_cols = [
        "playerName", "toi_display", "comp_fwd_display",
        "comp_def_display", "pct_vs_top_fwd", "pct_vs_top_def",
    ]

    # Build rows with position group separators
    rows = []
    header_indices = []
    for pos, label in [("F", "Forwards"), ("D", "Defensemen")]:
        pos_df = df[df["position"] == pos]
        if pos_df.empty:
            continue
        header_indices.append(len(rows))
        rows.append({col["id"]: (label if col["id"] == "playerName" else "") for col in columns})
        rows.extend(pos_df[display_cols].to_dict("records"))

    return dash_table.DataTable(
        columns=columns,
        data=rows,
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8f9fa", "fontWeight": "bold",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_cell={
            "textAlign": "left", "padding": "6px 10px",
            "border": "1px solid #dee2e6", "fontSize": "13px",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
            *[
                {
                    "if": {"row_index": i},
                    "backgroundColor": "#e9ecef",
                    "fontWeight": "bold",
                    "color": "#495057",
                }
                for i in header_indices
            ],
        ],
    )


def layout(game_id=None):
    if not game_id:
        return html.Div("No game specified.")

    try:
        gid = int(game_id)
    except (TypeError, ValueError):
        return html.Div(f"Invalid game ID: {game_id}")

    meta_df    = league_query(_META_SQL, params=(gid,))
    heavy_df   = league_query(_HEAVINESS_SQL, params=(gid,))
    players_df = league_query(_PLAYERS_SQL, params=(gid,))

    if meta_df.empty:
        return html.Div(f"Game {gid} not found.")

    meta       = meta_df.iloc[0]
    away       = meta["awayTeam_abbrev"]
    home       = meta["homeTeam_abbrev"]
    away_score = int(meta["awayTeam_score"])
    home_score = int(meta["homeTeam_score"])

    # Score display: winner first
    if home_score > away_score:
        score_str = f"{home} {home_score}–{away_score} {away}"
    else:
        score_str = f"{away} {away_score}–{home_score} {home}"

    # Heaviness summary table
    heavy = {}
    for _, row in heavy_df.iterrows():
        heavy[row["team"]] = row

    def _h(team, col):
        val = heavy.get(team, {}).get(col, None)
        return round(float(val), 4) if val is not None else "—"

    th_style = {
        "textAlign": "left", "padding": "6px 10px",
        "borderBottom": "2px solid #dee2e6", "fontSize": "13px", "fontWeight": "bold",
    }
    td_style = {"padding": "6px 10px", "borderBottom": "1px solid #dee2e6", "fontSize": "14px"}

    heaviness_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Team",            style=th_style),
            html.Th("Fwd Heaviness",   style=th_style),
            html.Th("Def Heaviness",   style=th_style),
            html.Th("Team Heaviness",  style=th_style),
        ])),
        html.Tbody([
            html.Tr([
                html.Td(away, style=td_style),
                html.Td(_h(away, "fwd_heaviness"), style=td_style),
                html.Td(_h(away, "def_heaviness"), style=td_style),
                html.Td(_h(away, "team_heaviness"), style=td_style),
            ]),
            html.Tr([
                html.Td(home, style=td_style),
                html.Td(_h(home, "fwd_heaviness"), style=td_style),
                html.Td(_h(home, "def_heaviness"), style=td_style),
                html.Td(_h(home, "team_heaviness"), style=td_style),
            ]),
        ]),
    ], style={"borderCollapse": "collapse", "marginBottom": "1.5rem"})

    # Player tables by team
    if players_df.empty:
        away_table = html.Div("No player data.")
        home_table = html.Div("No player data.")
    else:
        away_df = players_df[players_df["team"] == away]
        home_df = players_df[players_df["team"] == home]
        away_table = _make_player_table(away_df) if not away_df.empty else html.Div("No player data.")
        home_table = _make_player_table(home_df) if not home_df.empty else html.Div("No player data.")

    return html.Div([
        html.H2(f"Game {gid}"),
        html.P(
            f"{meta['gameDate']}  |  {score_str}",
            style={"fontSize": "1.1rem", "marginBottom": "1rem"},
        ),
        heaviness_table,
        html.Div([
            html.Div([
                html.H4(f"{away} (Away)"),
                away_table,
            ], style={"flex": "1", "minWidth": "0", "marginRight": "1rem"}),
            html.Div([
                html.H4(f"{home} (Home)"),
                home_table,
            ], style={"flex": "1", "minWidth": "0", "marginLeft": "1rem"}),
        ], style={"display": "flex", "alignItems": "flex-start", "gap": "1rem"}),
    ])
```

**Step 4: Run the test**

```bash
cd v2/browser && python -m pytest tests/test_smoke.py::test_game_page_registered -v
```

Expected: PASS.

**Step 5: Start app and verify manually**

```bash
cd v2/browser && python app.py
```

- Navigate to `http://127.0.0.1:8050/game/2025020871` (MIN @ EDM game)
- Header shows date, score like `EDM 4–2 MIN` (winner first)
- Heaviness table shows both teams
- Two tables side by side: away (MIN) on left, home (EDM) on right
- Each table groups by Forwards then Defensemen, sorted by TOI desc within group
- All TOI columns as MM:SS

**Step 6: Commit**

```bash
git add v2/browser/pages/game.py v2/browser/tests/test_smoke.py
git commit -m "feat: add game page with two-table side-by-side player view"
```

---

## Task 7: Update nav and home page

**Files:**
- Modify: `v2/browser/app.py`
- Modify: `v2/browser/pages/home.py`

**Step 1: Update app.py nav to exclude path-template pages**

In `v2/browser/app.py`, find the nav link list and add a filter to exclude pages whose `relative_path` contains `<` (i.e., path-template pages like `/team/<abbrev>` and `/game/<game_id>`):

Change from:
```python
html.Div([
    dcc.Link(page["name"], href=page["relative_path"])
    for page in dash.page_registry.values()
], className="app-nav"),
```

Change to:
```python
html.Div([
    dcc.Link(page["name"], href=page["relative_path"])
    for page in dash.page_registry.values()
    if "<" not in page["relative_path"]
], className="app-nav"),
```

**Step 2: Update pages/home.py to link to new pages**

Replace the contents of `v2/browser/pages/home.py` with:

```python
# v2/browser/pages/home.py
import dash
from dash import html, dcc

dash.register_page(__name__, path="/", name="Home")

layout = html.Div([
    html.H2("Welcome to the NHL Data Browser"),
    html.P("Select a view from the navigation above, or jump directly to a team:"),
    html.Ul([
        html.Li(dcc.Link("Skaters Leaderboard", href="/skaters")),
        html.Li(dcc.Link("Games (EDM)", href="/games")),
    ], style={"lineHeight": "2", "marginBottom": "1rem"}),
    html.P("Navigate to a specific team or game:"),
    html.Ul([
        html.Li([
            "Team page example: ",
            dcc.Link("/team/EDM", href="/team/EDM"),
        ]),
        html.Li([
            "Game page example: ",
            dcc.Link("/game/2025020871", href="/game/2025020871"),
        ]),
    ], style={"lineHeight": "2", "fontFamily": "monospace"}),
])
```

**Step 3: Run all tests**

```bash
cd v2/browser && python -m pytest tests/ -v
```

Expected: all tests PASS.

**Step 4: Start app and verify nav**

```bash
cd v2/browser && python app.py
```

- Top nav shows: `Home  |  Games  |  Skaters` — no `Team` or `Game` entries
- Home page lists links to Skaters, Games, and example team/game URLs
- All three example links navigate correctly

**Step 5: Commit**

```bash
git add v2/browser/app.py v2/browser/pages/home.py
git commit -m "feat: update nav to exclude path-template pages and update home links"
```

---

## Final Verification Checklist

After all tasks:

```bash
cd v2/browser && python -m pytest tests/ -v
```

Expected: all tests green.

Manual walkthrough:
- [ ] `/` — Home page with working links
- [ ] `/skaters` — Leaderboard table, 50 rows, sorted by 5v5 TOI desc, MM:SS display
- [ ] `/skaters?page=2&size=100` — Page 2 with 100 rows
- [ ] `/team/EDM` — Player stats + game log; "View" links in game log work
- [ ] `/team/MIN` — Different team, correct data
- [ ] `/game/2025020871` — Two tables side by side, F/D grouping, correct score header
- [ ] Top nav has Home, Games, Skaters — no Team or Game entries
