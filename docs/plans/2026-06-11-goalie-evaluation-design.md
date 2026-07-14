# Goalie Evaluation — Phase 1 Design (A + C)

**Date:** 2026-06-11
**Status:** Approved skeleton; spec for review
**Owner:** oiler
**Prior art doc:** `docs/ideas/2026-05-10-shooters.md` (shooters research arc; the pre-shot-context machinery and within-player methodology built there are direct inputs here)

## 1. Goal

Build a better way to evaluate NHL goaltending from public data. Working theory (oiler): goaltending performance is heavily environment-dependent — like NFL running backs, whose outcomes are dominated by blocking, scheme, and game state. The metric must separate what the goalie controls from what his team, coach, schedule, and shot-quality environment hand him.

Two layers, by explicit decision:

- **Talent layer** — how good is this goalie, environment stripped. Stable, portable, honest about uncertainty.
- **Performance layer** — how much did his play contribute in context. Leverage-weighted (a save in a tied third period counts more than up 5-0). Descriptive by design: clutch skill has no published repeatability, so this layer values what happened and never claims a talent.

## 2. Validation standard (decided)

- **Primary: portability.** The talent metric must predict a goalie's performance after he changes teams better than a GSAx baseline. This is the only test that directly measures environment-stripping. Target sample: ~80–100 switch cases across the data horizon.
- **Secondary: repeatability.** Season-pair self-correlation vs. GSAx — computed **only after rink-bias adjustment**, because arena scorer bias persists year-to-year and inflates the apparent repeatability of unadjusted metrics (a documented trap).

## 3. Data horizon and raw-first principle (decided)

- **Five seasons:** 2021-22 through 2025-26. Local holdings: 2023-24, 2024-25, 2025-26 complete (plays, boxscores, meta, players; shifts also present). To acquire: **2021-22 and 2022-23** (plays, boxscores, meta, players — no shifts).
- **Raw-first:** raw API responses stored verbatim under `data/<season>/{plays,boxscores,meta,players}/`, never mutated. Every derived table is rebuilt from raw by a script. We can always return to the raw data with new questions.

## 4. Approaches considered

- **A — Mini-Magnus (chosen):** layered shot-difficulty model with per-goalie regularized terms estimated inside the model. Chosen over residual-style GSAx because residual-vs-ML metrics carry finite-sample bias by construction (arXiv 2509.20083) and because layering separates skills that are real but uncorrelated (miss-forcing vs. stopping, r ≈ −0.01 per McCurdy).
- **B — Personnel-adjusted regression (deferred):** adds on-ice defender terms; the structural answer to "defended vs. alone." Deferred because it requires shift data for all seasons (flaky API + HTML fallback) and because published tandem work bounds team-defense effects on save% at roughly ±0.006 — possibly less value than cost. Revisit if A+C residuals show team-level structure. Cheap stopgap available first: team F/D shooter-mix adjustment (repeatable team skill, r = 0.72–0.80, worth ±0.5–1% of save%).
- **C — Natural experiments (chosen, dual role):** tandem comparisons (same team/defense, schedule-adjusted) and team-switch designs. Serves as secondary identification for the talent layer and as the validation harness. Environment-stripping by construction rather than by model.

## 5. Research anchors

Grounding facts the design leans on (full citations in §11):

| Fact | Value | Source |
|---|---|---|
| GSAx year-over-year repeatability | r ≈ 0.12 | JFresh |
| Freeze rate repeatability (2s stoppage window) | r ≈ 0.58 (most repeatable goalie skill in pbp) | Cane 2015 |
| Rebound-control repeatability | r ≈ 0.24–0.26 | Cane 2015 |
| Miss-forcing vs. goal-prevention correlation | r ≈ −0.01 (separate skills) | McCurdy xG8 |
| Goalie vs. shooter information per shot | ~6× less about the goalie | McCurdy xG7 |
| Rink bias magnitude | Lundqvist career GSAx 268.5 unadjusted vs ~91–107 adjusted | Skytte |
| Team-defense effect on save% (tandem bound) | ≈ ±0.006 | JLikens |
| Back-to-back cost | ≈ .011 save% | Tulsky |
| Within-game workload effect on save% | none (R² = 0.016) | Hohl |
| Clutch / hot-hand | no effect found; not repeatable | Ding et al. |
| Percentile-vs-mean scoring reliability gain (NFL RB analogue) | 0.17 → 0.40 split-half | Lopez |
| Cross-ice quick-play conversion (our data, forwards 5v5) | ~14.7% vs ~9% baseline | shooters phase |

