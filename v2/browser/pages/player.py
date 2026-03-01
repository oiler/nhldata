# v2/browser/pages/player.py
import dash
from dash import html, dash_table, callback, Input, Output, dcc
from dash.dash_table import FormatTemplate
from dash.dash_table.Format import Format, Scheme

from db import league_query
from filters import make_filter_bar, register_home_away_callback, compute_deployment_metrics
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

_LEAGUE_COMP_SQL = """
SELECT c.playerId, c.position, c.team, c.gameId, c.toi_seconds,
       c.pct_vs_top_fwd, c.pct_vs_top_def, c.comp_fwd, c.comp_def,
       g.homeTeam_abbrev, g.awayTeam_abbrev
FROM competition c
JOIN games g ON c.gameId = g.gameId
WHERE c.position = ?
  AND g.gameDate BETWEEN ? AND ?
"""

_LEAGUE_HA_HOME = " AND c.team = g.homeTeam_abbrev"
_LEAGUE_HA_AWAY = " AND c.team = g.awayTeam_abbrev"


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
        pos_code = "F"
    else:
        m = meta_df.iloc[0]
        name = f"{m['firstName']} {m['lastName']}"
        subtitle = f"{m['currentTeamAbbrev']} · {m['position']}"
        pos_code = "D" if m["position"] == "D" else "F"

    return html.Div([
        html.H2(name),
        html.P(subtitle, style={"color": "#6c757d", "marginTop": "-0.5rem", "marginBottom": "1rem"}),
        dcc.Store(id="player-pid", data=pid),
        dcc.Store(id="player-position", data=pos_code),
        make_filter_bar("player", include_home_away=True),
        html.Div(id="player-content"),
    ])


