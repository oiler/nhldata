# Goalie 5v5 re-check — approach note (pre-design, for a future session)

**Date:** 2026-07-21
**Status:** Idea, not yet brainstormed/spec'd. Seeds the next goalie session.
**Context:** All goalie-program results (P0–P6, freeze value, tandem bound) were computed at all strength states with strength as a per-shot covariate, per the 2026-06-11 spec decision. oiler's question: do the nulls we found need re-checking at 5v5-only?

## The short answer to the theory question

Partly — but not as a blanket re-run. The per-shot xG model already prices strength, so per-shot confounds are handled. Pooling strengths can hide a 5v5 signal through exactly two mechanisms, and only the tests exposed to those mechanisms are worth a second look:

1. **Attenuation from strength-specific skill.** If a skill expresses at 5v5 but drowns in PK chaos (screens, one-timers, scrambles — where the model's features explain less), per-goalie terms fit on pooled shots get dragged toward zero by the noisy slice. A 5v5-only refit trades ~20% of the sample for a cleaner per-shot signal; that trade can go either way and is worth measuring.
2. **Special-teams environment swamping the portability test.** PK schemes differ across teams far more than 5v5 defensive environments do. Part of the portability null could be "switching teams changes the special-teams context so much that nothing ports." Portability measured 5v5-to-5v5 is a genuinely different — and arguably fairer — test of talent transfer.

Nulls NOT worth re-checking at 5v5: the idle-gap/rust null and the hot-hand family (their mechanism arguments are strength-independent, priors very low), and the rebound era anomaly (a coding-era issue, not a strength issue).

## Prioritized scope

1. **Portability gate, 5v5 edition (highest value).** Rebuild candidates AND outcome 5v5-only; re-run the existing pre-registered harness (it is parameterized; frozen-params discipline carries over). Registry note: fenwick floors will thin the case list ~10–20% — revisit the 600 floor (maybe 500) and report the n cost.
2. **Component repeatability, 5v5.** Published anchors (freeze ≈ 0.58, stopping ≈ 0.12) are mostly 5v5-based — a 5v5 run makes our comparisons apples-to-apples and tests mechanism 1 directly (does stopping repeatability rise when PK noise is removed?).
3. **Freeze value by strength (not a null — a decomposition).** Fit the freeze effect with a froze × strength interaction instead of slicing: freezing on the PK buys a line change, so its value may be *higher* there. This sharpens a positive result rather than re-testing a null.

## First technical step (blocking)

The shots tables carry only a 3-level `strength` column (EV/SH/PP, goalie perspective) — **EV includes 4v4 and 3v3**, so it cannot produce a strict-5v5 cut. Options: (a) rebuild the shot stream with `situationCode` carried through from raw (project convention: strict `1551`, matching the skater side), or (b) accept EV as the cut and say so. Recommend (a) — it is one extract-layer column plus a rebuild, and the strict convention is already established in this repo.

## Statistical honesty (pre-register before running)

Re-testing nulls on a subset is a forking-paths risk: slice enough and something will cross a threshold by chance. Guardrails to write into the spec addendum before any result is seen:

- Exactly ONE pre-specified slice (strict 5v5). No further strength slices regardless of results.
- Same pre-registered statistics as P6 (weighted Δr, paired bootstrap, 90% CI); same frozen-params-before-real-cases ordering.
- Decision rule stated in advance: "5v5 reveals signal" requires the CI excluding zero AND a point estimate materially above the pooled estimate (not a noise-crossing at the boundary), with the second-look multiplicity stated plainly in the report (every re-tested hypothesis gets a doubled false-positive budget).
- A 5v5 null is a strengthened null — the finding would then hold in both the pooled and the cleanest slice — and should be reported as such, not as a failure of the re-check.

## Cost estimate

No new data. One extract-layer change + rebuild (~hours of compute), then the existing parameterized stacks re-run. Roughly a 4–5 task plan, smaller than P6.
