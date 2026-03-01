# Callback Filters — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor 4 browser pages from static layouts to callback-driven pages with date range and home/away filters, recalculating deployment stats (wPPI, wPPI+, avg_toi_share) on the fly.

**Architecture:** Each page's `layout()` returns filter controls + an empty container. A Dash callback fires when filters change, re-queries the DB with date/H-A constraints, computes deployment metrics in Python, and returns updated content. A shared `filters.py` utility provides consistent filter bar UI.

**Tech Stack:** Dash callbacks (`@callback`), `dcc.DatePickerSingle`, `html.Button` toggle group, SQLite parameterized queries, pandas for wPPI recalculation.

---

### Task 1: Shared filter bar utility

**Files:**
- Create: `v2/browser/filters.py`

This module provides `make_filter_bar()` and `season_date_range()` used by all 4 pages.

---

**Step 1: Implement `v2/browser/filters.py`**

```python
# v2/browser/filters.py
"""Shared filter bar components for browser pages."""

from dash import html, dcc
from db import league_query


def season_date_range(season: str = "2025") -> tuple[str, str]:
    """Return (min_date, max_date) from the games table."""
    df = league_query(
        "SELECT MIN(gameDate) AS min_d, MAX(gameDate) AS max_d FROM games WHERE awayTeam_score IS NOT NULL",
        season=season,
    )
    if df.empty or df.iloc[0]["min_d"] is None:
        return ("2025-10-01", "2026-06-30")
    return (df.iloc[0]["min_d"], df.iloc[0]["max_d"])


def make_filter_bar(page_id: str, include_home_away: bool = True) -> html.Div:
    """Build a filter bar with date pickers and optional home/away toggle.

    Component IDs are namespaced by page_id to avoid collisions:
      - f"{page_id}-date-start"
      - f"{page_id}-date-end"
      - f"{page_id}-home-away"  (only if include_home_away=True)
    """
    min_date, max_date = season_date_range()

    date_start = dcc.DatePickerSingle(
        id=f"{page_id}-date-start",
        date=min_date,
        min_date_allowed=min_date,
        max_date_allowed=max_date,
        display_format="MMM D, YYYY",
        style={"marginRight": "1rem"},
    )
    date_end = dcc.DatePickerSingle(
        id=f"{page_id}-date-end",
        date=max_date,
        min_date_allowed=min_date,
        max_date_allowed=max_date,
        display_format="MMM D, YYYY",
        style={"marginRight": "1rem"},
    )

    children = [
        html.Label("From", style={"marginRight": "0.5rem", "fontWeight": "bold", "fontSize": "0.9rem"}),
        date_start,
        html.Label("To", style={"marginRight": "0.5rem", "fontWeight": "bold", "fontSize": "0.9rem"}),
        date_end,
    ]

    if include_home_away:
        btn_style = {
            "padding": "6px 16px", "border": "1px solid #dee2e6",
            "backgroundColor": "#fff", "cursor": "pointer",
            "fontSize": "0.85rem",
        }
        active_style = {**btn_style, "backgroundColor": "#0d6efd", "color": "#fff", "borderColor": "#0d6efd"}

        children.append(
            html.Div([
                html.Button("All", id=f"{page_id}-ha-all", n_clicks=0,
                            style={**active_style, "borderRadius": "4px 0 0 4px"}),
                html.Button("Home", id=f"{page_id}-ha-home", n_clicks=0,
                            style={**btn_style, "borderLeft": "none"}),
                html.Button("Away", id=f"{page_id}-ha-away", n_clicks=0,
                            style={**btn_style, "borderLeft": "none", "borderRadius": "0 4px 4px 0"}),
                dcc.Store(id=f"{page_id}-home-away", data="all"),
            ], style={"display": "inline-flex", "marginLeft": "1rem"})
        )

    return html.Div(
        children,
        style={
            "display": "flex", "alignItems": "center", "padding": "0.75rem 0",
            "marginBottom": "1rem", "flexWrap": "wrap", "gap": "0.5rem",
        },
    )
```

**Step 2: Verify it imports cleanly**

```bash
cd /Users/jrf1039/files/projects/nhl/v2/browser && python -c "from filters import make_filter_bar, season_date_range; print('ok')"
```

Expected: `ok`

---

### Task 2: Shared home/away toggle callback utility

**Files:**
- Modify: `v2/browser/filters.py` (append)

