# Goalie 5v5 re-check — results report

**Date:** 2026-07-21
**Pre-registration:** docs/plans/2026-07-21-goalie-5v5-recheck-preregistration.md
**Multiplicity statement:** portability and stopping-repeatability are SECOND LOOKS at previously tested hypotheses; each carries a doubled false-positive budget. The freeze × strength item is a decomposition of an established positive result, not a new hypothesis test.

## 1. Registry and floor

Pooled real cases: 67. 5v5 registry at floor 600: 59 (88.1% of pooled). At floor 500: 66 (98.5% of pooled). Chosen floor: 600.

Rule (pre-registered, counts only, decided before any outcome data was examined): drop to floor 500 iff `n_600 < 0.75 * pooled_real_cases`. Here `0.75 * 67 = 50.25`, and `n_600 = 59 >= 50.25`, so the condition did not trigger. The 600 floor — identical to the pooled run's floor — was kept, per `data/generated/goalies/5v5/validation/floor_decision.json`.

## 2. Portability gate, 5v5 edition

| candidate | cut | dr | lo90 | hi90 | n_cases | r_cand | r_base_eb |
|---|---|---|---|---|---|---|---|
| stopping | 5v5 | 0.065 | -0.064 | 0.204 | 59 | -0.116 | -0.181 |
| stopping | pooled | 0.010 | -0.107 | 0.118 | 67 | -0.076 | -0.086 |
| freeze | 5v5 | -0.065 | -0.436 | 0.336 | 59 | -0.247 | -0.181 |
| freeze | pooled | -0.091 | -0.420 | 0.277 | 67 | -0.177 | -0.086 |
| rebound_control | 5v5 | 0.150 | -0.207 | 0.492 | 59 | -0.031 | -0.181 |
| rebound_control | pooled | 0.019 | -0.305 | 0.336 | 67 | -0.067 | -0.086 |
| perf | 5v5 | 0.117 | 0.037 | 0.190 | 59 | -0.064 | -0.181 |
| perf | pooled | 0.098 | 0.017 | 0.176 | 67 | 0.012 | -0.086 |
| composite | 5v5 | 0.080 | -0.077 | 0.252 | 59 | -0.102 | -0.181 |
| composite | pooled | 0.075 | -0.019 | 0.171 | 67 | -0.011 | -0.086 |

Verdict per pre-registered decision rule: **null strengthened**.

Four of five candidates (stopping, freeze, rebound_control, composite) have 90% CIs straddling zero in both the 5v5 and pooled runs — no signal in either cut, and the 5v5 CIs are wider throughout (n=59 vs n=67), which is the expected cost of the cleaner slice, not evidence of anything new.

`perf` is the one row whose CI excludes zero in both cuts (5v5: [0.037, 0.190]; pooled: [0.017, 0.176]). Per the decision rule this only counts as "5v5 reveals signal" if the CI excludes zero **and** the point estimate is materially above pooled. The point estimate moved from 0.098 to 0.117 — a +0.019 shift with heavily overlapping CIs, not a material jump. More importantly, the pooled P6 report (`data/generated/goalies/validation/p6_report.txt` §4) already diagnosed this exclusion as a baseline artifact: it is driven by `r_base_eb` reliably correlating negatively with post-switch outcome, not by `perf` predicting anything — `r_cand` for perf was only +0.012 pooled, indistinguishable from the other four candidates' `r_cand` values. The 5v5 run reproduces exactly that pattern: `r_cand` for perf is -0.064, again indistinguishable from stopping (-0.116), freeze (-0.247), rebound_control (-0.031), and composite (-0.102) — not a standout, and this time not even positive. The one nominal exclusion is the same known artifact recurring at 5v5, not new evidence, and it fails the "materially above pooled" test on its own terms.

No candidate crosses from null to signal at 5v5. This is a strengthened null: it holds in the pooled data and in the cleanest slice, at a doubled false-positive budget for having been tested twice.

## 3. Component repeatability, 5v5

Weighted r per layer (weight = min shared-season goalie count across the four consecutive-season pairs):

| layer | 5v5 weighted r | pooled weighted r | published anchor |
|---|---|---|---|
| onnet | 0.132 | 0.198 | — (no pre-registered anchor) |
| freeze | 0.639 | 0.664 | ≈0.58 |
| goal (stopping) | 0.166 | 0.118 | ≈0.12 |
| rebound | 0.183 | 0.227 | ≈0.24–0.26 |

