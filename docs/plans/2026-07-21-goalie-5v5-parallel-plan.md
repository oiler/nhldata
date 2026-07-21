# Goalie 5v5 Parallel Workstream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a strict-5v5 (`situationCode == "1551"`) parallel cut of the goalie pipeline — full descriptive parity in the browser behind an "All situations / 5v5" dropdown, plus the three pre-registered research re-checks (portability, repeatability, freeze×strength).

**Architecture:** One additive column (`situation_code`) in the shared shot extract; a tiny `v2/goalies/cut.py` module gives every pipeline script a `--situation 5v5` flag that filters input shots and redirects output to a mirrored `data/generated/goalies/5v5/` subtree. `goalies.db` gains a `situation` column on all four tables; the browser gets one global dropdown. Research re-runs are parameterized editions of the existing P6 harness, gated by a pre-registration addendum written before any result is computed.

**Tech Stack:** Python 3 / pandas / numpy / sqlite3 / Plotly Dash. No new dependencies.

**Spec:** `docs/plans/2026-07-21-goalie-5v5-parallel-design.md` (approved 2026-07-21).

## Global Constraints

- **Precondition (before Task 5):** oiler's in-progress notes work (`v2/browser/app.py`, `v2/browser/assets/style.css`, `v2/browser/pages/note.py`, `v2/browser/pages/notes.py`, `v2/browser/notes/` are uncommitted on master). Tasks 5–7 edit `app.py` and pages — oiler must commit or stash that work first, and execution happens on a fresh feature branch (`goalie-5v5`). **Halt and ask if `git status` still shows those files modified when Task 5 starts.**
- Git: local commits on the feature branch only; never push; never touch master/main. Stage ONLY the files named in each task's commit step — never `git add -A` or `git add .`.
- Never commit anything under `data/` (pipeline outputs are rebuilt, not versioned).
- Strict 5v5 = `situationCode "1551"` exactly. `1441`, `0551`, 3v3 etc. are excluded. ONE slice — no other strength slices anywhere, regardless of results.
- All existing all-situations outputs stay byte-identical: no default-behavior change in any script. Task 3 verifies this with a before/after diff of `gsax_2025.csv`.
- Per-goalie 5v5 rates are per-shot/per-save; game- and team-level workload rates keep all-situations TOI as the exposure denominator, labeled "per 60 (total TOI)" / "TOI (all situations)" in 5v5 UI (spec §2).
- Research ordering: the pre-registration addendum (Task 8 Step 1) MUST be committed before any 5v5 research output (registry, portability, repeatability) is computed.
- Run `python -m pytest v2/ -v` (288 tests currently green) before declaring any task complete that touches code.
- No hard-wrapped markdown in any doc this plan produces.

---

### Task 1: `situation_code` column in the shot extract + shots rebuild

**Files:**
- Modify: `v2/goalies/extract.py:87` (row dict)
- Test: `v2/goalies/tests/test_extract.py`

**Interfaces:**
- Produces: every `data/generated/goalies/shots_<season>.csv` gains a `situation_code` column (4-char string, e.g. `"1551"`, `"0551"`). All existing columns/rows unchanged. Consumed by Task 2's `filter_cut`/`load_shots`.

- [ ] **Step 1: Write the failing test** — append to `v2/goalies/tests/test_extract.py`:

```python
def test_situation_code_carried_through():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal"),
        _play("shot-on-goal", time="06:00", code="1451"),
    ]))
    assert rows[0]["situation_code"] == "1551"
    assert rows[1]["situation_code"] == "1451"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/goalies/tests/test_extract.py::test_situation_code_carried_through -v`
Expected: FAIL with `KeyError: 'situation_code'`

- [ ] **Step 3: Implement** — in `v2/goalies/extract.py`, in the `row = {` dict, directly after the `"strength": ...` line (line 87), add:

```python
                    "situation_code": code,
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest v2/goalies/tests/test_extract.py -v`
Expected: all PASS (new test + existing ones).