The H/A toggle needs a callback to highlight the active button and update the store. Since 3 pages use identical toggle logic, provide a helper that registers the callback.

---

**Step 1: Append to `v2/browser/filters.py`**

```python
from dash import callback, Input, Output, State, ctx


def register_home_away_callback(page_id: str):
    """Register a callback that syncs the H/A toggle buttons with the store."""

    btn_style = {
        "padding": "6px 16px", "border": "1px solid #dee2e6",
        "backgroundColor": "#fff", "cursor": "pointer",
        "fontSize": "0.85rem",
    }
    active_style = {**btn_style, "backgroundColor": "#0d6efd", "color": "#fff", "borderColor": "#0d6efd"}

    @callback(
        Output(f"{page_id}-home-away", "data"),
        Output(f"{page_id}-ha-all", "style"),
        Output(f"{page_id}-ha-home", "style"),
        Output(f"{page_id}-ha-away", "style"),
        Input(f"{page_id}-ha-all", "n_clicks"),
        Input(f"{page_id}-ha-home", "n_clicks"),
        Input(f"{page_id}-ha-away", "n_clicks"),
    )
    def toggle_home_away(n_all, n_home, n_away):
        triggered = ctx.triggered_id or f"{page_id}-ha-all"
        styles = {
            f"{page_id}-ha-all": {**btn_style, "borderRadius": "4px 0 0 4px"},
            f"{page_id}-ha-home": {**btn_style, "borderLeft": "none"},
            f"{page_id}-ha-away": {**btn_style, "borderLeft": "none", "borderRadius": "0 4px 4px 0"},
        }
        value_map = {
            f"{page_id}-ha-all": "all",
            f"{page_id}-ha-home": "home",
            f"{page_id}-ha-away": "away",
        }
        styles[triggered] = {**styles[triggered], "backgroundColor": "#0d6efd", "color": "#fff", "borderColor": "#0d6efd"}
        value = value_map.get(triggered, "all")
        return value, styles[f"{page_id}-ha-all"], styles[f"{page_id}-ha-home"], styles[f"{page_id}-ha-away"]
```

---

### Task 3: Shared wPPI recalculation utility

**Files:**
- Modify: `v2/browser/filters.py` (append)

Extract the wPPI/wPPI+/avg_toi_share calculation into a reusable function that operates on a filtered competition dataframe. Used by skaters and team page callbacks.

---

**Step 1: Append to `v2/browser/filters.py`**

```python
import pandas as pd


def compute_deployment_metrics(comp_df: pd.DataFrame, ppi_df: pd.DataFrame) -> pd.DataFrame:
    """Compute wPPI, wPPI+, avg_toi_share from filtered competition data.

    Args:
        comp_df: Filtered competition rows with columns:
                 playerId, team, gameId, toi_seconds, position
        ppi_df:  Player metrics with columns: playerId, ppi, ppi_plus
                 (full-season, not filtered)

    Returns:
        DataFrame indexed by playerId with columns:
        ppi, ppi_plus, wppi, wppi_plus, avg_toi_share
    """
    if comp_df.empty or ppi_df.empty:
        return pd.DataFrame()

    ppi = ppi_df.set_index("playerId")[["ppi", "ppi_plus"]]

    # Games played per player in filtered window
    gp = comp_df.groupby("playerId")["gameId"].nunique().rename("games_played")
    eligible = ppi.join(gp, how="inner")
    eligible = eligible[eligible["games_played"] >= 5].copy()
    if eligible.empty:
        return pd.DataFrame()

    # wPPI: PPI × games-weighted average TOI share across team stints
    eligible_comp = comp_df[comp_df["playerId"].isin(eligible.index)]
    player_team_toi   = eligible_comp.groupby(["playerId", "team"])["toi_seconds"].sum()
    player_team_games = eligible_comp.groupby(["playerId", "team"])["gameId"].nunique()
    player_avg_toi    = player_team_toi / player_team_games

    team_total_toi    = eligible_comp.groupby("team")["toi_seconds"].sum()
    team_unique_games = eligible_comp.groupby("team")["gameId"].nunique()
    team_avg_toi      = team_total_toi / team_unique_games

    share_num: dict[int, float] = {}
    share_den: dict[int, int] = {}
    for (pid, team), avg_toi in player_avg_toi.items():
        t_avg = team_avg_toi.get(team, 0)
        if t_avg == 0:
            continue
        share = avg_toi / t_avg
        games = int(player_team_games[(pid, team)])
        share_num[pid] = share_num.get(pid, 0.0) + share * games
        share_den[pid] = share_den.get(pid, 0) + games

    wppi_map = {}
    for pid, num in share_num.items():
        den = share_den.get(pid, 0)
        if den == 0:
            continue
        wppi_map[pid] = eligible.loc[pid, "ppi"] * (num / den)

    eligible["wppi"] = pd.Series(wppi_map)
    eligible = eligible[eligible["wppi"].notna()]
    if eligible.empty:
        return pd.DataFrame()

    mean_wppi = eligible["wppi"].mean()
    eligible["wppi_plus"] = 100.0 * eligible["wppi"] / mean_wppi

    # avg_toi_share
    game_team_toi = comp_df.groupby(["team", "gameId"])["toi_seconds"].transform("sum")
    cs = comp_df.copy()
    cs["toi_share"] = 5.0 * cs["toi_seconds"] / game_team_toi.where(game_team_toi > 0)
    avg_share = (
        cs[cs["playerId"].isin(eligible.index)]
        .groupby("playerId")["toi_share"]
        .mean()
        .rename("avg_toi_share")
    )
    eligible = eligible.join(avg_share)

    return eligible[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]]
```

