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

2026-07-15 era-split diagnostic (fit setup from `v2/goalies/rebound_diag.py`, era-split results and write-up in `.superpowers/sdd/probe-rebound-era.md`): 2021–22 pooled is positive under every candidate rebound definition tested. 2023–25 pooled is negative under every definition and every timing window up to 5 seconds (e.g. CORSI≤5s −0.14, sog_only≤5s −0.15), and widening the window never flips the sign back positive. The `dt_prev` mass table shows no rightward timing shift post-2023 either — if anything, era B has *more* rapid same-team shot-sequence mass at every threshold than era A, not less. This rules out the hypothesis that the sign flip is the same timestamp-lag issue that forced `FREEZE_WINDOW_S` from 2 to 5 seconds; widening the rebound window does not fix it.

Note: `v2/goalies/rebound_diag.py` as committed only runs the three pooled variants (all-seasons, not era-split); it provides the fit setup those variants share, but does not itself reproduce the era-split tables above — those came from an uncommitted probe that reused its fit setup. See `.superpowers/sdd/probe-rebound-era.md` for the era-split methodology and full results.

Status: `features.py`'s `is_rebound` definition is unchanged (2026-07-14 pooled diagnostic found no redefinition with a positive coefficient across all seasons; see `v2/goalies/rebound_diag.py`). Open research question for P6: why do post-2023 rebounds convert *below* feature-conditional expectation? Candidate explanation: a tracking-era event-coding or context change (e.g. more low-quality scramble attempts coded as on-net, or a shift in `froze`/`rebound_generated` behavior) rather than a fixable definitional or timing bug.

## perf_z / gsax comparisons across difficulty bands are inflated by an xga sort artifact

`perf_z` and `difficulty_pct` (Game Difficulty Index) correlate +0.18 (all games) / +0.23 (toi_s≥3000 subset), monotone across difficulty quintiles. This was investigated and ratified (2026-07-15) as a sort-on-own-prediction artifact, not a difficulty-adjustment defect — see `.superpowers/sdd/probe-xg-calibration.md` and section 3 of `data/generated/goalies/p4p5_report.txt` (`v2/goalies/report_p4p5.py`).

Mechanism: `xga` is a noisy per-game sum over ~30–56 shots. Ranking games on that same noisy `xga` (via `xg_per60`) selects disproportionately for positive-error games into the high-difficulty bands and negative-error games into the low bands, and `gsax_game = xga − ga` mechanically inherits that same error. Any imperfect per-shot model produces this; it does not require a real shot-level calibration defect (shot-level reliability is near-diagonal, ~7% relative deviation at the extreme decile and non-monotone) or a goalie-quality confound (the correlation lives almost entirely within a goalie's own game log, not between goalies of differing quality).

**Usage rule:** `perf_z`/`gsax` comparisons *across* difficulty bands are inflated by shared `xga` noise and should not be treated as difficulty-independent. Same-band comparisons (compare a goalie's `perf_z` only against same-decile peers) and season-aggregate comparisons are sound. Do not "correct" this via a GA~xGA recalibration curve — it would curve-fit the artifact itself and compress real within-goalie GSAx variance, which is exactly the quantity P3's repeatability analysis relies on.

## 2021-22 HTML shift reports are source-defective for 7 games (5 have no timeline)

Backfilling 2021-22 timelines yields **1307 of 1312**. Five games fail `validate_toi` (`v2/timelines/generate_timeline.py:448`) and no CSV is written: `2021020326`, `2021020416`, `2021020427`, `2021020452`, `2021021189`.

The defect is in NHL's source data, not our pipeline. The validator compares our reconstructed timeline against the shift file's own printed `gameTotals`; our timeline reproduces the listed shift rows exactly, and the reports contradict themselves — shift *counts* agree while summed row durations do not match the printed TOI. Re-fetching `TV020326.HTM` from nhl.com returns byte-identical data, so **re-scraping cannot fix this**. Do not spend a cycle on it.

Scope, measured across all five seasons (13,120 shift files, three comparisons):

| Season | rows vs HTML totals | rows vs API boxscore | HTML totals vs API |
|---|---|---|---|
| 2021-22 | 7 games | 7 games | 0 |
| 2022-23 | 0 | 1 game (1s) | 1 game (1s) |
| 2023-24 | 0 | 0 | 0 |
| 2024-25 | 0 | 0 | 0 |
| 2025-26 | 0 | 0 | 0 |

The HTML printed totals and the API boxscore agree on every player in every game except one second in one 2022-23 game, so the defect lives purely in the shift rows.

**Only 5 of the 7 defective games fail validation, and the direction of the error decides which.** Where rows *exceed* totals (`2021020014`, 2567s on one player; `2021021028`, 227s) the timeline correctly collapses duplicated/overlapping seconds and the game passes. Validation success is therefore not evidence that the source was clean.

Three of the five failures cluster: Gila River Arena on 2021-12-10, 12-11 and 12-15, each with exactly 7s of aggregate drift (±1s across 14–18 players), bracketed by clean ARI home games on 12-03 and 2022-01-04 — 3 of Arizona's 41 home games. The other two are isolated one-offs.

Publicly corroborated by [Puck Over the Glass, "A Brief History of NHL Play-by-Play Data"](https://puckovertheglass.substack.com/p/a-brief-history-of-nhl-play-by-play) (Nov 2025), which runs the same check and attributes the residue to the NHL's 2019-20 rollout of automated player tracking for shift reports, reporting zero discrepancies "in both of the last two full seasons" — matching our 7 / 1 / 0 / 0 exactly. `nhlerrata.com/systemic/htmlreports` catalogs HTML report errors but not this one, and `hockey_scraper` does not check for it at all (`broken_shifts_games` fires only on an empty scrape; `html_shifts.py` performs no TOI reconciliation).

**Decision (2026-08-11): accept the gap.** The five games have no timeline, so goalie-games in them carry `NaN` 5v5 TOI — distinct from the `0` written for a goalie who played but saw no 5v5. That affects 10 of 2818 2021 goalie-games (0.35%) across 8 goalies. One goalie, Keith Kinkaid (`8476234`), played exactly one 2021 game and it is `2021020452`, so his entire 2021 5v5 season is NULL; he falls below the 1200s eligibility gate regardless. NaN is the honest representation of ice time NHL does not have, and no tolerance was added to the validator.
