# Teams Leaderboard DataTable

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Context:** The teams page is currently a simple list of 32 clickable links. The user wants it replaced with a DataTable showing key team stats.

**Goal:** Replace the teams landing page with a filterable, sortable DataTable showing GP, P%, RW, PPI+, wPPI+, and 5v5 Goal Differential for all 32 teams.

**Architecture:** Rewrite `v2/browser/pages/teams.py` following the `skaters.py` DataTable pattern. Query games for records, competition + points_5v5 for 5v5 GD, and compute_deployment_metrics for PPI+/wPPI+ (TOI-weighted team averages). Unpivot games table in pandas to get per-team-game rows, apply home/away filter in pandas.

**Tech Stack:** Dash DataTable, pandas aggregation, `compute_deployment_metrics` from `filters.py`, `league_query` from `db.py`.

---

### Task 1: Rewrite teams.py with DataTable

**Files:**
- Modify: `v2/browser/pages/teams.py`
- Reference: `v2/browser/pages/skaters.py` (DataTable + callback pattern)
- Reference: `v2/browser/filters.py` (`make_filter_bar`, `register_home_away_callback`, `compute_deployment_metrics`)

---

**Step 1: Replace imports and page setup**

```python
# v2/browser/pages/teams.py
import pandas as pd
import dash
from dash import html, dash_table, callback, Input, Output
from dash.dash_table.Format import Format, Scheme

from db import league_query
from filters import make_filter_bar, register_home_away_callback, compute_deployment_metrics

dash.register_page(__name__, path="/teams", name="Teams")
register_home_away_callback("teams")
```

**Step 2: Add SQL constants**

```python
_GAMES_SQL = """
SELECT gameId, gameDate, homeTeam_abbrev, awayTeam_abbrev,
       homeTeam_score, awayTeam_score, periodDescriptor_number
FROM games
WHERE awayTeam_score IS NOT NULL
  AND gameDate BETWEEN ? AND ?
"""

_COMP_SQL = """
SELECT c.playerId, c.position, c.team, c.gameId, c.toi_seconds,
       g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
JOIN games g ON c.gameId = g.gameId
WHERE c.position IN ('F', 'D')
  AND g.gameDate BETWEEN ? AND ?
"""

_PPI_SQL = "SELECT playerId, ppi, ppi_plus FROM player_metrics"
_POINTS_SQL = "SELECT playerId, gameId, goals FROM points_5v5"
```

Note: no home/away filter in SQL — handled in pandas so we can query once and reuse for both records and 5v5 GD.

**Step 3: Add layout with filter bar**

```python
def layout():
    return html.Div([
        html.H2("Teams"),
        make_filter_bar("teams", include_home_away=True),
        html.Div(id="teams-content"),
    ])
```

**Step 4: Add callback — data queries**

```python
@callback(
    Output("teams-content", "children"),
    Input("teams-date-start", "date"),
    Input("teams-date-end", "date"),
    Input("teams-home-away", "data"),
)
def update_teams(date_start, date_end, home_away):
    if not date_start or not date_end:
        return html.P("Select a date range.")

    games_df = league_query(_GAMES_SQL, params=(date_start, date_end))
    if games_df.empty:
        return html.P("No games found for this range.")

    comp_df = league_query(_COMP_SQL, params=(date_start, date_end))
    pts_df = league_query(_POINTS_SQL)
    ppi_df = league_query(_PPI_SQL)
```

**Step 5: Add callback — records (GP, P%, RW)**

Unpivot games table so each game produces two rows (one per team), then apply home/away filter in pandas:

```python
    # Unpivot games to team-game rows
    home = games_df[["gameId", "homeTeam_abbrev", "homeTeam_score",
                      "awayTeam_score", "periodDescriptor_number"]].copy()
    home.columns = ["gameId", "team", "own_score", "opp_score", "period"]
    home["ha"] = "home"

    away = games_df[["gameId", "awayTeam_abbrev", "awayTeam_score",
                      "homeTeam_score", "periodDescriptor_number"]].copy()
    away.columns = ["gameId", "team", "own_score", "opp_score", "period"]
    away["ha"] = "away"

    tg = pd.concat([home, away])
    if home_away == "home":
        tg = tg[tg["ha"] == "home"]
    elif home_away == "away":
        tg = tg[tg["ha"] == "away"]

    # Compute results
    tg["win"] = tg["own_score"] > tg["opp_score"]
    tg["reg_win"] = tg["win"] & (tg["period"] <= 3)
    tg["otl"] = (~tg["win"]) & (tg["period"] > 3)
    tg["pts"] = tg["win"].astype(int) * 2 + tg["otl"].astype(int)

    records = tg.groupby("team").agg(
        gp=("gameId", "nunique"),
        wins=("win", "sum"),
        rw=("reg_win", "sum"),
        total_pts=("pts", "sum"),
    ).astype(int)
    records["pct"] = records["total_pts"] / (2 * records["gp"])
```

**Step 6: Add callback — 5v5 Goal Differential**

Join points_5v5 with competition for team attribution, compute GF/GA per team per game, filter to relevant (home/away-filtered) team-game pairs:

```python
    # 5v5 Goal Differential
    relevant = tg[["team", "gameId"]].drop_duplicates()

    if not comp_df.empty and not pts_df.empty:
        pts_team = pts_df.merge(
            comp_df[["playerId", "gameId", "team"]].drop_duplicates(),
            on=["playerId", "gameId"], how="inner",
        )
        team_game_goals = pts_team.groupby(["team", "gameId"])["goals"].sum().reset_index()
        game_total = pts_team.groupby("gameId")["goals"].sum().reset_index()
        game_total.columns = ["gameId", "game_total"]

        tgg = team_game_goals.merge(game_total, on="gameId")
        tgg["ga"] = tgg["game_total"] - tgg["goals"]
        tgg = tgg.merge(relevant, on=["team", "gameId"], how="inner")

        goal_agg = tgg.groupby("team").agg(gf=("goals", "sum"), ga=("ga", "sum"))
        goal_agg["gd_5v5"] = goal_agg["gf"] - goal_agg["ga"]
    else:
        goal_agg = pd.DataFrame(columns=["gd_5v5"])
```

**Step 7: Add callback — PPI+ / wPPI+ (TOI-weighted team average)**

Filter competition by home/away, call `compute_deployment_metrics` for per-player values, then TOI-weight by player-team stint:

```python
    # PPI+ / wPPI+ — TOI-weighted team averages
    if home_away == "home":
        ha_comp = comp_df[comp_df["team"] == comp_df["homeTeam_abbrev"]]
    elif home_away == "away":
        ha_comp = comp_df[comp_df["team"] == comp_df["awayTeam_abbrev"]]
    else:
        ha_comp = comp_df

    metrics = compute_deployment_metrics(ha_comp, ppi_df)

    if not metrics.empty:
        pt_toi = ha_comp.groupby(["playerId", "team"])["toi_seconds"].sum().reset_index()
        pt_toi = pt_toi.merge(
            metrics[["ppi_plus", "wppi_plus"]].reset_index(),
            on="playerId", how="inner",
        )
        pt_toi["w_ppi"] = pt_toi["ppi_plus"] * pt_toi["toi_seconds"]
        pt_toi["w_wppi"] = pt_toi["wppi_plus"] * pt_toi["toi_seconds"]

        team_ppi = pt_toi.groupby("team").agg(
            w_ppi_sum=("w_ppi", "sum"),
            w_wppi_sum=("w_wppi", "sum"),
            total_toi=("toi_seconds", "sum"),
        )
        team_ppi["ppi_plus"] = team_ppi["w_ppi_sum"] / team_ppi["total_toi"]
        team_ppi["wppi_plus"] = team_ppi["w_wppi_sum"] / team_ppi["total_toi"]
    else:
        team_ppi = pd.DataFrame(columns=["ppi_plus", "wppi_plus"])
```

**Step 8: Add callback — combine and build DataTable**

```python
    # Combine all metrics
    df = records[["gp", "pct", "rw"]].copy()
    if not team_ppi.empty:
        df = df.join(team_ppi[["ppi_plus", "wppi_plus"]], how="left")
    if not goal_agg.empty:
        df = df.join(goal_agg[["gd_5v5"]], how="left")
    for col in ["ppi_plus", "wppi_plus", "gd_5v5"]:
        if col not in df.columns:
            df[col] = None
    df["gd_5v5"] = df["gd_5v5"].fillna(0).astype(int)

    df = df.reset_index()
    df = df.sort_values("pct", ascending=False)
    df["team_link"] = df["team"].apply(lambda t: f"[{t}](/team/{t})")

    _ci = {"case": "insensitive"}
    columns = [
        {"name": "Team",  "id": "team_link", "presentation": "markdown", "filter_options": _ci},
        {"name": "GP",    "id": "gp",        "type": "numeric"},
        {"name": "P%",    "id": "pct",       "type": "numeric",
         "format": Format(precision=3, scheme=Scheme.fixed)},
        {"name": "RW",    "id": "rw",        "type": "numeric"},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric",
         "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "5v5 GD", "id": "gd_5v5",  "type": "numeric"},
    ]
    display_cols = ["team_link", "gp", "pct", "rw", "ppi_plus", "wppi_plus", "gd_5v5"]

    return dash_table.DataTable(
        columns=columns,
        data=df[display_cols].to_dict("records"),
        markdown_options={"link_target": "_self"},
        sort_action="native",
        filter_action="native",
        css=[{"selector": ".dash-filter--case", "rule": "display: none"}],
        page_action="none",
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
            {"if": {"filter_query": "{gd_5v5} > 0", "column_id": "gd_5v5"},
             "color": "green"},
            {"if": {"filter_query": "{gd_5v5} < 0", "column_id": "gd_5v5"},
             "color": "crimson"},
        ],
    )
```

Note: `page_action="none"` since there are only 32 teams — no pagination needed.

---

### Task 2: Run tests and verify

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v
```

Expected: All 68 tests pass. The existing `test_team_page_registered` smoke test should continue to pass. No new tests needed since this is a display-only change.

**Manual verification:**

```bash
cd /Users/jrf1039/files/projects/nhl/v2/browser && python app.py
```

Open http://127.0.0.1:8050/teams — verify:
- All 32 teams appear in the table
- Default sort is by P% descending
- Team names are clickable links to `/team/<abbrev>`
- GP and RW are integers
- P% shows 3 decimal places (e.g., 0.621)
- PPI+ and wPPI+ show 1 decimal place
- 5v5 GD is green for positive, red for negative
- Sorting works on all columns
- Filtering works (e.g., type team abbrev)
- Home/Away toggle updates all stats
- Date range changes update all stats