---

### Task 4: Refactor games page

**Files:**
- Modify: `v2/browser/pages/games.py`

Convert from static layout to callback-driven. Date range only (no H/A).

---

**Step 1: Rewrite `v2/browser/pages/games.py`**

```python
# v2/browser/pages/games.py
import dash
from dash import html, dash_table, callback, Input, Output

from db import league_query
from filters import make_filter_bar

dash.register_page(__name__, path="/games", name="Games")

_SQL = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
WHERE awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
ORDER BY gameDate DESC
"""


def layout():
    return html.Div([
        html.H2("Games"),
        make_filter_bar("games", include_home_away=False),
        html.Div(id="games-content"),
    ])


@callback(
    Output("games-content", "children"),
    Input("games-date-start", "date"),
    Input("games-date-end", "date"),
)
def update_games(date_start, date_end):
    if not date_start or not date_end:
        return html.P("Select a date range.")

    df = league_query(_SQL, params=(date_start, date_end))
    if df.empty:
        return html.P("No games found in this range.")

    df["game_link"] = df["gameId"].apply(lambda gid: f"[{gid}](/game/{gid})")
    df["score"] = (
        df["awayTeam_score"].fillna(0).astype(int).astype(str)
        + "\u2013"
        + df["homeTeam_score"].fillna(0).astype(int).astype(str)
    )

    def _result(periods):
        try:
            p = int(periods or 3)
        except (TypeError, ValueError):
            p = 3
        if p == 4:
            return "OT"
        if p >= 5:
            return "SO"
        return "REG"

    df["result"] = df["periodDescriptor_number"].apply(_result)

    columns = [
        {"name": "Game",   "id": "game_link",        "presentation": "markdown"},
        {"name": "Date",   "id": "gameDate",          "type": "text"},
        {"name": "Away",   "id": "awayTeam_abbrev",   "type": "text"},
        {"name": "Home",   "id": "homeTeam_abbrev",   "type": "text"},
        {"name": "Score",  "id": "score",             "type": "text"},
        {"name": "Result", "id": "result",            "type": "text"},
    ]
    display_cols = ["game_link", "gameDate", "awayTeam_abbrev", "homeTeam_abbrev", "score", "result"]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        markdown_options={"link_target": "_self"},
        sort_action="native",
        filter_action="native",
        filter_options={"case": "insensitive"},
        page_action="native",
        page_size=50,
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
```

**Step 2: Test manually**

```bash
cd /Users/jrf1039/files/projects/nhl/v2/browser && python app.py
```

Open http://127.0.0.1:8050/games — verify date pickers appear and filtering works.

---

### Task 5: Refactor skaters page

**Files:**
- Modify: `v2/browser/pages/skaters.py`

Convert to callback-driven with date range + H/A toggle. Deployment stats (wPPI, wPPI+, avg_toi_share) recalculated from filtered data. PPI/PPI+ remain fixed.

---

**Step 1: Rewrite `v2/browser/pages/skaters.py`**

