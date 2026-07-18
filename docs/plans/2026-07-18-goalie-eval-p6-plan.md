# Goalie Evaluation P6 (Portability Harness) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P6 validation harness — switch registry, pre-switch candidate/baseline estimates, weighted paired-bootstrap portability gate vs an EB-shrunk GSAx baseline, repeatability + tandem suite, and the phase report.

**Architecture:** Five flat modules in `v2/goalies/` per spec §6c: `era_probe.py` (Task 1, pre-registered decision rule feeding a verdict file), `switch_registry.py` (real + non-switch pseudo cases from goalie-game stints), `portability.py` (case estimates incl. mid-season refits, frozen non-switch params, gate statistics, CLI), `repeatability.py`, `report_p6.py`. Spec: `docs/plans/2026-06-11-goalie-evaluation-design.md` §6 as revised by §6c (governing). All P6 outputs under `data/generated/goalies/validation/`.

**Tech Stack:** system python3 (pyenv 3.11, NOT `uv run`), pandas 3.0, numpy 2.4, pytest. No scipy/sklearn.

## Global Constraints

- Branch `goalie-eval-p1` (verify before committing; never push, never master). Local per-task commits authorized.
- No new dependencies. Raw data read-only. Generated CSVs never committed (`data/` is gitignored). `data/generated/goalies/validation/` is created by the first CLI that writes there (`mkdir(parents=True, exist_ok=True)`).
- Tests: `python3 -m pytest v2/goalies/tests/ -v` per task; full `python3 -m pytest v2/ -q` before finishing. Suite currently **246 green**.
- Existing interfaces (do not change signatures): `fit_layer(df, layer, *, goalie_prior_shots=1000.0, structure_penalty=1.0, prior_centers=None, include_goalies=True) -> LayerFit` and `LAYERS`/`layer_frame`/`predict_structure` (difficulty.py); `chain_seasons(season_dfs, layer, goalie_prior_shots=1000.0) -> dict[season, DataFrame]` (build_terms.py); `blind_shot_xg(df) -> np.ndarray` (gsax_baseline.py); `build_features`/`STRUCTURE_COLS` (features.py); `fit_penalized_logistic/predict_proba` (irls.py); `wp_table`/`leverage_weight`/`leverage_weight_vectorized` (leverage.py).
- Input schemas (all exist): `shots_<season>.csv` seasons 2021–2025 (incl. `game_id, game_date, goalie_id, event, on_net, is_goal, froze, rebound_generated, season`; fenwick = `event != "blocked-shot"`); `goalie_games_<season>.csv` (`game_id, game_date, goalie_id, team_abbrev, season, ...`); `goalie_terms_<season>.csv` (`goalie_id, layer, term, se, n_shots, term_indep, se_indep`; layers onnet/freeze/goal/rebound); `game_ledger.csv` (`season, game_id, goalie_id, perf_z, ...`, no game_date — join goalie_games).
- **Pre-registration discipline:** the era-probe verdict (Task 1) and the frozen non-switch params (K, composite weights — Task 4) are computed and written to disk BEFORE any switch case is scored (Task 5 reads them; it never refits them). Determinism: all bootstrap/rng uses `np.random.default_rng(42)`.
- **Candidate orientation (higher = better goalie), fixed:** stopping = −(goal-layer chained term); freeze = +(freeze term); rebound_control = −(rebound term); perf = mean pre-switch `perf_z`; composite = frozen-ridge output. Outcome = post-switch (xGA − GA)/fenwick shots. Baselines: `baseline_eb` (EB-shrunk matched-horizon GSAx rate), `baseline_naive` (last pre-season raw GSAx rate, literature anchor).
- **Registry constants, fixed:** `FLOOR = 600` fenwick each side; case weight = `min(pre_fenwick, post_fenwick)`; era A = seasons {2021, 2022}, era B = {2023, 2024, 2025}.
- Era-probe decision rule (pre-registered, per outcome in {froze, rebound_generated}): |era_b logit coef| ≤ 0.05 → `stable` (terms enter as-is); > 0.15 → `normalize` (that component's terms are z-standardized within season before use); else → `sensitivity` (rebound candidate additionally reported era-B-only: cases with last-pre-season AND first post season ≥ 2023, using `term_indep` of the last pre season).

---

### Task 1: Era probe (froze / rebound_generated coding-shift check)

**Files:**
- Create: `v2/goalies/era_probe.py`
- Test: `v2/goalies/tests/test_era_probe.py`

**Interfaces:**
- Produces: `era_shift(shots: pd.DataFrame, outcome: str) -> dict` with keys `coef, se, rate_a, rate_b` — fits the structure model on the saves subset (`on_net & ~is_goal`, outcome notna) with an UNPENALIZED `era_b` dummy appended; `coef` is the feature-conditional era-B logit shift. `verdict(coef: float) -> str` applying the pre-registered thresholds (`stable`/`normalize`/`sensitivity`). CLI `python3 v2/goalies/era_probe.py` writes `data/generated/goalies/validation/era_probe_verdict.json` (`{"froze": <verdict>, "rebound_generated": <verdict>, "coefs": {...}}`) and `era_probe_report.txt` (raw + conditional rates per era, distance-band × shot-type table). Task 3/5 consume the JSON.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_era_probe.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.era_probe import era_shift, verdict


def _saves(n_per_era, rate_a, rate_b, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for season, rate in ((2021, rate_a), (2024, rate_b)):
        for i in range(n_per_era):
            rows.append({
                "season": season, "on_net": True, "is_goal": False,
                "froze": float(rng.random() < rate),
                "distance_adj": 30.0, "angle": 20.0, "shot_type": "wrist",
                "strength": "ev", "score_diff": 0, "goalie_is_home": True,
                "dt_prev": np.nan, "prev_type": np.nan, "prev_same_team": np.nan,
                "prev_x_norm": np.nan, "prev_y_norm": np.nan, "y_norm": 0.0,
                "x_norm": 60.0, "period": 1, "time_s": 300,
            })
    return pd.DataFrame(rows)


def test_era_shift_detects_injected_offset():
    r = era_shift(_saves(4000, 0.30, 0.40), "froze")
    assert r["coef"] > 0.2                      # ~0.44 logit injected
    assert r["rate_b"] > r["rate_a"]


def test_era_shift_near_zero_when_stable():
    r = era_shift(_saves(4000, 0.31, 0.31), "froze")
    assert abs(r["coef"]) < 0.1


def test_verdict_thresholds():
    assert verdict(0.03) == "stable"
    assert verdict(-0.04) == "stable"
    assert verdict(0.09) == "sensitivity"
    assert verdict(0.30) == "normalize"
```

- [ ] **Step 2: Run to verify failure** — `python3 -m pytest v2/goalies/tests/test_era_probe.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# v2/goalies/era_probe.py
"""Era probe: did froze/rebound_generated CODING shift at the 2023 tracking era?

Fits the structure model on saves with an unpenalized era_b dummy; the dummy's
logit coefficient is the feature-conditional era shift. Pre-registered rule
(spec 6c): |coef| <= 0.05 stable; > 0.15 normalize; else sensitivity.

Usage: python3 v2/goalies/era_probe.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.features import STRUCTURE_COLS, build_features  # noqa: E402
from v2.goalies.irls import fit_penalized_logistic  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
ERA_B = {2023, 2024, 2025}


def era_shift(shots: pd.DataFrame, outcome: str) -> dict:
    frame = shots[shots["on_net"] & ~shots["is_goal"]]
    frame = frame[frame[outcome].notna()]
    y = frame[outcome].to_numpy(dtype=float)
    era_b = frame["season"].isin(ERA_B).to_numpy(dtype=float)
    X = np.hstack([build_features(frame).to_numpy(), era_b[:, None]])
    penalty = np.full(X.shape[1], 1.0)
    penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
    penalty[-1] = 1e-6
    fit = fit_penalized_logistic(X, y, penalty)
    return {
        "coef": float(fit.coef[-1]), "se": float(fit.se[-1]),
        "rate_a": float(y[era_b == 0].mean()), "rate_b": float(y[era_b == 1].mean()),
    }


def verdict(coef: float) -> str:
    if abs(coef) <= 0.05:
        return "stable"
    if abs(coef) > 0.15:
        return "normalize"
    return "sensitivity"


def main() -> None:
    VAL.mkdir(parents=True, exist_ok=True)
    shots = pd.concat([pd.read_csv(GEN / f"shots_{s}.csv") for s in SEASONS],
                      ignore_index=True)
    lines, verdicts, coefs = [], {}, {}
    for outcome in ("froze", "rebound_generated"):
        r = era_shift(shots, outcome)
        verdicts[outcome] = verdict(r["coef"])
        coefs[outcome] = r
        lines.append(f"{outcome}: era_b coef={r['coef']:+.4f} se={r['se']:.4f} "
                     f"raw rates A={r['rate_a']:.4f} B={r['rate_b']:.4f} "
                     f"-> verdict {verdicts[outcome]}")
    saves = shots[shots["on_net"] & ~shots["is_goal"]].copy()
    saves["era"] = np.where(saves["season"].isin(ERA_B), "B", "A")
    saves["dist_band"] = pd.cut(np.maximum(saves["distance_adj"], 0),
                                [0, 15, 30, 50, 200], right=False)
    binned = saves.groupby(["era", "dist_band", "shot_type"], observed=True)["froze"].agg(
        ["mean", "size"])
    lines.append("\nfroze rate by era x distance band x shot type (n >= 2000 cells):")
    lines.append(binned[binned["size"] >= 2000].to_string())
    (VAL / "era_probe_verdict.json").write_text(json.dumps(
        {"froze": verdicts["froze"], "rebound_generated": verdicts["rebound_generated"],
         "coefs": coefs}, indent=2))
    report = "\n".join(lines)
    (VAL / "era_probe_report.txt").write_text(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests green, run the CLI.** Fit is over ~490k saves with 2 fits — minutes are normal. Record both verdicts in the task report. Expectation is genuinely open (that is why the probe exists): P0–P2 found freeze% era-stable at the 5s window (so `froze` likely `stable`) and rebound% trending upward smoothly (so `rebound_generated` could land anywhere). Whatever the verdicts, they are DATA for Task 3/5, not stop conditions.

- [ ] **Step 5: Commit** — `git add v2/goalies/era_probe.py v2/goalies/tests/test_era_probe.py && git commit -m "feat(goalies): era probe for freeze/rebound coding shift (pre-registered rule)"`

---

### Task 2: Switch registry (real cases + non-switch pseudo-cases)

**Files:**
- Create: `v2/goalies/switch_registry.py`
- Test: `v2/goalies/tests/test_switch_registry.py`

**Interfaces:**
- Produces: `stint_table(gg: pd.DataFrame, fenwick: pd.DataFrame) -> pd.DataFrame` — per (goalie_id, stint_id): `team, start, end, first_season, last_season, fenwick` from date-ordered goalie-games (a stint = maximal run of consecutive games with one team). `switch_cases(stints: pd.DataFrame) -> pd.DataFrame` — one row per stint boundary with a team change where cumulative-prior fenwick ≥ FLOOR and new-stint fenwick ≥ FLOOR: `case_id, goalie_id, switch_type` (`offseason` if the boundary spans seasons else `midseason`), `switch_date` (new stint's first game_date), `pre_team, post_team, pre_fenwick, post_fenwick, weight, last_pre_season, first_post_season`. `nonswitch_pseudo_cases(stints: pd.DataFrame, gg: pd.DataFrame, fenwick: pd.DataFrame) -> pd.DataFrame` — same columns (`switch_type="nonswitch"`): for every stint spanning consecutive seasons (t, t+1) with same team, a pseudo-boundary at the first game of season t+1 with that team, same floors/weights (pre = all games before the boundary, post = season t+1 with that team); used ONLY to freeze K and composite weights (Task 4). `fenwick_by_game(shots) -> pd.DataFrame` (`season, game_id, goalie_id, fenwick`). CLI writes `validation/switch_registry.csv` (real + pseudo, `switch_type` distinguishes).
- Consumes: `goalie_games_<season>.csv`, `shots_<season>.csv`.
- Post-stint definition (spec §6c): post window = the new stint only (runs until the next team change or data end). Pre window = ALL shots strictly before `switch_date` (any team) — matched horizon for candidates and baseline alike.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_switch_registry.py
import pandas as pd
import pytest

from v2.goalies.switch_registry import (fenwick_by_game, nonswitch_pseudo_cases,
                                        stint_table, switch_cases)


def _gg(rows):
    return pd.DataFrame(rows, columns=["season", "game_id", "goalie_id",
                                       "team_abbrev", "game_date"])


def _fw(gg, per_game=40):
    return gg[["season", "game_id", "goalie_id"]].assign(fenwick=per_game)


def test_offseason_switch_and_floor():
    rows = ([(2021, i, 1, "EDM", f"2021-11-{i:02d}") for i in range(1, 21)]
            + [(2022, 100 + i, 1, "CGY", f"2022-11-{i:02d}") for i in range(1, 21)])
    stints = stint_table(_gg(rows), _fw(_gg(rows)))
    cases = switch_cases(stints)
    assert len(cases) == 1
    c = cases.iloc[0]
    assert c["switch_type"] == "offseason" and c["switch_date"] == "2022-11-01"
    assert c["pre_team"] == "EDM" and c["post_team"] == "CGY"
    assert c["pre_fenwick"] == 800 and c["post_fenwick"] == 800 and c["weight"] == 800
    assert c["last_pre_season"] == 2021 and c["first_post_season"] == 2022


def test_midseason_switch_classified_and_low_workload_excluded():
    rows = ([(2023, i, 2, "TOR", f"2023-11-{i:02d}") for i in range(1, 21)]
            + [(2023, 50 + i, 2, "VAN", f"2023-12-{i:02d}") for i in range(1, 21)]
            + [(2023, 90 + i, 3, "BOS", f"2023-11-{i:02d}") for i in range(1, 3)]
            + [(2023, 95 + i, 3, "SEA", f"2023-12-{i:02d}") for i in range(1, 3)])
    gg = _gg(rows)
    cases = switch_cases(stint_table(gg, _fw(gg)))
    assert len(cases) == 1                      # goalie 3 fails the 600 floor
    assert cases.iloc[0]["switch_type"] == "midseason"
    assert cases.iloc[0]["goalie_id"] == 2


def test_pre_fenwick_is_cumulative_over_all_prior_stints():
    rows = ([(2021, i, 4, "EDM", f"2021-11-{i:02d}") for i in range(1, 11)]
            + [(2022, 30 + i, 4, "CGY", f"2022-11-{i:02d}") for i in range(1, 11)]
            + [(2023, 60 + i, 4, "VAN", f"2023-11-{i:02d}") for i in range(1, 21)])
    gg = _gg(rows)
    cases = switch_cases(stint_table(gg, _fw(gg)))
    van = cases[cases["post_team"] == "VAN"].iloc[0]
    assert van["pre_fenwick"] == 800            # EDM 400 + CGY 400 pooled


def test_nonswitch_pseudo_cases():
    rows = ([(2021, i, 5, "EDM", f"2021-11-{i:02d}") for i in range(1, 21)]
            + [(2022, 100 + i, 5, "EDM", f"2022-11-{i:02d}") for i in range(1, 21)])
    gg = _gg(rows)
    fw = _fw(gg)
    pseudo = nonswitch_pseudo_cases(stint_table(gg, fw), gg, fw)
    assert len(pseudo) == 1
    p = pseudo.iloc[0]
    assert p["switch_type"] == "nonswitch" and p["switch_date"] == "2022-11-01"
    assert p["pre_team"] == "EDM" and p["post_team"] == "EDM"
    assert p["pre_fenwick"] == 800 and p["post_fenwick"] == 800


def test_fenwick_by_game_excludes_blocked():
    shots = pd.DataFrame({
        "season": [2023] * 3, "game_id": [1] * 3, "goalie_id": [9] * 3,
        "event": ["shot-on-goal", "blocked-shot", "missed-shot"],
    })
    fw = fenwick_by_game(shots)
    assert fw.iloc[0]["fenwick"] == 2
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# v2/goalies/switch_registry.py
"""Switch registry: real team-change cases + non-switch pseudo-cases.

A stint is a maximal date-ordered run of games with one team. Every stint
boundary with a team change is a candidate case; floors (600 fenwick each
side) and min(pre, post) weights per spec 6c. Pre window = everything before
switch_date; post window = the new stint only. Non-switch pseudo-cases
(same team, consecutive seasons) exist ONLY to freeze the baseline K and
composite weights before any real case is scored.

Usage: python3 v2/goalies/switch_registry.py
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
FLOOR = 600


def fenwick_by_game(shots: pd.DataFrame) -> pd.DataFrame:
    fen = shots[shots["event"] != "blocked-shot"]
    return (fen.groupby(["season", "game_id", "goalie_id"]).size()
            .rename("fenwick").reset_index())


def stint_table(gg: pd.DataFrame, fenwick: pd.DataFrame) -> pd.DataFrame:
    g = gg.sort_values(["goalie_id", "game_date", "game_id"]).merge(
        fenwick, on=["season", "game_id", "goalie_id"], how="left")
    g["fenwick"] = g["fenwick"].fillna(0)
    changed = (g["team_abbrev"] != g.groupby("goalie_id")["team_abbrev"].shift())
    g["stint_id"] = changed.cumsum()
    return (g.groupby(["goalie_id", "stint_id"]).agg(
        team=("team_abbrev", "first"), start=("game_date", "min"),
        end=("game_date", "max"), first_season=("season", "min"),
        last_season=("season", "max"), fenwick=("fenwick", "sum"))
        .reset_index().sort_values(["goalie_id", "start"], ignore_index=True))


def _case_row(prev_rows, cur, case_id, switch_type):
    pre_fenwick = int(prev_rows["fenwick"].sum())
    return {
        "case_id": case_id, "goalie_id": cur["goalie_id"],
        "switch_type": switch_type, "switch_date": cur["start"],
        "pre_team": prev_rows.iloc[-1]["team"], "post_team": cur["team"],
        "pre_fenwick": pre_fenwick, "post_fenwick": int(cur["fenwick"]),
        "weight": min(pre_fenwick, int(cur["fenwick"])),
        "last_pre_season": int(prev_rows.iloc[-1]["last_season"]),
        "first_post_season": int(cur["first_season"]),
    }


def switch_cases(stints: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, grp in stints.groupby("goalie_id"):
        grp = grp.reset_index(drop=True)
        for i in range(1, len(grp)):
            prev_rows, cur = grp.iloc[:i], grp.iloc[i]
            if prev_rows["fenwick"].sum() < FLOOR or cur["fenwick"] < FLOOR:
                continue
            switch_type = ("offseason"
                           if prev_rows.iloc[-1]["last_season"] != cur["first_season"]
                           else "midseason")
            rows.append(_case_row(prev_rows, cur,
                                  f"S{cur['goalie_id']}-{cur['start']}", switch_type))
    return pd.DataFrame(rows)


def nonswitch_pseudo_cases(stints: pd.DataFrame, gg: pd.DataFrame,
                           fenwick: pd.DataFrame) -> pd.DataFrame:
    """Same-team consecutive-season pseudo-cases, for frozen-param fitting only."""
    g = gg.merge(fenwick, on=["season", "game_id", "goalie_id"], how="left")
    g["fenwick"] = g["fenwick"].fillna(0)
    rows = []
    for _, st in stints.iterrows():
        for t in range(int(st["first_season"]), int(st["last_season"])):
            mine = g[g["goalie_id"] == st["goalie_id"]].sort_values("game_date")
            post = mine[(mine["season"] == t + 1)
                        & (mine["team_abbrev"] == st["team"])]
            if post.empty:
                continue
            switch_date = post["game_date"].min()
            pre = mine[mine["game_date"] < switch_date]
            if pre["fenwick"].sum() < FLOOR or post["fenwick"].sum() < FLOOR:
                continue
            rows.append({
                "case_id": f"N{st['goalie_id']}-{switch_date}",
                "goalie_id": st["goalie_id"], "switch_type": "nonswitch",
                "switch_date": switch_date, "pre_team": st["team"],
                "post_team": st["team"],
                "pre_fenwick": int(pre["fenwick"].sum()),
                "post_fenwick": int(post["fenwick"].sum()),
                "weight": int(min(pre["fenwick"].sum(), post["fenwick"].sum())),
                "last_pre_season": t, "first_post_season": t + 1,
            })
    cols = ["case_id", "goalie_id", "switch_type", "switch_date", "pre_team",
            "post_team", "pre_fenwick", "post_fenwick", "weight",
            "last_pre_season", "first_post_season"]
    return pd.DataFrame(rows, columns=cols)


def main() -> None:
    VAL.mkdir(parents=True, exist_ok=True)
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    shots = pd.concat([pd.read_csv(GEN / f"shots_{s}.csv",
                                   usecols=["season", "game_id", "goalie_id", "event"])
                       for s in SEASONS], ignore_index=True)
    fw = fenwick_by_game(shots)
    stints = stint_table(gg, fw)
    real = switch_cases(stints)
    pseudo = nonswitch_pseudo_cases(stints, gg, fw)
    registry = pd.concat([real, pseudo], ignore_index=True)
    registry.to_csv(VAL / "switch_registry.csv", index=False)
    counts = real.groupby("switch_type").size().to_dict()
    print(f"registry: {len(real)} real cases {counts}, {len(pseudo)} nonswitch pseudo; "
          f"weights p10/p50/p90 = "
          f"{real['weight'].quantile(.1):.0f}/{real['weight'].median():.0f}/"
          f"{real['weight'].quantile(.9):.0f}")


if __name__ == "__main__":
    main()
```

Implementation note: the pseudo-case post window is the SEASON with that team (not the remaining multi-season stint) — one pseudo-case per season boundary inside a long stint, which is exactly the consecutive-season-pair shape the frozen params need. The per-goalie `mine` filter inside the stint loop is O(stints × games); at ~700 stints over ~14k goalie-games this is seconds — do not optimize.

- [ ] **Step 4: Tests green, run the CLI.** Anchors from the design scan (pre-plan probe, 2026-07-18): expect roughly 55–65 offseason cases at the 600 floor (scan said 60 via a primary-team method; the stint method may differ slightly — report the delta and spot-check 2–3 differing goalies), ~8–20 midseason cases, and a few hundred nonswitch pseudo-cases. If offseason count is outside 45–75, STOP and reconcile with the scan method before proceeding.

- [ ] **Step 5: Commit** — `git add v2/goalies/switch_registry.py v2/goalies/tests/test_switch_registry.py && git commit -m "feat(goalies): switch registry (stint-based, floors+weights, nonswitch pseudo-cases)"`

---

### Task 3: Case estimates (candidates, baselines, outcome, mid-season refits)

**Files:**
- Create: `v2/goalies/portability.py` (functions only; CLI comes in Task 5)
- Test: `v2/goalies/tests/test_portability.py`

**Interfaces:**
- Produces (all consumed by Tasks 4–5):
  - `case_outcome(case: dict, shots_xg: pd.DataFrame, gg: pd.DataFrame) -> dict | None` — post-stint outcome: filters `shots_xg` (columns `season, game_id, goalie_id, game_date, fenwick_flag, xg, is_goal`) to the goalie's post window (`game_date >= switch_date` AND game in a goalie-game row with `team_abbrev == post_team`), fenwick only; returns `{"n_post": int, "outcome": (xga - ga) / n_post}` or None if n_post == 0.
  - `pre_gsax(case, shots_xg) -> dict` — over ALL fenwick shots with `game_date < switch_date`: `{"n_pre": int, "gsax_sum": float, "naive_rate": float}` where `naive_rate` is the last-pre-season-only raw rate (`(xga-ga)/n` within `season == last_pre_season`), np.nan if that season has no pre shots.
  - `eb_rate(gsax_sum: float, n: int, k: float) -> float` = `gsax_sum / (n + k)`.
  - `term_lookup(case, terms: dict[int, pd.DataFrame], normalize: set[str]) -> dict` — chained `term` per layer from `terms[last_pre_season]` (the per-season goalie_terms frames); layers in `normalize` are z-standardized within season (over that season's goalies for that layer) before lookup; returns `{"stopping": -goal_term, "freeze": freeze_term, "rebound_control": -rebound_term}` with np.nan for a goalie absent from a layer.
  - `midseason_refit(season_shots: pd.DataFrame, goalie_id: int, switch_date: str, prior_terms: dict[str, dict[int, float]]) -> dict[str, float]` — for layers goal/freeze/rebound: `fit_layer` on the season's shots with THIS goalie's shots on/after switch_date dropped, `prior_centers=prior_terms[layer]`; returns the goalie's clean partial-season term per layer (0.0 if the goalie has no remaining shots in a layer's frame).
  - `pre_perf(case, ledger_dated: pd.DataFrame) -> float` — mean `perf_z` over the goalie's games with `game_date < switch_date` (NaN perf_z rows dropped; np.nan if none).
- Consumes: `switch_registry.csv` rows as dicts; `goalie_terms_<season>.csv` split per season into per-layer frames; `blind_shot_xg` for the per-season xg columns (assembled in Task 5's CLI; tests pass synthetic frames).

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_portability.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.portability import (case_outcome, eb_rate, pre_gsax, pre_perf,
                                    term_lookup)


def _case():
    return {"case_id": "S1-2023-01-15", "goalie_id": 1, "switch_type": "midseason",
            "switch_date": "2023-01-15", "pre_team": "TOR", "post_team": "VAN",
            "last_pre_season": 2023, "first_post_season": 2023}


def _shots_xg():
    rows = []
    for i, (date, goal) in enumerate((("2023-01-10", 1), ("2023-01-10", 0),
                                      ("2023-01-20", 0), ("2023-01-20", 0))):
        rows.append({"season": 2023, "game_id": 100 + i // 2, "goalie_id": 1,
                     "game_date": date, "fenwick_flag": True, "xg": 0.10,
                     "is_goal": bool(goal)})
    return pd.DataFrame(rows)


def _gg():
    return pd.DataFrame({
        "season": [2023] * 2, "game_id": [100, 101], "goalie_id": [1, 1],
        "team_abbrev": ["TOR", "VAN"],
        "game_date": ["2023-01-10", "2023-01-20"],
    })


def test_case_outcome_post_stint_only():
    r = case_outcome(_case(), _shots_xg(), _gg())
    assert r["n_post"] == 2
    assert r["outcome"] == pytest.approx((0.2 - 0.0) / 2)


def test_pre_gsax_and_naive():
    r = pre_gsax(_case(), _shots_xg())
    assert r["n_pre"] == 2
    assert r["gsax_sum"] == pytest.approx(0.2 - 1.0)
    assert r["naive_rate"] == pytest.approx(-0.4)


def test_eb_rate_shrinks_toward_zero():
    assert eb_rate(-0.8, 2, 0) == pytest.approx(-0.4)
    assert abs(eb_rate(-0.8, 2, 1000)) < 0.001


def test_term_lookup_signs_and_normalize():
    terms = {2023: pd.DataFrame({
        "goalie_id": [1, 2, 3], "layer": ["goal"] * 3,
        "term": [0.2, 0.0, -0.2],
    })}
    t = term_lookup(_case(), terms, normalize=set())
    assert t["stopping"] == pytest.approx(-0.2)      # positive goal term = bad
    tz = term_lookup(_case(), terms, normalize={"goal"})
    assert tz["stopping"] == pytest.approx(-0.2 / np.std([0.2, 0.0, -0.2]))
    assert np.isnan(t["freeze"])                     # layer absent from frame


def test_pre_perf_uses_dated_games():
    ledger = pd.DataFrame({
        "goalie_id": [1, 1, 1], "game_date": ["2023-01-05", "2023-01-10", "2023-01-20"],
        "perf_z": [1.0, 0.0, 5.0],
    })
    assert pre_perf(_case(), ledger) == pytest.approx(0.5)
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# v2/goalies/portability.py
"""P6 portability harness: pre-switch estimates for candidates and baselines.

Per spec 6c: pre window = all shots before switch_date (matched horizon for
candidates and baseline alike); post window = the new stint only. Candidate
orientation is fixed so higher = better goalie. Mid-season cases refit the
switch season's layers with the goalie's post shots excluded (leakage rule).

Usage (Task 5 adds the CLI): python3 v2/goalies/portability.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.difficulty import fit_layer  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
CAND_LAYERS = ("goal", "freeze", "rebound")
ORIENT = {"goal": -1.0, "freeze": 1.0, "rebound": -1.0}
CAND_NAME = {"goal": "stopping", "freeze": "freeze", "rebound": "rebound_control"}


def case_outcome(case: dict, shots_xg: pd.DataFrame, gg: pd.DataFrame):
    post_games = gg[(gg["goalie_id"] == case["goalie_id"])
                    & (gg["game_date"] >= case["switch_date"])
                    & (gg["team_abbrev"] == case["post_team"])]
    keys = set(zip(post_games["season"], post_games["game_id"]))
    s = shots_xg[(shots_xg["goalie_id"] == case["goalie_id"])
                 & shots_xg["fenwick_flag"]]
    s = s[[k in keys for k in zip(s["season"], s["game_id"])]]
    if len(s) == 0:
        return None
    return {"n_post": len(s),
            "outcome": float((s["xg"].sum() - s["is_goal"].sum()) / len(s))}


def pre_gsax(case: dict, shots_xg: pd.DataFrame) -> dict:
    s = shots_xg[(shots_xg["goalie_id"] == case["goalie_id"])
                 & shots_xg["fenwick_flag"]
                 & (shots_xg["game_date"] < case["switch_date"])]
    last = s[s["season"] == case["last_pre_season"]]
    naive = (float((last["xg"].sum() - last["is_goal"].sum()) / len(last))
             if len(last) else np.nan)
    return {"n_pre": len(s),
            "gsax_sum": float(s["xg"].sum() - s["is_goal"].sum()),
            "naive_rate": naive}


def eb_rate(gsax_sum: float, n: int, k: float) -> float:
    return gsax_sum / (n + k)


def term_lookup(case: dict, terms: dict[int, pd.DataFrame],
                normalize: set[str]) -> dict:
    season_frame = terms.get(case["last_pre_season"])
    out = {}
    for layer in CAND_LAYERS:
        name = CAND_NAME[layer]
        if season_frame is None:
            out[name] = np.nan
            continue
        lf = season_frame[season_frame["layer"] == layer]
        if layer in normalize and len(lf) > 1:
            sd = float(lf["term"].std(ddof=0))
            lf = lf.assign(term=(lf["term"] - lf["term"].mean()) / (sd or 1.0))
        row = lf[lf["goalie_id"] == case["goalie_id"]]
        out[name] = (float(ORIENT[layer] * row["term"].iloc[0])
                     if len(row) else np.nan)
    return out


def midseason_refit(season_shots: pd.DataFrame, goalie_id: int, switch_date: str,
                    prior_terms: dict[str, dict[int, float]]) -> dict[str, float]:
    drop = ((season_shots["goalie_id"] == goalie_id)
            & (season_shots["game_date"] >= switch_date))
    clean = season_shots[~drop]
    out = {}
    for layer in CAND_LAYERS:
        fit = fit_layer(clean, layer, prior_centers=prior_terms.get(layer))
        row = fit.goalie_terms[fit.goalie_terms["goalie_id"] == goalie_id]
        out[layer] = float(row["term"].iloc[0]) if len(row) else 0.0
    return out


def pre_perf(case: dict, ledger_dated: pd.DataFrame) -> float:
    mine = ledger_dated[(ledger_dated["goalie_id"] == case["goalie_id"])
                        & (ledger_dated["game_date"] < case["switch_date"])]
    vals = mine["perf_z"].dropna()
    return float(vals.mean()) if len(vals) else np.nan
```

- [ ] **Step 4: Tests green** — `python3 -m pytest v2/goalies/tests/test_portability.py -v`. `midseason_refit` has no synthetic test here (it wraps `fit_layer`, already tested in P3; a synthetic IRLS fit test would re-test the solver) — its verification is Task 5's cache run plus this task's review. Full suite green.

- [ ] **Step 5: Commit** — `git add v2/goalies/portability.py v2/goalies/tests/test_portability.py && git commit -m "feat(goalies): portability case estimates (candidates, baselines, outcome, midseason refits)"`

---

### Task 4: Gate statistics + frozen non-switch params

**Files:**
- Modify: `v2/goalies/portability.py` (append functions)
- Modify: `v2/goalies/tests/test_portability.py` (append tests)

**Interfaces:**
- Produces (consumed by Task 5):
  - `weighted_r(x, y, w) -> float` — weighted Pearson; pairs with NaN in x or y dropped WITH their weights.
  - `weighted_spearman(x, y, w) -> float` — `weighted_r` of the rank-transformed values (average ranks).
  - `paired_bootstrap_dr(cand, base, y, w, n_boot=10000, seed=42) -> dict` — resamples case indices with replacement; returns `{"dr": point Δr, "lo90": ..., "hi90": ...}` (5th/95th percentiles of the bootstrap Δr distribution).
  - `incremental_beta(cand, base, y, w) -> float` — weighted OLS of y on [1, standardized base, standardized cand]; returns the cand coefficient (supporting diagnostic only).
  - `fit_k(pseudo: pd.DataFrame, grid=(250, 500, 1000, 2000, 4000)) -> int` — K maximizing `weighted_r(eb_rate per case, outcome, weight)` over nonswitch pseudo-cases (columns `gsax_sum, n_pre, outcome, weight`).
  - `fit_composite(pseudo: pd.DataFrame, cols=("stopping", "freeze", "rebound_control", "perf"), lam=1.0) -> dict` — ridge on standardized columns predicting `outcome`, weighted; solves `(XᵀWX + λI)β = XᵀWy` (intercept unpenalized via centering); returns `{"means": {...}, "stds": {...}, "beta": {...}}`. Rows with any NaN in `cols` dropped with weights. `apply_composite(row: dict, params: dict) -> float`.
- λ=1.0 and the K grid are pre-registered constants; Task 5 writes the fitted values to `validation/frozen_params.json` BEFORE scoring real cases and never refits them.

- [ ] **Step 1: Append the failing tests**

```python
# append to v2/goalies/tests/test_portability.py
from v2.goalies.portability import (apply_composite, fit_composite, fit_k,
                                    incremental_beta, paired_bootstrap_dr,
                                    weighted_r, weighted_spearman)


def test_weighted_r_matches_numpy_when_uniform():
    rng = np.random.default_rng(0)
    x, y = rng.normal(size=50), rng.normal(size=50)
    w = np.ones(50)
    assert weighted_r(x, y, w) == pytest.approx(np.corrcoef(x, y)[0, 1])


def test_weighted_r_zero_weight_case_ignored():
    x = np.array([1.0, 2.0, 3.0, 100.0])
    y = np.array([1.0, 2.0, 3.0, -100.0])
    w = np.array([1.0, 1.0, 1.0, 0.0])
    assert weighted_r(x, y, w) == pytest.approx(1.0)


def test_weighted_r_drops_nan_pairs():
    x = np.array([1.0, 2.0, np.nan, 3.0])
    y = np.array([1.0, 2.0, 5.0, 3.0])
    w = np.ones(4)
    assert weighted_r(x, y, w) == pytest.approx(1.0)


def test_paired_bootstrap_recovers_sign():
    rng = np.random.default_rng(1)
    y = rng.normal(size=200)
    cand = y + rng.normal(scale=0.5, size=200)      # r ~ 0.9
    base = y + rng.normal(scale=2.0, size=200)      # r ~ 0.45
    r = paired_bootstrap_dr(cand, base, y, np.ones(200), n_boot=2000)
    assert r["dr"] > 0.2
    assert r["lo90"] > 0                            # CI excludes zero


def test_incremental_beta_zero_when_candidate_is_noise():
    rng = np.random.default_rng(2)
    y = rng.normal(size=500)
    base = y + rng.normal(scale=0.5, size=500)
    noise = rng.normal(size=500)
    assert abs(incremental_beta(noise, base, y, np.ones(500))) < 0.1


def test_fit_k_prefers_heavy_shrinkage_for_noisy_signal():
    # k is identified only through HETEROGENEOUS n_pre: with constant n_pre,
    # dividing by (n + k) is a pure rescale and correlation is k-invariant
    # (plan defect caught at execution, 2026-07-18; fixture corrected).
    rng = np.random.default_rng(3)
    n = np.concatenate([np.full(300, 500), np.full(300, 4000)])
    true = rng.normal(scale=0.003, size=600)
    pseudo = pd.DataFrame({
        "n_pre": n,
        "gsax_sum": true * n + rng.normal(scale=np.sqrt(0.06 * n)),
        "outcome": true + rng.normal(scale=0.0055, size=600),
        "weight": np.ones(600),
    })
    assert fit_k(pseudo) >= 1000


def test_composite_recovers_dominant_column():
    rng = np.random.default_rng(4)
    n = 300
    a, b = rng.normal(size=n), rng.normal(size=n)
    pseudo = pd.DataFrame({
        "stopping": a, "freeze": b, "rebound_control": rng.normal(size=n),
        "perf": rng.normal(size=n),
        "outcome": a * 0.01 + rng.normal(scale=0.001, size=n),
        "weight": np.ones(n),
    })
    params = fit_composite(pseudo)
    assert abs(params["beta"]["stopping"]) > 3 * abs(params["beta"]["freeze"])
    row = {"stopping": 1.0, "freeze": 0.0, "rebound_control": 0.0, "perf": 0.0}
    assert apply_composite(row, params) != 0.0
```

- [ ] **Step 2: Run to verify failure** — `ImportError` on the new names.

- [ ] **Step 3: Append the implementation**

```python
# append to v2/goalies/portability.py

def _clean(x, y, w):
    x, y, w = np.asarray(x, float), np.asarray(y, float), np.asarray(w, float)
    m = ~(np.isnan(x) | np.isnan(y)) & (w > 0)
    return x[m], y[m], w[m]


def weighted_r(x, y, w) -> float:
    x, y, w = _clean(x, y, w)
    if len(x) < 3:
        return float("nan")
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    vx = np.average((x - mx) ** 2, weights=w)
    vy = np.average((y - my) ** 2, weights=w)
    return float(cov / np.sqrt(vx * vy)) if vx > 0 and vy > 0 else float("nan")


def _ranks(a):
    order = np.argsort(a)
    ranks = np.empty(len(a))
    ranks[order] = np.arange(len(a), dtype=float)
    for v in np.unique(a):                      # average ties
        m = a == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    return ranks


def weighted_spearman(x, y, w) -> float:
    x, y, w = _clean(x, y, w)
    if len(x) < 3:
        return float("nan")
    return weighted_r(_ranks(x), _ranks(y), w)


def paired_bootstrap_dr(cand, base, y, w, n_boot: int = 10000, seed: int = 42) -> dict:
    cand, base, y, w = (np.asarray(a, float) for a in (cand, base, y, w))
    keep = ~(np.isnan(cand) | np.isnan(base) | np.isnan(y)) & (w > 0)
    cand, base, y, w = cand[keep], base[keep], y[keep], w[keep]
    point = weighted_r(cand, y, w) - weighted_r(base, y, w)
    rng = np.random.default_rng(seed)
    n = len(y)
    drs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        drs[b] = (weighted_r(cand[idx], y[idx], w[idx])
                  - weighted_r(base[idx], y[idx], w[idx]))
    drs = drs[~np.isnan(drs)]
    return {"dr": float(point), "lo90": float(np.percentile(drs, 5)),
            "hi90": float(np.percentile(drs, 95)), "n_cases": int(n)}


def _standardize(a, w):
    m = np.average(a, weights=w)
    s = np.sqrt(np.average((a - m) ** 2, weights=w))
    return (a - m) / (s or 1.0)


def incremental_beta(cand, base, y, w) -> float:
    cand, base, y, w = (np.asarray(a, float) for a in (cand, base, y, w))
    keep = ~(np.isnan(cand) | np.isnan(base) | np.isnan(y)) & (w > 0)
    cand, base, y, w = cand[keep], base[keep], y[keep], w[keep]
    X = np.column_stack([np.ones(len(y)), _standardize(base, w),
                         _standardize(cand, w)])
    W = np.diag(w)
    beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ y)
    return float(beta[2])


def fit_k(pseudo: pd.DataFrame, grid=(250, 500, 1000, 2000, 4000)) -> int:
    best_k, best_r = grid[0], -np.inf
    for k in grid:
        rate = pseudo["gsax_sum"] / (pseudo["n_pre"] + k)
        r = weighted_r(rate, pseudo["outcome"], pseudo["weight"])
        if not np.isnan(r) and r > best_r:
            best_k, best_r = k, r
    return int(best_k)


def fit_composite(pseudo: pd.DataFrame,
                  cols=("stopping", "freeze", "rebound_control", "perf"),
                  lam: float = 1.0) -> dict:
    d = pseudo.dropna(subset=list(cols) + ["outcome"])
    w = d["weight"].to_numpy(dtype=float)
    y = d["outcome"].to_numpy(dtype=float)
    means = {c: float(np.average(d[c], weights=w)) for c in cols}
    stds = {c: float(np.sqrt(np.average((d[c] - means[c]) ** 2, weights=w))) or 1.0
            for c in cols}
    X = np.column_stack([(d[c] - means[c]) / stds[c] for c in cols])
    yc = y - np.average(y, weights=w)
    W = np.diag(w / w.mean())
    beta = np.linalg.solve(X.T @ W @ X + lam * np.eye(len(cols)), X.T @ W @ yc)
    return {"means": means, "stds": stds,
            "beta": {c: float(b) for c, b in zip(cols, beta)}}


def apply_composite(row: dict, params: dict) -> float:
    return float(sum(params["beta"][c]
                     * (row[c] - params["means"][c]) / params["stds"][c]
                     for c in params["beta"]))
```

- [ ] **Step 4: Tests green, full suite green.** The 10k-resample bootstrap over ~75 cases is a plain python loop over numpy ops — ~5-15 s per candidate is expected at Task 5 time; do not optimize here.

- [ ] **Step 5: Commit** — `git add v2/goalies/portability.py v2/goalies/tests/test_portability.py && git commit -m "feat(goalies): gate statistics and frozen nonswitch params (weighted r, paired bootstrap, K, composite)"`

---

### Task 5: Harness CLI (assemble, freeze, score)

**Files:**
- Modify: `v2/goalies/portability.py` (append `main()` + helpers)

**Interfaces:**
- CLI `python3 v2/goalies/portability.py` runs the full pipeline in this ORDER (pre-registration): (1) load registry, split real vs pseudo; (2) build per-season `shots_xg` (per-season `blind_shot_xg` over the full shots frame, columns per Task 3, `fenwick_flag = event != "blocked-shot"`; xg computed on ALL shots — the model's own definition — and outcome sums taken over fenwick rows); (3) run + cache mid-season refits to `validation/midseason_refits.csv` (`case_id, layer, term`; skip already-cached rows so reruns are cheap); (4) compute pseudo-case estimates, fit K and composite params, write `validation/frozen_params.json`; (5) compute real-case estimates (era-probe verdicts from `era_probe_verdict.json` decide the `normalize` set: verdict `normalize` for `froze` → normalize `freeze` layer; for `rebound_generated` → normalize `rebound`), write `validation/portability_cases.csv` (one row per real case: registry columns + all candidates, baselines, outcome, n_pre, n_post); (6) score the gate table → `validation/gate_table.csv` (rows = stopping, freeze, rebound_control, perf, composite; columns = `dr, lo90, hi90, n_cases, r_cand, r_base_eb, r_base_naive, spearman_cand, incr_beta`), plus the era-B-only sensitivity row for `rebound_control` if its verdict was `sensitivity`.
- Mid-season candidate terms: for `midseason` cases, `term_lookup`'s chained values for the switch season are REPLACED by the cached refit terms (oriented the same way). `prior_terms` for a refit = chained terms from `goalie_terms_<season-1>.csv` per layer (empty dict for 2021).

- [ ] **Step 1: Append `main()` and helpers**

```python
# append to v2/goalies/portability.py
import json  # (top of file with the other imports)

from v2.goalies.gsax_baseline import blind_shot_xg  # (top of file)


def build_shots_xg() -> pd.DataFrame:
    frames = []
    for s in SEASONS:
        shots = pd.read_csv(GEN / f"shots_{s}.csv")
        xg = blind_shot_xg(shots)
        frames.append(pd.DataFrame({
            "season": shots["season"], "game_id": shots["game_id"],
            "goalie_id": shots["goalie_id"], "game_date": shots["game_date"],
            "fenwick_flag": shots["event"] != "blocked-shot",
            "xg": xg, "is_goal": shots["is_goal"],
        }))
    return pd.concat(frames, ignore_index=True)


def load_terms() -> dict[int, pd.DataFrame]:
    return {int(s): pd.read_csv(GEN / f"goalie_terms_{s}.csv") for s in SEASONS}


def run_midseason_refits(cases: pd.DataFrame, terms: dict[int, pd.DataFrame]) -> pd.DataFrame:
    cache_path = VAL / "midseason_refits.csv"
    cached = (pd.read_csv(cache_path) if cache_path.exists()
              else pd.DataFrame(columns=["case_id", "layer", "term"]))
    done = set(cached["case_id"])
    rows = list(cached.to_dict("records"))
    todo = cases[(cases["switch_type"] == "midseason") & ~cases["case_id"].isin(done)]
    for _, c in todo.iterrows():
        season = int(c["first_post_season"])
        season_shots = pd.read_csv(GEN / f"shots_{season}.csv")
        prev = terms.get(season - 1)
        prior_terms = {}
        if prev is not None:
            for layer in CAND_LAYERS:
                lf = prev[prev["layer"] == layer]
                prior_terms[layer] = dict(zip(lf["goalie_id"], lf["term"]))
        refit = midseason_refit(season_shots, int(c["goalie_id"]),
                                c["switch_date"], prior_terms)
        rows.extend({"case_id": c["case_id"], "layer": layer, "term": t}
                    for layer, t in refit.items())
        print(f"refit {c['case_id']}: " +
              " ".join(f"{l}={t:+.3f}" for l, t in refit.items()))
    out = pd.DataFrame(rows)
    out.to_csv(cache_path, index=False)
    return out


def case_estimates(cases: pd.DataFrame, shots_xg: pd.DataFrame, gg: pd.DataFrame,
                   terms: dict[int, pd.DataFrame], ledger_dated: pd.DataFrame,
                   normalize: set[str], refits: pd.DataFrame, k: float | None) -> pd.DataFrame:
    rows = []
    for _, c in cases.iterrows():
        case = c.to_dict()
        oc = case_outcome(case, shots_xg, gg)
        if oc is None:
            continue
        pg = pre_gsax(case, shots_xg)
        cand = term_lookup(case, terms, normalize)
        if case["switch_type"] == "midseason":
            mine = refits[refits["case_id"] == case["case_id"]]
            for layer in CAND_LAYERS:
                row = mine[mine["layer"] == layer]
                if len(row):
                    cand[CAND_NAME[layer]] = float(ORIENT[layer] * row["term"].iloc[0])
        rows.append({**case, **oc, **pg, **cand,
                     "perf": pre_perf(case, ledger_dated),
                     "baseline_naive": pg["naive_rate"],
                     **({"baseline_eb": eb_rate(pg["gsax_sum"], pg["n_pre"], k)}
                        if k is not None else {})})
    return pd.DataFrame(rows)


def main() -> None:
    VAL.mkdir(parents=True, exist_ok=True)
    registry = pd.read_csv(VAL / "switch_registry.csv")
    real = registry[registry["switch_type"] != "nonswitch"].reset_index(drop=True)
    pseudo_reg = registry[registry["switch_type"] == "nonswitch"].reset_index(drop=True)
    verdicts = json.loads((VAL / "era_probe_verdict.json").read_text())
    normalize = set()
    if verdicts["froze"] == "normalize":
        normalize.add("freeze")
    if verdicts["rebound_generated"] == "normalize":
        normalize.add("rebound")

    shots_xg = build_shots_xg()
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    terms = load_terms()
    ledger_dated = pd.read_csv(GEN / "game_ledger.csv").merge(
        gg[["season", "game_id", "goalie_id", "game_date"]],
        on=["season", "game_id", "goalie_id"], how="left")
    refits = run_midseason_refits(real, terms)

    # (4) frozen params from pseudo-cases ONLY, before any real case is scored
    pseudo = case_estimates(pseudo_reg, shots_xg, gg, terms, ledger_dated,
                            normalize, refits, k=None)
    k = fit_k(pseudo)
    pseudo["baseline_eb"] = pseudo.apply(
        lambda r: eb_rate(r["gsax_sum"], r["n_pre"], k), axis=1)
    comp = fit_composite(pseudo)
    (VAL / "frozen_params.json").write_text(json.dumps(
        {"k": k, "composite": comp, "normalize": sorted(normalize)}, indent=2))

    # (5) real cases
    cases = case_estimates(real, shots_xg, gg, terms, ledger_dated,
                           normalize, refits, k=float(k))
    cases["composite"] = cases.apply(
        lambda r: (apply_composite(r.to_dict(), comp)
                   if not any(np.isnan(r[c]) for c in comp["beta"]) else np.nan),
        axis=1)
    cases.to_csv(VAL / "portability_cases.csv", index=False)

    # (6) gate table
    y, w = cases["outcome"], cases["weight"]
    base = cases["baseline_eb"]
    gate = []
    for cand_col in ("stopping", "freeze", "rebound_control", "perf", "composite"):
        boot = paired_bootstrap_dr(cases[cand_col], base, y, w)
        gate.append({"candidate": cand_col, **boot,
                     "r_cand": weighted_r(cases[cand_col], y, w),
                     "r_base_eb": weighted_r(base, y, w),
                     "r_base_naive": weighted_r(cases["baseline_naive"], y, w),
                     "spearman_cand": weighted_spearman(cases[cand_col], y, w),
                     "incr_beta": incremental_beta(cases[cand_col], base, y, w)})
    if verdicts["rebound_generated"] == "sensitivity":
        eb = cases[(cases["last_pre_season"] >= 2023)
                   & (cases["first_post_season"] >= 2023)]
        boot = paired_bootstrap_dr(eb["rebound_control"], eb["baseline_eb"],
                                   eb["outcome"], eb["weight"])
        gate.append({"candidate": "rebound_control_eraB", **boot,
                     "r_cand": weighted_r(eb["rebound_control"], eb["outcome"], eb["weight"]),
                     "r_base_eb": weighted_r(eb["baseline_eb"], eb["outcome"], eb["weight"]),
                     "r_base_naive": np.nan,
                     "spearman_cand": weighted_spearman(eb["rebound_control"], eb["outcome"], eb["weight"]),
                     "incr_beta": np.nan})
    gate_df = pd.DataFrame(gate)
    gate_df.to_csv(VAL / "gate_table.csv", index=False)
    print(f"K={k}, normalize={sorted(normalize)}, {len(cases)} real cases scored")
    print(gate_df.to_string(index=False))


if __name__ == "__main__":
    main()
```

Sensitivity-row note: for era-B-only, spec 6c says use `term_indep` of the last pre season, not the chained `term`. Implement by having `case_estimates` also emit a `rebound_control_indep` column for every case (same lookup as `term_lookup`'s rebound branch but reading `term_indep`, same −1 orientation, same normalize rule), and use `eb["rebound_control_indep"]` — not `eb["rebound_control"]` — in the sensitivity row's bootstrap and correlations. The gate-block code above shows `rebound_control`; apply this substitution when the sensitivity branch is live.

- [ ] **Step 2: Run the CLI.** Expected runtime: 5 season xg fits (~1 min) + ~10–20 mid-season refits × 3 layers × ~10 s (~5–10 min, cached thereafter) + 6 bootstraps (~1 min). Anchors:
  - Frozen K expected in the 1000–4000 range (GSAx is noise-dominated → heavy shrinkage wins on pseudo-cases). K=250 would be suspicious — report it prominently if so.
  - `r_base_naive` expected weakly positive (~0.0–0.2, the r≈0.12 literature family); `r_base_eb` ≥ `r_base_naive` is expected but not guaranteed at this n.
  - Honest prior on the gate: NO candidate's CI excludes zero. If one does, that is the headline — double-check its column for leakage (the two known traps: a mid-season case whose refit silently failed back to the contaminated chained term, and pseudo-case rows leaking into the real-case frame).
  - Every real case must have `n_post` > 0 and non-NaN `baseline_eb`; report the count of cases with NaN candidates (goalies absent from a layer).
- [ ] **Step 3: Full suite** — `python3 -m pytest v2/ -q` green (no new tests this task; the CLI is orchestration over Task 3/4-tested functions).
- [ ] **Step 4: Commit** — `git add v2/goalies/portability.py && git commit -m "feat(goalies): portability harness CLI (frozen params, case scoring, gate table)"`

---

### Task 6: Repeatability suite + tandem table

**Files:**
- Create: `v2/goalies/repeatability.py`
- Test: `v2/goalies/tests/test_repeatability.py`

**Interfaces:**
- Produces: `component_repeatability(terms: dict[int, pd.DataFrame], min_shots: int = 500) -> pd.DataFrame` — per (layer, season_pair): weighted r of `term_indep` across consecutive seasons (goalies present both seasons with `n_shots >= min_shots` in both; weight = min of the two `n_shots`). Uses `term_indep` (independent fits) — chained terms would mechanically inflate repeatability. `tandem_table(gg, shots_xg, terms) -> pd.DataFrame` — per team-season with ≥2 goalies of ≥600 fenwick: top-2 goalies by fenwick, columns `season, team, goalie_hi, goalie_lo, gsax_gap` (fenwick gsax-rate difference, hi−lo by gsax rate), `term_gap` (goal-layer `term_indep` difference, same orientation), `b2b_share_hi, b2b_share_lo` (share of each goalie's games on a day after ANY team game — from goalie-game dates of all that team's goalies). CLI writes `validation/repeatability.csv` + `validation/tandem_table.csv`.
- Consumes: `goalie_terms_<season>.csv`, `goalie_games_<season>.csv`, and Task 5's `build_shots_xg()` (imported from `portability`).

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_repeatability.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.repeatability import component_repeatability, tandem_table


def test_component_repeatability_perfect_and_filtered():
    terms = {
        2023: pd.DataFrame({"goalie_id": [1, 2, 3, 4], "layer": ["freeze"] * 4,
                            "term_indep": [0.3, 0.1, -0.1, 5.0],
                            "n_shots": [1000, 1000, 1000, 100]}),
        2024: pd.DataFrame({"goalie_id": [1, 2, 3, 4], "layer": ["freeze"] * 4,
                            "term_indep": [0.6, 0.2, -0.2, -5.0],
                            "n_shots": [1000, 1000, 1000, 100]}),
    }
    r = component_repeatability(terms)
    row = r[(r["layer"] == "freeze") & (r["pair"] == "2023-2024")].iloc[0]
    assert row["r"] == pytest.approx(1.0)       # goalie 4 under min_shots, excluded
    assert row["n_goalies"] == 3


def test_tandem_table_pairs_and_b2b():
    gg = pd.DataFrame({
        "season": [2023] * 6, "game_id": [1, 2, 3, 1, 2, 3],
        "goalie_id": [1, 1, 2, 3, 3, 3],
        "team_abbrev": ["EDM", "EDM", "EDM", "CGY", "CGY", "CGY"],
        "game_date": ["2023-11-01", "2023-11-02", "2023-11-03"] * 2,
    })
    shots_xg = pd.DataFrame({
        "season": [2023] * 4, "game_id": [1, 3, 1, 2], "goalie_id": [1, 2, 3, 3],
        "game_date": ["2023-11-01", "2023-11-03", "2023-11-01", "2023-11-02"],
        "fenwick_flag": [True] * 4, "xg": [0.1] * 4,
        "is_goal": [False, True, False, False],
    })
    terms = {2023: pd.DataFrame({"goalie_id": [1, 2], "layer": ["goal"] * 2,
                                 "term_indep": [-0.2, 0.3], "n_shots": [900, 800]})}
    t = tandem_table(gg, shots_xg, terms, min_fenwick=1)
    edm = t[t["team"] == "EDM"].iloc[0]         # CGY has one goalie -> excluded
    assert len(t) == 1
    assert edm["gsax_gap"] > 0                   # goalie 1 saved, goalie 2 scored on
    # goalie 1 played 11-02, day after team game 11-01 -> b2b share 0.5
    assert edm["b2b_share_hi"] == pytest.approx(0.5)
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# v2/goalies/repeatability.py
"""P6 secondary suite: component repeatability + tandem sanity table.

Repeatability uses term_indep (independent per-season fits) — chained terms
carry information across seasons by construction and would inflate r.
Anchors (report, don't assert): freeze ~ 0.58+, stopping ~ 0.12.

Usage: python3 v2/goalies/repeatability.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.portability import weighted_r  # noqa: E402

GEN = ROOT / "data" / "generated" / "goalies"
VAL = GEN / "validation"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
LAYER_LIST = ("onnet", "freeze", "goal", "rebound")


def component_repeatability(terms: dict[int, pd.DataFrame],
                            min_shots: int = 500) -> pd.DataFrame:
    rows = []
    seasons = sorted(terms)
    for layer in LAYER_LIST:
        for a, b in zip(seasons, seasons[1:]):
            ta = terms[a][(terms[a]["layer"] == layer)
                          & (terms[a]["n_shots"] >= min_shots)]
            tb = terms[b][(terms[b]["layer"] == layer)
                          & (terms[b]["n_shots"] >= min_shots)]
            m = ta.merge(tb, on="goalie_id", suffixes=("_a", "_b"))
            if len(m) < 3:
                continue
            w = np.minimum(m["n_shots_a"], m["n_shots_b"])
            rows.append({"layer": layer, "pair": f"{a}-{b}",
                         "r": weighted_r(m["term_indep_a"], m["term_indep_b"], w),
                         "n_goalies": len(m)})
    return pd.DataFrame(rows)


def tandem_table(gg: pd.DataFrame, shots_xg: pd.DataFrame,
                 terms: dict[int, pd.DataFrame], min_fenwick: int = 600) -> pd.DataFrame:
    fen = shots_xg[shots_xg["fenwick_flag"]]
    per_goalie = fen.groupby(["season", "goalie_id"]).agg(
        n=("xg", "size"), xga=("xg", "sum"), ga=("is_goal", "sum")).reset_index()
    per_goalie["gsax_rate"] = (per_goalie["xga"] - per_goalie["ga"]) / per_goalie["n"]
    team_of = gg.groupby(["season", "goalie_id"])["team_abbrev"].agg(
        lambda s: s.mode().iloc[0]).rename("team").reset_index()
    per_goalie = per_goalie.merge(team_of, on=["season", "goalie_id"])
    rows = []
    for (season, team), grp in per_goalie.groupby(["season", "team"]):
        grp = grp[grp["n"] >= min_fenwick].sort_values("n", ascending=False)
        if len(grp) < 2:
            continue
        pair = grp.head(2).sort_values("gsax_rate", ascending=False)
        hi, lo = pair.iloc[0], pair.iloc[1]
        tframe = terms.get(season)
        goal_terms = (tframe[tframe["layer"] == "goal"].set_index("goalie_id")
                      if tframe is not None else None)

        def _term(gid):
            if goal_terms is None or gid not in goal_terms.index:
                return np.nan
            return -float(goal_terms.loc[gid, "term_indep"])   # orient: higher=better

        team_dates = set(gg[(gg["season"] == season)
                            & (gg["team_abbrev"] == team)]["game_date"])

        def _b2b_share(gid):
            mine = gg[(gg["season"] == season) & (gg["goalie_id"] == gid)
                      & (gg["team_abbrev"] == team)]["game_date"]
            prev = (pd.to_datetime(mine) - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
            return float(prev.isin(team_dates).mean()) if len(mine) else np.nan

        rows.append({"season": season, "team": team,
                     "goalie_hi": int(hi["goalie_id"]), "goalie_lo": int(lo["goalie_id"]),
                     "gsax_gap": float(hi["gsax_rate"] - lo["gsax_rate"]),
                     "term_gap": _term(int(hi["goalie_id"])) - _term(int(lo["goalie_id"])),
                     "b2b_share_hi": _b2b_share(int(hi["goalie_id"])),
                     "b2b_share_lo": _b2b_share(int(lo["goalie_id"]))})
    return pd.DataFrame(rows)


def main() -> None:
    from v2.goalies.portability import build_shots_xg, load_terms
    VAL.mkdir(parents=True, exist_ok=True)
    terms = load_terms()
    rep = component_repeatability(terms)
    rep.to_csv(VAL / "repeatability.csv", index=False)
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    tandem = tandem_table(gg, build_shots_xg(), terms)
    tandem.to_csv(VAL / "tandem_table.csv", index=False)
    print(rep.to_string(index=False))
    print(f"\ntandem pairs: {len(tandem)}; "
          f"corr(gsax_gap, term_gap) = "
          f"{weighted_r(tandem['gsax_gap'], tandem['term_gap'], np.ones(len(tandem))):+.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests green, run the CLI.** Anchors (report, don't assert): freeze pair r in the 0.55–0.85 band (P3 found 0.60–0.80); goal pair r near 0.1; onnet/rebound between. Tandem: expect ~60–120 pairs over 5 seasons; corr(gsax_gap, term_gap) strongly positive (same-season terms fit the same goals — this is a consistency check, not skill evidence; the report must label it so).
- [ ] **Step 5: Full suite, commit** — `git add v2/goalies/repeatability.py v2/goalies/tests/test_repeatability.py && git commit -m "feat(goalies): repeatability suite and tandem table"`

---

### Task 7: P6 report + suite

**Files:**
- Create: `v2/goalies/report_p6.py` (no test — report script over tested computations)

**Interfaces:** CLI writing `data/generated/goalies/validation/p6_report.txt` (follow the shape of `v2/goalies/report_p4p5.py`): (1) era-probe verdicts + coefficients; (2) registry summary (real cases by type, weight distribution, floor/fallback note); (3) frozen params (K, composite betas, normalize set); (4) THE GATE TABLE with a plain-language reading per row (CI excludes 0 or not) and the mandatory multiplicity caveat sentence: five candidate families were tested; a single nominal CI exclusion among five is weak evidence; (5) literature anchor line (`r_base_naive` vs the r≈0.12 family); (6) repeatability table vs anchors + tandem summary with its consistency-check caveat; (7) honest-null framing per spec §7: a null with tight CIs is a valid program outcome.

- [ ] **Step 1: Write the report script** — pandas over `validation/*.csv` + the two JSONs; print and write.
- [ ] **Step 2: Run it.** Verify every number in the report traces to a CSV the harness wrote (no recomputation in the report script beyond formatting).
- [ ] **Step 3: Full suite** — `python3 -m pytest v2/ -q` all green.
- [ ] **Step 4: Commit** — `git add v2/goalies/report_p6.py && git commit -m "feat(goalies): P6 report"`

---

## After this plan

Deliverables oiler reviews: `p6_report.txt` (the phase-gate artifact), `gate_table.csv`, `portability_cases.csv` (spot-check goalies he knows switched), `era_probe_report.txt`. The §7 P6 phase gate reads on the gate table: does anything beat GSAx on portability? Per the spec, a well-measured null is a success criterion. After oiler's gate reading: either a follow-up phase (winning-candidate deepening or the B-approach personnel terms) or the browser-layer integration of the validated metrics.