- [ ] **Step 5: Snapshot the all-situations invariant baseline** (used by Task 3's regression check):

```bash
mkdir -p /private/tmp/claude-501/-Users-jrf1039-files-projects-nhl/98473687-4ad7-44db-ad18-7f89722cbb64/scratchpad/goalie5v5
cp data/generated/goalies/gsax_2025.csv /private/tmp/claude-501/-Users-jrf1039-files-projects-nhl/98473687-4ad7-44db-ad18-7f89722cbb64/scratchpad/goalie5v5/gsax_2025_baseline.csv
```

- [ ] **Step 6: Rebuild shots CSVs (all five seasons) and re-apply rink adjustment.** `rink_adjust.py` rewrites `shots_*.csv` in place to add `distance_adj` — it MUST run after `build_shots.py`, or every downstream script crashes on the missing column:

```bash
for s in 2021 2022 2023 2024 2025; do python3 v2/goalies/build_shots.py $s; done
python3 v2/goalies/rink_adjust.py
```

Expected: per-season lines like `2025: NNNNN shots, NN goalies, NNNN goals -> ...` with the same counts the files had before (rows unchanged), then `shots_<season>.csv: mean |adjustment| = N.NN ft` lines.

- [ ] **Step 7: Verify the new column survived the round trip:**

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('data/generated/goalies/shots_2025.csv', dtype={'situation_code': str})
assert 'situation_code' in df.columns and 'distance_adj' in df.columns
print(df['situation_code'].value_counts().head())
print('5v5 share:', (df['situation_code'] == '1551').mean().round(3))
"
```

Expected: `1551` dominates (~0.75–0.80 share).

- [ ] **Step 8: Run the full suite:** `python -m pytest v2/ -v` — Expected: 289 passed.

- [ ] **Step 9: Commit**

```bash
git add v2/goalies/extract.py v2/goalies/tests/test_extract.py
git commit -m "feat(goalies): carry situation_code through the shot extract"
```

---

### Task 2: `v2/goalies/cut.py` — situation-cut plumbing

**Files:**
- Create: `v2/goalies/cut.py`
- Test: `v2/goalies/tests/test_cut.py`

**Interfaces:**
- Produces (consumed by Tasks 3, 4, 8, 9, 10):
  - `parse_situation(argv: list[str] | None = None) -> str` — returns `"all"` or `"5v5"` from `--situation`; unknown args ignored (so scripts can add more flags).
  - `gen_dir(situation: str) -> Path` — `GEN` or `GEN / "5v5"`.
  - `filter_cut(df, situation) -> pd.DataFrame` — identity for `"all"`; strict `"1551"` rows (handles str or int dtype) for `"5v5"`.
  - `load_shots(season: str, situation: str, usecols: list[str] | None = None) -> pd.DataFrame` — reads `GEN/shots_<season>.csv` with `situation_code` as string, filters, returns exactly `usecols` when given.
  - Constants: `GEN`, `STRICT_5V5 = "1551"`.

- [ ] **Step 1: Write the failing tests** — create `v2/goalies/tests/test_cut.py`:

```python
import pandas as pd

import v2.goalies.cut as cut
from v2.goalies.cut import GEN, filter_cut, gen_dir, parse_situation


def test_parse_situation_default_flag_and_unknown_args():
    assert parse_situation([]) == "all"
    assert parse_situation(["--situation", "5v5"]) == "5v5"
    assert parse_situation(["--situation", "5v5", "--floor", "500"]) == "5v5"


def test_gen_dir():
    assert gen_dir("all") == GEN
    assert gen_dir("5v5") == GEN / "5v5"


def test_filter_cut_strict_1551_only():
    df = pd.DataFrame({"situation_code": ["1551", "1451", "0551", "1551"],
                       "x": [1, 2, 3, 4]})
    assert list(filter_cut(df, "5v5")["x"]) == [1, 4]


def test_filter_cut_handles_int_codes():
    # a plain read_csv parses "0551" as int 551 — 551 != 1551 so it still drops
    df = pd.DataFrame({"situation_code": [1551, 551, 1441], "x": [1, 2, 3]})
    assert list(filter_cut(df, "5v5")["x"]) == [1]


def test_filter_cut_all_is_identity():
    df = pd.DataFrame({"situation_code": ["1451"], "x": [1]})
    assert filter_cut(df, "all") is df


def test_load_shots_5v5_with_usecols(tmp_path, monkeypatch):
    pd.DataFrame({"season": [2025, 2025], "situation_code": ["1551", "0551"],
                  "is_goal": [False, True]}).to_csv(tmp_path / "shots_2025.csv",
                                                    index=False)
    monkeypatch.setattr(cut, "GEN", tmp_path)
    df = cut.load_shots("2025", "5v5", usecols=["season", "is_goal"])
    assert list(df.columns) == ["season", "is_goal"]
    assert len(df) == 1 and not bool(df["is_goal"].iloc[0])


def test_load_shots_all_keeps_every_row(tmp_path, monkeypatch):
    pd.DataFrame({"season": [2025, 2025], "situation_code": ["1551", "0551"],
                  "is_goal": [False, True]}).to_csv(tmp_path / "shots_2025.csv",
                                                    index=False)
    monkeypatch.setattr(cut, "GEN", tmp_path)
    assert len(cut.load_shots("2025", "all")) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest v2/goalies/tests/test_cut.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'v2.goalies.cut'`

- [ ] **Step 3: Implement** — create `v2/goalies/cut.py`:

```python
"""Situation-cut plumbing for the parallel strict-5v5 pipeline.

The all-situations pipeline is the default; `--situation 5v5` filters the
shared shots CSVs to situationCode 1551 and redirects outputs to GEN/5v5.
Shared inputs that are not shot-derived (goalie_games TOI, wp_table) always
come from the parent GEN dir regardless of cut.
"""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
STRICT_5V5 = "1551"


def parse_situation(argv: list[str] | None = None) -> str:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--situation", choices=("all", "5v5"), default="all")
    return p.parse_known_args(argv)[0].situation


def gen_dir(situation: str) -> Path:
    return GEN / "5v5" if situation == "5v5" else GEN


def filter_cut(df: pd.DataFrame, situation: str) -> pd.DataFrame:
    if situation == "all":
        return df
    mask = df["situation_code"].astype(str) == STRICT_5V5
    return df[mask].reset_index(drop=True)


def load_shots(season: str, situation: str,
               usecols: list[str] | None = None) -> pd.DataFrame:
    cols = usecols
    if cols is not None and situation == "5v5" and "situation_code" not in cols:
        cols = [*cols, "situation_code"]
    df = pd.read_csv(GEN / f"shots_{season}.csv", usecols=cols,
                     dtype={"situation_code": str})
    df = filter_cut(df, situation)
    if usecols is not None and "situation_code" not in usecols:
        df = df.drop(columns="situation_code", errors="ignore")
    return df[usecols] if usecols is not None else df
```

(The final `df[usecols]` reorder matters: `read_csv` + `usecols` returns file order, not request order, and Task 4 relies on exact column lists.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest v2/goalies/tests/test_cut.py -v`
Expected: 7 passed. If `test_load_shots_5v5_with_usecols` fails with a pandas `ValueError` about dtype keys not in `usecols`, wrap the dtype: `dtype={"situation_code": str} if (cols is None or "situation_code" in cols) else None`.

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/cut.py v2/goalies/tests/test_cut.py
git commit -m "feat(goalies): cut.py situation-cut plumbing for parallel 5v5 pipeline"
```

---

### Task 3: Parameterize the six pipeline scripts + run the 5v5 build

**Files:**
- Modify: `v2/goalies/gsax_baseline.py:43-49`, `v2/goalies/build_terms.py:42-63`, `v2/goalies/game_difficulty.py:60-71`, `v2/goalies/game_ledger.py:38-53`, `v2/goalies/environment.py:64-80`, `v2/goalies/freeze_value.py:121-236`

**Interfaces:**
- Consumes: Task 2's `parse_situation`, `gen_dir`, `load_shots`.
- Produces: `data/generated/goalies/5v5/` containing `gsax_<season>.csv`, `goalie_terms_<season>.csv`, `structure_coefs_<season>.csv`, `game_difficulty.csv`, `game_ledger.csv`, `team_environment.csv`, `arena_freeze_offsets.csv`, `validation/freeze_value.json`, `validation/freeze_value_report.txt` — identical schemas to the parent dir. `freeze_value._load_saves_and_shots(situation="all")` keeps its zero-arg call meaning for Task 11.
- Library functions (`gsax_table`, `blind_shot_xg`, `fit_layer`, `ledger_rows`, `game_rows`, `team_environment`, `freeze_effect`, `window_xga`, `ridge_linear`) are untouched — only `main()`s and module I/O change.

Only `main()` functions change (plus one loader in `freeze_value.py`). Shared-input rules, applied consistently: `goalie_games_<season>.csv` and `wp_table.csv` are always read from the parent `GEN` (TOI and the win-probability table are game-state objects, not shot-cut objects — WP estimated on a 5v5-only shot stream would be conceptually wrong and noisier). `leverage.py` is therefore NOT parameterized.

- [ ] **Step 1: `gsax_baseline.py`** — add to the imports block (after the `irls` import): `from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402` and replace `main()`:

```python
def main() -> None:
    situation = parse_situation()
    out = gen_dir(situation)
    out.mkdir(parents=True, exist_ok=True)
    for season in SEASONS:
        df = load_shots(season, situation)
        table = gsax_table(df)
        table.to_csv(out / f"gsax_{season}.csv", index=False)
        print(f"{season}: gsax for {len(table)} goalies "
              f"(league xga {table['xga'].sum():.0f} vs ga {table['ga'].sum()})")
```

- [ ] **Step 2: `build_terms.py`** — add import `from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402` and replace `main()`'s first line and the output block:

```python
def main() -> None:
    situation = parse_situation()
    out = gen_dir(situation)
    out.mkdir(parents=True, exist_ok=True)
    season_dfs = {s: load_shots(s, situation) for s in SEASONS}
    per_season_terms = {s: [] for s in SEASONS}
    structure_rows = {s: [] for s in SEASONS}

    for layer in LAYERS:
        chained = chain_seasons(season_dfs, layer)
        for season, terms in chained.items():
            per_season_terms[season].append(terms.assign(layer=layer))
        for season, df in season_dfs.items():
            fit = fit_layer(df, layer, include_goalies=False)
            structure_rows[season].extend(
                {"layer": layer, "feature": f, "coef": c}
                for f, c in fit.structure.items())

    for season in SEASONS:
        pd.concat(per_season_terms[season], ignore_index=True)[
            ["goalie_id", "layer", "term", "se", "n_shots", "term_indep", "se_indep"]
        ].to_csv(out / f"goalie_terms_{season}.csv", index=False)
        pd.DataFrame(structure_rows[season]).to_csv(
            out / f"structure_coefs_{season}.csv", index=False)
        print(f"{season}: terms + structure written")
```

- [ ] **Step 3: `game_difficulty.py`** — add (after the existing imports) `from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402` and replace `main()`:

```python
def main() -> None:
    situation = parse_situation()
    out = gen_dir(situation)
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for season in SEASONS:
        shots = load_shots(season, situation)
        toi = pd.read_csv(GEN / f"goalie_games_{season}.csv")   # TOI: shared, all-situations
        frames.append(game_rows(shots, blind_shot_xg(shots), toi))
    games = add_difficulty_pct(pd.concat(frames, ignore_index=True))
    games.to_csv(out / "game_difficulty.csv", index=False)
    e = games[games["difficulty_pct"].notna()]
    print(f"{len(games)} goalie-games ({len(e)} eligible); "
          f"xg_per60 median {e['xg_per60'].median():.2f}, "
          f"p10 {e['xg_per60'].quantile(.1):.2f}, p90 {e['xg_per60'].quantile(.9):.2f}")
```

(In 5v5 mode `xg_per60` is 5v5 xG per 60 of total TOI — the spec §2 exposure rule; no code change, the denominator is already `toi_s`.)

- [ ] **Step 4: `game_ledger.py`** — add `from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402` after the leverage import, and replace `main()`:

```python
def main() -> None:
    situation = parse_situation()
    out = gen_dir(situation)
    out.mkdir(parents=True, exist_ok=True)
    wp = pd.read_csv(GEN / "wp_table.csv")   # WP is a game-state object: shared across cuts
    frames = []
    for season in SEASONS:
        shots = load_shots(season, situation)
        xg = blind_shot_xg(shots)
        lev = leverage_weight_vectorized(shots, wp)
        frames.append(ledger_rows(shots, xg, lev))
    ledger = pd.concat(frames, ignore_index=True)
    diff = pd.read_csv(out / "game_difficulty.csv")[
        ["season", "game_id", "goalie_id", "difficulty_pct", "xg_per60", "toi_s"]]
    ledger = ledger.merge(diff, on=["season", "game_id", "goalie_id"], how="left")
    ledger["gsax_per60"] = ledger["gsax_game"] * 3600 / ledger["toi_s"]
    ledger.to_csv(out / "game_ledger.csv", index=False)
    print(f"{len(ledger)} goalie-games; mean perf_z {ledger['perf_z'].mean():+.3f} "
          f"(should be ~0); mean lev_value {ledger['lev_value'].mean():+.4f}")
```

- [ ] **Step 5: `environment.py`** — this module has no `sys.path` insert; add one so the `cut` import works. After the `ROOT = ...` line add:

```python
import sys
sys.path.insert(0, str(ROOT))
from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402
```

and replace `main()`:

```python
def main() -> None:
    situation = parse_situation()
    out = gen_dir(situation)
    out.mkdir(parents=True, exist_ok=True)
    games = pd.read_csv(out / "game_difficulty.csv")
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    shots = pd.concat([load_shots(s, situation) for s in SEASONS], ignore_index=True)
    env = team_environment(games, gg, shots)
    env.to_csv(out / "team_environment.csv", index=False)
    offs = arena_freeze_offsets(shots)
    offs.to_csv(out / "arena_freeze_offsets.csv", index=False)
    print(f"env rows: {len(env)}")
    print(f"b2b_games range: {env['b2b_games'].min()}-{env['b2b_games'].max()}")
    print(env.sort_values("mean_xg_faced_per60").tail(5).to_string(index=False))
    print(f"arena freeze offsets: max |offset| = {offs['freeze_offset'].abs().max():.3f}")
    over_03 = offs[offs["freeze_offset"].abs() > 0.03].sort_values(
        "freeze_offset", key=lambda s: s.abs(), ascending=False)
    if len(over_03):
        print("arenas with |offset| > 0.03:")
        print(over_03.to_string(index=False))
```

- [ ] **Step 6: `freeze_value.py`** — add `from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402` after the portability import. Change the loader to accept a situation (default keeps Task 11's pooled call working):

```python
def _load_saves_and_shots(situation: str = "all"):
    frames = []
    for season in SEASONS:
        shots = load_shots(season, situation)
        shots["xg"] = blind_shot_xg(shots)
        frames.append(shots)
    return pd.concat(frames, ignore_index=True)
```

In `main()`, replace the first two lines with:

```python
def main() -> None:
    situation = parse_situation()
    val = gen_dir(situation) / "validation"
    val.mkdir(parents=True, exist_ok=True)
    shots = _load_saves_and_shots(situation)
```

and replace every later `VAL /` in `main()` with `val /` (two sites: `freeze_value_report.txt`, `freeze_value.json`). The module-level `VAL` constant stays (other code imports the module; nothing else uses `VAL`).

- [ ] **Step 7: All-situations invariance check** — rerun the default path and diff against Task 1's baseline:

```bash
python3 v2/goalies/gsax_baseline.py
diff data/generated/goalies/gsax_2025.csv /private/tmp/claude-501/-Users-jrf1039-files-projects-nhl/98473687-4ad7-44db-ad18-7f89722cbb64/scratchpad/goalie5v5/gsax_2025_baseline.csv && echo IDENTICAL
```

Expected: `IDENTICAL`. If not, STOP — the default path changed behavior; find and fix before proceeding.

- [ ] **Step 8: Run the 5v5 build** (order matters — difficulty before ledger, ledger before environment reads nothing but difficulty; freeze_value last is convention):

```bash
python3 v2/goalies/gsax_baseline.py --situation 5v5
python3 v2/goalies/build_terms.py --situation 5v5
python3 v2/goalies/game_difficulty.py --situation 5v5
python3 v2/goalies/game_ledger.py --situation 5v5
python3 v2/goalies/environment.py --situation 5v5
python3 v2/goalies/freeze_value.py --situation 5v5
```

Expected: each prints its normal summary with ~75–80% of the pooled shot counts; `data/generated/goalies/5v5/` contains all files listed in Interfaces. Note the 5v5 freeze-value coef and `significant` flag in the task report — if `significant` is false, `freeze_value.json` carries `per_freeze_xga_delta: null` and the browser will (correctly) drop the freeze-impact line in 5v5 mode.

- [ ] **Step 9: Full suite:** `python -m pytest v2/ -v` — Expected: all pass (existing script tests exercise the library functions, which are unchanged).

- [ ] **Step 10: Commit**

```bash
git add v2/goalies/gsax_baseline.py v2/goalies/build_terms.py v2/goalies/game_difficulty.py v2/goalies/game_ledger.py v2/goalies/environment.py v2/goalies/freeze_value.py
git commit -m "feat(goalies): --situation 5v5 flag across the descriptive pipeline"
```

---

### Task 4: `goalies.db` situation dimension + sync guard

**Files:**
- Modify: `v2/browser/build_goalies_db.py`
- Modify: `tools/sync-runtime-data.sh`
- Test: `v2/browser/tests/test_build_goalies_db.py` (existing tests must stay green unchanged — `build_goalie_seasons`'s signature does not change)

**Interfaces:**
- Consumes: Task 3's `data/generated/goalies/5v5/` subtree; Task 2's `load_shots`.
- Produces: `goalies.db` tables `goalie_seasons`, `goalie_games`, `team_environment`, `freeze_value` each gain a `situation` TEXT column with values `'all'` / `'5v5'`. Existing column set otherwise unchanged. Consumed by Tasks 5–7 via `WHERE situation = ?`.

- [ ] **Step 1: Rewrite `main()` in `v2/browser/build_goalies_db.py`.** Add near the top (after `REPO = ...`):

```python
import sys
sys.path.insert(0, str(REPO))
from v2.goalies.cut import load_shots  # noqa: E402

SITUATIONS = ("all", "5v5")
```

Replace `main()`:

```python
def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    season_frames, game_frames, env_frames, fv_frames = [], [], [], []
    for situation in SITUATIONS:
        src = GOALIES / "5v5" if situation == "5v5" else GOALIES
        ledger = pd.read_csv(src / "game_ledger.csv")
        for season in SEASONS:
            # gp/toi/teams are all-situations by design (spec §2) — shared source
            gg = pd.read_csv(GOALIES / f"goalie_games_{season}.csv")
            gsax = pd.read_csv(src / f"gsax_{season}.csv")
            shots = load_shots(season, situation,
                               usecols=["season", "goalie_id", "on_net", "is_goal", "froze"])
            terms = pd.read_csv(src / f"goalie_terms_{season}.csv")
            led = ledger[ledger["season"] == int(season)]
            gs = build_goalie_seasons(gg, gsax, shots, terms, led)
            gs["name"] = [(_name(season, g)) for g in gs["goalie_id"]]
            season_frames.append(gs.assign(situation=situation))

            games = led.merge(
                gg[["season", "game_id", "goalie_id", "game_date", "opp_abbrev"]],
                on=["season", "game_id", "goalie_id"], how="left")
            game_frames.append(games.assign(situation=situation))

        env_frames.append(pd.read_csv(src / "team_environment.csv")
                          .assign(situation=situation))
        fv_path = src / "validation" / "freeze_value.json"
        fv = json.loads(fv_path.read_text()) if fv_path.exists() else {"per_freeze_xga_delta": None}
        rows = ([] if fv.get("per_freeze_xga_delta") is None
                else [{"per_freeze_xga_delta": fv["per_freeze_xga_delta"],
                       "window_s": fv.get("window_s", 30), "situation": situation}])
        fv_frames.append(pd.DataFrame(
            rows, columns=["per_freeze_xga_delta", "window_s", "situation"]))

    conn = sqlite3.connect(str(OUT))
    try:
        pd.concat(season_frames, ignore_index=True).to_sql(
            "goalie_seasons", conn, if_exists="replace", index=False)
        pd.concat(game_frames, ignore_index=True).to_sql(
            "goalie_games", conn, if_exists="replace", index=False)
        pd.concat(env_frames, ignore_index=True).to_sql(
            "team_environment", conn, if_exists="replace", index=False)
        pd.concat(fv_frames, ignore_index=True).to_sql(
            "freeze_value", conn, if_exists="replace", index=False)
    finally:
        conn.close()
    n_seasons = sum(len(f) for f in season_frames)
    n_games = sum(len(f) for f in game_frames)
    print(f"goalies.db: {n_seasons} goalie-seasons, {n_games} goalie-games, "
          f"freeze_value rows={sum(len(f) for f in fv_frames)} "
          f"(situations: {', '.join(SITUATIONS)})")
```

Notes: `_name`'s cache persists across the two cut passes (same names — fine). Goalie-games with zero 5v5 shots faced have no 5v5 ledger row and simply don't appear in the 5v5 cut — expected, not a bug. Freeze percentiles are computed inside `build_goalie_seasons` per call, so 5v5 percentiles rank only against 5v5 rates automatically.

- [ ] **Step 2: Run existing tests** — `python -m pytest v2/browser/tests/test_build_goalies_db.py -v` — Expected: PASS unchanged (the refactor didn't touch the tested functions).

- [ ] **Step 3: Build and verify the db:**

```bash
python3 v2/browser/build_goalies_db.py
sqlite3 data/generated/browser/goalies.db "SELECT situation, COUNT(*) FROM goalie_seasons GROUP BY situation; SELECT situation, COUNT(*) FROM goalie_games GROUP BY situation; SELECT situation, COUNT(*) FROM team_environment GROUP BY situation; SELECT * FROM freeze_value;"
```

Expected: both `all` and `5v5` rows in every table; `all` counts match the pre-change build; `freeze_value` has an `all` row and (only if Task 3 found the 5v5 effect significant) a `5v5` row.

- [ ] **Step 4: Extend the sync guard** — in `tools/sync-runtime-data.sh`, after the existing `for f in ...` missing/empty-file loop, add:

```bash
# goalies.db must carry BOTH situation cuts — a stale single-cut db would
# blank the 5v5 dropdown in prod while looking superficially healthy.
python3 - "$DST/goalies.db" <<'EOF'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
n = dict(conn.execute(
    "SELECT situation, COUNT(*) FROM goalie_seasons GROUP BY situation"))
assert set(n) == {"all", "5v5"} and min(n.values()) > 0, \
    f"goalies.db situation coverage broken: {n}"
print(f"goalies.db situation coverage OK: {n}")
EOF
```

- [ ] **Step 5: Run the guard end-to-end:** `./tools/sync-runtime-data.sh` — Expected: `goalies.db situation coverage OK: {...}` plus the normal sync output.

- [ ] **Step 6: Full suite:** `python -m pytest v2/ -v` — Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add v2/browser/build_goalies_db.py tools/sync-runtime-data.sh
git commit -m "feat(browser): goalies.db situation dimension (all + strict 5v5)"
```

---

### Task 5: Global situation dropdown + goalies list page

**Files:**
- Modify: `v2/browser/app.py` (layout + one callback + glossary sentence is Task 7's — do NOT touch glossary here)
- Modify: `v2/browser/pages/goalies.py`

**Interfaces:**
- Consumes: Task 4's `situation` column.
- Produces: global component `dcc.Dropdown(id="goalie-situation")` with values `"all"` / `"5v5"`, session-persisted, visible only on `/goalies`, `/goalie/<id>`, `/team/<abbrev>`. Pages consume it as `Input("goalie-situation", "value")`. Consumed by Tasks 6–7.

**PRECONDITION CHECK:** run `git status --porcelain -- v2/browser/app.py v2/browser/assets/style.css`. If either shows modified, HALT and ask oiler to commit/stash the in-progress notes work first (Global Constraints).

- [ ] **Step 1: Add the dropdown bar to `app.py`.** In `app.layout`, directly after the existing season filter-bar `html.Div(...)` (the one with `className="filter-bar"` and `style={"display": "none"}`), insert:

```python
    # Goalie situation filter — visible only on goalie-bearing pages (toggled
    # below). Session-persisted so the choice follows the user across views.
    html.Div([
        html.Div([
            html.Label("Situations"),
            dcc.Dropdown(
                id="goalie-situation",
                options=[{"label": "All situations", "value": "all"},
                         {"label": "5v5 (1551)", "value": "5v5"}],
                value="all", clearable=False, searchable=False,
                persistence=True, persistence_type="session",
                style={"width": "200px"},
            ),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
    ], id="goalie-situation-bar", className="filter-bar",
       style={"display": "none"}),
```

- [ ] **Step 2: Add the visibility callback** in `app.py` next to `toggle_glossary_footer`:

```python
@callback(Output("goalie-situation-bar", "style"), Input("url", "pathname"))
def toggle_goalie_situation_bar(pathname):
    p = pathname or ""
    show = p == "/goalies" or p.startswith("/goalie/") or p.startswith("/team/")
    return {} if show else {"display": "none"}
```

- [ ] **Step 3: Wire `pages/goalies.py`.** Replace `_SQL` and the callback:

```python
_SQL = """
SELECT goalie_id, name, teams, gp, toi_s, shots_faced, ga, xga, gsax, gsax_per100,
       freeze_rate, freeze_pct, mean_difficulty_pct, mean_perf_z
FROM goalie_seasons WHERE season = ? AND situation = ? ORDER BY gsax DESC
"""

_CUT_NOTE = ("Strict 5v5 (situationCode 1551): shot metrics count 5v5 play only. "
             "GP and TOI/GP remain all-situations.")
```

```python
@callback(
    Output("goalies-content", "children"),
    Input("store-season", "data"),
    Input("goalie-situation", "value"),
)
def update_goalies(season, situation):
    season = season or "2025"
    situation = situation if situation in ("all", "5v5") else "all"
    df = goalies_query(_SQL, params=(int(season), situation))
    if df.empty:
        return html.P("No goalie data for this season.")
```

then keep the existing body, with two additions: the `TOI/GP` column name becomes `"TOI/GP (all sit)"` when `situation == "5v5"` (build `columns` after computing `toi_name = "TOI/GP (all sit)" if situation == "5v5" else "TOI/GP"` and use `{"name": toi_name, "id": "toi_display", ...}`), and prepend a cut note to the returned Div when in 5v5 mode:

```python
    note = ([html.P(_CUT_NOTE, style={"fontSize": "0.8rem", "color": "#6c757d"})]
            if situation == "5v5" else [])
    return html.Div(note + [html.Div(
        dash_table.DataTable(...unchanged...),
        className="table-wrap",
    )])
```

- [ ] **Step 4: Manual smoke test** — `python3 v2/browser/app.py`, open `http://127.0.0.1:8050/goalies`. Verify: dropdown appears on /goalies, absent on /skaters; switching to 5v5 changes GSAx/shots numbers downward and shows the cut note; selection survives navigating to a goalie page and back (session persistence).

- [ ] **Step 5: Full suite:** `python -m pytest v2/ -v` — Expected: all pass (smoke tests import pages; no callback assertions exist).

- [ ] **Step 6: Commit**

```bash
git add v2/browser/app.py v2/browser/pages/goalies.py
git commit -m "feat(browser): goalie situation dropdown; 5v5 cut on goalies list"
```

---

### Task 6: Goalie detail page in both cuts

**Files:**
- Modify: `v2/browser/pages/goalie.py`

**Interfaces:**
- Consumes: `Input("goalie-situation", "value")` from Task 5; Task 4 schema.
- Produces: `/goalie/<id>` fully situation-aware.

- [ ] **Step 1: Make the four SQL constants situation-aware:**

```python
_SEASONS_SQL = """
SELECT season, name, teams, gp, toi_s, gsax, gsax_per100, freeze_rate, freeze_pct,
       mean_difficulty_pct
FROM goalie_seasons WHERE goalie_id = ? AND situation = ? ORDER BY season DESC
"""

_GAMES_SQL = """
SELECT season, game_date, opp_abbrev, ga, xga, gsax_game, difficulty_pct,
       perf_z, lev_value, toi_s
FROM goalie_games WHERE goalie_id = ? AND situation = ? ORDER BY game_date DESC
"""

_FREEZE_SQL = "SELECT per_freeze_xga_delta FROM freeze_value WHERE situation = ?"

_FREEZE_MEDIAN_SQL = """
SELECT freeze_rate FROM goalie_seasons
WHERE season = ? AND situation = ? AND freeze_pct IS NOT NULL
"""
```

- [ ] **Step 2: Convert the static layout to a callback.** Add `dcc`, `callback`, `Input`, `Output` to the dash import. Replace `layout()` and move its body into a render callback:

```python
def layout(goalie_id=None):
    try:
        gid = int(goalie_id)
    except (TypeError, ValueError):
        return html.Div(html.P("Unknown goalie."))
    return html.Div([
        dcc.Store(id="goalie-gid", data=gid),
        html.Div(id="goalie-content"),
    ])


@callback(
    Output("goalie-content", "children"),
    Input("goalie-gid", "data"),
    Input("goalie-situation", "value"),
)
def render_goalie(gid, situation):
    situation = situation if situation in ("all", "5v5") else "all"
    seasons = goalies_query(_SEASONS_SQL, params=(gid, situation))
    if seasons.empty:
        return html.P("No goalie data for this cut.")
    games = goalies_query(_GAMES_SQL, params=(gid, situation))
    games["toi_display"] = games["toi_s"].apply(seconds_to_mmss)

    children = [html.H2(seasons.iloc[0]["name"]),
                html.Div([_season_card(r, situation) for _, r in seasons.iterrows()])]
    if situation == "5v5":
        children.insert(1, html.P(
            "Strict 5v5 (situationCode 1551). GP and TOI are all-situations; "
            "shot metrics count 5v5 play only.",
            style={"fontSize": "0.8rem", "color": "#6c757d"}))

    fv = goalies_query(_FREEZE_SQL, params=(situation,))
    if not fv.empty:
        delta = float(fv.iloc[0]["per_freeze_xga_delta"])
        latest = seasons.iloc[0]
        if pd.notna(latest["freeze_rate"]) and pd.notna(latest["freeze_pct"]):
            median_df = goalies_query(_FREEZE_MEDIAN_SQL,
                                      params=(int(latest["season"]), situation))
            if not median_df.empty:
                median_rate = median_df["freeze_rate"].median()
                goals_vs_median = -delta * STARTER_SEASON_SAVES * (float(latest["freeze_rate"]) - median_rate)
                children.append(html.P(
                    f"Freeze impact vs the league-median freeze rate: {goals_vs_median:+.1f} "
                    f"goals per starter season (this goalie: p{latest['freeze_pct']:.0f} freeze "
                    f"rate; validated pathway estimate).",
                    style={"fontSize": "0.9rem", "color": "#495057"}))
```

then the games table exactly as today, except the TOI column header:

```python
    toi_name = "TOI (all sit)" if situation == "5v5" else "TOI"
    columns = [
        {"name": "Date", "id": "game_date"},
        {"name": "Opp", "id": "opp_abbrev"},
        {"name": toi_name, "id": "toi_display"},
        ...rest unchanged...
    ]
```

`_season_card` gains the situation for its own TOI label:

```python
def _season_card(r, situation="all"):
    ...
    toi_label = "TOI/GP (all sit)" if situation == "5v5" else "TOI/GP"
    gp_line = f"GP {r['gp']} · {toi_label} {seconds_to_mmss(r['toi_s'] / max(r['gp'], 1))}"
    ...
```

(keep every existing NaN guard in `_season_card` — they exist for real edge-case rows). The `"Unknown goalie."` for a bad id stays in `layout()`; the callback's empty-frame case says "No goalie data for this cut." because a valid goalie can lack 5v5 rows.

- [ ] **Step 3: Manual smoke test** — with the app running, open a goalie (e.g. from /goalies), toggle the dropdown. Verify: season cards and game ledger change; freeze-impact line disappears in 5v5 mode if Task 3 found the 5v5 freeze value non-significant (no row in `freeze_value`); TOI labels show "(all sit)" in 5v5.

- [ ] **Step 4: Full suite:** `python -m pytest v2/ -v` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add v2/browser/pages/goalie.py
git commit -m "feat(browser): goalie detail page situation-aware (all / strict 5v5)"
```

---

### Task 7: Team-page goalie environment + glossary copy

**Files:**
- Modify: `v2/browser/pages/team.py:74-96,170-178,333`
- Modify: `v2/browser/app.py` (glossary copy only)

**Interfaces:**
- Consumes: `Input("goalie-situation", "value")`; Task 4 schema.

- [ ] **Step 1: `team.py` env SQL + section function:**

```python
_ENV_SQL = """
SELECT mean_difficulty_pct, mean_xg_faced_per60, hd_share, crossice_per60, b2b_games
FROM team_environment WHERE season = ? AND team_abbrev = ? AND situation = ?
"""


def _goalie_environment_section(season, team, situation):
    env = goalies_query(_ENV_SQL, params=(int(season), team, situation))
    if env.empty:
        return None
    r = env.iloc[0]
    heading = "Goalie environment (5v5)" if situation == "5v5" else "Goalie environment"
    per60_suffix = " (per 60 total TOI)" if situation == "5v5" else ""
    return html.Div([
        html.H3(heading),
        html.P("How hard this team makes its goalies' lives — workload served, "
               "not goalie quality.", style={"fontSize": "0.85rem", "color": "#6c757d"}),
        html.Ul([
            html.Li(f"Difficulty served: p{r['mean_difficulty_pct']:.0f} league percentile"),
            html.Li(f"xG faced/60{per60_suffix}: {r['mean_xg_faced_per60']:.2f}"),
            html.Li(f"High-danger share: {r['hd_share']:.1%}"),
            html.Li(f"Cross-ice/60{per60_suffix}: {r['crossice_per60']:.2f}"),
            html.Li(f"Back-to-backs: {int(r['b2b_games'])}"),
        ]),
    ])
```

- [ ] **Step 2: Thread the input through the team callback.** At `team.py:170-178` add the input and parameter (position it last to leave the existing arg order intact):

```python
@callback(
    Output("team-content", "children"),
    Input("team-date-start", "date"),
    Input("team-date-end", "date"),
    Input("team-home-away", "data"),
    Input("team-abbrev", "data"),
    Input("store-season", "data"),
    Input("goalie-situation", "value"),
)
def update_team(date_start, date_end, home_away, abbrev, season, goalie_situation):
```

and at line ~333:

```python
    goalie_situation = goalie_situation if goalie_situation in ("all", "5v5") else "all"
    env_section = _goalie_environment_section(season, abbrev, goalie_situation)
```

- [ ] **Step 3: Glossary copy in `app.py`.** Replace the goalies glossary intro paragraph ("Goalie stats cover all strength states (not 5v5-only), ...") with:

```python
        html.P(
            [
                "Goalie stats cover ",
                html.B("all strength states"),
                " by default; the situation filter on goalie pages switches every "
                "goalie stat to the strict ",
                html.B("5v5"),
                " cut (situationCode 1551 — both goalies in net, five skaters each; "
                "4v4 and 3v3 excluded). GP and TOI always count all situations. "
                "Seasons 2021-22 through 2025-26. These are descriptive "
                "measurements: our validation found goalie results are dominated by "
                "environment and sample noise, so read them as what happened, not as "
                "talent rankings.",
            ],
            className="glossary-note",
        ),
```

and extend the `Difficulty` `<dd>` with one sentence appended to its existing text: `" In 5v5 mode, the rate is 5v5 xG faced per 60 of total ice time."`

- [ ] **Step 4: Manual smoke test** — open a team page, toggle the dropdown: env section heading gains "(5v5)", numbers change; skater tables on the same page are unaffected.

- [ ] **Step 5: Full suite:** `python -m pytest v2/ -v` — Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add v2/browser/pages/team.py v2/browser/app.py
git commit -m "feat(browser): team goalie environment + glossary situation-aware"
```

---

### Task 8: Pre-registration addendum + 5v5 switch registry with floor decision

**Files:**
- Create: `docs/plans/2026-07-21-goalie-5v5-recheck-preregistration.md`
- Modify: `v2/goalies/switch_registry.py`
- Test: `v2/goalies/tests/test_switch_registry.py` (existing tests keep passing — floor becomes a defaulted parameter)

**Interfaces:**
- Consumes: Task 2 (`cut`), Task 1 (shots with `situation_code`).
- Produces: `data/generated/goalies/5v5/validation/switch_registry.csv` (at the chosen floor), `data/generated/goalies/5v5/validation/floor_decision.json`. `switch_cases(stints, floor=600)` and `nonswitch_pseudo_cases(stints, gg, fenwick, floor=600)` signatures. Consumed by Task 9.

- [ ] **Step 1 (BEFORE any research code): write and commit the pre-registration addendum** `docs/plans/2026-07-21-goalie-5v5-recheck-preregistration.md`:

```markdown
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
```

Commit immediately: `git add docs/plans/2026-07-21-goalie-5v5-recheck-preregistration.md && git commit -m "docs(goalies): pre-registration addendum for 5v5 re-check"`

- [ ] **Step 2: Write the failing test** — append to `v2/goalies/tests/test_switch_registry.py` (it already builds synthetic `stints`/`gg`/`fenwick` frames; reuse its fixtures/builders — read the file first and follow its existing constructors):

```python
def test_switch_cases_floor_parameter():
    # two stints of 550 fenwick each: below the 600 floor, above a 500 floor
    stints = pd.DataFrame({
        "goalie_id": [1, 1], "stint_id": [1, 2], "team": ["EDM", "CGY"],
        "start": ["2023-10-01", "2024-10-01"], "end": ["2024-04-01", "2025-04-01"],
        "first_season": [2023, 2024], "last_season": [2023, 2024],
        "fenwick": [550, 550],
    })
    assert len(switch_cases(stints)) == 0                 # default 600 floor
    assert len(switch_cases(stints, floor=500)) == 1
```

- [ ] **Step 3: Run to verify failure** — `python -m pytest v2/goalies/tests/test_switch_registry.py -v` — Expected: new test FAILS with `TypeError: switch_cases() got an unexpected keyword argument 'floor'`.

- [ ] **Step 4: Implement.** In `switch_registry.py`:
  - `def switch_cases(stints: pd.DataFrame, floor: int = FLOOR) -> pd.DataFrame:` and use `floor` in the two comparisons at line 62.
  - `def nonswitch_pseudo_cases(stints, gg, fenwick, floor: int = FLOOR) -> pd.DataFrame:` and use `floor` at line 87.
  - Add imports + `main()` parameterization:

```python
import argparse
import sys
sys.path.insert(0, str(ROOT))
from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402


def main() -> None:
    situation = parse_situation()
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--floor", type=int, default=FLOOR)
    floor = p.parse_known_args()[0].floor
    val = gen_dir(situation) / "validation"
    val.mkdir(parents=True, exist_ok=True)
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    shots = pd.concat([load_shots(s, situation,
                                  usecols=["season", "game_id", "goalie_id", "event"])
                       for s in SEASONS], ignore_index=True)
    fw = fenwick_by_game(shots)
    stints = stint_table(gg, fw)
    real = switch_cases(stints, floor=floor)
    pseudo = nonswitch_pseudo_cases(stints, gg, fw, floor=floor)
    registry = pd.concat([real, pseudo], ignore_index=True)
    registry.to_csv(val / "switch_registry.csv", index=False)
    counts = real.groupby("switch_type").size().to_dict()
    print(f"registry [{situation}, floor {floor}]: {len(real)} real cases {counts}, "
          f"{len(pseudo)} nonswitch pseudo; weights p10/p50/p90 = "
          f"{real['weight'].quantile(.1):.0f}/{real['weight'].median():.0f}/"
          f"{real['weight'].quantile(.9):.0f}")
```

- [ ] **Step 5: Run tests** — `python -m pytest v2/goalies/tests/test_switch_registry.py -v` — Expected: all pass.

- [ ] **Step 6: Apply the pre-registered floor rule.** Get the pooled real-case count, then run both 5v5 floors:

```bash
python3 -c "
import pandas as pd
r = pd.read_csv('data/generated/goalies/validation/switch_registry.csv')
print('pooled real cases:', (r['switch_type'] != 'nonswitch').sum())
"
python3 v2/goalies/switch_registry.py --situation 5v5 --floor 600   # note count A
python3 v2/goalies/switch_registry.py --situation 5v5 --floor 500   # note count B
```

Apply the rule from the addendum (A < 0.75 × pooled → floor 500, else 600), re-run at the chosen floor so `switch_registry.csv` holds the chosen registry, and record the decision:

```bash
python3 -c "
import json
from pathlib import Path
Path('data/generated/goalies/5v5/validation/floor_decision.json').write_text(json.dumps({
    'pooled_real_cases': POOLED, 'n_600': A, 'n_500': B,
    'chosen_floor': CHOSEN,
    'rule': 'floor 500 iff n_600 < 0.75 * pooled_real_cases (pre-registered, counts only)',
}, indent=2))
"
```

(replace POOLED/A/B/CHOSEN with the actual integers observed).

- [ ] **Step 7: Full suite:** `python -m pytest v2/ -v` — Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add v2/goalies/switch_registry.py v2/goalies/tests/test_switch_registry.py
git commit -m "feat(goalies): situation+floor parameterized switch registry; 5v5 registry built per pre-registered floor rule"
```

---

### Task 9: Portability gate, 5v5 edition

**Files:**
- Modify: `v2/goalies/portability.py`
- Test: `v2/goalies/tests/test_portability.py` (existing tests must keep passing — all changed functions keep defaulted parameters)

**Interfaces:**
- Consumes: Task 8's 5v5 `switch_registry.csv`; Task 3's 5v5 terms/ledger; pooled `era_probe_verdict.json` (reused per addendum).
- Produces: `data/generated/goalies/5v5/validation/{frozen_params.json, midseason_refits.csv, portability_cases.csv, gate_table.csv}`. Changed signatures (all backward-compatible): `build_shots_xg(situation="all")`, `load_terms(situation="all")`, `run_midseason_refits(cases, terms, situation="all")`. Consumed by Tasks 10 (imports) and 12 (report).

- [ ] **Step 1: Parameterize the loaders and cache path** in `portability.py`. Add `from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402` after the existing imports, then:

```python
def build_shots_xg(situation: str = "all") -> pd.DataFrame:
    frames = []
    for s in SEASONS:
        # dtype checkpoint: case_outcome's tuple-membership join on
        # (season, game_id) fails silently (drops the case) if dtypes
        # mismatch across frames -- cast explicitly here.
        shots = load_shots(s, situation).astype(
            {"season": "int64", "game_id": "int64"})
        xg = blind_shot_xg(shots)
        frames.append(pd.DataFrame({
            "season": shots["season"], "game_id": shots["game_id"],
            "goalie_id": shots["goalie_id"], "game_date": shots["game_date"],
            "fenwick_flag": shots["event"] != "blocked-shot",
            "xg": xg, "is_goal": shots["is_goal"],
        }))
    return pd.concat(frames, ignore_index=True)


def load_terms(situation: str = "all") -> dict[int, pd.DataFrame]:
    d = gen_dir(situation)
    return {int(s): pd.read_csv(d / f"goalie_terms_{s}.csv") for s in SEASONS}
```

`run_midseason_refits(cases, terms, situation: str = "all")`: replace `cache_path = VAL / "midseason_refits.csv"` with `cache_path = gen_dir(situation) / "validation" / "midseason_refits.csv"`, and inside its loop replace the season-shots read with `season_shots = load_shots(str(season), situation).astype({"season": "int64", "game_id": "int64"})` — the refit must fit on 5v5 shots in the 5v5 edition (leakage rule unchanged).

- [ ] **Step 2: Parameterize `main()`.** At the top of `main()`:

```python
def main() -> None:
    situation = parse_situation()
    val = gen_dir(situation) / "validation"
    val.mkdir(parents=True, exist_ok=True)
    registry = pd.read_csv(val / "switch_registry.csv")
    ...
    # era verdicts REUSED from the pooled run (pre-registration addendum:
    # tracking-era coding shifts are dataset-wide, not strength-specific)
    verdicts = json.loads((VAL / "era_probe_verdict.json").read_text())
```

then: `shots_xg = build_shots_xg(situation)`, `terms = load_terms(situation)`, `ledger_dated = pd.read_csv(gen_dir(situation) / "game_ledger.csv")...` (rest of that expression unchanged), `refits = run_midseason_refits(real, terms, situation)`, and every output write (`frozen_params.json`, `portability_cases.csv`, `gate_table.csv`) goes to `val /` instead of `VAL /`. Nothing else in `main()` changes — the frozen-params-before-real-cases ordering and the real-case coverage assert are the pre-registered discipline and stay exactly as they are.

- [ ] **Step 3: Run existing tests** — `python -m pytest v2/goalies/tests/test_portability.py -v` — Expected: all pass (defaults preserve behavior).

- [ ] **Step 4: Run the 5v5 gate:**

```bash
python3 v2/goalies/portability.py --situation 5v5
```

Expected: `real case coverage: N/N scored, dropped=[]` (the assert halts on any drop — investigate before proceeding if it fires), then the gate table. Record the full gate table output in the task report for Task 12.

- [ ] **Step 5: Full suite:** `python -m pytest v2/ -v` — Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add v2/goalies/portability.py
git commit -m "feat(goalies): portability harness --situation 5v5 (pre-registered re-run)"
```

---

### Task 10: Component repeatability at 5v5

**Files:**
- Modify: `v2/goalies/repeatability.py`

**Interfaces:**
- Consumes: Task 9's `build_shots_xg(situation)`/`load_terms(situation)`; Task 3's 5v5 terms.
- Produces: `data/generated/goalies/5v5/validation/{repeatability.csv, tandem_table.csv}`.

- [ ] **Step 1: Parameterize `main()`** (the two computation functions are untouched):

```python
def main() -> None:
    from v2.goalies.cut import gen_dir, parse_situation
    from v2.goalies.portability import build_shots_xg, load_terms
    situation = parse_situation()
    val = gen_dir(situation) / "validation"
    val.mkdir(parents=True, exist_ok=True)
    terms = load_terms(situation)
    rep = component_repeatability(terms)
    rep.to_csv(val / "repeatability.csv", index=False)
    gg = pd.concat([pd.read_csv(GEN / f"goalie_games_{s}.csv") for s in SEASONS],
                   ignore_index=True)
    tandem = tandem_table(gg, build_shots_xg(situation), terms)
    tandem.to_csv(val / "tandem_table.csv", index=False)
    print(rep.to_string(index=False))
    print(f"\ntandem pairs: {len(tandem)}; "
          f"corr(gsax_gap, term_gap) = "
          f"{weighted_r(tandem['gsax_gap'], tandem['term_gap'], np.ones(len(tandem))):+.3f}")
```

- [ ] **Step 2: Run** — `python3 v2/goalies/repeatability.py --situation 5v5` — Expected: per-layer, per-season-pair `r` table. Record it: the pre-registered question is whether the `goal` (stopping) layer's r rises above the pooled ≈0.12 when PK noise is removed, and how freeze compares to the ≈0.58 anchor.

- [ ] **Step 3: Full suite:** `python -m pytest v2/ -v` — Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add v2/goalies/repeatability.py
git commit -m "feat(goalies): repeatability --situation 5v5 (pre-registered re-run)"
```

---

### Task 11: Freeze × strength decomposition (pooled data by design)

**Files:**
- Create: `v2/goalies/freeze_by_strength.py`
- Test: `v2/goalies/tests/test_freeze_by_strength.py`

**Interfaces:**
- Consumes: `freeze_value.ridge_linear`, `freeze_value.window_xga`, `freeze_value._load_saves_and_shots` (default pooled), `features.build_features`/`STRUCTURE_COLS`.
- Produces: `data/generated/goalies/validation/freeze_by_strength.json` + `.txt` (pooled VAL — this item is not a 5v5 slice). `freeze_strength_design(saves) -> np.ndarray` (n×3: froze, froze×SH, froze×PP).

- [ ] **Step 1: Write the failing test** — create `v2/goalies/tests/test_freeze_by_strength.py`:

```python
import numpy as np
import pandas as pd

from v2.goalies.freeze_by_strength import freeze_strength_design


def test_design_matrix_interactions():
    saves = pd.DataFrame({
        "froze": [1.0, 1.0, 1.0, 0.0],
        "strength": ["EV", "SH", "PP", "SH"],
    })
    X = freeze_strength_design(saves)
    # columns: froze, froze*SH, froze*PP
    assert X.shape == (4, 3)
    np.testing.assert_array_equal(X[0], [1.0, 0.0, 0.0])   # EV freeze: main only
    np.testing.assert_array_equal(X[1], [1.0, 1.0, 0.0])   # PK freeze
    np.testing.assert_array_equal(X[2], [1.0, 0.0, 1.0])   # PP freeze
    np.testing.assert_array_equal(X[3], [0.0, 0.0, 0.0])   # non-freeze: all zero
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest v2/goalies/tests/test_freeze_by_strength.py -v` — Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — create `v2/goalies/freeze_by_strength.py`:

```python
"""Freeze value x strength decomposition (5v5 program item 3; pooled by design).

Adds froze x SH and froze x PP interactions to the 30s branch-pricing
regression: a PK freeze buys a line change, so its value may differ from EV.
Sharpens the positive freeze-value result -- NOT a null re-test; runs on
all-situations data per the pre-registration addendum.

Usage: python3 v2/goalies/freeze_by_strength.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.features import STRUCTURE_COLS, build_features  # noqa: E402
from v2.goalies.freeze_value import (_load_saves_and_shots, ridge_linear,  # noqa: E402
                                     window_xga)

VAL = ROOT / "data" / "generated" / "goalies" / "validation"


def freeze_strength_design(saves: pd.DataFrame) -> np.ndarray:
    froze = saves["froze"].to_numpy(dtype=float)
    sh = saves["strength"].eq("SH").to_numpy(dtype=float)
    pp = saves["strength"].eq("PP").to_numpy(dtype=float)
    return np.column_stack([froze, froze * sh, froze * pp])


def main() -> None:
    VAL.mkdir(parents=True, exist_ok=True)
    shots = _load_saves_and_shots()
    saves = shots[shots["on_net"] & ~shots["is_goal"] & shots["froze"].notna()].copy()
    y = window_xga(shots, saves, window_s=30)
    # base features already carry pp/sh main effects, so the interactions are
    # identified; froze main = EV freeze effect, froze_sh/froze_pp = deltas
    X = np.hstack([build_features(saves).to_numpy(), freeze_strength_design(saves)])
    penalty = np.full(X.shape[1], 1.0)
    penalty[STRUCTURE_COLS.index("intercept")] = 1e-6
    penalty[-3:] = 1e-6
    beta, se = ridge_linear(X, y.astype(float), penalty)
    names = ("froze_ev", "froze_x_sh", "froze_x_pp")
    est = {n: {"coef": float(beta[i]), "se": float(se[i])}
           for n, i in zip(names, (-3, -2, -1))}
    counts = (saves.groupby(["strength", "froze"]).size()
              .rename("n").reset_index().to_dict("records"))
    lines = [f"{n}: coef={e['coef']:+.5f} se={e['se']:.5f}" for n, e in est.items()]
    lines.append(f"PK freeze total = froze_ev + froze_x_sh = "
                 f"{est['froze_ev']['coef'] + est['froze_x_sh']['coef']:+.5f}")
    lines.append(f"saves by strength/froze: {counts}")
    lines.append("SE caveat: iid ridge SEs; clustering makes true uncertainty "
                 "larger (plausibly 2-5x), same as the headline freeze study.")
    report = "\n".join(lines)
    (VAL / "freeze_by_strength.txt").write_text(report + "\n")
    (VAL / "freeze_by_strength.json").write_text(json.dumps(est, indent=2))
    print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests** — `python -m pytest v2/goalies/tests/test_freeze_by_strength.py -v` — Expected: PASS.

- [ ] **Step 5: Run the study** — `python3 v2/goalies/freeze_by_strength.py` — Expected: three coefficients + PK total + counts. Record output for Task 12.

- [ ] **Step 6: Full suite:** `python -m pytest v2/ -v` — Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add v2/goalies/freeze_by_strength.py v2/goalies/tests/test_freeze_by_strength.py
git commit -m "feat(goalies): freeze x strength decomposition (pre-registered item 3)"
```

---

### Task 12: 5v5 re-check report + final verification

**Files:**
- Create: `docs/plans/2026-07-21-goalie-5v5-recheck-report.md`

**Interfaces:**
- Consumes: Task 8 `floor_decision.json`, Task 9 `gate_table.csv` (5v5 + pooled), Task 10 `repeatability.csv` (5v5 + pooled), Task 11 `freeze_by_strength.json`, Task 3's 5v5 `validation/freeze_value_report.txt`.

- [ ] **Step 1: Write the report** at `docs/plans/2026-07-21-goalie-5v5-recheck-report.md` with these sections, filling every number from the artifacts above (no placeholders may survive):

```markdown
# Goalie 5v5 re-check — results report

**Date:** <run date>
**Pre-registration:** docs/plans/2026-07-21-goalie-5v5-recheck-preregistration.md
**Multiplicity statement:** portability and stopping-repeatability are SECOND LOOKS
at previously tested hypotheses; each carries a doubled false-positive budget.
The freeze × strength item is a decomposition of an established positive result.

## 1. Registry and floor
pooled real cases: N; 5v5 at floor 600: A; at floor 500: B; chosen floor: F (rule: ...).

## 2. Portability gate, 5v5 edition
<gate table: candidate | dr | lo90 | hi90 | n_cases | r_cand | r_base_eb, for both
the 5v5 run and the pooled run side by side>
Verdict per pre-registered decision rule: <"null strengthened" or "signal revealed",
justified against BOTH criteria (CI excludes zero AND materially above pooled)>.

## 3. Component repeatability, 5v5
<per-layer weighted r, 5v5 vs pooled vs published anchors (freeze ≈ 0.58, stopping ≈ 0.12)>
Answer to mechanism 1: does stopping repeatability rise when PK noise is removed? <yes/no + magnitude>

## 4. Freeze × strength decomposition
<froze_ev / froze_x_sh / froze_x_pp coefficients ± SE, PK total, save counts by strength>
Interpretation: <is a PK freeze worth more, per the line-change hypothesis?>

## 5. Descriptive 5v5 layer
5v5 freeze-value pathway: <coef, significant?>. Browser: goalies.db now carries both
cuts; dropdown default remains all-situations.

## 6. What stays closed
Rust/idle-gap, hot-hand, rebound-era: not re-tested (pre-registered exclusion).
```

- [ ] **Step 2: Verify no placeholder text remains:** `grep -n "<" docs/plans/2026-07-21-goalie-5v5-recheck-report.md` — Expected: no template angle-bracket stubs left (markdown/HTML tags aside — check matches by eye).

- [ ] **Step 3: Rebuild the browser db against final artifacts and re-run the sync guard** (freeze_value 5v5 may have changed if any research task re-ran the pipeline):

```bash
python3 v2/browser/build_goalies_db.py
./tools/sync-runtime-data.sh
```

Expected: situation coverage OK.

- [ ] **Step 4: Full suite, final:** `python -m pytest v2/ -v` — Expected: all pass (≈295+, exact count from new tests).

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-07-21-goalie-5v5-recheck-report.md
git commit -m "docs(goalies): 5v5 re-check results report"
```

- [ ] **Step 6: Do NOT merge, do NOT push.** Report the branch state to oiler: findings summary, gate verdicts, and the deploy reminder (rebuild goalies.db + sync-runtime-data before `fly deploy`).
