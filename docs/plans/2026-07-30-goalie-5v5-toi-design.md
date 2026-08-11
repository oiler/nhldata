# Cut-Aware Goalie TOI — Design

**Date:** 2026-07-30
**Status:** Spec, approved design pending oiler review
**Supersedes:** `docs/plans/2026-07-21-goalie-5v5-parallel-design.md` §2 "TOI wrinkle" and its non-goal "No goalie 5v5 TOI computation". Everything else in that design stands.

## Problem

Goalie TOI is all-situations on every row of `goalie_seasons`, including the `5v5` one. `build_goalies_db.py:109` reads `goalie_games_<season>.csv` outside the situation branch, and `game_difficulty.py:67` does the same with an explicit comment (`# TOI: shared, all-situations`). `cut.py`'s module docstring states the rule: "Shared inputs that are not shot-derived (goalie_games TOI, wp_table) always come from the parent GEN dir regardless of cut."

Every per-60 in the 5v5 cut is therefore a 5v5 numerator over an all-situations denominator: `xg_per60`, the `difficulty_pct` that ranks it, `gsax_per60`, and the team-level `mean_xg_faced_per60` and `crossice_per60`.

Measured against true 5v5 TOI for 2025 (66 goalies, 20+ GP), this understates 5v5 rates by a **median 23.6%**, range **19.1%–29.4%**. The 5v5 share of a goalie's ice time runs **median 0.809, range 0.773–0.840**.

The spread is the reason this matters. The 2026-07-21 design accepted the mixed base on the grounds that per-60-of-total-TOI "is a consistent exposure measure across games and preserves the difficulty percentile's workload semantics without inventing a 5v5-TOI denominator we don't have." The first half of that does not hold across goalies: because the 5v5 share varies by seven percentage points between the lightest and heaviest special-teams workloads, the exposure denominator is not consistent, and the distortion perturbs rank order rather than applying a uniform rescale. The second half was simply true at the time and is no longer — see below.

The consequence for display is that GSAx/60 cannot be shown on the 5v5 cut at all (it is currently hidden there, per `metrics.gsax_per60()`), xGA/60 cannot be offered per goalie, and two team-page rates carry a `(per 60 total TOI)` disclaimer.

## Goal

Give the 5v5 cut its own TOI denominator, derived from the per-second timelines, and make every 5v5 rate in the pipeline and the browser correct on that basis.

Success means: GSAx/60 and xGA/60 both display in both cuts; the team page carries no denominator disclaimer; and the shot-layer research outputs are provably unchanged.

## Non-goals

- No change to any all-situations output. The `all` cut keeps reading boxscore TOI and must produce byte-identical results.
- No change to the shot layer. GSAx, `gsax_per100`, freeze metrics, `perf_z`, leverage value and `goalie_terms` never touch TOI and must not move.
- No skater-side changes.
- No new strength slices.

## Why this is now possible

The 2026-07-21 non-goal rested on a timeline join being out of scope. Three facts make it in scope:

1. **The data is already there.** `data/<season>/generated/timelines/csv/*.csv` carries `situationCode` alongside `awayGoalie` and `homeGoalie` on every second. This is the same source and the same method `compute_competition.py:67-75` already uses for skater TOI — with one difference: that code filters on `SCORED_SITUATIONS = {"1551", "0651", "1560"}`, which includes the two goalie-pulled codes. `toi_5v5.py` filters `1551` only; copying the skater constant would credit the remaining goalie during empty-net time.
2. **The 2021–22 gap is closable.** Those seasons have complete raw inputs (1312 plays, boxscores, meta, and HTML-scraped shift files each) but no generated timelines. `v2/timelines/generate_timeline.py` produces them: verified on game `2021020001` (3600 seconds, 38 players validated) and on a 20-game batch (20 succeeded, 0 failed, 2 seconds). Full 2021+2022 backfill extrapolates to roughly 4 minutes.
3. **Coverage is complete where it has been measured.** All 2765 of 2765 2025 goalie-games in the 5v5 cut matched a timeline; all 98 of 98 goalies resolved a 5v5 TOI.

## Architecture

One new producer and one new selector. Everything downstream becomes cut-agnostic and mostly needs no edit.