Selection-pressure caveat (McCurdy): coaches bench slumping goalies, so observed samples are censored; part of apparent goalie randomness may be this artifact. Handled via shrinkage, priors, and reporting uncertainty rather than point rankings.

## 6. Components and build order

Code lives in `v2/goalies/` (keeps the `python -m pytest v2/` convention). Derived tables under `data/generated/goalies/`. Each stage lands with synthetic-data tests before the next begins.

### P0 — Data acquisition
Extend existing backfill tooling (see memory: season-backfill procedure) to pull 2021-22 and 2022-23: plays, boxscores, meta, players. Verify counts per season (~1,312 games each). Game dates for back-to-back computation come from meta.

### P1 — Goalie-shot extraction
New extractor (pattern: `tools/offwing_splits.py::extract_shots`). Scope: **all strength states** (strength is a covariate; PK matters for goalies; 5v5-only cuts remain possible from raw). Per unblocked shot: goalie ID (`goalieInNetId`), shooter, coordinates (attack-normalized), shot type, strength/situationCode, score state, period/time, prior-event context (`dt_prev`, `prev_type`, `prev_same_team`, `prev_x/y_norm`), and two derived outcomes:
- **freeze**: next event after the save is a stoppage within 5 s (era-robust widening of Cane's 2 s window, changed at implementation: NHL event timestamps shifted ~1–2 s later starting 2023 with the tracking era, so a fixed 2 s window reads ~0.29 freeze in 2021–22 but ~0.23 in 2023+ despite the next-event-is-stoppage share being stable ~0.36–0.38 across eras. A 5 s window captures ~86% of save-adjacent stoppages on both sides of the boundary and yields a flat ~0.31 freeze rate across all five seasons. Ratified by oiler at the P0–P2 gate, 2026-07-02.)
- **rebound_generated**: same-team shot attempt within 3 s of the save
Empty-net and penalty-shot/shootout shots excluded. All window rules covered by synthetic-game tests.

### P2 — Rink-bias adjustment
Per-arena location calibration: compare each arena's recorded shot-location distributions (home games) against the same teams' road baselines; derive per-arena correction (distance and/or coordinate offsets). Standalone module with tests; all downstream models consume adjusted geometry. Every repeatability claim in validation depends on this stage.

### P3 — Difficulty model + goalie terms (core of A)
Layered regularized logistic models on the shot stream:
1. on-net (vs. missed)
2. frozen (vs. in-play), given on-net save
3. goal (vs. save), given on-net
4. rebound-generation, given save
Features: adjusted location, shot type, strength state, score state, rush/rebound/cross-ice-quick proxies, home/away. Per-goalie terms in layers 2–4 (and 1, for miss-forcing), heavily shrunk toward league average with season-chained priors (McCurdy pattern: goalies need far more evidence than shooters to move). Outputs: per-goalie, per-layer skill estimates with uncertainty; a goalie-blind version of the same model doubles as the GSAx baseline for validation.
Solver: pure-numpy penalized IRLS with per-group penalty weights (generalized ridge). Decided here rather than at plan time because the model requires differential penalties — heavy on goalie terms, light on structural terms — which sklearn's uniform-L2 LogisticRegression cannot express. Validate the solver against a reference implementation on uniform-penalty test cases.

### P4 — Environment profile ("o-line grade")
Per team-season, from the same shot stream: cross-ice-quick rate allowed, tip/deflection share, F/D shooter mix, point-shot share, rebound exposure, per-goalie back-to-back burden. First-class deliverable — the defense/coaching legs of the theory, measured directly. Also feeds tandem schedule adjustment.

### P5 — Percentile scoring + performance layer
- **Percentile scoring (talent):** each shot outcome scored against its conditional outcome distribution from P3 (the Lopez transform); per-goalie aggregation. Rationale: mean-based over-expected metrics are hostage to the shot-quality mix faced; percentile scoring addresses the low-quality/low-quantity environment complaint directly.
- **Performance layer:** empirical win-probability table from our own five seasons — P(win | score differential, period, time remaining) — leverage weight per shot, leverage-weighted save/goal ledger per goalie-game. Explicitly descriptive.

### P6 — Validation harness (the C in A+C)
- **Switch registry:** goalie-seasons with team changes and a workload minimum of ≥1,000 unblocked shots faced (~20 starts) on each side of the switch — tunable, but this is the default (~80–100 cases expected).
- **Portability test:** talent estimate (from pre-switch data only) vs. GSAx baseline predicting post-switch performance. Primary criterion.
- **Repeatability suite:** season-pair correlations per metric and per component (stopping, freeze, rebound control), post-rink-adjustment only. Secondary criterion. Expected anchors: freeze ≈ 0.58, stopping ≈ 0.12 — if our stopping estimate repeats materially above 0.12 without beating portability, suspect leaked environment.
- **Tandem comparisons:** same-team goalie pairs, adjusted for back-to-back burden and opponent strength; bounds team effects and sanity-checks the model's environment stripping.

## 6b. P3 gate outcomes and P4–P6 revisions (addendum, 2026-07-14; approved by oiler)

P3 gate (accepted): freeze is a real, artifact-tested individual skill (year-pair r 0.60–0.80, split-half 0.712; travels with team-switchers, absent between teammates). Stopping is noise-dominated at single-season scale (r ≈ 0.1, ≥ GSAx in all four season pairs but within sampling error). Rebound control likely modest-real (r 0.26–0.36). Direction decision: **carry both** stopping (chained multi-season terms) and puck-handling (freeze/rebound) into the P6 portability test; do not pre-pick the talent layer's lead metric.

Revisions to the remaining phases:

- **P5 becomes "per-game difficulty and performance."** New deliverables: goalie TOI extraction from boxscores (needed for any /60 rate); a **Game Difficulty Index** — each goalie-game's workload (xG-faced per 60, danger mix, rush/rebound exposure) scored as a percentile against the league distribution of goalie-games; and a per-game ledger combining raw results, difficulty-adjusted performance (per-shot conditional outcomes aggregated to a game z-score), and leverage-weighted value from an empirical win-probability table. Rationale: games differ materially in how hard they are on goalies, and season aggregates hide it (oiler's workload thesis, 2026-07-14).
- **No idle-gap/"cold goalie" term.** Probed 2026-07-14 on all five seasons (562k shots): time-since-last-shot-faced has no effect on shot outcomes after standard difficulty controls (all gap-bin coefficients |z| < 0.8, wrong-signed; high-danger slice non-monotone). Third null in this family alongside Hohl's volume null and the playoff hot-hand null. Burst danger is fully carried by shot features (proximity, rebounds, rushes).
- **Mandatory before percentile scoring:** resolve the goal-layer `is_rebound` sign anomaly (coefficient −0.29, opposite literature; suspected dilution from blocked-shot prior events and coordinate-bearing-only dt), then refit terms/GSAx.
- **P4 additions:** per-arena freeze-timing offsets (small residual scorer effect, 2023-24); team-level aggregation of game difficulty (the "o-line grade" made concrete); back-to-back burden must sort by game_date, not game ID (2021-22 reschedules).
- **P6 candidates to test for portability vs GSAx:** chained goal-layer terms, freeze terms, rebound-control terms, and P5's difficulty-adjusted per-game aggregates.

