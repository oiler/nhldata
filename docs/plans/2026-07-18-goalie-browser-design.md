# Goalie Browser Surfaces — Design

**Date:** 2026-07-18
**Status:** Approved design (oiler, 2026-07-18)
**Owner:** oiler
**Parent:** `docs/plans/2026-06-11-goalie-evaluation-design.md` §6d (post-P6 phase, sub-project B)

## 1. Goal

Ship the validated, descriptive layers of the goalie-evaluation program (P4–P5 tables; P6-tested metrics with their earned caveats) as browser surfaces in the v2 Dash app. This is the product payoff of the research program: the environment/difficulty story is the finding, and the UI presents goalie results in that frame — not as a "best goalie" leaderboard the research showed we cannot honestly rank.

## 2. Constraints inherited from the research (non-negotiable UI semantics)

- **GSAx carries its measured caveat.** Year-over-year r ≈ 0.1 family and it does not predict across team switches (P6). Index header copy states this in one sentence; GSAx remains the default sort because it is the field-standard descriptive stat, not because it is predictive.
- **Per-game `perf_z` never drives a cross-game leaderboard.** The difficulty↔perf_z correlation is a sort-on-own-prediction artifact (§6c). perf_z appears in per-game ledger rows and season aggregates only. No page sorts games or goalies by single-game perf_z across difficulty bands.
- **Freeze is the proven skill.** Freeze rate + league percentile are first-class columns. A freeze *value* line (goals/season scale) appears only if sub-project A lands a non-null estimate; the layout reads correctly with the line absent.
- **Rebound figures are era-caveated.** `rebound_generated` coding shifted at 2023 (§6d); any rebound-suppression display is per-season (never pooled across the 2023 boundary) with a footnote.

## 3. Data plumbing

- **`goalies.db` — a cross-season sidecar DB** (precedent: `edm.db`). Per-season `league.db` files would amputate the multi-season views the goalie data exists to show (chained terms, era comparisons, 5-season ledgers).
- Built by **`v2/browser/build_goalies_db.py`** from `data/generated/goalies/*.csv` (+ `data/<season>/players/<id>.json` for names, `["default"]` locale per the report_p4p5 pattern). Output: `data/generated/browser/goalies.db`.
- Tables:
  - `goalie_seasons` — one row per (season, goalie_id): name, team(s) ("/"-joined in first-appearance order, matching the skaters-page display convention), gp, toi_s, shots_faced, ga, xga, gsax, gsax_per100, freeze_rate, freeze_pct (league percentile within season, min 500 saves), rebound_term_indep (per-season, oriented suppression-positive), mean_difficulty_pct, mean_perf_z, lev_value_sum.
  - `goalie_games` — the P5 ledger joined with game_date, opponent, and name: (season, game_id, goalie_id, game_date, opp_abbrev, ga, xga, gsax_game, perf_z, lev_value, difficulty_pct, xg_per60, toi_s).
  - `team_environment` — as generated (season, team_abbrev, gp, mean_difficulty_pct, mean_xg_faced_per60, hd_share, crossice_per60, b2b_games, tip_share, d_shot_share).
  - `freeze_value` — zero or one row (per_freeze_xga_delta, window_s, fitted_date, source) written only if sub-project A's estimate is non-null; consumers treat absence as "no validated value."
- **`db.py`** gains `goalies_query(sql, params=())` mirroring `league_query`'s parameterized pattern against the goalies.db path. All queries parameterized; no f-string SQL.
- **`tools/sync-runtime-data.sh`** gains one copy line for goalies.db; **`runtime_paths.py`** resolves it with the same env-var/gated-lookup discipline as the existing DBs (no module-level `Path().parents[N]` — containerization lesson).
- Build-order note: `build_goalies_db.py` requires the goalie pipeline CSVs to exist (P1–P5 CLIs). It fails loudly with the missing filename if run on a fresh tree.

## 4. Pages

- **`pages/goalies.py` — league goalies index.** Dash DataTable, one row per goalie-season; season filter (existing filter-bar pattern); default sort GSAx desc; columns from `goalie_seasons` incl. freeze rate + percentile and mean difficulty faced. Header copy carries the GSAx caveat sentence. Names link to the detail page.
- **`pages/goalie.py` — goalie detail at `/goalie/<goalie_id>`.** Path-template page (Dash 3.x gotcha: `relative_path` stores `/goalie/none`; nav filtering must use `page["path_template"] is None`). Sections: (1) season summary cards per season (GSAx, freeze rate/pct, difficulty faced, TOI); (2) per-game ledger table, date-sorted desc, columns per `goalie_games`, difficulty_pct rendered as a badge; (3) freeze-value line if the `freeze_value` table has a row, framed RELATIVE to the same-season league-median freeze rate (≥500-save floor) — "Freeze impact vs the league-median freeze rate: ±X goals per starter season (this goalie: pNN freeze rate)" — never as an absolute vs an implicit zero-freeze baseline (superseded 2026-07-19: the absolute framing misled for below-median goalies, e.g. a p3 goalie showing +8.2; sub-project A's ratified between-goalie framing governs); silently absent otherwise and for sub-floor goalies.
- **Team page (existing `pages/team.py`) — environment section.** "Goalie environment" card block for the selected team-season from `team_environment`: mean difficulty served, hd share, crossice/60, b2b burden, with a one-line explanation of the o-line-grade framing. No new page.

## 5. Testing

Project norms (CLAUDE.md): test computations, not callbacks. Targeted synthetic-frame tests for: `build_goalies_db.py`'s per-season aggregation (goalie_seasons math incl. freeze_pct percentile and the 500-save floor), the team-list join, and the name extraction; plus any new pure helper the pages introduce. No Dash callback tests. `python -m pytest v2/ -q` green before done.

## 6. Security

Existing app patterns apply (parameterized queries via the db.py layer; `security.py` headers untouched). The goalie_id path parameter is cast to int before any query; non-numeric or unknown ids render the standard empty-state, not an error.

## 7. Out of scope

- Any predictive/talent ranking claim in UI copy (the research result is the null).
- Leverage/WP visualizations beyond the per-game lev_value column.
- edm.db or skater-page changes.
- Backfilled seasons before 2021.
