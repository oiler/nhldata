# v2/browser/metrics.py
"""Shared metric calculations used by both build_league_db and filters."""

import pandas as pd


def compute_wppi_and_toi_share(eligible: pd.DataFrame, comp_df: pd.DataFrame) -> pd.DataFrame:
    """Compute wPPI, wPPI+, avg_toi_share for eligible players.

    wPPI (raw) = avg(ppi_plus × toi_seconds) per game.
    Every second a player is on ice they contribute their PPI+ to the raw score.
    A player at 100 PPI+ playing average minutes scores exactly the league mean.

    wPPI+ = wPPI / league_mean(wPPI) × 100  (ratio-normalized, same as PPI+)
    - Heavy player (PPI+ > 100) playing few minutes: wPPI+ < PPI+
    - Heavy player playing heavy minutes: wPPI+ > PPI+
    - Light player (PPI+ < 100) playing heavy minutes: wPPI+ > PPI+ (more below 100 in absolute terms)
    - Light player playing few minutes: wPPI+ closer to 100 than PPI+

    avg_toi_share: per-game mean of (5 × player_toi / team_toi), retained for display.

    Args:
        eligible: DataFrame indexed by playerId with columns: ppi, ppi_plus.
                  Rows should already be filtered to eligible players (GP >= 5).
        comp_df:  Full competition data with columns:
                  playerId, team, gameId, toi_seconds.

    Returns:
        Copy of eligible with added columns: wppi, wppi_plus, avg_toi_share.
        Players with no valid games are dropped.
        Returns empty DataFrame if no valid values can be computed.
    """
    eligible = eligible.copy()

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
    eligible = eligible[eligible["avg_toi_share"].notna()]

    if eligible.empty:
        return pd.DataFrame()

    # wPPI: avg per-game raw score = ppi_plus × toi_seconds.
    # Each second on ice contributes the player's PPI+ to the running total.
    player_games = cs[cs["playerId"].isin(eligible.index)].merge(
        eligible[["ppi_plus"]].reset_index(), on="playerId"
    )
    player_games["raw_score"] = player_games["ppi_plus"] * player_games["toi_seconds"]
    wppi = (
        player_games.groupby("playerId")["raw_score"]
        .mean()
        .rename("wppi")
    )
    eligible = eligible.join(wppi)
    eligible = eligible[eligible["wppi"].notna()]

    if eligible.empty:
        return pd.DataFrame()

    # wPPI+: ratio-normalized to league mean = 100, same pattern as PPI+.
    league_mean = eligible["wppi"].mean()
    if league_mean and league_mean > 0:
        eligible["wppi_plus"] = eligible["wppi"] / league_mean * 100.0
    else:
        eligible["wppi_plus"] = 100.0

    return eligible


def carryover_per_player(comp_df: pd.DataFrame, bursts_df: pd.DataFrame) -> pd.DataFrame:
    """Per-player carry-over stats: mean line number joined with skating bursts.

    Args:
        comp_df:   competition rows with columns playerId, line_number.
        bursts_df: indexed by playerId with bursts_per_60, speed_max_mph.

    Returns:
        DataFrame indexed by playerId with avg_line, bursts_per_60, speed_max_mph.
        bursts columns are NaN for players absent from bursts_df.
    """
    out = (
        comp_df.groupby("playerId")["line_number"]
        .mean()
        .rename("avg_line")
        .to_frame()
    )
    return out.join(bursts_df[["bursts_per_60", "speed_max_mph"]])