@callback(
    Output("player-content", "children"),
    Input("player-date-start", "date"),
    Input("player-date-end", "date"),
    Input("player-home-away", "data"),
    Input("player-pid", "data"),
    Input("player-position", "data"),
)
def update_player(date_start, date_end, home_away, pid, position):
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

    # --- Season Summary ---
    comp_sql = _COMP_SQL
    if home_away == "home":
        comp_sql += _COMP_HA_HOME
    elif home_away == "away":
        comp_sql += _COMP_HA_AWAY
    comp_df = league_query(comp_sql, params=(pid, date_start, date_end))

    summary_section = html.Div()
    if not comp_df.empty:
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

        # --- League-wide ranks ---
        league_sql = _LEAGUE_COMP_SQL
        if home_away == "home":
            league_sql += _LEAGUE_HA_HOME
        elif home_away == "away":
            league_sql += _LEAGUE_HA_AWAY
        league_comp_df = league_query(league_sql, params=(position, date_start, date_end))

        ranks = {}
        if not league_comp_df.empty:
            lg = league_comp_df.groupby("playerId").agg(
                games_played=("gameId", "nunique"),
                total_toi=("toi_seconds", "sum"),
                weighted_pct_fwd=("pct_vs_top_fwd", lambda x: (x * league_comp_df.loc[x.index, "toi_seconds"]).sum()),
                weighted_pct_def=("pct_vs_top_def", lambda x: (x * league_comp_df.loc[x.index, "toi_seconds"]).sum()),
                weighted_comp_fwd=("comp_fwd", lambda x: (x * league_comp_df.loc[x.index, "toi_seconds"]).sum()),
                weighted_comp_def=("comp_def", lambda x: (x * league_comp_df.loc[x.index, "toi_seconds"]).sum()),
            )
            lg = lg[lg["games_played"] >= 5]
            lg["toi_per_game"] = lg["total_toi"] / lg["games_played"]
            lg["avg_pct_fwd"] = lg["weighted_pct_fwd"] / lg["total_toi"]
            lg["avg_pct_def"] = lg["weighted_pct_def"] / lg["total_toi"]
            lg["avg_comp_fwd"] = lg["weighted_comp_fwd"] / lg["total_toi"]
            lg["avg_comp_def"] = lg["weighted_comp_def"] / lg["total_toi"]

            # TOI share per player
            game_teams = league_comp_df.groupby(["gameId", "team"]).agg(
                team_total=("toi_seconds", "sum")
            )
            merged = league_comp_df.merge(game_teams, on=["gameId", "team"])
            merged["game_share"] = 5.0 * merged["toi_seconds"] / merged["team_total"]
            lg["avg_toi_share"] = merged.groupby("playerId")["game_share"].mean()

            # Points
            if not pts_df.empty:
                valid = league_comp_df[["playerId", "gameId"]].drop_duplicates()
                lpts = pts_df.merge(valid, on=["playerId", "gameId"], how="inner")
                lpts_agg = lpts.groupby("playerId").agg(
                    total_goals=("goals", "sum"),
                    total_assists=("assists", "sum"),
                    total_points=("points", "sum"),
                )
                lg = lg.join(lpts_agg)
            for c in ["total_goals", "total_assists", "total_points"]:
                lg[c] = lg[c].fillna(0).astype(int) if c in lg.columns else 0
            lg["p_per_60"] = lg["total_points"] * 3600 / lg["total_toi"]

            # PPI / wPPI from deployment metrics
            lg_metrics = compute_deployment_metrics(league_comp_df, ppi_df)
            if not lg_metrics.empty:
                lg = lg.join(lg_metrics[["ppi", "ppi_plus", "wppi", "wppi_plus"]])

            pool = len(lg)

            # Rank helper: ascending=False means higher value = rank 1
            def _rank(col, ascending=False):
                if col not in lg.columns or pid not in lg.index:
                    return None
                series = lg[col].dropna()
                if pid not in series.index:
                    return None
                r = int(series.rank(ascending=ascending, method="min").loc[pid])
                return f"{r} / {pool}"

            ranks = {
                "GP":          _rank("games_played"),
                "G":           _rank("total_goals"),
                "A":           _rank("total_assists"),
                "P":           _rank("total_points"),
                "P/60":        _rank("p_per_60"),
                "5v5 TOI/GP":  _rank("toi_per_game"),
                "TOI%":        _rank("avg_toi_share"),
                "vs Top Fwd":  _rank("avg_pct_fwd"),
                "vs Top Def":  _rank("avg_pct_def"),
                "OPP F TOI":   _rank("avg_comp_fwd"),
                "OPP D TOI":   _rank("avg_comp_def"),
                "PPI":         _rank("ppi"),
                "PPI+":        _rank("ppi_plus"),
                "wPPI":        _rank("wppi"),
                "wPPI+":       _rank("wppi_plus"),
            }

        def _fmt(val, decimals=2):
            return f"{val:.{decimals}f}" if val is not None else "\u2014"

        label_style = {"color": "#6c757d", "fontSize": "0.8rem", "marginBottom": "2px"}
        value_style = {"fontSize": "1.1rem", "fontWeight": "bold"}
        rank_style = {"color": "#6c757d", "fontSize": "0.75rem"}
        cell_style = {"textAlign": "center", "padding": "0.5rem 1rem"}

        def stat_cell(label, value, rank=None):
            children = [
                html.Div(label, style=label_style),
                html.Div(str(value), style=value_style),
            ]
            if rank:
                children.append(html.Div(rank, style=rank_style))
            return html.Div(children, style=cell_style)

        summary_section = html.Div([
            html.H4("Season Summary", style={"marginBottom": "0.5rem"}),
            html.Div([
                stat_cell("GP", gp, ranks.get("GP")),
                stat_cell("Record", f"{wins}-{losses}-{otl}"),
                stat_cell("G", total_goals, ranks.get("G")),
                stat_cell("A", total_assists, ranks.get("A")),
                stat_cell("P", total_points, ranks.get("P")),
                stat_cell("P/60", _fmt(p_per_60), ranks.get("P/60")),
                stat_cell("5v5 TOI/GP", seconds_to_mmss(toi_per_game), ranks.get("5v5 TOI/GP")),
                stat_cell("TOI%", _fmt(avg_toi_share * 100, 1) + "%", ranks.get("TOI%")),
                stat_cell("vs Top Fwd", _fmt(avg_pct_fwd * 100, 1) + "%", ranks.get("vs Top Fwd")),
                stat_cell("vs Top Def", _fmt(avg_pct_def * 100, 1) + "%", ranks.get("vs Top Def")),
                stat_cell("OPP F TOI", seconds_to_mmss(avg_comp_fwd), ranks.get("OPP F TOI")),
                stat_cell("OPP D TOI", seconds_to_mmss(avg_comp_def), ranks.get("OPP D TOI")),
                stat_cell("PPI", _fmt(ppi_val), ranks.get("PPI")),
                stat_cell("PPI+", _fmt(ppi_plus_val, 1), ranks.get("PPI+")),
                stat_cell("wPPI", _fmt(wppi_val, 4), ranks.get("wPPI")),
                stat_cell("wPPI+", _fmt(wppi_plus_val, 1), ranks.get("wPPI+")),
            ], style={
                "display": "flex", "flexWrap": "wrap", "gap": "0.25rem",
                "padding": "0.75rem", "backgroundColor": "#f8f9fa",
                "borderRadius": "8px", "marginBottom": "1.5rem",
                "border": "1px solid #dee2e6",
            }),
        ])

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
        summary_section,
        html.H4("Game Log", style={"marginBottom": "0.5rem"}),
        dash_table.DataTable(
            columns=columns,
            data=rows,
            markdown_options={"link_target": "_self"},
            sort_action="native",
            filter_action="native",
            css=[{"selector": ".dash-filter--case", "rule": "display: none"}],
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