```
data/<season>/generated/timelines/csv/*.csv
        │  situationCode == "1551"; credit awayGoalie and homeGoalie
        ▼
v2/goalies/toi_5v5.py  ──►  GEN/5v5/goalie_toi_<season>.csv
                             (season, game_id, goalie_id, toi_5v5_s)

cut.load_toi(season, situation)
   all → GEN/goalie_games_<season>.csv, unchanged
   5v5 → the same frame with toi_s overwritten from the 5v5 file
        │
        ├──► game_difficulty.py   xg_per60, difficulty_pct
        ├──► game_ledger.py       gsax_per60           (inherits via merge; no edit)
        ├──► environment.py       mean_xg_faced_per60, crossice_per60 (inherits; no edit)
        └──► build_goalies_db.py  goalie_seasons.toi_s
```

`load_toi` returns the entire `goalie_games` frame with only `toi_s` replaced, never a bare TOI series. Consumers also need `team_abbrev`, `game_date`, `opp_abbrev`, `is_home` and `starter` from that frame, and preserving them is what allows `game_ledger.py` and `environment.py` to require no changes at all — both read `toi_s` downstream of `game_difficulty.py`.

`toi_5v5.py` writes an artifact rather than being called inline. Two modules call `load_toi` directly and two further stages (`game_ledger.py:51`, `environment.py:72`) consume the result through `game_difficulty.csv`; computing it inline would walk 6560 timeline files once per consumer, duplicate the parsing in the places most likely to drift, and leave it untestable as a unit.

## Components

| File | Change |
|---|---|
| `v2/goalies/toi_5v5.py` | New. Walk timelines, count `1551` seconds per goalie, write the per-season CSV. |
| `v2/goalies/cut.py` | Add `load_toi(season, situation)`. Rewrite the docstring line asserting TOI is cut-invariant — that is the rule being reversed and it should be visible in the diff. |
| `v2/goalies/game_difficulty.py:67` | `toi = load_toi(season, situation)`, replacing the direct read and its `# TOI: shared, all-situations` comment. |
| `v2/browser/build_goalies_db.py:109` | Same swap, so `goalie_seasons.toi_s` is per-cut. Also rewrite the `:108` comment (`# gp/toi/teams are all-situations by design (spec §2) — shared source`): "toi" becomes false under this design, and "spec §2" points at the superseded 2026-07-21 doc. |
| `v2/browser/metrics.py` | Remove `gsax_per60`'s situation guard and the docstring paragraph explaining it. Add `xga_per60`. |
| `v2/browser/pages/goalies.py` | GSAx/60 and xGA/60 in both cuts; remove the conditional column insert; cut-aware TOI/GP label and value; rewrite `_CUT_NOTE`. |
| `v2/browser/pages/goalie.py:55,123` | Both `(all sit)` TOI labels become false once `toi_s` is cut-aware. Relabel to plain `TOI/GP` and `TOI`, which are now correct in both cuts. |
| `v2/browser/pages/team.py:86` | Delete `per60_suffix`. |
| `v2/browser/app.py:205` | The situation-filter blurb states "GP and TOI always count all situations." Half of that stops being true: GP still does, TOI no longer does. Reword to say GP counts appearances while TOI follows the selected cut. |
| `v2/browser/app.py` glossary | Revise the GSAx/60 entry to drop the all-situations-only caveat; add xGA/60. Leave the `iTOI%` entry at `:186` alone — its "(all situations)" wording describes a skater metric and is unaffected. |

## Decisions

**Eligibility gate stays at 1200 seconds, applied to the cut's own TOI.** `add_difficulty_pct(min_toi_s=1200)` exists to keep short relief appearances out of the difficulty ranking, so it should measure the quantity being ranked. At 5v5 this excludes 46 of 2765 2025 goalie-games (1.6%) that the current gate admits. Rescaling the threshold to 978 seconds would cost 5 instead, but 978 is chosen to preserve a population rather than to mean anything, and a gate whose value drifts with the cut is harder to reason about than one that always means twenty minutes of the play being measured.

**`gp` stays all-situations.** A goalie who dressed and played is one appearance. 5v5 TOI/GP therefore reads as 5v5 minutes per appearance.

**TOI/GP displays 5v5 TOI under the 5v5 cut**, replacing today's all-situations figure and its `(all sit)` label. This changes what the column means between cuts, which is the cost of the column being correct in both.

**2021–22 timelines get backfilled** as part of this work rather than shipping two blank seasons. Those seasons appear on `/goalie/<id>` season history even though `/goalies` currently renders 2025 only (`app.py:7`, `SEASONS = ["2025"]`).

