# v2/browser/metrics.py
"""Shared metric calculations used by both build_league_db and filters."""

import pandas as pd


def compute_wppi_and_toi_share(eligible: pd.DataFrame, comp_df: pd.DataFrame) -> pd.DataFrame:
    """Compute wPPI, wPPI+, avg_toi_share for eligible players.

    wPPI formula: (PPI - mean_PPI) × avg_toi_share
    - Below-mean PPI players accumulate negative wPPI as they play more.
    - Above-mean PPI players accumulate positive wPPI as they play more.
    - A player at exactly mean PPI gets wPPI = 0 regardless of minutes.

    avg_toi_share: per-game mean of (5 × player_toi / team_toi).
    wPPI+: z-score normalized, mean=100, std=15.

    Args:
        eligible: DataFrame indexed by playerId with at least a 'ppi' column.
                  Rows should already be filtered to eligible players (GP >= 5).
        comp_df:  Full competition data with columns:
                  playerId, team, gameId, toi_seconds.

    Returns:
        Copy of eligible with added columns: wppi, wppi_plus, avg_toi_share.
        Players with missing avg_toi_share are dropped.
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

    # wPPI: deviation from mean PPI, scaled by TOI share.
    # Light players (below mean) who play more drag their score further negative.
    # Heavy players (above mean) who play more push their score further positive.
    mean_ppi = eligible["ppi"].mean()
    eligible["wppi"] = (eligible["ppi"] - mean_ppi) * eligible["avg_toi_share"]

    # wPPI+: z-score normalized, centered at 100 with std=15.
    # Cannot use ratio normalization (mean wPPI ≈ 0), so use z-score instead.
    wppi_std = eligible["wppi"].std()
    if wppi_std and wppi_std > 0:
        eligible["wppi_plus"] = 100.0 + (eligible["wppi"] - eligible["wppi"].mean()) / wppi_std * 15.0
    else:
        eligible["wppi_plus"] = 100.0

    return eligible
