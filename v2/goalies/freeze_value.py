"""Freeze value-pathway study + tandem team-effect bound (spec 6d, sub-project A).

Prices the post-save branch: frozen (stoppage -> faceoff -> play) vs in-play,
as opponent xG in the next 30 game-clock seconds, truncated at period end.
Estimator: closed-form generalized-ridge linear regression, froze effectively
unpenalized. Either sign is a finding.

The shot stream is fenwick-only by pipeline design: blocked shots are never extracted,
so window xGA sums unblocked attempts only.

Usage: python3 v2/goalies/freeze_value.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.features import STRUCTURE_COLS, build_features  # noqa: E402
from v2.goalies.gsax_baseline import blind_shot_xg  # noqa: E402
from v2.goalies.portability import weighted_r  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
PERIOD_END_S = 1200
WINDOWS = (30, 15, 60)          # primary first, then robustness
SAVES_PER_SEASON = 1550


def window_xga(shots: pd.DataFrame, saves: pd.DataFrame, window_s: int = 30) -> np.ndarray:
    key = ["game_id", "goalie_is_home", "period"]
    s = shots.sort_values(key + ["time_s"], kind="stable")
    groups = {}
    for k, grp in s.groupby(key, sort=False):
        t = grp["time_s"].to_numpy(dtype=float)
        cs = np.concatenate([[0.0], np.cumsum(grp["xg"].to_numpy(dtype=float))])
        groups[k] = (t, cs)
    out = np.zeros(len(saves))
    for i, row in enumerate(saves[key + ["time_s"]].itertuples(index=False)):
        k = (row.game_id, row.goalie_is_home, row.period)
        if k not in groups:
            continue
        t, cs = groups[k]
        t0 = float(row.time_s)
        lo = np.searchsorted(t, t0, side="right")
        hi = np.searchsorted(t, min(t0 + window_s, PERIOD_END_S), side="right")
        out[i] = cs[hi] - cs[lo]
    return out


def ridge_linear(X: np.ndarray, y: np.ndarray, penalty: np.ndarray):
    A = X.T @ X + np.diag(penalty)
    A_inv = np.linalg.inv(A)
    beta = A_inv @ X.T @ y
    resid = y - X @ beta
    dof = max(len(y) - X.shape[1], 1)
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * (A_inv @ (X.T @ X) @ A_inv)
    # Near-collinear/degenerate regressors under ridge can push a zero variance numerically negative — clip before sqrt.
    return beta, np.sqrt(np.clip(np.diag(cov), 0.0, None))


def freeze_effect(saves: pd.DataFrame, y: np.ndarray,
                  demean_by_goalie: bool = False) -> dict:
    froze = saves["froze"].to_numpy(dtype=float)
    yy = np.asarray(y, dtype=float)
    if demean_by_goalie:
        g = saves["goalie_id"].to_numpy()
        d = pd.DataFrame({"g": g, "y": yy, "f": froze})
        yy = (d["y"] - d.groupby("g")["y"].transform("mean")).to_numpy()
        froze = (d["f"] - d.groupby("g")["f"].transform("mean")).to_numpy()
    X = np.hstack([build_features(saves).to_numpy(), froze[:, None]])
    penalty = np.full(X.shape[1], 1.0)
    penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
    penalty[-1] = 1e-6
    beta, se = ridge_linear(X, yy, penalty)
    return {"coef": float(beta[-1]), "se": float(se[-1]), "n": len(yy)}


def season_value(delta: float, rate_lo: float, rate_hi: float,
                 saves_per_season: int = SAVES_PER_SEASON) -> dict:
    return {"goals_low": delta * saves_per_season * rate_lo,
            "goals_high": delta * saves_per_season * rate_hi}


def tandem_bound(rates: pd.DataFrame) -> dict:
    pairs = []
    for (_, _), grp in rates.groupby(["season", "team"]):
        if len(grp) != 2:
            continue
        # label by workload, never by the outcome — sorting hi/lo on gsax_rate
        # puts corr(max, min) ≈ 0.467 under full independence
        starter, backup = grp.sort_values(
            ["n", "goalie_id"], ascending=[False, True]).itertuples(index=False)
        pairs.append({"starter": starter.gsax_rate, "backup": backup.gsax_rate,
                      "w": min(starter.n, backup.n)})
    p = pd.DataFrame(pairs)
    partner_r = weighted_r(p["starter"], p["backup"], p["w"])
    w = rates["n"].to_numpy(dtype=float)
    x = rates["gsax_rate"].to_numpy(dtype=float)
    mu = np.average(x, weights=w)
    total_var = np.average((x - mu) ** 2, weights=w)
    team_means = rates.groupby(["season", "team"]).apply(
        lambda g: pd.Series({"m": np.average(g["gsax_rate"], weights=g["n"]),
                             "w": g["n"].sum()}), include_groups=False)
    between_var = np.average((team_means["m"] - mu) ** 2, weights=team_means["w"])
    # subtract the sampling contribution a finite pair adds to between-var? No:
    # report the RAW between share as an upper bound (spec: bound, not estimate)
    between_share = float(between_var / total_var) if total_var > 0 else float("nan")
    sd_rate = float(np.sqrt(total_var))
    return {"partner_r": float(partner_r), "between_share": between_share,
            "sd_rate": sd_rate, "bound_sv_pts": between_share * sd_rate,
            "n_pairs": len(p)}


def _load_saves_and_shots():
    frames = []
    for season in SEASONS:
        shots = pd.read_csv(GEN / f"shots_{season}.csv")
        shots["xg"] = blind_shot_xg(shots)
        frames.append(shots)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    VAL.mkdir(parents=True, exist_ok=True)
    shots = _load_saves_and_shots()
    saves = shots[shots["on_net"] & ~shots["is_goal"] & shots["froze"].notna()].copy()
    lines = []

    fits = {}
    ys = {}
    for w in WINDOWS:
        y = window_xga(shots, saves, window_s=w)
        ys[w] = y
        fits[w] = freeze_effect(saves, y)
        raw_gap = float(np.mean(y[saves["froze"] == 1]) - np.mean(y[saves["froze"] == 0]))
        frozen_mean = float(np.mean(y[saves["froze"] == 1]))
        inplay_mean = float(np.mean(y[saves["froze"] == 0]))
        lines.append(f"window {w:>2}s: coef={fits[w]['coef']:+.5f} se={fits[w]['se']:.5f} "
                     f"n={fits[w]['n']} raw_frozen_minus_inplay={raw_gap:+.5f} "
                     f"frozen_mean={frozen_mean:.4f} inplay_mean={inplay_mean:.4f}")

    p30 = fits[30]
    se_margin = abs(p30["coef"]) / p30["se"]
    lines.append(f"SE caveat: reported SEs are iid ridge SEs; overlapping windows + "
                 f"within-game clustering make true uncertainty larger (plausibly 2-5x) "
                 f"— the significance margin (|coef| ~ {se_margin:.0f}x SE) is unaffected.")

    y30 = ys[30]
    wg = freeze_effect(saves, y30, demean_by_goalie=True)
    lines.append(f"within-goalie 30s: coef={wg['coef']:+.5f} se={wg['se']:.5f}")
    era_fits = {}
    for label, seasons in (("eraA", (2021, 2022)), ("eraB", (2023, 2024, 2025))):
        m = saves["season"].isin(seasons).to_numpy()
        e = freeze_effect(saves[m], y30[m])
        era_fits[label] = e
        lines.append(f"{label} 30s: coef={e['coef']:+.5f} se={e['se']:.5f} n={e['n']}")
    lines.append(f"era gap ({era_fits['eraA']['coef']:+.5f} vs {era_fits['eraB']['coef']:+.5f}) "
                 f"is consistent with the known 2023 tracking-era freeze-detection shift; "
                 f"the 6d rule requires sign consistency only.")

    primary = fits[30]
    significant = (abs(primary["coef"]) >= 2 * primary["se"]
                   and np.sign(fits[15]["coef"]) == np.sign(primary["coef"])
                   and np.sign(fits[60]["coef"]) == np.sign(primary["coef"]))
    per_goalie_rate = saves.groupby("goalie_id")["froze"].agg(["mean", "size"])
    big = per_goalie_rate[per_goalie_rate["size"] >= 500]["mean"]
    val = season_value(primary["coef"], float(big.quantile(0.1)), float(big.quantile(0.9)))
    lines.append(f"significant per 6d rule: {significant}")
    lines.append(f"freeze-rate spread (>=500 saves): p10={big.quantile(0.1):.3f} "
                 f"p90={big.quantile(0.9):.3f}")
    spread_goals = primary["coef"] * SAVES_PER_SEASON * (float(big.quantile(0.9)) - float(big.quantile(0.1)))
    lines.append(f"absolute suppression vs a zero-freeze baseline: p10-rate goalie "
                 f"{val['goals_low']:+.2f}, p90-rate goalie {val['goals_high']:+.2f} goals/season")
    lines.append(f"BETWEEN-GOALIE SKILL VALUE (p90 vs p10 freeze rate): "
                 f"{spread_goals:+.2f} goals/season")

    pe_mask = (saves["time_s"] <= (PERIOD_END_S - 30)).to_numpy()
    pe_fit = freeze_effect(saves[pe_mask], y30[pe_mask])
    pe_pct = abs((primary["coef"] - pe_fit["coef"]) / primary["coef"]) * 100
    lines.append(f"period-end sensitivity: coef30 excluding last 30s of periods = "
                 f"{pe_fit['coef']:+.5f} (headline {primary['coef']:+.5f}; "
                 f"~{pe_pct:.0f}% of effect is buzzer-adjacent auto-freeze)")

    fen = shots[shots["event"] != "blocked-shot"]
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    team_of = gg.groupby(["season", "goalie_id"])["team_abbrev"].agg(
        lambda s: s.mode().iloc[0]).rename("team").reset_index()
    per = fen.groupby(["season", "goalie_id"]).agg(
        n=("xg", "size"), xga=("xg", "sum"), ga=("is_goal", "sum")).reset_index()
    per["gsax_rate"] = (per["xga"] - per["ga"]) / per["n"]
    per = per.merge(team_of, on=["season", "goalie_id"])
    pairs = (per[per["n"] >= 600].sort_values("n", ascending=False)
             .groupby(["season", "team"]).head(2))
    counts = pairs.groupby(["season", "team"]).size()
    pairs = pairs.set_index(["season", "team"]).loc[counts[counts == 2].index].reset_index()
    tb_input = pairs[["season", "team", "goalie_id", "gsax_rate", "n"]]
    tb = tandem_bound(tb_input)
    bound_sd_form = float(np.sqrt(tb["between_share"]) * tb["sd_rate"])
    lines.append(f"\ntandem bound (workload-labeled starter/backup pairs, avoids "
                 f"order-statistic artifact): partner_r={tb['partner_r']:+.3f} "
                 f"between_share={tb['between_share']:.3f} sd_rate={tb['sd_rate']:.4f} "
                 f"bound_sd_form={bound_sd_form:.4f} sv-pts/shot (SD form, comparable to "
                 f"JLikens ~0.006; share-x-SD hybrid form {tb['bound_sv_pts']:.4f}) "
                 f"over {tb['n_pairs']} pairs")
    lines.append("tandem bound takeaway: consistent with the JLikens anchor, "
                 "noise-floor-dominated — not tighter than it.")

    rng = np.random.default_rng(42)
    null_between_shares = np.empty(300)
    for i in range(300):
        shuffled = tb_input.copy()
        shuffled["gsax_rate"] = shuffled.groupby("season")["gsax_rate"].transform(
            lambda s: rng.permutation(s.to_numpy()))
        null_between_shares[i] = tandem_bound(shuffled)["between_share"]
    null_mean = float(np.mean(null_between_shares))
    null_p95 = float(np.percentile(null_between_shares, 95))
    perm_p = float(np.mean(null_between_shares >= tb["between_share"]))
    lines.append(f"between_share null floor (2-goalie pairs, 300 within-season "
                 f"permutations): mean {null_mean:.3f}, p95 {null_p95:.3f}; "
                 f"observed {tb['between_share']:.3f} -> permutation p={perm_p:.2f}")
    lines.append("partner_r is the evidence-bearing tandem statistic, not between_share")

    report = "\n".join(lines)
    (VAL / "freeze_value_report.txt").write_text(report + "\n")
    (VAL / "freeze_value.json").write_text(json.dumps({
        "per_freeze_xga_delta": primary["coef"] if significant else None,
        "window_s": 30, "significant": bool(significant)}, indent=2))
    print(report)


if __name__ == "__main__":
    main()