```python
# v2/browser/pages/skaters.py
import dash
from dash import html, dash_table, callback, Input, Output
from dash.dash_table import FormatTemplate
from dash.dash_table.Format import Format, Scheme

from db import league_query
from filters import make_filter_bar, register_home_away_callback, compute_deployment_metrics
from utils import seconds_to_mmss

dash.register_page(__name__, path="/skaters", name="Skaters")
register_home_away_callback("skaters")

_COMP_SQL = """
SELECT c.playerId,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
       GROUP_CONCAT(DISTINCT c.team) AS teams_raw,
       c.position, c.team, c.gameId, c.toi_seconds,
       c.pct_vs_top_fwd, c.pct_vs_top_def,
       c.comp_fwd, c.comp_def,
       g.gameDate, g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
JOIN games g ON c.gameId = g.gameId
WHERE c.position IN ('F', 'D')
  AND g.gameDate BETWEEN ? AND ?
"""

_HA_HOME = " AND c.team = g.homeTeam_abbrev"
_HA_AWAY = " AND c.team = g.awayTeam_abbrev"

_PPI_SQL = """
SELECT playerId, ppi, ppi_plus FROM player_metrics
"""


def layout():
    return html.Div([
        html.H2("Skaters"),
        make_filter_bar("skaters", include_home_away=True),
        html.Div(id="skaters-content"),
    ])


@callback(
    Output("skaters-content", "children"),
    Input("skaters-date-start", "date"),
    Input("skaters-date-end", "date"),
    Input("skaters-home-away", "data"),
)
def update_skaters(date_start, date_end, home_away):
    if not date_start or not date_end:
        return html.P("Select a date range.")

    sql = _COMP_SQL
    if home_away == "home":
        sql += _HA_HOME
    elif home_away == "away":
        sql += _HA_AWAY

    comp_df = league_query(sql, params=(date_start, date_end))
    if comp_df.empty:
        return html.P("No data found for this range.")

    ppi_df = league_query(_PPI_SQL)

    # Aggregate per player
    grouped = comp_df.groupby("playerId").agg(
        playerName=("playerName", "first"),
        teams_raw=("team", lambda x: ",".join(sorted(x.unique()))),
        position=("position", "first"),
        games_played=("gameId", "nunique"),
        total_toi=("toi_seconds", "sum"),
        weighted_pct_fwd=("pct_vs_top_fwd", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
        weighted_pct_def=("pct_vs_top_def", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
        weighted_comp_fwd=("comp_fwd", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
        weighted_comp_def=("comp_def", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
    )
    grouped["toi_per_game"] = grouped["total_toi"] / grouped["games_played"]
    grouped["avg_pct_vs_top_fwd"] = grouped["weighted_pct_fwd"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
    grouped["avg_pct_vs_top_def"] = grouped["weighted_pct_def"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
    grouped["avg_comp_fwd"] = grouped["weighted_comp_fwd"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
    grouped["avg_comp_def"] = grouped["weighted_comp_def"] / grouped["total_toi"].where(grouped["total_toi"] > 0)

    # Deployment metrics (wPPI, wPPI+, avg_toi_share) from filtered data
    metrics = compute_deployment_metrics(comp_df, ppi_df)
    if not metrics.empty:
        grouped = grouped.join(metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]])
    else:
        for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]:
            grouped[col] = None

    df = grouped.reset_index()
    df = df.sort_values("toi_per_game", ascending=False)

    # Display formatting
    for col, decimals in [("ppi", 2), ("ppi_plus", 1), ("wppi", 4), ("wppi_plus", 1)]:
        df[col] = df[col].round(decimals)
    df["team"] = df["teams_raw"].apply(lambda s: "/".join(sorted(s.split(","))) if s else "")
    df["player_link"] = df.apply(lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1)
    df["toi_display"]      = df["toi_per_game"].apply(seconds_to_mmss)
    df["comp_fwd_display"] = df["avg_comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"] = df["avg_comp_def"].apply(seconds_to_mmss)

    _ci = {"case": "insensitive"}
    columns = [
        {"name": "Player",       "id": "player_link",       "presentation": "markdown", "filter_options": _ci},
        {"name": "Team",         "id": "team",               "filter_options": _ci},
        {"name": "Pos",          "id": "position",           "filter_options": _ci},
        {"name": "GP",           "id": "games_played",       "type": "numeric"},
        {"name": "5v5 TOI/GP",   "id": "toi_display",        "filter_options": _ci},
        {"name": "TOI%",         "id": "avg_toi_share", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "vs Top Fwd %", "id": "avg_pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Top Def %", "id": "avg_pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "OPP F TOI",    "id": "comp_fwd_display",   "filter_options": _ci},
        {"name": "OPP D TOI",    "id": "comp_def_display",   "filter_options": _ci},
        {"name": "PPI",   "id": "ppi",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "wPPI",  "id": "wppi",      "type": "numeric", "format": Format(precision=4, scheme=Scheme.fixed)},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "team", "position", "games_played", "toi_display",
        "avg_toi_share", "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
        "comp_fwd_display", "comp_def_display",
        "ppi", "ppi_plus", "wppi", "wppi_plus",
    ]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        markdown_options={"link_target": "_self"},
        sort_action="native",
        filter_action="native",
        page_action="native",
        page_size=50,
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
```