## 7. Phase gates

- **After P3:** do goalie terms separate from noise at all (posterior spread vs. shrinkage)? If not, that is itself a publishable finding — and the RB literature says it is a live possibility.
- **After P6:** does anything beat GSAx on portability? Honest prior from the literature: possibly only marginally. A null result with tight error bars is a success criterion, not a failure.

## 8. Testing

Project norms apply: test computations, not pipelines; synthetic DataFrames/games; every window rule, adjustment formula, solver, and transform gets targeted tests; `python -m pytest v2/ -v` green before any stage is called done.

## 9. Storage layout

```
data/
├── 2021/ 2022/            # new raw seasons (plays, boxscores, meta, players)
└── generated/goalies/     # derived, cross-season, all rebuildable from raw
    ├── shots_<season>.csv         # P1 output
    ├── arena_adjustments.csv      # P2
    ├── goalie_terms_<season>.csv  # P3
    ├── team_environment.csv       # P4
    ├── leverage_ledger.csv        # P5
    └── validation/                # P6 outputs
v2/goalies/                # extraction, models, validation code + tests
```

## 10. Risks and honest expectations

- **Signal may be small.** The literature's central finding is that goalie residual metrics are noise-dominated at single-season scale. Multi-season priors and component decomposition are the mitigations; uncertainty is always reported.
- **Selection pressure** censors bad stretches (benchings); estimates are conditional on usage.
- **Rink adjustment is load-bearing** for both validation criteria; it lands early (P2) for that reason.
- **Pre-shot context is proxied, not observed** (no pass events in pbp — established in the shooters phase). Screens/one-timers remain invisible; the environment profile measures exposure proxies instead.
- oiler's stated prior: "not convinced this will produce results, but excited to see where it leads." The design treats a well-measured null as a valid outcome.

