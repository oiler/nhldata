"""P3 phase-gate analysis: do goalie terms separate from noise?

All correlations use INDEPENDENT per-season fits (term_indep) — chained
priors would mechanically inflate repeatability.

Usage: python3 v2/goalies/gate_p3.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from v2.goalies.difficulty import LAYERS, fit_layer, layer_frame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def signal_share(terms: pd.DataFrame) -> float:
    var_obs = float(terms["term_indep"].var(ddof=1))
    noise = float((terms["se_indep"] ** 2).mean())
    if var_obs <= 0:
        return 0.0
    return max(0.0, var_obs - noise) / var_obs


def year_pair_r(a: pd.DataFrame, b: pd.DataFrame, col: str,
                min_shots: int = 1000) -> tuple[float, int]:
    shot_col = "n_shots" if "n_shots" in a.columns else "shots"
    a = a[a[shot_col] >= min_shots]
    b = b[b[shot_col] >= min_shots]
    merged = a.merge(b, on="goalie_id", suffixes=("_a", "_b"))
    if len(merged) < 3:
        return float("nan"), len(merged)
    r = float(np.corrcoef(merged[f"{col}_a"], merged[f"{col}_b"])[0, 1])
    return r, len(merged)


def common_population_r(terms_a: pd.DataFrame, terms_b: pd.DataFrame,
                         gsax_a: pd.DataFrame, gsax_b: pd.DataFrame,
                         min_shots: int = 1000) -> tuple[float, float, int]:
    """Goal-layer term_indep r and GSAx r over the SAME goalie population.

    Population = goalies present in both seasons' goalie_terms (goal layer)
    and both seasons' gsax tables, with >= min_shots unblocked shots (gsax
    'shots' column) in both seasons. Using gsax shots (not the goal layer's
    on-net n_shots) for the qualifying threshold keeps the two correlations
    comparable on a common footing.
    """
    ga = gsax_a[gsax_a["shots"] >= min_shots][["goalie_id", "shots", "gsax_per100"]]
    gb = gsax_b[gsax_b["shots"] >= min_shots][["goalie_id", "shots", "gsax_per100"]]
    g_merged = ga.merge(gb, on="goalie_id", suffixes=("_a", "_b"))

    ta = terms_a[["goalie_id", "term_indep"]]
    tb = terms_b[["goalie_id", "term_indep"]]
    t_merged = ta.merge(tb, on="goalie_id", suffixes=("_a", "_b"))

    common = g_merged.merge(t_merged, on="goalie_id")
    n = len(common)
    if n < 3:
        return float("nan"), float("nan"), n
    r_goal = float(np.corrcoef(common["term_indep_a"], common["term_indep_b"])[0, 1])
    r_gsax = float(np.corrcoef(common["gsax_per100_a"], common["gsax_per100_b"])[0, 1])
    return r_goal, r_gsax, n


def main() -> None:
    lines = []
    terms = {s: pd.read_csv(GEN / f"goalie_terms_{s}.csv") for s in SEASONS}
    gsax = {s: pd.read_csv(GEN / f"gsax_{s}.csv") for s in SEASONS}

    lines.append("=== 1. Signal share per layer-season (indep fits) ===")
    for layer in LAYERS:
        for s in SEASONS:
            t = terms[s][terms[s]["layer"] == layer]
            lines.append(f"{layer} {s}: n={len(t)} sd={t['term_indep'].std(ddof=1):.4f} "
                         f"mean_se={t['se_indep'].mean():.4f} signal_share={signal_share(t):.3f}")

    lines.append("\n=== 2. Year-pair repeatability (min 1000 shots both sides) ===")
    for layer in LAYERS:
        rs = []
        for s1, s2 in zip(SEASONS, SEASONS[1:]):
            a = terms[s1][terms[s1]["layer"] == layer]
            b = terms[s2][terms[s2]["layer"] == layer]
            r, n = year_pair_r(a, b, "term_indep")
            rs.append(f"{s1}->{s2}: r={r:.3f} (n={n})")
        lines.append(f"{layer}: " + "  ".join(rs))
    rs = []
    for s1, s2 in zip(SEASONS, SEASONS[1:]):
        r, n = year_pair_r(gsax[s1], gsax[s2], "gsax_per100")
        rs.append(f"{s1}->{s2}: r={r:.3f} (n={n})")
    lines.append("GSAx baseline: " + "  ".join(rs))

    lines.append("\n=== 2b. Common-population goal-layer vs GSAx "
                 "(>=1000 unblocked shots, same goalies both metrics) ===")
    for s1, s2 in zip(SEASONS, SEASONS[1:]):
        ta = terms[s1][terms[s1]["layer"] == "goal"]
        tb = terms[s2][terms[s2]["layer"] == "goal"]
        r_goal, r_gsax, n = common_population_r(ta, tb, gsax[s1], gsax[s2])
        lines.append(f"{s1}->{s2}: goal r={r_goal:.3f}  gsax r={r_gsax:.3f}  (n={n})")

    lines.append("\n=== 3. Split-half (2023, even/odd game_id) ===")
    df23 = pd.read_csv(GEN / "shots_2023.csv")
    for layer in ("goal", "freeze"):
        halves = []
        for parity in (0, 1):
            half = df23[df23["game_id"] % 2 == parity]
            fit = fit_layer(half, layer)
            halves.append(fit.goalie_terms.rename(columns={"term": "term_indep",
                                                           "se": "se_indep"}))
        r, n = year_pair_r(halves[0], halves[1], "term_indep", min_shots=500)
        lines.append(f"{layer}: split-half r={r:.3f} (n={n})")

    lines.append("\n=== 4. Prior-strength sensitivity (goal layer, 2023) ===")
    fits = {ps: fit_layer(df23, "goal", goalie_prior_shots=ps).goalie_terms
            for ps in (250, 1000, 4000)}
    for a, b in ((250, 1000), (1000, 4000), (250, 4000)):
        merged = fits[a].merge(fits[b], on="goalie_id", suffixes=("_a", "_b"))
        rho = float(merged["term_a"].rank().corr(merged["term_b"].rank()))
        lines.append(f"prior {a} vs {b}: spearman={rho:.3f}")

    lines.append("\n=== 5. Gate anchors (spec) ===")
    lines.append("freeze year-pair expected ~0.5+; GSAx-style stopping ~0.12.")
    lines.append("Gate question: does goal-layer signal_share / year-pair r beat GSAx?")
    lines.append("")
    lines.append(
        "CAVEAT - signal_share on shrunken terms is a one-sided test with a "
        "high zero-threshold: with shrinkage weight w = I/(I+lambda), "
        "observed variance compresses ~w^2 while mean(se^2) compresses ~w, "
        "so signal_share reads 0.000 whenever true skill variance is below "
        "((1-w)/w)*noise - a metric with true reliability ~0.5 can report "
        "0.000 at w=0.5. Read 0.000 as 'not detectably above heavy-shrinkage "
        "noise', NOT 'no skill exists'. Weight the year-pair and split-half "
        "correlations more heavily."
    )

    report = "\n".join(lines)
    print(report)
    (GEN / "gate_p3_report.txt").write_text(report + "\n")


if __name__ == "__main__":
    main()