**Step 2: Test manually**

```bash
cd /Users/jrf1039/files/projects/nhl/v2/browser && python app.py
```

Open http://127.0.0.1:8050/skaters — verify date pickers and H/A toggle work. Check that wPPI values change when filtering to a date range or home/away.

---

### Task 6: Refactor team page

**Files:**
- Modify: `v2/browser/pages/team.py`

Convert to callback-driven with date range + H/A toggle. Both the player stats tables and the game log filter. The team page uses `path_template="/team/<abbrev>"`, so the callback reads `abbrev` from the URL.

---

**Step 1: Rewrite `v2/browser/pages/team.py`**

```python
# v2/browser/pages/team.py
import dash
import pandas as pd
from dash import html, dash_table, callback, Input, Output, dcc
from dash.dash_table import FormatTemplate
from dash.dash_table.Format import Format, Scheme

from db import league_query
from filters import make_filter_bar, register_home_away_callback, compute_deployment_metrics
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/team/<abbrev>", name="Team")
register_home_away_callback("team")

_COMP_SQL = """
SELECT c.playerId,
       COALESCE(p.firstName || ' ' || p.lastName, 'Player ' || c.playerId) AS playerName,
       c.position, c.team, c.gameId, c.toi_seconds,
       c.pct_vs_top_fwd, c.pct_vs_top_def,
       c.comp_fwd, c.comp_def,
       g.gameDate, g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
LEFT JOIN players p ON c.playerId = p.playerId
JOIN games g ON c.gameId = g.gameId
WHERE c.position IN ('F', 'D') AND c.team = ?
  AND g.gameDate BETWEEN ? AND ?
"""

_HA_HOME = " AND c.team = g.homeTeam_abbrev"
_HA_AWAY = " AND c.team = g.awayTeam_abbrev"

_GAMES_SQL = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
WHERE (homeTeam_abbrev = ? OR awayTeam_abbrev = ?)
  AND awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
ORDER BY gameDate ASC
"""

_GAMES_HA_HOME = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
WHERE homeTeam_abbrev = ?
  AND awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
ORDER BY gameDate ASC
"""

_GAMES_HA_AWAY = """
SELECT gameId, gameDate, awayTeam_abbrev, homeTeam_abbrev,
       awayTeam_score, homeTeam_score, periodDescriptor_number
FROM games
WHERE awayTeam_abbrev = ?
  AND awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
ORDER BY gameDate ASC
"""

_HEAVINESS_SQL = """
SELECT gameId, team, MAX(weighted_team_heaviness) AS wth
FROM competition
WHERE gameId IN ({placeholders})
GROUP BY gameId, team
"""

_PPI_SQL = "SELECT playerId, ppi, ppi_plus FROM player_metrics"


def _make_position_table(df):
    """Build a single sortable DataTable for one position group."""
    df = df.copy()
    df["player_link"]      = df.apply(lambda r: f"[{r['playerName']}](/player/{r['playerId']})", axis=1)
    df["toi_display"]      = df["toi_per_game"].apply(seconds_to_mmss)
    df["comp_fwd_display"] = df["avg_comp_fwd"].apply(seconds_to_mmss)
    df["comp_def_display"] = df["avg_comp_def"].apply(seconds_to_mmss)
    columns = [
        {"name": "Player",       "id": "player_link",        "presentation": "markdown"},
        {"name": "GP",           "id": "games_played",       "type": "numeric"},
        {"name": "5v5 TOI/GP",   "id": "toi_display"},
        {"name": "TOI%",         "id": "avg_toi_share", "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "vs Top Fwd %", "id": "avg_pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Top Def %", "id": "avg_pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "OPP F TOI",    "id": "comp_fwd_display"},
        {"name": "OPP D TOI",    "id": "comp_def_display"},
        {"name": "PPI",   "id": "ppi",       "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "wPPI",  "id": "wppi",      "type": "numeric", "format": Format(precision=4, scheme=Scheme.fixed)},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
    ]
    display_cols = [
        "player_link", "games_played", "toi_display", "avg_toi_share",
        "avg_pct_vs_top_fwd", "avg_pct_vs_top_def",
        "comp_fwd_display", "comp_def_display",
        "ppi", "ppi_plus", "wppi", "wppi_plus",
    ]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        markdown_options={"link_target": "_self"},
        sort_action="native",
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


def _make_player_tables(df):
    sections = []
    for pos, label in [("F", "Forwards"), ("D", "Defensemen")]:
        pos_df = df[df["position"] == pos]
        if pos_df.empty:
            continue
        sections.append(html.H4(label, style={"marginTop": "1.5rem", "marginBottom": "0.25rem"}))
        sections.append(_make_position_table(pos_df))
    return html.Div(sections) if sections else html.Div("No player data.")


def layout(abbrev=None):
    if not abbrev:
        return html.Div("No team specified.")
    abbrev = abbrev.upper()
    return html.Div([
        html.H2(f"{abbrev} — Season Overview"),
        dcc.Store(id="team-abbrev", data=abbrev),
        make_filter_bar("team", include_home_away=True),
        html.Div(id="team-content"),
    ])


@callback(
    Output("team-content", "children"),
    Input("team-date-start", "date"),
    Input("team-date-end", "date"),
    Input("team-home-away", "data"),
    Input("team-abbrev", "data"),
)
def update_team(date_start, date_end, home_away, abbrev):
    if not date_start or not date_end or not abbrev:
        return html.P("Select a date range.")

    # Player stats
    sql = _COMP_SQL
    if home_away == "home":
        sql += _HA_HOME
    elif home_away == "away":
        sql += _HA_AWAY

    comp_df = league_query(sql, params=(abbrev, date_start, date_end))
    ppi_df = league_query(_PPI_SQL)

    # Aggregate per player
    if not comp_df.empty:
        grouped = comp_df.groupby("playerId").agg(
            playerName=("playerName", "first"),
            position=("position", "first"),
            games_played=("gameId", "nunique"),
            total_toi=("toi_seconds", "sum"),
            weighted_pct_fwd=("pct_vs_top_fwd", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
            weighted_pct_def=("pct_vs_top_def", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
            weighted_comp_fwd=("comp_fwd", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
            weighted_comp_def=("comp_def", lambda x: (x * comp_df.loc[x.index, "toi_seconds"]).sum()),
        )
        grouped["toi_per_game"] = grouped["total_toi"] / grouped["games_played"]
        grouped["avg_pct_vs_top_fwd"] = grouped["weighted_pct_fwd"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
        grouped["avg_pct_vs_top_def"] = grouped["weighted_pct_def"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
        grouped["avg_comp_fwd"] = grouped["weighted_comp_fwd"] / grouped["total_toi"].where(grouped["total_toi"] > 0)
        grouped["avg_comp_def"] = grouped["weighted_comp_def"] / grouped["total_toi"].where(grouped["total_toi"] > 0)

        metrics = compute_deployment_metrics(comp_df, ppi_df)
        if not metrics.empty:
            grouped = grouped.join(metrics[["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]])
        else:
            for col in ["ppi", "ppi_plus", "wppi", "wppi_plus", "avg_toi_share"]:
                grouped[col] = None

        player_df = grouped.reset_index().sort_values("toi_per_game", ascending=False)
        for col, dec in [("ppi", 2), ("ppi_plus", 1), ("wppi", 4), ("wppi_plus", 1)]:
            player_df[col] = player_df[col].round(dec)
    else:
        player_df = pd.DataFrame()

    # Game log
    if home_away == "home":
        games_df = league_query(_GAMES_HA_HOME, params=(abbrev, date_start, date_end))
    elif home_away == "away":
        games_df = league_query(_GAMES_HA_AWAY, params=(abbrev, date_start, date_end))
    else:
        games_df = league_query(_GAMES_SQL, params=(abbrev, abbrev, date_start, date_end))

    # Heaviness lookup
    game_ids = games_df["gameId"].tolist() if not games_df.empty else []
    heaviness_map = {}
    if game_ids:
        placeholders = ",".join("?" * len(game_ids))
        heaviness_df = league_query(
            _HEAVINESS_SQL.format(placeholders=placeholders),
            params=tuple(game_ids),
        )
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
        own_score = int(row["homeTeam_score"] or 0) if is_home else int(row["awayTeam_score"] or 0)
        opp_score = int(row["awayTeam_score"] or 0) if is_home else int(row["homeTeam_score"] or 0)

        if own_score > opp_score:
            result = "W"
        elif int(row["periodDescriptor_number"] or 0) > 3:
            result = "OTL"
        else:
            result = "L"

        gid  = row["gameId"]
        gmap = heaviness_map.get(gid, {})
        game_rows.append({
            "gameDate":      row["gameDate"],
            "opponent":      opponent,
            "homeAway":      "Home" if is_home else "Away",
            "score":         f"{own_score}\u2013{opp_score}",
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
        html.H3("Players"),
        _make_player_tables(player_df) if not player_df.empty else html.Div("No player data."),
        html.H3("Game Log", style={"marginTop": "2rem"}),
        game_table if game_rows else html.P("No games found in this range."),
    ])
```

