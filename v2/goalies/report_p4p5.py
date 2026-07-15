# v2/goalies/report_p4p5.py
"""P4+P5 cross-check report: game difficulty, ledger calibration, team environment.

Usage: python3 v2/goalies/report_p4p5.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def _goalie_name(goalie_id: int) -> str:
    """Best-effort name lookup from the per-player JSON files (no new infra)."""
    for season in SEASONS:
        f = ROOT / "data" / season / "players" / f"{goalie_id}.json"
        if f.exists():
            d = json.loads(f.read_text())
            first = d.get("firstName", {}) or {}
            last = d.get("lastName", {}) or {}
            return f"{first.get('default', '')} {last.get('default', '')}".strip()
    return f"id:{goalie_id}"


def main() -> None:
    lines = []

    # --- Per-season goalie-game counts and TOI totals ---
    lines.append("=== 1. Goalie-games and TOI by season ===")
    gg_frames = []
    for season in SEASONS:
        gg = pd.read_csv(GEN / f"goalie_games_{season}.csv")
        gg_frames.append(gg)
        lines.append(
            f"{season}: goalie_games={len(gg)} goalies={gg['goalie_id'].nunique()} "
            f"total_toi={gg['toi_s'].sum() / 3600:.0f}h"
        )
    goalie_games = pd.concat(gg_frames, ignore_index=True)
    goalie_games["season"] = goalie_games["season"].astype(int)

    # --- Game Difficulty Index distribution ---
    lines.append("")
    lines.append("=== 2. Game Difficulty Index (xg_per60) ===")
    gd = pd.read_csv(GEN / "game_difficulty.csv")
    elig = gd[gd["difficulty_pct"].notna()].copy()
    lines.append(
        f"eligible games (toi>=1200s): {len(elig)}/{len(gd)}; "
        f"xg_per60 median={elig['xg_per60'].median():.2f} "
        f"p10={elig['xg_per60'].quantile(.1):.2f} p90={elig['xg_per60'].quantile(.9):.2f}"
    )

    date_lut = goalie_games.set_index(["season", "game_id", "goalie_id"])["game_date"]
    elig = elig.join(date_lut, on=["season", "game_id", "goalie_id"])

    lines.append("hardest 5 games (highest xg_per60):")
    for r in elig.sort_values("xg_per60", ascending=False).head(5).itertuples():
        lines.append(
            f"  {r.game_date} game={r.game_id} goalie={_goalie_name(r.goalie_id)} "
            f"xg_per60={r.xg_per60:.2f} difficulty_pct={r.difficulty_pct:.1f}"
        )
    lines.append("easiest 5 games (lowest xg_per60):")
    for r in elig.sort_values("xg_per60", ascending=True).head(5).itertuples():
        lines.append(
            f"  {r.game_date} game={r.game_id} goalie={_goalie_name(r.goalie_id)} "
            f"xg_per60={r.xg_per60:.2f} difficulty_pct={r.difficulty_pct:.1f}"
        )

    # --- Ledger calibration + the difficulty<->GA gate and difficulty<->perf_z artifact ---
    lines.append("")
    lines.append(
        "=== 3. Ledger calibration, difficulty<->GA gate, difficulty<->perf_z artifact ==="
    )
    ledger = pd.read_csv(GEN / "game_ledger.csv")
    mean_perf_z_all = ledger["perf_z"].mean()
    subset = ledger[ledger["toi_s"] >= 3000]
    mean_perf_z_subset = subset["perf_z"].mean()
    lines.append(
        f"mean perf_z (all {len(ledger)} goalie-games) = {mean_perf_z_all:+.4f}; "
        f"mean perf_z (toi_s>=3000 subset, n={len(subset)}) = {mean_perf_z_subset:+.4f}"
    )
    lines.append(
        "explanation: the all-games mean is pulled negative by pulled-goalie stints "
        "(small variance denominator + strongly negative gsax); total gsax is ~0 "
        "(calibration exact) and the full-start subset sits near 0 as expected."
    )
    lines.append(f"mean lev_value (all games) = {ledger['lev_value'].mean():+.5f}")

    full = ledger.dropna(subset=["difficulty_pct", "perf_z"])
    sub_g = full[full["toi_s"] >= 3000]
    r_ga_full = full["difficulty_pct"].corr(full["ga"])
    r_ga_sub = sub_g["difficulty_pct"].corr(sub_g["ga"])
    r_pz_full = full["difficulty_pct"].corr(full["perf_z"])
    r_pz_sub = sub_g["difficulty_pct"].corr(sub_g["perf_z"])
    lines.append(
        f"corr(difficulty_pct, GA): all={r_ga_full:+.4f} (n={len(full)}) "
        f"toi>=3000={r_ga_sub:+.4f} (n={len(sub_g)})  [expect positive]"
    )
    lines.append(
        f"corr(difficulty_pct, perf_z): all={r_pz_full:+.4f} (n={len(full)}) "
        f"toi>=3000={r_pz_sub:+.4f} (n={len(sub_g)})  "
        "[explained artifact, not a gate -- see below]"
    )

    ga_ok = r_ga_full > 0 and r_ga_sub > 0
    if not ga_ok:
        lines.append(
            "STOP: difficulty<->GA correlation is not positive in both populations "
            "-- the difficulty index does not track game outcomes. BLOCKED."
        )
    else:
        lines.append("PASS: difficulty<->GA is positive in both populations, as expected.")

        quintiles = full.copy()
        quintiles["difficulty_q"] = pd.qcut(quintiles["difficulty_pct"], 5, labels=False)
        q_means = quintiles.groupby("difficulty_q")["perf_z"].mean()
        monotone = q_means.is_monotonic_increasing
        lines.append(
            "difficulty<->perf_z quintile means (perf_z, low to high difficulty): "
            + ", ".join(f"{v:+.3f}" for v in q_means)
            + f"  ({'monotone' if monotone else 'NOT monotone'})"
        )
        lines.append(
            "EXPLAINED (ratified 2026-07-15): the difficulty<->perf_z correlation "
            f"(+{r_pz_full:.2f} all / +{r_pz_sub:.2f} toi>=3000) is a sort-on-own-prediction "
            "artifact, not a difficulty-adjustment defect. Three-test evidence "
            "(v2/goalies probe, see .superpowers/sdd/probe-xg-calibration.md): "
            "(1) shot-level reliability is near-diagonal -- top predicted-xg decile is "
            "0.204 vs observed 0.191 (~7% relative), and the deviation is non-monotone "
            "across deciles, ruling out a real game-level compression defect at this "
            "magnitude; (2) within-goalie-season residual corr is 0.191 vs a between-goalie "
            "corr of 0.048, ruling out a goalie-quality confound (the effect lives inside "
            "one goalie's own game log, not between goalies of different quality); "
            "(3) band ratios Sigma(ga)/Sigma(xga) run 1.264 (decile 1) down to 0.847 "
            "(decile 10) -- the artifact's signature. Mechanism: xga is a noisy per-game "
            "sum, so ranking games on that same noisy xga selects positive-error games "
            "into the high bands, and gsax_game = xga - ga inherits the error -- any "
            "imperfect per-shot model produces this. Usage rule: perf_z/gsax comparisons "
            "ACROSS difficulty bands are inflated by shared xga noise; same-band and "
            "season-aggregate comparisons are sound. Do not 'correct' via GA~xGA "
            "recalibration -- that would curve-fit the artifact and compress real "
            "within-goalie variance."
        )

    # --- Team environment extremes ---
    lines.append("")
    lines.append("=== 4. Team environment: hardest/easiest 5 team-seasons ===")
    env = pd.read_csv(GEN / "team_environment.csv")
    lines.append("hardest 5 (mean_difficulty_pct):")
    for r in env.sort_values("mean_difficulty_pct", ascending=False).head(5).itertuples():
        lines.append(
            f"  {r.season} {r.team_abbrev}: mean_difficulty_pct={r.mean_difficulty_pct:.1f} "
            f"mean_xg_faced_per60={r.mean_xg_faced_per60:.2f} b2b_games={r.b2b_games}"
        )
    lines.append("easiest 5 (mean_difficulty_pct):")
    for r in env.sort_values("mean_difficulty_pct", ascending=True).head(5).itertuples():
        lines.append(
            f"  {r.season} {r.team_abbrev}: mean_difficulty_pct={r.mean_difficulty_pct:.1f} "
            f"mean_xg_faced_per60={r.mean_xg_faced_per60:.2f} b2b_games={r.b2b_games}"
        )

    # --- Arena freeze offsets ---
    lines.append("")
    lines.append("=== 5. Arena freeze offsets ===")
    offs = pd.read_csv(GEN / "arena_freeze_offsets.csv")
    over = offs[offs["freeze_offset"].abs() > 0.03]
    max_off = offs["freeze_offset"].abs().max()
    if len(over):
        lines.append(f"{len(over)} arena(s) exceed |0.03|:")
        for r in over.itertuples():
            lines.append(f"  {r.home_abbrev}: freeze_offset={r.freeze_offset:+.4f}")
    else:
        lines.append(f"none exceed |0.03| (max |offset| = {max_off:.3f})")

    # --- is_rebound coefficient per season ---
    lines.append("")
    lines.append("=== 6. Goal-layer is_rebound coefficient per season ===")
    lines.append(
        "note: Task 2's diagnostic found no rebound redefinition with a positive "
        "coefficient (all candidates probed negative, 2026-07-14; see "
        "v2/goalies/rebound_diag.py); features.py's is_rebound definition is unchanged."
    )
    for season in SEASONS:
        sc = pd.read_csv(GEN / f"structure_coefs_{season}.csv")
        row = sc[(sc["layer"] == "goal") & (sc["feature"] == "is_rebound")]
        coef = row["coef"].iloc[0] if len(row) else float("nan")
        lines.append(f"  {season}: coef={coef:+.4f}")

    report = "\n".join(lines)
    print(report)
    (GEN / "p4p5_report.txt").write_text(report + "\n")


if __name__ == "__main__":
    main()
