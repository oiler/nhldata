"""P6 phase-gate report: era probe, registry, frozen params, portability gate,
repeatability, tandem sanity check, honest-null framing (spec Sec 6c / Sec 7).

Usage: python3 v2/goalies/report_p6.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
VAL = ROOT / "data" / "generated" / "goalies" / "validation"

CANDIDATES = ("stopping", "freeze", "rebound_control", "perf", "composite")

# Anchors from the P3 gate (docs/plans/2026-06-11-goalie-evaluation-design.md
# Sec 6b, approved 2026-07-14) and repeatability.py's docstring anchors.
REPEAT_ANCHORS = {
    "freeze": "P3 anchor: year-pair r 0.60-0.80, split-half 0.712 (real skill)",
    "goal": "anchor: stopping ~0.12 (P3: noise-dominated at single-season scale)",
    "rebound": "P3 anchor: r 0.26-0.36 (modest-real)",
    "onnet": "no pre-registered anchor (on-net layer, team shot-suppression, "
             "not a portability candidate)",
}


def main() -> None:
    lines = []

    # === 1. Era probe verdicts + coefficients ===
    lines.append("=== 1. Era probe (rebound-anomaly mechanism, Task 1) ===")
    verdict = json.loads((VAL / "era_probe_verdict.json").read_text())
    for key in ("froze", "rebound_generated"):
        c = verdict["coefs"][key]
        sigma = abs(c["coef"] / c["se"]) if c["se"] else float("nan")
        lines.append(
            f"{key}: era_b coef={c['coef']:+.4f} se={c['se']:.4f} ({sigma:.0f}sigma) "
            f"rate_a={c['rate_a']:.4f} rate_b={c['rate_b']:.4f} -> verdict={verdict[key]}"
        )
    lines.append(
        "reading: 'froze' is era-stable (small, non-actionable coefficient) -- freeze "
        "terms need no era treatment. 'rebound_generated' shifted materially at the "
        "2023 coding boundary (+0.305, ~26 standard errors) -- the first direct "
        "mechanism evidence for the P4/P5 is_rebound sign anomaly (Sec 6c). Per the "
        "pre-registered decision rule this is outcome (a): rebound terms are "
        "era-normalized before candidacy (frozen_params.json normalize=['rebound'])."
    )

    # === 2. Switch registry summary ===
    lines.append("")
    lines.append("=== 2. Switch registry ===")
    reg = pd.read_csv(VAL / "switch_registry.csv")
    counts = reg["switch_type"].value_counts()
    real = reg[reg["switch_type"] != "nonswitch"]
    lines.append(
        f"total cases={len(reg)}: offseason={counts.get('offseason', 0)} "
        f"midseason={counts.get('midseason', 0)} pseudo(nonswitch)={counts.get('nonswitch', 0)}"
    )
    lines.append(
        f"real cases (offseason+midseason)={len(real)}; weight (=min pre/post fenwick) "
        f"min={real['weight'].min():.0f} median={real['weight'].median():.0f} "
        f"mean={real['weight'].mean():.0f} max={real['weight'].max():.0f}"
    )
    lines.append(
        "floor/fallback note (Sec 6c): registry floor lowered from the spec's >=1,000 "
        "default to >=600 fenwick each side (the >=1,000 floor yielded only 34 "
        "season-boundary cases, not the ~80-100 estimated); mid-season trades added "
        "under the same rule. Fallback to season-boundary-only (option B) was not "
        "needed -- the combined real-case yield (67) landed inside the expected "
        "~60-75 range."
    )

    # === 3. Frozen params ===
    lines.append("")
    lines.append("=== 3. Frozen non-switch params ===")
    params = json.loads((VAL / "frozen_params.json").read_text())
    lines.append(
        f"K={params['k']} (grid top of (250, 500, 1000, 2000, 4000) -- railed at the "
        "grid's upper boundary; the pseudo-case shrinkage optimum may exceed the grid, "
        "meaning GSAx is even more noise-dominated than the P3 grid anticipated)"
    )
    beta = params["composite"]["beta"]
    lines.append(
        "composite betas (standardized units): "
        + ", ".join(f"{k}={v:+.5f}" for k, v in beta.items())
    )
    lines.append(
        f"largest beta={max(beta, key=lambda k: abs(beta[k]))} "
        f"({beta[max(beta, key=lambda k: abs(beta[k]))]:+.5f}) -- 'perf' is largest in "
        "relative terms only; all betas are tiny in absolute terms, consistent with "
        "GSAx being noise-dominated at this population."
    )
    lines.append(f"normalize set={params['normalize']}")

    # === 4. The gate table ===
    lines.append("")
    lines.append("=== 4. Portability gate (67 real switch cases vs EB-shrunk GSAx baseline) ===")
    gate = pd.read_csv(VAL / "gate_table.csv")
    for r in gate.itertuples():
        excludes_zero = (r.lo90 > 0) or (r.hi90 < 0)
        reading = "CI EXCLUDES ZERO" if excludes_zero else "CI straddles zero (null)"
        lines.append(
            f"  {r.candidate}: dr={r.dr:+.4f} [{r.lo90:+.4f}, {r.hi90:+.4f}] "
            f"n={r.n_cases} r_cand={r.r_cand:+.4f} r_base_eb={r.r_base_eb:+.4f} "
            f"spearman={r.spearman_cand:+.4f} incr_beta={r.incr_beta:+.5f}  -> {reading}"
        )
    lines.append("")
    lines.append(
        "plain-language reading: 'perf' is the sole row whose 90% CI nominally "
        "excludes zero (lo90=+0.0168, hi90=+0.176). Per the Task 5 investigation "
        "(both known leakage traps -- mid-season refit fallback, pseudo-case "
        "contamination -- were checked and ruled out), this exclusion is DRIVEN by "
        "the EB baseline correlating reliably negatively with post-switch outcome "
        "(r_base_eb=-0.086 across bootstrap resamples), not by 'perf' itself "
        "predicting anything: r_cand for perf is only +0.0115, indistinguishable "
        "from the other four candidates' r_cand values (all in [-0.18, +0.02]). "
        "This is a flag for the gate reading -- an artifact of the paired-difference "
        "statistic against a reliably-negative baseline -- not a candidate win."
    )
    lines.append(
        "MANDATORY MULTIPLICITY CAVEAT: five candidate families were tested; a "
        "single nominal CI exclusion among five is weak evidence."
    )
    lines.append(
        "headline: no candidate shows predictive signal on post-switch GSAx at "
        "this n. The deeper finding is that pre-switch GSAx itself anti-predicts "
        "post-switch GSAx here (see Sec 5 below) -- an honest-null result, not "
        "a measurement failure."
    )

    # === 5. Literature anchor line ===
    lines.append("")
    lines.append("=== 5. Literature anchor (naive single-prior-season GSAx) ===")
    r_base_naive = gate["r_base_naive"].iloc[0]
    r_base_eb = gate["r_base_eb"].iloc[0]
    lines.append(
        f"r_base_naive={r_base_naive:+.4f} vs the literature-comparable r~0.12 family "
        "(spec Sec 6c) -- sign-flipped and small at this n, not merely 'weaker than "
        "the anchor'."
    )
    lines.append(
        f"r_base_eb={r_base_eb:+.4f} (EB-shrunk baseline, the actual gate baseline) "
        "is more negative than the naive anchor, not less -- pre-switch GSAx "
        "anti-predicts post-switch GSAx in both baseline forms at this n. This is "
        "the honest-null family the spec's research anchors warned was possible, "
        "not a data defect."
    )

    # === 6. Repeatability + tandem ===
    lines.append("")
    lines.append("=== 6. Component repeatability vs P3 anchors ===")
    rep = pd.read_csv(VAL / "repeatability.csv")
    for layer in ("onnet", "freeze", "goal", "rebound"):
        sub = rep[rep["layer"] == layer]
        lines.append(
            f"  {layer}: r range [{sub['r'].min():+.3f}, {sub['r'].max():+.3f}] "
            f"across {len(sub)} season-pairs (n_goalies {sub['n_goalies'].min()}-"
            f"{sub['n_goalies'].max()})  -- {REPEAT_ANCHORS[layer]}"
        )
    goal_mean = rep[rep["layer"] == "goal"]["r"].mean()
    lines.append(
        f"freeze repeatability (0.630-0.719) reconfirms the P3 real-skill finding. "
        f"goal-layer (stopping) mean r={goal_mean:+.3f}, in the ~0.1 anchor family -- "
        "the Sec 6c repeatability warning (stopping repeating well above its ~0.12 "
        "anchor without beating portability would suggest a leaked-environment "
        "confound) does NOT fire here; the observed repeatability sits at, not "
        "above, the anchor."
    )
    lines.append("")
    tandem = pd.read_csv(VAL / "tandem_table.csv")
    tandem_corr = tandem["gsax_gap"].corr(tandem["term_gap"])
    lines.append(
        f"tandem table: {len(tandem)} same-team same-season goalie pairs, "
        f"corr(gsax_gap, term_gap)={tandem_corr:+.4f}."
    )
    lines.append(
        "caveat: this is a same-season consistency check between two derivations "
        "of the same underlying result (fenwick GSAx-rate gap vs goal-layer term "
        "gap, same goalies, same season) -- it confirms internal consistency of the "
        "environment-stripping pipeline, NOT independent skill evidence. It says "
        "nothing about whether either quantity predicts anything out-of-sample."
    )

    # === 7. Honest-null framing (spec Sec 7) ===
    lines.append("")
    lines.append("=== 7. Phase-gate framing (spec Sec 7) ===")
    lines.append(
        "spec Sec 7: 'After P6: does anything beat GSAx on portability? Honest "
        "prior from the literature: possibly only marginally. A null result with "
        "tight error bars is a success criterion, not a failure.'"
    )
    lines.append(
        "P6 result: no candidate beats the EB-shrunk GSAx baseline on post-switch "
        "portability at n=67 (all five Delta-r estimates are near zero or negative, "
        "the sole nominal exclusion is a baseline artifact, not a candidate signal, "
        "per Sec 4/5 above). The CIs are wide (n=67 is small) but centered near "
        "zero, not narrowly missing a real effect. Per the spec's own framing, "
        "this well-measured null is a valid, reportable program outcome -- freeze's "
        "P3-confirmed individual-skill signal (Sec 6) does not translate into a "
        "'trade this goalie and expect the number to travel' portability claim at "
        "this sample size, and the era-probe result (Sec 1) resolves the P4/P5 "
        "rebound anomaly's mechanism independent of the gate outcome."
    )

    report = "\n".join(lines)
    print(report)
    (VAL / "p6_report.txt").write_text(report + "\n")


if __name__ == "__main__":
    main()
