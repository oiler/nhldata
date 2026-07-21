# Goalie 5v5 re-check — pre-registration addendum

**Date:** 2026-07-21 (written before any 5v5 research output was computed)
**Parent spec:** docs/plans/2026-07-21-goalie-5v5-parallel-design.md §5

## Slice

Exactly one: strict 5v5, situationCode 1551. No further strength slices will be
run or reported regardless of results.

## Items (closed list)

1. Portability gate, 5v5 edition — candidates AND outcome 5v5-only.
2. Component repeatability at 5v5, vs published anchors (freeze ≈ 0.58, stopping ≈ 0.12).
3. Freeze × strength interaction on ALL-SITUATIONS data (decomposition, not a slice).

Rust/idle-gap, hot-hand, and rebound-era stay closed and are not re-tested.

## Statistics

Identical to P6: weighted Δr, paired bootstrap (10,000 resamples, seed 42), 90% CI.
Frozen-params-before-real-cases ordering carries over: K and composite weights are
fit on nonswitch pseudo-cases only, then frozen, before any real case is scored.
Era-probe verdicts are REUSED from the pooled run (tracking-era coding shifts are
dataset-wide, not strength-specific); re-probing the subset would be a second fork.

## Fenwick floor rule (decided from counts alone, before outcomes)

Build the 5v5 registry at floors 600 and 500 and record real-case counts. If the
600-floor 5v5 registry retains fewer than 75% of the pooled registry's real-case
count, run the gate at floor 500; otherwise keep 600. Both counts are reported
either way. The decision uses case counts only — no outcome data is examined
before the floor is frozen in floor_decision.json.

## Decision rule for "5v5 reveals signal"

The 90% CI excludes zero AND the point estimate is materially above the pooled
estimate (not a noise-crossing at the CI boundary). Every re-tested hypothesis
carries a doubled false-positive budget, stated plainly in the report. A 5v5
null is a strengthened null (holds in the pooled data AND the cleanest slice)
and will be reported as such.