## Data flow and rebuild order

1. Backfill timelines: `generate_timeline.py 1 1312 2021`, then the same for 2022.
2. `toi_5v5.py` for all five seasons.
3. `game_difficulty.py --situation 5v5`, then `game_ledger.py --situation 5v5`, then `environment.py --situation 5v5`.
4. `build_goalies_db.py`.
5. `tools/sync-runtime-data.sh`, then deploy.

The `all` cut is not re-run. It reads the same inputs it always has, and its outputs must not change.

## Error handling

Two failure modes must stay distinguishable, because they mean opposite things and one is a bug while the other is a fact about the game.

**No timeline for a goalie-game** yields `toi_5v5_s` of NaN, and every rate derived from it is NaN. This is missing data. `toi_5v5.py` and `load_toi` each report the count.

**A goalie who played but saw no 5v5 ice** yields `toi_5v5_s` of 0. This is a real zero, not a gap, and is reported separately from the NaN count. In the browser layer, rates go NaN through the `.where(toi > 0)` idiom already used by `events_per60`, `corsi_per60` and `gsax_per60`. The pipeline divides unguarded — `game_difficulty.py:49` and `game_ledger.py:54` — which is safe only because those stages carry rows solely for goalie-games with at least one shot in the cut, and a 1551-coded shot implies at least one 1551 timeline second for the goalie who faced it. That implication ties the shots CSV to the reconstructed timeline, two independently derived artifacts, so it is asserted by an invariant test rather than assumed — see Testing.

`toi_5v5.py` raises rather than writing an empty CSV when a season's timeline directory is empty. That is the pre-backfill state of 2021 and 2022, and a silently empty artifact would blank a whole season's rates downstream while every stage still reported success. This mirrors `burst_data.load_bursts()`, which fails loudly in production for the same reason.

`game_rows()` in `game_difficulty.py` already prints a dropped-row note when shots have no matching TOI row. That note stays and becomes the coverage signal for the 5v5 join.

## Testing

`v2/goalies/tests/test_toi_5v5.py`, new, against synthetic timeline rows:

- counts only seconds whose `situationCode` is `1551`
- credits both `awayGoalie` and `homeGoalie` on the same second
- tolerates an empty goalie cell, which is a pulled goalie, without crediting anyone
- returns 0, not a missing row, for a game played with no 5v5 seconds
- aggregates to the `(season, game_id, goalie_id)` grain

`v2/goalies/tests/test_cut.py`, extended: `load_toi` selects the right source per situation, preserves the non-TOI columns of `goalie_games`, and leaves the `all` cut's frame identical to a direct read.

`v2/browser/test_rate_metrics.py`: the three existing `gsax_per60` tests change, since the situation guard is removed and the `5v5` case no longer returns all-NaN. Add `xga_per60` coverage including the zero-TOI case.

Invariant tests: for every goalie-season, 5v5 `toi_s` is strictly less than all-situations `toi_s`; and no goalie-game with `toi_5v5_s` of 0 carries any 5v5 shots — this is what licenses the pipeline's unguarded divisions (see Error handling).

## Acceptance

**The shot layer must not move.** `gsax_<season>.csv`, `goalie_terms_<season>.csv` and the freeze outputs are TOI-independent, so a before/after diff must be byte-identical for all five seasons in both cuts. Any drift means the change leaked past its boundary. This is also what protects the conclusions in `docs/plans/2026-07-21-goalie-5v5-recheck-report.md`, whose headline figures — stopping repeatability 0.166, freeze 0.639, the portability null, the freeze-value pricing — all rest on shot-layer terms and GSAx rather than on any rate.

The rest:

- 5v5 share of TOI lands at median ≈ 0.81, range ≈ 0.77–0.84, matching the 2025 measurement.
- Timeline coverage is complete for all five seasons, matching the 2765 of 2765 already observed for 2025.
- `difficulty_pct` eligibility at 5v5 drops by roughly 46 goalie-games per season against the current gate.
- No `(per 60 total TOI)` or `(all sit)` string remains in `v2/browser/pages/` — those labels exist only to disclose the mixed base this change removes. `app.py:186`'s "all situations" wording is the skater `iTOI%` glossary entry and stays.
- GSAx/60 and xGA/60 both render on `/goalies` in both cuts. `/goalie/<id>` shows 5v5 TOI under the 5v5 cut for all five seasons, unlabelled because it no longer needs a caveat.
- Full suite green.
