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


def events_per60(events_df: pd.DataFrame, toi_df: pd.DataFrame) -> pd.DataFrame:
    """Per-60 individual-event rates over all of a player's 5v5 TOI.

    Args:
        events_df: per-(gameId, playerId) with hits, blocks, takeaways, giveaways, ishots.
        toi_df:    per-(gameId, playerId) with toi_seconds (denominator = all filtered games).

    Returns:
        Indexed by playerId: hits_per60, blocks_per60, tk_per60, gv_per60, ishots_per60.
    """
    toi = toi_df.groupby("playerId")["toi_seconds"].sum()
    sums = events_df.groupby("playerId")[["hits", "blocks", "takeaways", "giveaways", "ishots"]].sum()
    out = sums.reindex(toi.index).fillna(0).join(toi.rename("toi"))
    denom = out["toi"].where(out["toi"] > 0)
    return pd.DataFrame({
        "hits_per60":    out["hits"]       * 3600 / denom,
        "blocks_per60":  out["blocks"]     * 3600 / denom,
        "tk_per60":      out["takeaways"]  * 3600 / denom,
        "gv_per60":      out["giveaways"]  * 3600 / denom,
        "ishots_per60":  out["ishots"]     * 3600 / denom,
    })


def corsi_per60(onice_df: pd.DataFrame, toi_df: pd.DataFrame) -> pd.DataFrame:
    """Per-60 on-ice Corsi, with the TOI denominator restricted to games that have
    on-ice rows (so missing-timeline games do not dilute the rate).

    Args:
        onice_df: per-(gameId, playerId) with cf, ca.
        toi_df:   per-(gameId, playerId) with toi_seconds.

    Returns:
        Indexed by playerId: cf_per60, ca_per60, cf_pct.
    """
    if onice_df.empty:
        return pd.DataFrame(columns=["cf_per60", "ca_per60", "cf_pct"])
    covered = onice_df[["gameId", "playerId"]].drop_duplicates()
    toi_cov = toi_df.merge(covered, on=["gameId", "playerId"], how="inner")
    toi = toi_cov.groupby("playerId")["toi_seconds"].sum()
    sums = onice_df.groupby("playerId")[["cf", "ca"]].sum()
    out = sums.join(toi.rename("toi"))
    denom = out["toi"].where(out["toi"] > 0)
    total = (out["cf"] + out["ca"]).where((out["cf"] + out["ca"]) > 0)
    return pd.DataFrame({
        "cf_per60": out["cf"] * 3600 / denom,
        "ca_per60": out["ca"] * 3600 / denom,
        "cf_pct":   out["cf"] / total,
    })