## 11. References

- McCurdy, Magnus 8 xG (goalie layers, penalties, selection pressure): https://hockeyviz.com/txt/xg8
- McCurdy, Magnus 7 (6× information asymmetry): https://hockeyviz.com/txt/xg7
- McCurdy, sGA (skater-swap counterfactual, 2017): https://hockeyviz.com/txt/sGA
- Cane, rebound control & freeze rates (2015): https://hockey-graphs.com/2015/11/10/how-can-we-measure-a-goalies-rebound-control-examining-pekka-rinne-and-james-reimer/
- JFresh, goaltending randomness (r ≈ 0.12): https://jfresh.substack.com/p/why-goaltending-is-basically-random
- JFresh, Vasilevskiy case study (rink bias, rebound adjustment): https://jfresh.substack.com/p/do-analytics-say-that-andrei-vasilevskiy
- Skytte, talent distribution & rink bias: https://hockey-statistics.com/2021/09/03/talent-distribution-goaltending-part-iv/
- JLikens, team effects on EV save% (tandem method): http://objectivenhl.blogspot.com/2011/05/team-effects-and-even-strength-save.html
- Cane, F/D shot-mix adjustment: https://puckplusplus.com/2014/05/29/adjusting-save-percentage-for-team-effects/
- Hohl, shots-against vs save%: https://hockey-graphs.com/2014/08/28/save-percentage-vs-the-experts-do-shots-against-inflate-a-goaltenders-save-percentage/
- Tulsky/Lukan, goalie workload & back-to-backs: https://www.nhl.com/kraken/news/core-concepts-examining-goalie-workload-329507592
- Ding, Cribben, Ingolfsson & Tran, playoff hot-hand (null): https://arxiv.org/abs/2102.09689
- Expected Buffalo, GSAx vs team defense: https://www.expectedbuffalo.com/chaos-unmasked-part-1-an-exhaustive-search-for-trends-in-nhl-goalie-analysis/
- Schuckers, DIGR (defense-independent goaltending): https://www.statsportsconsulting.com/wp-content/uploads/Schuckers_DIGR_MIT_2011.pdf
- Noel, skill-adjusted xG (2025): https://arxiv.org/abs/2511.07703
- Residual-metric bias critique (2025): https://arxiv.org/abs/2509.20083
- Lopez, RB evaluation via conditional distributions: https://statsbylopez.netlify.app/post/assessing-running-back-performance-using-distributions/
- NFL Next Gen Stats, RYOE: https://www.nfl.com/news/next-gen-stats-intro-to-expected-rushing-yards
- nfelo, over-expected metric stability: https://www.nfeloapp.com/analysis/over-expected-explained-what-are-cpoe-ryoe-and-yacoe/
- Yurko, Ventura & Horowitz, nflWAR (mixed-effects, no tracking): https://arxiv.org/abs/1802.00998
