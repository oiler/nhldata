# v2/browser/metrics.py
"""Shared metric calculations used by both build_league_db and filters."""

import pandas as pd


def compute_wppi_and_toi_share(eligible: pd.DataFrame, comp_df: pd.DataFrame) -> pd.DataFrame:
    """Compute wPPI, wPPI+, avg_toi_share for eligible players.

    Args:
        eligible: DataFrame indexed by playerId with at least a 'ppi' column.
                  Rows should already be filtered to eligible players (GP >= 5).
        comp_df:  Full competition data with columns:
                  playerId, team, gameId, toi_seconds.

    Returns:
        Copy of eligible with added columns: wppi, wppi_plus, avg_toi_share.
        Players with missing wPPI are dropped.
        Returns empty DataFrame if no valid wPPI values can be computed.
    """
    eligible = eligible.copy()

    # wPPI: PPI × games-weighted average TOI share across team stints.
    # Weighted average (not sum) ensures traded players aren't double-counted
    # relative to single-team players with identical per-game deployment.
    eligible_comp = comp_df[comp_df["playerId"].isin(eligible.index)]
    player_team_toi   = eligible_comp.groupby(["playerId", "team"])["toi_seconds"].sum()
    player_team_games = eligible_comp.groupby(["playerId", "team"])["gameId"].nunique()
    player_avg_toi    = player_team_toi / player_team_games  # avg seconds/game per stint

    team_total_toi    = eligible_comp.groupby("team")["toi_seconds"].sum()
    team_unique_games = eligible_comp.groupby("team")["gameId"].nunique()
    team_avg_toi      = team_total_toi / team_unique_games   # team avg eligible-seconds/game

    share_numerator: dict[int, float] = {}
    share_denominator: dict[int, int] = {}
    for (pid, team), avg_toi in player_avg_toi.items():
        team_avg = team_avg_toi.get(team, 0)
        if team_avg == 0:
            continue
        share = avg_toi / team_avg
        games = int(player_team_games[(pid, team)])
        share_numerator[pid] = share_numerator.get(pid, 0.0) + share * games
        share_denominator[pid] = share_denominator.get(pid, 0) + games

    wppi_map: dict[int, float] = {}
    for pid, numerator in share_numerator.items():
        denom = share_denominator.get(pid, 0)
        if denom == 0:
            continue
        wppi_map[pid] = eligible.loc[pid, "ppi"] * (numerator / denom)

    eligible["wppi"] = pd.Series(wppi_map)
    eligible = eligible[eligible["wppi"].notna()]

    if eligible.empty:
        return pd.DataFrame()

    # wPPI+
    mean_wppi = eligible["wppi"].mean()
    eligible["wppi_plus"] = 100.0 * eligible["wppi"] / mean_wppi

    # avg_toi_share: mean of per-game (5 × player_toi / team_toi) across player's games.
    # team_toi uses full comp (all skaters, not just eligible), matching real game deployment totals.
    game_team_toi = comp_df.groupby(["team", "gameId"])["toi_seconds"].transform("sum")
    cs = comp_df.copy()
    cs["toi_share"] = 5.0 * cs["toi_seconds"] / game_team_toi.where(game_team_toi > 0)
    avg_toi_share = (
        cs[cs["playerId"].isin(eligible.index)]
        .groupby("playerId")["toi_share"]
        .mean()
        .rename("avg_toi_share")
    )
    eligible = eligible.join(avg_toi_share)

    return eligible
