# Player Page Season Summary — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Season Summary" section to the player page between the filter bar and the game log, showing aggregated stats matching the skaters leaderboard columns. Updates with date range and H/A filters.

**Architecture:** Single file change to `v2/browser/pages/player.py`. The callback already has per-game data in `games_df`. Aggregate it into a single summary row, query `player_metrics` for PPI and `points_5v5` for G/A/P, compute P/60 and wPPI-related stats, and render as a styled key-value section above the game log.

**Tech Stack:** Existing Dash callback, pandas aggregation, `compute_deployment_metrics` from `filters.py`.

---

### Task 1: Add season summary to player page

**Files:**
- Modify: `v2/browser/pages/player.py`

---

**Step 1: Add imports and SQL constants**

Add to the imports at the top of the file:

```python
from dash.dash_table.Format import Format, Scheme
from filters import compute_deployment_metrics
```

Add SQL constants after the existing `_ORDER`:

```python
_COMP_SQL = """
SELECT c.playerId, c.team, c.gameId, c.toi_seconds, c.position,
       c.pct_vs_top_fwd, c.pct_vs_top_def, c.comp_fwd, c.comp_def
FROM competition c
JOIN games g ON c.gameId = g.gameId
WHERE c.playerId = ?
  AND c.position IN ('F', 'D')
  AND g.gameDate BETWEEN ? AND ?
"""

_COMP_HA_HOME = " AND c.team = g.homeTeam_abbrev"
_COMP_HA_AWAY = " AND c.team = g.awayTeam_abbrev"

_PPI_SQL = "SELECT playerId, ppi, ppi_plus FROM player_metrics"
_POINTS_SQL = "SELECT playerId, gameId, goals, assists, points FROM points_5v5"
```

**Step 2: Build the summary section in the callback**

In the `update_player` callback, after getting `games_df` and confirming it's not empty, add the summary computation before building the game log rows. Insert this block after `if games_df.empty: return ...` and before `rows = []`:

```python
    # --- Season Summary ---
    comp_sql = _COMP_SQL
    if home_away == "home":
        comp_sql += _COMP_HA_HOME
    elif home_away == "away":
        comp_sql += _COMP_HA_AWAY
    comp_df = league_query(comp_sql, params=(pid, date_start, date_end))

    summary_section = html.Div()
    if not comp_df.empty:
        import pandas as pd
        gp = comp_df["gameId"].nunique()
        total_toi = comp_df["toi_seconds"].sum()
        toi_per_game = total_toi / gp if gp > 0 else 0
        avg_pct_fwd = (comp_df["pct_vs_top_fwd"] * comp_df["toi_seconds"]).sum() / total_toi if total_toi > 0 else 0
        avg_pct_def = (comp_df["pct_vs_top_def"] * comp_df["toi_seconds"]).sum() / total_toi if total_toi > 0 else 0
        avg_comp_fwd = (comp_df["comp_fwd"] * comp_df["toi_seconds"]).sum() / total_toi if total_toi > 0 else 0
        avg_comp_def = (comp_df["comp_def"] * comp_df["toi_seconds"]).sum() / total_toi if total_toi > 0 else 0

        # TOI share (avg of per-game share)
        game_toi_share = games_df["toi_share"].dropna()
        avg_toi_share = game_toi_share.mean() if not game_toi_share.empty else 0

        # Points
        pts_df = league_query(_POINTS_SQL)
        total_goals = total_assists = total_points = 0
        if not pts_df.empty:
            player_pts = pts_df[
                (pts_df["playerId"] == pid)
                & (pts_df["gameId"].isin(comp_df["gameId"].unique()))
            ]
            total_goals = int(player_pts["goals"].sum())
            total_assists = int(player_pts["assists"].sum())
            total_points = int(player_pts["points"].sum())
        p_per_60 = total_points * 3600 / total_toi if total_toi > 0 else 0

        # PPI / wPPI
        ppi_df = league_query(_PPI_SQL)
        ppi_val = wppi_val = ppi_plus_val = wppi_plus_val = None
        if not ppi_df.empty:
            player_ppi = ppi_df[ppi_df["playerId"] == pid]
            if not player_ppi.empty:
                ppi_val = round(float(player_ppi.iloc[0]["ppi"]), 2)
                ppi_plus_val = round(float(player_ppi.iloc[0]["ppi_plus"]), 1)
            # wPPI from filtered data
            metrics = compute_deployment_metrics(comp_df, ppi_df)
            if not metrics.empty and pid in metrics.index:
                wppi_val = round(float(metrics.loc[pid, "wppi"]), 4)
                wppi_plus_val = round(float(metrics.loc[pid, "wppi_plus"]), 1)

        # Record (W-L-OTL)
        wins = losses = otl = 0
        for _, r in games_df.iterrows():
            is_home = r["team"] == r["homeTeam_abbrev"]
            own = int(r["homeTeam_score"] or 0) if is_home else int(r["awayTeam_score"] or 0)
            opp = int(r["awayTeam_score"] or 0) if is_home else int(r["homeTeam_score"] or 0)
            if own > opp:
                wins += 1
            elif int(r["periodDescriptor_number"] or 0) > 3:
                otl += 1
            else:
                losses += 1

        def _fmt(val, decimals=2):
            return f"{val:.{decimals}f}" if val is not None else "—"

        label_style = {"color": "#6c757d", "fontSize": "0.8rem", "marginBottom": "2px"}
        value_style = {"fontSize": "1.1rem", "fontWeight": "bold"}
        cell_style = {"textAlign": "center", "padding": "0.5rem 1rem"}

        def stat_cell(label, value):
            return html.Div([
                html.Div(label, style=label_style),
                html.Div(str(value), style=value_style),
            ], style=cell_style)

        summary_section = html.Div([
            html.H4("Season Summary", style={"marginBottom": "0.5rem"}),
            html.Div([
                stat_cell("GP", gp),
                stat_cell("Record", f"{wins}-{losses}-{otl}"),
                stat_cell("G", total_goals),
                stat_cell("A", total_assists),
                stat_cell("P", total_points),
                stat_cell("P/60", _fmt(p_per_60)),
                stat_cell("5v5 TOI/GP", seconds_to_mmss(toi_per_game)),
                stat_cell("TOI%", _fmt(avg_toi_share * 100, 1) + "%"),
                stat_cell("vs Top Fwd", _fmt(avg_pct_fwd * 100, 1) + "%"),
                stat_cell("vs Top Def", _fmt(avg_pct_def * 100, 1) + "%"),
                stat_cell("OPP F TOI", seconds_to_mmss(avg_comp_fwd)),
                stat_cell("OPP D TOI", seconds_to_mmss(avg_comp_def)),
                stat_cell("PPI", _fmt(ppi_val)),
                stat_cell("PPI+", _fmt(ppi_plus_val, 1)),
                stat_cell("wPPI", _fmt(wppi_val, 4)),
                stat_cell("wPPI+", _fmt(wppi_plus_val, 1)),
            ], style={
                "display": "flex", "flexWrap": "wrap", "gap": "0.25rem",
                "padding": "0.75rem", "backgroundColor": "#f8f9fa",
                "borderRadius": "8px", "marginBottom": "1.5rem",
                "border": "1px solid #dee2e6",
            }),
        ])
```

**Step 3: Insert the summary section into the return value**

Replace the existing return block (which has the placeholder comment) with:

```python
    return html.Div([
        summary_section,
        html.H4("Game Log", style={"marginBottom": "0.5rem"}),
        dash_table.DataTable(
            ...  # existing DataTable unchanged
        ),
    ])
```

**Step 4: Verify**

```bash
cd /Users/jrf1039/files/projects/nhl/v2/browser && python app.py
```

Open http://127.0.0.1:8050/player/8478402 — verify:
- Season summary section appears between filter bar and game log
- Shows GP, Record, G, A, P, P/60, TOI/GP, TOI%, competition stats, PPI, wPPI
- Changing date range updates the summary
- Changing H/A toggle updates the summary
- Game log still works as before

---

### Task 2: Run tests and verify

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v
```

Expected: All 68 tests pass. No new tests needed since this is a display-only change to an existing callback.
