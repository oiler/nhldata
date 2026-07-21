# Goalie 5v5 Parallel Workstream — Design

**Date:** 2026-07-21
**Status:** Spec, approved design pending oiler review
**Supersedes:** nothing — this is additive. All P0–P6 all-situations outputs, research conclusions, and browser views remain in place as the all-situations record.
**Seeds:** `docs/ideas/2026-07-21-goalie-5v5-recheck.md` (approach note; its guardrails are copied into §5 verbatim-in-substance and are binding).

## Goal

Stand up a strict-5v5 (`situationCode == "1551"`) parallel cut of the goalie pipeline alongside the existing all-situations work:

1. **Descriptive parity:** every shipped goalie metric recomputed at strict 5v5, exposed in the browser behind an "All situations / 5v5" dropdown.
2. **Inferential re-checks:** exactly the three pre-registered items from the approach note — portability (5v5 edition), component repeatability (5v5), freeze × strength decomposition. Rust, hot-hand, and rebound-era nulls stay closed; they are not re-tested at 5v5.

## Non-goals

- No modification of existing all-situations outputs, research artifacts, or conclusions. The only shared-file change is one additive column in the shots extract (§1).
- No additional strength slices (no PP-only, no 4v4, no EV-including-4v4). One slice, pre-registered.
- No goalie 5v5 TOI computation (see §2, TOI wrinkle).
- No skater-side changes.

## 1. Extract layer (the one shared touch)

`v2/goalies/extract.py` adds one output column: `situation_code` — the raw 4-character `situationCode` string, captured at `extract.py:50` where it is already in scope, emitted alongside the existing collapsed `strength`. Nothing else in the row changes.

Rebuild `data/generated/goalies/shots_<season>.csv` for all five seasons (2021–2025) via `build_shots.py`. Same rows, one new column — every existing consumer keeps working unchanged. This is option (a) from the approach note.

**5v5 definition:** strict `1551` only, matching the skater-side convention (`FIVE_V_FIVE = {"1551"}`). 4v4 (`1441`) and 3v3 are excluded, consistent with the project-wide decision.

## 2. Parallel 5v5 pipeline run

The downstream stack reads the same shots CSVs; the 5v5 run filters to `situation_code == "1551"` and writes to a mirrored subtree:

```
data/generated/goalies/          # existing all-situations outputs — untouched
data/generated/goalies/5v5/      # new: identical filenames, 5v5 cut
```

Mechanism: each pipeline script that consumes shots gains a `--situation 5v5` CLI flag (default `all`, byte-identical to today) that applies the input filter and redirects the output base dir to the `5v5/` subtree — one mechanism, used consistently across scripts. Scripts in scope: `gsax_baseline.py`, `build_terms.py`, `difficulty.py`, `game_difficulty.py`, `leverage.py`, `game_ledger.py`, `environment.py`, `freeze_value.py`.

**xG refit note:** `features.py` includes `pp`/`sh` strength dummies (`features.py:40-41`). On the strict-5v5 slice these columns are all-zero; the penalized IRLS fit tolerates degenerate columns (coefficients shrink to zero), so the feature builder is not forked. The 5v5 xG model is a genuine refit on 5v5 shots only — per the note's mechanism 1, this is the point: per-goalie terms fit without PK noise.

**TOI wrinkle (explicit, not silently mixed):** per-game goalie TOI comes from game logs and is all-situations; we have no goalie 5v5 TOI without a timeline join, which is out of scope. Consequences:

- Per-shot metrics (GSAx, freeze rate, perf_z, leverage value) are unaffected — they never touch TOI. Per-goalie rates stay per-shot (`gsax_per100`) or per-save (freeze rate).
- Game-level and team-level workload rates (`xg_per60` — the difficulty percentile's basis — plus `gsax_per60` and `crossice_per60`) keep the goalie's all-situations TOI as the **exposure denominator**: 5v5 xG faced per 60 of total ice time is a consistent exposure measure across games and preserves the difficulty percentile's workload semantics without inventing a 5v5-TOI denominator we don't have. Labeled "per 60 (total TOI)" wherever shown in 5v5 mode.
- Where TOI is displayed in 5v5 mode (e.g. season cards), it is labeled "TOI (all situations)" — shown for context, never presented as 5v5 ice time.

**Freeze value at 5v5:** `freeze_value.py` (30-second branch-pricing study) runs on the 5v5 cut so the browser's freeze-value reference line reflects the selected mode. This is descriptive re-estimation for display parity, distinct from the §5 freeze × strength decomposition.

## 3. Browser

### goalies.db schema

`build_goalies_db.py` builds both cuts into `data/generated/browser/goalies.db`, adding a `situation` column (`'all'` / `'5v5'`) to `goalie_seasons`, `goalie_games`, `team_environment`, and `freeze_value`. The db is fully generated — restructuring it is safe; source CSVs and research artifacts are the durable record. All existing browser queries gain `WHERE situation = ?`.

The 5v5 rows apply the same eligibility floors as the all-situations rows (e.g. `MIN_SAVES_FOR_PCT = 500` for freeze percentile) computed within the 5v5 cut — percentiles rank 5v5 rates against 5v5 rates only, never across cuts.

### Dropdown

A shared **All situations / 5v5** dropdown on `/goalies`, `/goalie/<id>`, and the team-page goalie environment section. Selection persists across goalie views using the same `dcc.Store` pattern as the existing home/away filter (`filters.py:71`). Default: **all situations** — today's views are unchanged until the user opts in.

In 5v5 mode:

- All tables/cards re-query with `situation = '5v5'`.
- The freeze-value line uses the 5v5-estimated `per_freeze_xga_delta`.
- TOI displays carry the "(all situations)" label per §2.
- Sample-size honesty: 5v5 removes ~20% of shots; anywhere the all-situations view discloses n (saves, shots faced), the 5v5 view does too.

## 4. Research artifacts layout

5v5 research outputs mirror the same subtree convention: machine outputs under `data/generated/goalies/5v5/validation/` (mirroring the existing `data/generated/goalies/validation/`, where `p6_report.txt` lives), and the human-readable findings in a dated doc `docs/plans/2026-XX-XX-goalie-5v5-recheck-report.md`. All-situations reports are never overwritten.

## 5. Pre-registered inferential scope (binding guardrails)

Written before any 5v5 result is computed, per the approach note:

- **Exactly one slice:** strict `1551`. No further strength slices regardless of what the results show.
- **Same statistics as P6:** weighted Δr, paired bootstrap, 90% CI; frozen-params-before-real-cases ordering carries over unchanged.
- **Decision rule (in advance):** "5v5 reveals signal" requires the CI excluding zero AND a point estimate materially above the pooled estimate — not a noise-crossing at the boundary. Every re-tested hypothesis carries a doubled false-positive budget, stated plainly in the report.
- **A 5v5 null is a strengthened null** — the finding then holds in both the pooled data and the cleanest slice, and is reported as such.
- **Closed items stay closed:** rust/idle-gap, hot-hand family, rebound-era anomaly are not re-tested (mechanisms strength-independent; rebound-era is a coding-era issue).

### The three items

1. **Portability gate, 5v5 edition (highest value).** Candidates AND outcome rebuilt 5v5-only; re-run the existing parameterized harness. Before choosing the fenwick floor, measure the case-list n at 600 vs 500 and report the cost; pick the floor from the n table, then freeze it before looking at outcomes.
2. **Component repeatability, 5v5.** Compare against published anchors (freeze ≈ 0.58, stopping ≈ 0.12), which are themselves mostly 5v5-based — this is the apples-to-apples run and the direct test of mechanism 1 (does stopping repeatability rise when PK noise is removed?).
3. **Freeze value by strength.** A froze × strength interaction fit on the **all-situations** data — a decomposition of a positive result, not a slice re-test. PK freezes may be worth more (they buy a line change); this sharpens the pricing, and it is the one item that uses pooled data by design.

## 6. Testing

Per project convention (computations, not callbacks; synthetic DataFrames):

- `extract.py`: `situation_code` present and correct on a synthetic play dict.
- 5v5 filter logic: given synthetic shots with mixed situation codes, the 5v5 run selects exactly `1551`.
- `build_goalies_db.py`: `situation` column populated for both cuts; 5v5 freeze percentile ranks within-cut only.
- Browser query helpers: `situation` parameter reaches the SQL.
- `python -m pytest v2/ -v` green before finishing; existing 288-test suite must stay green untouched.

## 7. Deploy

Unchanged procedure with one addition: rebuild `goalies.db` (now both cuts) and run `./tools/sync-runtime-data.sh` before `fly deploy` — runtime_data is image-baked, no Fly volume.

## 8. Execution shape / cost

No new data downloads. Rough order: (1) extract column + shots rebuild, (2) pipeline parameterization + 5v5 run, (3) goalies.db + browser dropdown, (4) research items 1–3 with §5 guardrails, (5) reports. Approximately a 5–6 task plan — the descriptive layer (tasks 1–3) is independent of, and lands before, the research layer (task 4+), so the browser dropdown can ship even if the research runs take longer.