**Step 2: Test manually**

Open http://127.0.0.1:8050/team/EDM — verify filters work on both player tables and game log.

---

### Task 7: Refactor player page

**Files:**
- Modify: `v2/browser/pages/player.py`

Convert to callback-driven with date range + H/A toggle. Per-game rows filtered. Summary stats placeholder for future use.

---

**Step 1: Rewrite `v2/browser/pages/player.py`**

```python
# v2/browser/pages/player.py
import dash
from dash import html, dash_table, callback, Input, Output, dcc
from dash.dash_table import FormatTemplate

from db import league_query
from filters import make_filter_bar, register_home_away_callback
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/player/<player_id>", name="Player")
register_home_away_callback("player")

_META_SQL = """
SELECT firstName, lastName, currentTeamAbbrev, position
FROM players WHERE playerId = ?
"""

_GAMES_SQL = """
SELECT c.gameId, g.gameDate, c.team,
       g.awayTeam_abbrev, g.homeTeam_abbrev,
       g.awayTeam_score, g.homeTeam_score,
       g.periodDescriptor_number,
       c.toi_seconds,
       5.0 * c.toi_seconds / NULLIF(tt.team_total, 0) AS toi_share,
       c.comp_fwd, c.comp_def,
       c.pct_vs_top_fwd, c.pct_vs_top_def
FROM competition c
JOIN games g ON c.gameId = g.gameId
JOIN (
    SELECT gameId, team, SUM(toi_seconds) AS team_total
    FROM competition
    WHERE position IN ('F', 'D')
    GROUP BY gameId, team
) tt ON c.gameId = tt.gameId AND c.team = tt.team
WHERE c.playerId = ?
  AND g.gameDate BETWEEN ? AND ?
"""

_HA_HOME = " AND c.team = g.homeTeam_abbrev"
_HA_AWAY = " AND c.team = g.awayTeam_abbrev"

_ORDER = " ORDER BY g.gameDate ASC"


def layout(player_id=None):
    if player_id is None:
        return html.Div("No player specified.")
    try:
        pid = int(player_id)
    except (TypeError, ValueError):
        return html.Div(f"Invalid player ID: {player_id}")

    meta_df = league_query(_META_SQL, params=(pid,))
    if meta_df.empty:
        name = f"Player {pid}"
        subtitle = ""
    else:
        m = meta_df.iloc[0]
        name = f"{m['firstName']} {m['lastName']}"
        subtitle = f"{m['currentTeamAbbrev']} · {m['position']}"

    return html.Div([
        html.H2(name),
        html.P(subtitle, style={"color": "#6c757d", "marginTop": "-0.5rem", "marginBottom": "1rem"}),
        dcc.Store(id="player-pid", data=pid),
        make_filter_bar("player", include_home_away=True),
        html.Div(id="player-content"),
    ])


@callback(
    Output("player-content", "children"),
    Input("player-date-start", "date"),
    Input("player-date-end", "date"),
    Input("player-home-away", "data"),
    Input("player-pid", "data"),
)
def update_player(date_start, date_end, home_away, pid):
    if not date_start or not date_end or pid is None:
        return html.P("Select a date range.")

    sql = _GAMES_SQL
    if home_away == "home":
        sql += _HA_HOME
    elif home_away == "away":
        sql += _HA_AWAY
    sql += _ORDER

    games_df = league_query(sql, params=(pid, date_start, date_end))
    if games_df.empty:
        return html.P("No game data for this range.")

    rows = []
    for _, r in games_df.iterrows():
        is_home  = r["team"] == r["homeTeam_abbrev"]
        opponent = r["awayTeam_abbrev"] if is_home else r["homeTeam_abbrev"]
        own_score = int(r["homeTeam_score"] or 0) if is_home else int(r["awayTeam_score"] or 0)
        opp_score = int(r["awayTeam_score"] or 0) if is_home else int(r["homeTeam_score"] or 0)

        if own_score > opp_score:
            result = "W"
        elif int(r["periodDescriptor_number"] or 0) > 3:
            result = "OTL"
        else:
            result = "L"

        rows.append({
            "game_link":      f"[{r['gameId']}](/game/{r['gameId']})",
            "gameDate":       r["gameDate"],
            "team":           r["team"],
            "homeAway":       "Home" if is_home else "Away",
            "opponent":       opponent,
            "score":          f"{own_score}\u2013{opp_score}",
            "result":         result,
            "toi_display":    seconds_to_mmss(r["toi_seconds"]),
            "toi_share":      round(float(r["toi_share"]), 4) if r["toi_share"] is not None else None,
            "comp_fwd":       seconds_to_mmss(r["comp_fwd"]),
            "comp_def":       seconds_to_mmss(r["comp_def"]),
            "pct_vs_top_fwd": round(float(r["pct_vs_top_fwd"]), 4) if r["pct_vs_top_fwd"] is not None else None,
            "pct_vs_top_def": round(float(r["pct_vs_top_def"]), 4) if r["pct_vs_top_def"] is not None else None,
        })

    _ci = {"case": "insensitive"}
    columns = [
        {"name": "Game",         "id": "game_link",      "presentation": "markdown", "filter_options": _ci},
        {"name": "Date",         "id": "gameDate",        "type": "text",    "filter_options": _ci},
        {"name": "Team",         "id": "team",            "type": "text",    "filter_options": _ci},
        {"name": "H/A",          "id": "homeAway",        "type": "text",    "filter_options": _ci},
        {"name": "Opp",          "id": "opponent",        "type": "text",    "filter_options": _ci},
        {"name": "Score",        "id": "score",           "type": "text",    "filter_options": _ci},
        {"name": "Result",       "id": "result",          "type": "text",    "filter_options": _ci},
        {"name": "5v5 TOI",      "id": "toi_display",     "type": "text",    "filter_options": _ci},
        {"name": "TOI%",         "id": "toi_share",        "type": "numeric", "format": FormatTemplate.percentage(1)},
        {"name": "OPP F TOI",    "id": "comp_fwd",        "type": "text",    "filter_options": _ci},
        {"name": "OPP D TOI",    "id": "comp_def",        "type": "text",    "filter_options": _ci},
        {"name": "vs Top Fwd %", "id": "pct_vs_top_fwd",  "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Top Def %", "id": "pct_vs_top_def",  "type": "numeric", "format": FormatTemplate.percentage(2)},
    ]

    return html.Div([
        # Summary stats placeholder — add here when ready
        dash_table.DataTable(
            columns=columns,
            data=rows,
            markdown_options={"link_target": "_self"},
            sort_action="native",
            filter_action="native",
            page_action="native",
            page_size=50,
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
                {"if": {"filter_query": '{result} = "W"', "column_id": "result"}, "color": "green"},
                {"if": {"filter_query": '{result} = "OTL"', "column_id": "result"}, "color": "darkorange"},
                {"if": {"filter_query": '{result} = "L"', "column_id": "result"}, "color": "crimson"},
            ],
        ),
    ])
```

**Step 2: Test manually**

Open http://127.0.0.1:8050/player/8478402 — verify date pickers and H/A toggle work.

---

### Task 8: Run full test suite and verify

**Step 1: Run existing tests**

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v
```

Expected: All tests pass. The browser smoke tests may need updating if they test layout() return values directly.

**Step 2: Manual smoke test all pages**

```bash
cd /Users/jrf1039/files/projects/nhl/v2/browser && python app.py
```

Verify:
- `/games` — date pickers filter the game list
- `/skaters` — date pickers + H/A toggle filter and recalculate stats
- `/team/EDM` — date pickers + H/A toggle filter player tables and game log
- `/player/8478402` — date pickers + H/A toggle filter game rows
- `/game/2025020917` — no changes, still works
- Changing dates recalculates wPPI, wPPI+, avg_toi_share on skaters and team pages
- H/A toggle highlights the active button