Freeze repeatability sits comfortably above its published anchor in both cuts (0.639 at 5v5, 0.664 pooled, vs ≈0.58), reconfirming freeze as the most repeatable component regardless of strength state. Rebound repeatability is modestly below its anchor band in both cuts, more so at 5v5 (0.183 vs 0.227 pooled, anchor 0.24–0.26) — same direction as pooled, not a new pattern (anchor added post hoc for context from the design doc's literature table; no verdict rides on it).

**Answer to mechanism 1: does stopping (goal-layer) repeatability rise when PK noise is removed?** Yes, modestly: 0.118 pooled → 0.166 at 5v5, a rise of +0.049 (≈41% relative). This is a point-estimate comparison only — no bootstrap CI was computed on these weighted-r values (unlike the gate statistics in §2), so the size of the rise should be read as suggestive, not as a significance-tested result, and it carries the same doubled false-positive budget as the portability re-check. The rise is directionally consistent with the mechanism-1 hypothesis (removing PK situations, where save difficulty and defensive-zone chaos are less goalie-controlled, should let true stopping skill repeat more cleanly), but the 5v5 stopping estimate (0.166) remains well below the freeze layer's repeatability (0.639) in the same cut — it does not close the gap between "stopping" and "freeze" as goalie skills, it only narrows it slightly.

## 4. Freeze × strength decomposition

All-situations data (decomposition, not a strength slice), from `data/generated/goalies/validation/freeze_by_strength.json`:

| term | coef | SE |
|---|---|---|
| froze_ev (EV baseline effect) | -0.01788 | 0.00034 |
| froze_x_sh (SH interaction) | -0.02267 | 0.00087 |
| froze_x_pp (PP interaction) | +0.00447 | 0.00250 |

Implied per-freeze effect by strength: EV = -0.01788 (froze_ev alone); SH (penalty kill) = froze_ev + froze_x_sh = -0.04055 (matches the reported PK total exactly); PP = froze_ev + froze_x_pp = -0.01340.

Save counts by strength/froze (from `freeze_by_strength.txt`): EV — 195,820 in-play, 90,262 frozen; PP — 8,432 in-play, 1,406 frozen; SH — 39,105 in-play, 16,103 frozen.

Interpretation: **yes, a PK freeze is worth more**, per the line-change hypothesis. A freeze while shorthanded suppresses expected goals against by roughly 2.3x the EV effect (-0.0406 vs -0.0179), and the SH interaction term is precisely estimated (coef/SE ≈ 26, before any clustering inflation). A freeze while on the power play is worth less than an EV freeze (-0.0134 vs -0.0179) — consistent with the goalie's own team already suppressing shot quality and volume while up a skater, so there is less marginal value in stopping play. The PK result is the stronger and more interesting one: it supports the idea that a stoppage during a penalty kill has outsized value beyond the immediate save, plausibly through letting tired penalty-killers change and resetting defensive-zone structure — exactly the mechanism the line-change hypothesis proposes. As with the headline freeze study, the reported SEs are iid ridge SEs; clustering would inflate true uncertainty by a plausible 2–5x, which does not threaten the significance margin on froze_ev or froze_x_sh but leaves froze_x_pp (coef/SE ≈ 1.8 even before inflation) unresolved either way.

## 5. Descriptive 5v5 layer

5v5 freeze-value pathway: coef = -0.017979 (per-freeze xGA delta, 30s window), significant = true, per `data/generated/goalies/5v5/validation/freeze_value.json` and `freeze_value_report.txt`. This is smaller in magnitude than the all-situations (pooled) estimate of -0.021296 — consistent with §4's finding that PK freezes (excluded from the 5v5 cut) carry the largest per-freeze effect, so pooling them in raises the all-situations average above the 5v5-only estimate.

Browser: `goalies.db` now carries both cuts (`SITUATIONS = ("all", "5v5")` in `v2/browser/build_goalies_db.py`). The situations dropdown (`v2/browser/app.py`, id `goalie-situation`) offers "All situations" and "5v5 (1551)"; dropdown default remains `all`, session-persisted once changed.

## 6. What stays closed

Rust/idle-gap, hot-hand, and rebound-era nulls are not re-tested at 5v5, per the pre-registered exclusion list in the addendum. These remain closed findings from the pooled program.
