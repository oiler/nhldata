# Data Limitations & Snapshot Discipline

## Player height/weight is not season-accurate for historical backfills

PPI (`weight_lbs / height_in`) and the competition "heaviness" columns depend on each
player's listed height/weight. The source matters:

- **NHL Edge** (`/v1/edge/skater-detail/{id}/{season}/{type}`) is **season-scoped** — the
  speed/burst data is point-in-time and correct for any season we fetch.
- **Player bio** (`/v1/player/{id}/landing`, used by `v2/players/get_players.py`) returns
  only the player's **current** height/weight — there is no historical bio endpoint.

So when a past season's players are fetched *late* (e.g. 2023-24 built in 2026), their
height/weight are **today's** measurements, not that season's. Listed weight drifts year to
year (e.g. Skinner 206 → 230 → 215 lb across 2021-22 / 2024-25 / current), so historical
PPI/heaviness are approximate.

**Partial recovery exists but wasn't pursued:** the season-scoped roster endpoint
(`/v1/roster/{team}/{season}`) *does* carry point-in-time height/weight, but it's a roster
snapshot covering only ~59% of players who actually appear in a season (call-ups and
mid-season trades are missing). Decision (2026-07): accept approximate historical h/w rather
than build a 59%-coverage recovery path. Historical seasons already backfilled (2023-24,
and partly 2024-25) carry this caveat.

## Snapshot discipline (going forward)

The fix for *future* seasons is timing, not new data sources: capture bio while it is still
current, then freeze it.

- Each season's raw player files live in `data/<season>/players/`. Fetched during the active
  season, they are an accurate point-in-time snapshot for everyone who played.
- The orchestrator already keeps the active season current: daily `fetch_players` +
  `backfill_players` (after `compute_competition`) catch new IDs and call-ups.
- **Freeze on completion.** A completed season's players dir carries a `.snapshot_frozen`
  marker. `get_players` full/targeted mode refuses to overwrite a frozen season (graceful
  skip). `backfill` stays allowed (additive). Override with `NHL_FORCE_REFETCH=1`.
- **At season rollover:** bump `NHL_SEASON` to the new season, let the orchestrator populate
  it, and drop a `.snapshot_frozen` marker into the prior season once it's complete.

Frozen as of 2026-07: 2023-24, 2024-25, 2025-26.

## Goal-layer is_rebound coefficient is era-dependent

The goal-layer logistic model's `is_rebound` coefficient (`structure_coefs_<season>.csv`) flips sign at the 2023 tracking-era transition: +0.38 (2021), +0.10 (2022), −0.29 (2023), −0.33 (2024), −0.34 (2025). Per-season fits already carry these era-appropriate coefficients, so downstream goalie-evaluation outputs (gsax, perf_z, etc.) are internally consistent — this is a note about interpreting the coefficient, not a pipeline bug.

2026-07-15 era-split diagnostic (`v2/goalies/rebound_diag.py`, see `.superpowers/sdd/probe-rebound-era.md`): 2021–22 pooled is positive under every candidate rebound definition tested. 2023–25 pooled is negative under every definition and every timing window up to 5 seconds (e.g. CORSI≤5s −0.14, sog_only≤5s −0.15), and widening the window never flips the sign back positive. The `dt_prev` mass table shows no rightward timing shift post-2023 either — if anything, era B has *more* rapid same-team shot-sequence mass at every threshold than era A, not less. This rules out the hypothesis that the sign flip is the same timestamp-lag issue that forced `FREEZE_WINDOW_S` from 2 to 5 seconds; widening the rebound window does not fix it.

Status: `features.py`'s `is_rebound` definition is unchanged (2026-07-14 pooled diagnostic found no redefinition with a positive coefficient across all seasons; see `v2/goalies/rebound_diag.py`). Open research question for P6: why do post-2023 rebounds convert *below* feature-conditional expectation? Candidate explanation: a tracking-era event-coding or context change (e.g. more low-quality scramble attempts coded as on-net, or a shift in `froze`/`rebound_generated` behavior) rather than a fixable definitional or timing bug.

## perf_z / gsax comparisons across difficulty bands are inflated by an xga sort artifact

`perf_z` and `difficulty_pct` (Game Difficulty Index) correlate +0.18 (all games) / +0.23 (toi_s≥3000 subset), monotone across difficulty quintiles. This was investigated and ratified (2026-07-15) as a sort-on-own-prediction artifact, not a difficulty-adjustment defect — see `.superpowers/sdd/probe-xg-calibration.md` and section 3 of `data/generated/goalies/p4p5_report.txt` (`v2/goalies/report_p4p5.py`).

Mechanism: `xga` is a noisy per-game sum over ~30–56 shots. Ranking games on that same noisy `xga` (via `xg_per60`) selects disproportionately for positive-error games into the high-difficulty bands and negative-error games into the low bands, and `gsax_game = xga − ga` mechanically inherits that same error. Any imperfect per-shot model produces this; it does not require a real shot-level calibration defect (shot-level reliability is near-diagonal, ~7% relative deviation at the extreme decile and non-monotone) or a goalie-quality confound (the correlation lives almost entirely within a goalie's own game log, not between goalies of differing quality).

**Usage rule:** `perf_z`/`gsax` comparisons *across* difficulty bands are inflated by shared `xga` noise and should not be treated as difficulty-independent. Same-band comparisons (compare a goalie's `perf_z` only against same-decile peers) and season-aggregate comparisons are sound. Do not "correct" this via a GA~xGA recalibration curve — it would curve-fit the artifact itself and compress real within-goalie GSAx variance, which is exactly the quantity P3's repeatability analysis relies on.
