# Cut-Aware Goalie TOI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the strict-5v5 goalie cut its own TOI denominator, derived from the per-second timelines, so every 5v5 rate in the pipeline and the browser is correct on that basis.

**Architecture:** A new producer (`v2/goalies/toi_5v5.py`) walks the timelines and writes per-season 5v5 goalie TOI. A new selector (`cut.load_toi`) hands each pipeline stage the TOI frame for its cut. Two stages call it directly; two more inherit the corrected denominator through `game_difficulty.csv` and need no edit.

**Tech Stack:** Python 3.10+, pandas, pytest. No new dependencies.

**Spec:** `docs/plans/2026-07-30-goalie-5v5-toi-design.md`

## Global Constraints

- **Strict `1551` only.** Never reuse `compute_competition.SCORED_SITUATIONS = {"1551", "0651", "1560"}`; `0651` and `1560` are goalie-pulled states and counting them credits the remaining goalie with empty-net ice time.
- **The all-situations cut must not change.** It keeps reading boxscore TOI; its outputs must be byte-identical before and after.
- **The shot layer must not move.** `gsax_<season>.csv`, `goalie_terms_<season>.csv` and the freeze outputs are TOI-independent. Any diff means the change leaked past its boundary.
- **`gp` stays all-situations** — a goalie who dressed and played is one appearance.
- **The difficulty eligibility gate stays at `min_toi_s=1200`**, now applied to the cut's own TOI.
- **Git:** work on branch `goalie-5v5-toi`. Per-task local commits are authorized; never push, never commit to `master`.
- **Run `python -m pytest v2/ -v` from the repo root before finishing any task.** Baseline at plan time: 301 passing.
- Never hard-wrap markdown in docs you touch.

## File Structure

| File | Responsibility |
|---|---|
| `v2/goalies/toi_5v5.py` | **new** — sole owner of timeline parsing for goalie TOI. Emits `GEN/5v5/goalie_toi_<season>.csv`. |
| `v2/goalies/tests/test_toi_5v5.py` | **new** — unit tests for the above, synthetic rows only. |
| `v2/goalies/cut.py` | Gains `load_toi(season, situation)`, the cut-aware TOI selector. Already owns cut-aware input selection (`load_shots`). |
| `v2/goalies/tests/test_cut.py` | Extended for `load_toi`. |
| `v2/goalies/game_difficulty.py` | Consumes `load_toi`. One line plus an import plus a comment. |
| `v2/browser/build_goalies_db.py` | Consumes `load_toi`. One line plus an import plus a comment. |
| `v2/browser/metrics.py` | `gsax_per60` loses its situation guard; `xga_per60` added. |
| `v2/browser/test_rate_metrics.py` | Updated for both. |
| `v2/browser/pages/goalies.py` | Both rate columns in both cuts; cut-aware TOI label; rewritten note. |
| `v2/browser/pages/goalie.py` | Two stale `(all sit)` labels removed. |
| `v2/browser/pages/team.py` | `per60_suffix` deleted. |
| `v2/browser/app.py` | Situation blurb corrected; glossary updated. |

`game_ledger.py` and `environment.py` are deliberately absent: both read `toi_s` downstream of `game_difficulty.csv` (`game_ledger.py:51`, `environment.py:72`) and inherit the fix.

---

### Task 1: 5v5 TOI producer

**Files:**
- Create: `v2/goalies/toi_5v5.py`
- Test: `v2/goalies/tests/test_toi_5v5.py`

**Interfaces:**
- Consumes: `cut.GEN`, `cut.STRICT_5V5`, `cut.gen_dir` (all exist).
- Produces: `count_5v5_seconds(rows) -> dict[int, int]`, `season_frame(season: str, tl_dir: Path) -> pd.DataFrame` with columns `["season", "game_id", "goalie_id", "toi_5v5_s"]` all `int64`, and `timelines_dir(season: str) -> Path`. Task 2 reads the CSV this writes; Task 4 appends a test to this task's test file.

- [ ] **Step 1: Write the failing tests**

Create `v2/goalies/tests/test_toi_5v5.py`:

```python
import pytest

from v2.goalies.toi_5v5 import count_5v5_seconds, season_frame


def _row(code, away="8001", home="8002"):
    return {"situationCode": code, "awayGoalie": away, "homeGoalie": home}


def test_counts_only_strict_1551():
    rows = [_row("1551"), _row("1551"), _row("1451"), _row("0551")]
    assert count_5v5_seconds(rows) == {8001: 2, 8002: 2}


def test_credits_both_goalies_on_the_same_second():
    assert count_5v5_seconds([_row("1551")]) == {8001: 1, 8002: 1}


def test_empty_goalie_cell_credits_nobody():
    # Goalie pulled: the cell is blank. Nobody gains a second, and the pulled
    # goalie is not invented as a 0 row unless he appears elsewhere.
    rows = [_row("1551", away=""), _row("1551", away="")]
    assert count_5v5_seconds(rows) == {8002: 2}


def test_goalie_who_played_but_saw_no_5v5_gets_explicit_zero():
    # Appears in the game, never at 1551 -> 0, not a missing row. Downstream
    # needs to tell "played, no 5v5" apart from "no timeline at all".
    rows = [_row("1451"), _row("0651")]
    assert count_5v5_seconds(rows) == {8001: 0, 8002: 0}


def test_excludes_goalie_pulled_codes_that_the_skater_constant_includes():
    # compute_competition uses SCORED_SITUATIONS = {"1551","0651","1560"}.
    # Copying it here would pay the remaining goalie for empty-net time.
    rows = [_row("0651"), _row("1560"), _row("1551")]
    assert count_5v5_seconds(rows) == {8001: 1, 8002: 1}


def test_season_frame_grain_and_dtypes(tmp_path):
    (tmp_path / "2025020001.csv").write_text(
        "situationCode,awayGoalie,homeGoalie\n1551,8001,8002\n1551,8001,8002\n")
    (tmp_path / "2025020002.csv").write_text(
        "situationCode,awayGoalie,homeGoalie\n1551,8003,8002\n")
    df = season_frame("2025", tmp_path).sort_values(
        ["game_id", "goalie_id"]).reset_index(drop=True)

    assert list(df.columns) == ["season", "game_id", "goalie_id", "toi_5v5_s"]
    # Merge keys must match goalie_games_<season>.csv, which reads back int64.
    assert all(str(df[c].dtype) == "int64" for c in df.columns)
    assert len(df) == 4
    assert df.loc[0].tolist() == [2025, 2025020001, 8001, 2]
    assert df.loc[3].tolist() == [2025, 2025020002, 8003, 1]


def test_season_frame_raises_on_empty_timeline_dir(tmp_path):
    # The pre-backfill state of 2021/2022. An empty CSV here would blank a
    # whole season downstream while every stage still reported success.
    with pytest.raises(RuntimeError, match="no timelines"):
        season_frame("2021", tmp_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest v2/goalies/tests/test_toi_5v5.py -v`
Expected: FAIL at collection — `ModuleNotFoundError: No module named 'v2.goalies.toi_5v5'`

- [ ] **Step 3: Write the implementation**

Create `v2/goalies/toi_5v5.py`:

```python
"""Per-goalie 5v5 time on ice, reconstructed from the per-second timelines.

Boxscore TOI (v2/goalies/toi.py) is all-situations and has no 5v5 variant, so
every per-60 in the 5v5 cut divided a 5v5 numerator by an all-situations
denominator. This module supplies the missing denominator.

Usage: python3 v2/goalies/toi_5v5.py
"""

import csv
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from v2.goalies.cut import STRICT_5V5, gen_dir  # noqa: E402

SEASONS = ("2021", "2022", "2023", "2024", "2025")
GOALIE_COLS = ("awayGoalie", "homeGoalie")


def timelines_dir(season: str) -> Path:
    return ROOT / "data" / season / "generated" / "timelines" / "csv"


def count_5v5_seconds(rows) -> dict[int, int]:
    """Strict-5v5 seconds per goalie for one game's timeline rows.

    Goalies who appear in the game but never at 1551 get an explicit 0, so a
    caller can tell "played, saw no 5v5" apart from "no timeline at all".

    Strict 1551 only. compute_competition.py:24 uses
    SCORED_SITUATIONS = {"1551", "0651", "1560"} for skaters; the latter two are
    goalie-pulled states, and counting them would credit the remaining goalie
    with ice time while the other net is empty.
    """
    seconds: Counter[int] = Counter()
    seen: set[int] = set()
    for row in rows:
        at_5v5 = row["situationCode"] == STRICT_5V5
        for col in GOALIE_COLS:
            raw = row.get(col)
            if not raw:
                continue
            gid = int(raw)
            seen.add(gid)
            if at_5v5:
                seconds[gid] += 1
    return {gid: seconds.get(gid, 0) for gid in sorted(seen)}


def season_frame(season: str, tl_dir: Path) -> pd.DataFrame:
    paths = sorted(tl_dir.glob("*.csv"))
    if not paths:
        raise RuntimeError(
            f"no timelines for {season} at {tl_dir} — run "
            f"'python v2/timelines/generate_timeline.py 1 1312 {season}' first. "
            "Writing an empty file here would blank every 5v5 rate for the "
            "season while each downstream stage still reported success.")
    rows = []
    for path in paths:
        with path.open(newline="") as f:
            counts = count_5v5_seconds(list(csv.DictReader(f)))
        game_id = int(path.stem)
        rows.extend({"season": int(season), "game_id": game_id,
                     "goalie_id": gid, "toi_5v5_s": secs}
                    for gid, secs in counts.items())
    return pd.DataFrame(
        rows, columns=["season", "game_id", "goalie_id", "toi_5v5_s"]
    ).astype("int64")


def main() -> None:
    out_dir = gen_dir("5v5")
    out_dir.mkdir(parents=True, exist_ok=True)
    for season in SEASONS:
        df = season_frame(season, timelines_dir(season))
        df.to_csv(out_dir / f"goalie_toi_{season}.csv", index=False)
        zeros = int((df["toi_5v5_s"] == 0).sum())
        print(f"{season}: {len(df)} goalie-games, "
              f"{df['goalie_id'].nunique()} goalies, "
              f"5v5 TOI {df['toi_5v5_s'].sum() / 3600:.0f} h, "
              f"{zeros} with zero 5v5 seconds")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest v2/goalies/tests/test_toi_5v5.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest v2/ -q`
Expected: 308 passed

- [ ] **Step 6: Commit**

```bash
git add v2/goalies/toi_5v5.py v2/goalies/tests/test_toi_5v5.py
git commit -m "feat(goalies): 5v5 goalie TOI from per-second timelines"
```

---

### Task 2: Cut-aware TOI selector

**Files:**
- Modify: `v2/goalies/cut.py:1-7` (docstring), append `load_toi`
- Test: `v2/goalies/tests/test_cut.py`

**Interfaces:**
- Consumes: the CSV written by Task 1 at `gen_dir("5v5") / f"goalie_toi_{season}.csv"`.
- Produces: `load_toi(season: str, situation: str) -> pd.DataFrame` — the full `goalie_games` frame with `toi_s` replaced by the cut's denominator. Tasks 3 and 5 call it.

- [ ] **Step 1: Write the failing tests**

Append to `v2/goalies/tests/test_cut.py`:

```python
def _write_goalie_games(tmp_path):
    pd.DataFrame({
        "season": [2025, 2025, 2025],
        "game_id": [2025020001, 2025020001, 2025020002],
        "goalie_id": [8001, 8002, 8003],
        "team_abbrev": ["EDM", "CGY", "EDM"],
        "game_date": ["2025-10-07"] * 3,
        "starter": [True, True, True],
        "toi_s": [3600, 3600, 1800],
    }).to_csv(tmp_path / "goalie_games_2025.csv", index=False)


def test_load_toi_all_returns_boxscore_toi_unchanged(tmp_path, monkeypatch):
    _write_goalie_games(tmp_path)
    monkeypatch.setattr(cut, "GEN", tmp_path)
    df = cut.load_toi("2025", "all")
    assert list(df["toi_s"]) == [3600, 3600, 1800]
    assert list(df.columns) == list(
        pd.read_csv(tmp_path / "goalie_games_2025.csv").columns)


def test_load_toi_5v5_swaps_denominator_and_keeps_other_columns(tmp_path, monkeypatch):
    _write_goalie_games(tmp_path)
    (tmp_path / "5v5").mkdir()
    pd.DataFrame({
        "season": [2025, 2025, 2025],
        "game_id": [2025020001, 2025020001, 2025020002],
        "goalie_id": [8001, 8002, 8003],
        "toi_5v5_s": [2900, 2880, 1500],
    }).to_csv(tmp_path / "5v5" / "goalie_toi_2025.csv", index=False)
    monkeypatch.setattr(cut, "GEN", tmp_path)

    df = cut.load_toi("2025", "5v5").sort_values("goalie_id").reset_index(drop=True)
    assert list(df["toi_s"]) == [2900, 2880, 1500]
    # Consumers read these off the same frame; losing them breaks environment.py.
    assert {"team_abbrev", "game_date", "starter"} <= set(df.columns)
    assert "toi_5v5_s" not in df.columns
    assert list(df["team_abbrev"]) == ["EDM", "CGY", "EDM"]


def test_load_toi_5v5_missing_timeline_row_is_nan_not_zero(tmp_path, monkeypatch):
    # NaN means "no timeline" (a data gap); 0 means "played, saw no 5v5".
    # Collapsing them would hide missing data behind a legitimate-looking rate.
    _write_goalie_games(tmp_path)
    (tmp_path / "5v5").mkdir()
    pd.DataFrame({
        "season": [2025, 2025],
        "game_id": [2025020001, 2025020001],
        "goalie_id": [8001, 8002],
        "toi_5v5_s": [2900, 0],
    }).to_csv(tmp_path / "5v5" / "goalie_toi_2025.csv", index=False)
    monkeypatch.setattr(cut, "GEN", tmp_path)

    df = cut.load_toi("2025", "5v5").set_index("goalie_id")
    assert df.loc[8002, "toi_s"] == 0
    assert pd.isna(df.loc[8003, "toi_s"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest v2/goalies/tests/test_cut.py -v -k load_toi`
Expected: FAIL with `AttributeError: module 'v2.goalies.cut' has no attribute 'load_toi'`

- [ ] **Step 3: Rewrite the module docstring**

In `v2/goalies/cut.py`, replace lines 1-7 with:

```python
"""Situation-cut plumbing for the parallel strict-5v5 pipeline.

The all-situations pipeline is the default; `--situation 5v5` filters the
shared shots CSVs to situationCode 1551 and redirects outputs to GEN/5v5.

Goalie TOI is cut-aware as of 2026-07-30 (see
docs/plans/2026-07-30-goalie-5v5-toi-design.md): `load_toi` serves boxscore TOI
for the all cut and timeline-derived 5v5 TOI for the 5v5 cut. It previously came
from the parent GEN dir regardless of cut, which made every 5v5 per-60 a 5v5
numerator over an all-situations denominator. `wp_table` remains genuinely
shared — it is a game-state object, not an exposure measure.
"""
```

- [ ] **Step 4: Append `load_toi`**

Add to the end of `v2/goalies/cut.py`:

```python
def load_toi(season: str, situation: str) -> pd.DataFrame:
    """Goalie-game rows whose `toi_s` is the exposure denominator for `situation`.

    Returns the whole goalie_games frame rather than a bare TOI series:
    consumers also read team_abbrev, game_date, opp_abbrev, is_home and starter
    off it, and preserving them is what lets game_ledger.py and environment.py
    inherit the corrected denominator without edits.

    A goalie-game with no timeline gets NaN, which is distinct from the 0 that
    toi_5v5.py writes for a goalie who played but saw no 5v5.
    """
    gg = pd.read_csv(GEN / f"goalie_games_{season}.csv")
    if situation == "all":
        return gg
    toi5 = pd.read_csv(gen_dir("5v5") / f"goalie_toi_{season}.csv")
    merged = (gg.drop(columns="toi_s")
              .merge(toi5, on=["season", "game_id", "goalie_id"], how="left")
              .rename(columns={"toi_5v5_s": "toi_s"}))
    missing = int(merged["toi_s"].isna().sum())
    if missing:
        print(f"note: {missing} {season} goalie-games have no timeline; "
              "their 5v5 rates will be NaN")
    return merged
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest v2/goalies/tests/test_cut.py -v`
Expected: PASS, 10 tests

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest v2/ -q`
Expected: 311 passed

- [ ] **Step 7: Commit**

```bash
git add v2/goalies/cut.py v2/goalies/tests/test_cut.py
git commit -m "feat(goalies): cut-aware load_toi; TOI is no longer cut-invariant"
```

---

### Task 3: Backfill 2021-22 timelines and generate the TOI artifacts

This task runs code rather than writing it. Its deliverable is data plus a verified coverage report.

**Files:**
- Create: `data/2021/generated/timelines/{csv,json}/*` and the same for 2022
- Create: `data/generated/goalies/5v5/goalie_toi_<season>.csv` for all five seasons

- [x] **Step 1: Backfill 2021 timelines** — DONE 2026-08-11

Run: `python v2/timelines/generate_timeline.py 1 1312 2021`
Actual: `Batch complete: 1307 succeeded, 5 failed`. The five failures are a **known, accepted NHL source defect**, not a pipeline problem — `2021020326`, `2021020416`, `2021020427`, `2021020452`, `2021021189` have shift reports whose row durations contradict their own printed totals. Re-scraping returns byte-identical data and cannot fix it. Full investigation and the decision to accept the gap are in `docs/data-limitations.md`. **Do not add a validation tolerance and do not re-scrape.**

- [x] **Step 2: Backfill 2022 timelines** — DONE 2026-08-11

Run: `python v2/timelines/generate_timeline.py 1 1312 2022`
Actual: `Batch complete: 1312 succeeded, 0 failed`

- [x] **Step 3: Confirm coverage for all five seasons** — DONE 2026-08-11

```bash
for s in 2021 2022 2023 2024 2025; do
  echo "$s: $(ls data/$s/generated/timelines/csv | wc -l) timelines"
done
```

Expected: 1312 for 2022–2025, and **1307 for 2021** (see Step 1). Any other shortfall is unexplained — stop and investigate.

- [ ] **Step 4: Generate the 5v5 TOI CSVs**

Run: `python v2/goalies/toi_5v5.py`
Expected: five lines, each roughly `<season>: ~2800 goalie-games, ~100 goalies, 5v5 TOI ~2400 h, 0 with zero 5v5 seconds`

- [ ] **Step 5: Verify the denominator against the spec's measurement**

```bash
python3 -c "
import pandas as pd
gg = pd.read_csv('data/generated/goalies/goalie_games_2025.csv')
t5 = pd.read_csv('data/generated/goalies/5v5/goalie_toi_2025.csv')
m = gg.merge(t5, on=['season','game_id','goalie_id'], how='left')
print('unmatched goalie-games:', int(m['toi_5v5_s'].isna().sum()))
s = m.groupby('goalie_id')[['toi_s','toi_5v5_s']].sum()
s = s[s['toi_s'] >= 20*3600]
share = s['toi_5v5_s'] / s['toi_s']
print(f'5v5 share: median {share.median():.3f} min {share.min():.3f} max {share.max():.3f}')
"
```

Expected: `unmatched goalie-games: 0`, and a share of median ≈ 0.81 within roughly 0.77–0.84. A median outside 0.78–0.84 means the situation filter is wrong — most likely goalie-pulled codes leaked in — so stop and re-read `count_5v5_seconds`.

- [ ] **Step 6: Commit**

The CSVs under `data/` are gitignored, so only note the run. No commit for this task.

---

### Task 4: Wire the pipeline and regenerate the 5v5 cut

**Files:**
- Modify: `v2/goalies/game_difficulty.py:16` (import), `:67` (the read)

**Interfaces:**
- Consumes: `cut.load_toi` from Task 2, the CSVs from Task 3.
- Produces: corrected `xg_per60` and `difficulty_pct` in `GEN/5v5/game_difficulty.csv`, which `game_ledger.py:51` and `environment.py:72` then inherit.

- [ ] **Step 1: Snapshot the shot layer**

These must be byte-identical afterwards. Capture them first so the claim is testable rather than assumed.

```bash
mkdir -p /tmp/shotlayer-before
cp data/generated/goalies/gsax_*.csv data/generated/goalies/goalie_terms_*.csv /tmp/shotlayer-before/
mkdir -p /tmp/shotlayer-before/5v5
cp data/generated/goalies/5v5/gsax_*.csv data/generated/goalies/5v5/goalie_terms_*.csv /tmp/shotlayer-before/5v5/
```

- [ ] **Step 2: Add the import**

In `v2/goalies/game_difficulty.py`, change the `cut` import line to:

```python
from v2.goalies.cut import gen_dir, load_shots, load_toi, parse_situation  # noqa: E402
```

- [ ] **Step 3: Swap the TOI read**

In `main()`, replace:

```python
        toi = pd.read_csv(GEN / f"goalie_games_{season}.csv")   # TOI: shared, all-situations
```

with:

```python
        toi = load_toi(season, situation)
```

- [ ] **Step 4: Regenerate the 5v5 cut**

```bash
python v2/goalies/game_difficulty.py --situation 5v5
python v2/goalies/game_ledger.py --situation 5v5
python v2/goalies/environment.py --situation 5v5
```

Expected: `game_difficulty` prints a higher `xg_per60 median` than before (the denominator shrank by roughly a fifth). `game_ledger` still prints `mean perf_z` near 0 — `perf_z` is variance-normalized and must not move.

- [ ] **Step 5: Verify the shot layer did not move**

```bash
diff -r /tmp/shotlayer-before/ <(true) >/dev/null 2>&1
for f in /tmp/shotlayer-before/*.csv; do diff -q "$f" "data/generated/goalies/$(basename $f)" || echo "DRIFT: $f"; done
for f in /tmp/shotlayer-before/5v5/*.csv; do diff -q "$f" "data/generated/goalies/5v5/$(basename $f)" || echo "DRIFT: 5v5/$f"; done
echo "shot-layer check done"
```

Expected: no `DRIFT:` lines. Any drift means the change escaped its boundary — stop and investigate before continuing.

- [ ] **Step 6: Confirm the all cut is untouched**

Run: `python v2/goalies/game_difficulty.py --situation all`
Then: `git diff --stat` on nothing (outputs are gitignored), so instead compare against a pre-run copy:

```bash
cp data/generated/goalies/game_difficulty.csv /tmp/gd-all-after.csv
python v2/goalies/game_difficulty.py --situation all
diff -q /tmp/gd-all-after.csv data/generated/goalies/game_difficulty.csv && echo "all cut stable"
```

Expected: `all cut stable`.

- [ ] **Step 7: Add the invariant that licenses the unguarded divisions**

`game_difficulty.py:49` and `game_ledger.py:54` divide by `toi_s` with no `.where(> 0)` guard. That is safe only because those frames carry rows solely for goalie-games with at least one shot in the cut, and a `1551` shot implies at least one `1551` timeline second for the goalie who faced it. That implication links two independently derived artifacts — the shots CSV and the reconstructed timeline — so it gets asserted, not assumed.

Append to `v2/goalies/tests/test_toi_5v5.py`:

```python
@pytest.mark.requires_data
def test_zero_5v5_toi_implies_no_5v5_shots():
    """Licenses the unguarded /toi_s divisions in game_difficulty.py:49 and
    game_ledger.py:54. If a goalie faced a 1551 shot he must have at least one
    1551 second, or those stages divide by zero and emit inf."""
    import pandas as pd

    from v2.goalies.cut import GEN, load_shots

    for season in ("2021", "2022", "2023", "2024", "2025"):
        toi = pd.read_csv(GEN / "5v5" / f"goalie_toi_{season}.csv")
        zero = toi[toi["toi_5v5_s"] == 0][["game_id", "goalie_id"]]
        if zero.empty:
            continue
        shots = load_shots(season, "5v5", usecols=["game_id", "goalie_id"])
        clash = zero.merge(shots.drop_duplicates(), on=["game_id", "goalie_id"])
        assert clash.empty, (
            f"{season}: {len(clash)} goalie-games have 0 5v5 seconds but faced "
            f"5v5 shots — unguarded divisions would produce inf: "
            f"{clash.head().to_dict('records')}")
```

- [ ] **Step 8: Run it**

Run: `python -m pytest v2/goalies/tests/test_toi_5v5.py -v`
Expected: PASS, 8 tests. A failure here means the timeline reconstruction and the shots extract disagree about when 5v5 was in effect, which must be understood before shipping — do not weaken the assertion.

- [ ] **Step 9: Run the full suite**

Run: `python -m pytest v2/ -q`
Expected: 312 passed

- [ ] **Step 10: Commit**

```bash
git add v2/goalies/game_difficulty.py v2/goalies/tests/test_toi_5v5.py
git commit -m "fix(goalies): 5v5 difficulty uses 5v5 TOI as its denominator"
```

---

### Task 5: Cut-aware TOI in goalies.db

**Files:**
- Modify: `v2/browser/build_goalies_db.py:20` (import), `:108-109` (comment and read)
- Test: `v2/browser/tests/test_build_goalies_db.py`

**Interfaces:**
- Consumes: `cut.load_toi`.
- Produces: `goalie_seasons.toi_s` per cut. Tasks 6 and 7 read it through `goalies_query`.

- [ ] **Step 1: Write the failing invariant test**

Append to `v2/browser/tests/test_build_goalies_db.py`:

Add `import pytest` to the file's imports if it is not already there, then:

```python
@pytest.mark.requires_data
def test_5v5_toi_is_strictly_less_than_all_situations_toi():
    """Every goalie plays some non-5v5 hockey, so the 5v5 denominator must be
    smaller. Equality means the cut-aware read silently fell back to boxscore
    TOI — the exact regression this change exists to prevent."""
    import sqlite3
    from pathlib import Path
    db = Path(__file__).resolve().parents[3] / "data" / "generated" / "browser" / "goalies.db"
    conn = sqlite3.connect(str(db))
    bad = conn.execute("""
        SELECT COUNT(*) FROM goalie_seasons a
        JOIN goalie_seasons b
          ON a.season = b.season AND a.goalie_id = b.goalie_id
        WHERE a.situation = '5v5' AND b.situation = 'all'
          AND a.toi_s >= b.toi_s
    """).fetchone()[0]
    conn.close()
    assert bad == 0, f"{bad} goalie-seasons have 5v5 TOI >= all-situations TOI"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest v2/browser/tests/test_build_goalies_db.py -v -k strictly_less`
Expected: FAIL — every row is currently equal, since both cuts share the same TOI.

- [ ] **Step 3: Add the import**

In `v2/browser/build_goalies_db.py`, change line 20 to:

```python
from v2.goalies.cut import load_shots, load_toi  # noqa: E402
```

- [ ] **Step 4: Swap the read and fix the stale comment**

Replace lines 108-109:

```python
            # gp/toi/teams are all-situations by design (spec §2) — shared source
            gg = pd.read_csv(GOALIES / f"goalie_games_{season}.csv")
```

with:

```python
            # gp/teams stay all-situations: a goalie who dressed and played is
            # one appearance regardless of cut. TOI follows the cut as of
            # 2026-07-30 — see docs/plans/2026-07-30-goalie-5v5-toi-design.md.
            gg = load_toi(season, situation)
```

- [ ] **Step 5: Rebuild the database**

Run: `python v2/browser/build_goalies_db.py`
Expected: completes, reporting both situations.

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_build_goalies_db.py -v`
Expected: PASS

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest v2/ -q`
Expected: 313 passed

- [ ] **Step 8: Commit**

```bash
git add v2/browser/build_goalies_db.py v2/browser/tests/test_build_goalies_db.py
git commit -m "fix(goalies): goalie_seasons.toi_s follows the situation cut"
```

---

### Task 6: Rate metrics

**Files:**
- Modify: `v2/browser/metrics.py:122-140`
- Modify: `v2/browser/pages/goalies.py:51` (call site, so the suite stays green)
- Test: `v2/browser/test_rate_metrics.py`

**Interfaces:**
- Produces: `gsax_per60(gsax: pd.Series, toi_s: pd.Series) -> pd.Series` (the `situation` parameter is removed) and `xga_per60(xga: pd.Series, toi_s: pd.Series) -> pd.Series`. Task 7 calls both.

- [ ] **Step 1: Replace the existing gsax tests and add xga tests**

In `v2/browser/test_rate_metrics.py`, update the import line to:

```python
from metrics import carryover_per_player, events_per60, corsi_per60, gsax_per60, xga_per60
```

Then replace the three `test_gsax_per60_*` functions with:

```python
def test_gsax_per60_all_situations():
    out = gsax_per60(pd.Series([6.0, -3.0]), pd.Series([7200.0, 3600.0]))
    assert out.tolist() == [3.0, -3.0]


def test_gsax_per60_works_on_the_5v5_cut_now():
    # Was all-NaN before 2026-07-30: goalie_seasons.toi_s is cut-aware now, so
    # the caller passes 5v5 TOI and there is nothing left to guard against.
    out = gsax_per60(pd.Series([6.0]), pd.Series([5760.0]))
    assert out.tolist() == [3.75]


def test_gsax_per60_zero_toi_is_na_not_inf():
    assert gsax_per60(pd.Series([6.0]), pd.Series([0.0])).isna().all()


def test_gsax_per60_missing_toi_is_na():
    # NaN toi_s means no timeline for that goalie-season.
    assert gsax_per60(pd.Series([6.0]), pd.Series([float("nan")])).isna().all()


def test_xga_per60_basic():
    # 48 xGA over 2 h = 24 per 60.
    out = xga_per60(pd.Series([48.0, 30.0]), pd.Series([7200.0, 3600.0]))
    assert out.tolist() == [24.0, 30.0]


def test_xga_per60_zero_toi_is_na_not_inf():
    assert xga_per60(pd.Series([48.0]), pd.Series([0.0])).isna().all()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest v2/browser/test_rate_metrics.py -v -k "gsax or xga"`
Expected: FAIL at collection — `ImportError: cannot import name 'xga_per60'`

- [ ] **Step 3: Rewrite `gsax_per60` and add `xga_per60`**

In `v2/browser/metrics.py`, replace the whole `gsax_per60` function with:

```python
def gsax_per60(gsax: pd.Series, toi_s: pd.Series) -> pd.Series:
    """GSAx per 60 minutes of goaltending, valid in either situation cut.

    Pairs with GSAx/100 (per 100 shots): the /100 rate asks how well a goalie
    stopped the pucks he saw, the /60 rate asks how many goals he saved per unit
    of ice time. A goalie behind a leaky team faces more shots per 60, so the two
    can disagree — that gap is the point of showing both.

    The caller passes the TOI for its own cut; goalie_seasons.toi_s has been
    cut-aware since 2026-07-30. NaN TOI (no timeline) and zero TOI (played, saw
    no 5v5) both yield NaN.
    """
    return gsax * 3600 / toi_s.where(toi_s > 0)


def xga_per60(xga: pd.Series, toi_s: pd.Series) -> pd.Series:
    """Expected goals against per 60 minutes — the workload term.

    Reads as how much danger the team in front served up, which is what makes
    GSAx/100 and GSAx/60 disagree: two goalies with the same GSAx/100 diverge on
    GSAx/60 exactly in proportion to this.
    """
    return xga * 3600 / toi_s.where(toi_s > 0)
```

- [ ] **Step 4: Run to verify passing**

Run: `python -m pytest v2/browser/test_rate_metrics.py -v`
Expected: PASS, 15 tests

- [ ] **Step 5: Update the one existing call site**

Dropping the `situation` parameter breaks `pages/goalies.py:51`. Fix it here rather than leaving the suite red for a whole task; Task 7 does the column work.

In `v2/browser/pages/goalies.py`, change line 51 from:

```python
    df["gsax_per60"] = gsax_per60(df["gsax"], df["toi_s"], situation)
```

to:

```python
    df["gsax_per60"] = gsax_per60(df["gsax"], df["toi_s"])
```

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest v2/ -q`
Expected: 316 passed

- [ ] **Step 7: Commit**

```bash
git add v2/browser/metrics.py v2/browser/test_rate_metrics.py v2/browser/pages/goalies.py
git commit -m "feat(browser): xga_per60; gsax_per60 valid in both cuts"
```

---

### Task 7: Browser display

**Files:**
- Modify: `v2/browser/pages/goalies.py:7,23-26,50-76`
- Modify: `v2/browser/pages/goalie.py:55,123`
- Modify: `v2/browser/pages/team.py:86,93,95`
- Modify: `v2/browser/app.py:205,231-237`

**Interfaces:**
- Consumes: `gsax_per60` and `xga_per60` from Task 6, cut-aware `toi_s` from Task 5.

- [ ] **Step 1: Update the goalies page imports and note**

In `v2/browser/pages/goalies.py`, change line 7 to:

```python
from metrics import gsax_per60, xga_per60
```

Replace `_CUT_NOTE` with:

```python
_CUT_NOTE = ("Strict 5v5 (situationCode 1551): shot metrics, TOI and every rate "
             "count 5v5 play only. GP still counts appearances in all situations.")
```

- [ ] **Step 2: Make the rate columns unconditional**

Replace lines 50-76 (from `df["toi_display"]` through `display = ...`) with:

```python
    df["toi_display"] = (df["toi_s"] / df["gp"].where(df["gp"] > 0)).apply(seconds_to_mmss)
    df["gsax_per60"] = gsax_per60(df["gsax"], df["toi_s"])
    df["xga_per60"] = xga_per60(df["xga"], df["toi_s"])
    _ci = {"case": "insensitive"}
    columns = [
        {"name": "Goalie", "id": "goalie_link", "presentation": "markdown", "filter_options": _ci},
        {"name": "Team", "id": "teams", "filter_options": _ci},
        {"name": "GP", "id": "gp", "type": "numeric"},
        {"name": "TOI/GP", "id": "toi_display", "filter_options": _ci},
        {"name": "Shots", "id": "shots_faced", "type": "numeric"},
        {"name": "GA", "id": "ga", "type": "numeric"},
        {"name": "xGA", "id": "xga", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "xGA/60", "id": "xga_per60", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "GSAx", "id": "gsax", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "GSAx/100", "id": "gsax_per100", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "GSAx/60", "id": "gsax_per60", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Freeze rate", "id": "freeze_rate", "type": "numeric", "format": Format(precision=3, scheme=Scheme.fixed)},
        {"name": "Freeze pct", "id": "freeze_pct", "type": "numeric", "format": Format(precision=0, scheme=Scheme.fixed)},
        {"name": "Difficulty faced", "id": "mean_difficulty_pct", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "Perf (season z̄)", "id": "mean_perf_z", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
    ]
    display = [c["id"] for c in columns]
```

- [ ] **Step 3: Drop the stale labels on the goalie detail page**

In `v2/browser/pages/goalie.py`, replace line 55:

```python
    toi_label = "TOI/GP (all sit)" if situation == "5v5" else "TOI/GP"
    gp_line = f"GP {r['gp']} · {toi_label} {seconds_to_mmss(r['toi_s'] / max(r['gp'], 1))}"
```

with:

```python
    gp_line = f"GP {r['gp']} · TOI/GP {seconds_to_mmss(r['toi_s'] / max(r['gp'], 1))}"
```

And replace line 123:

```python
    toi_name = "TOI (all sit)" if situation == "5v5" else "TOI"
```

with:

```python
    toi_name = "TOI"
```

Then replace the `{"name": toi_name, "id": "toi_display"}` column entry with `{"name": "TOI", "id": "toi_display"}` and delete the now-unused `toi_name` variable.

- [ ] **Step 4: Drop the team-page disclaimer**

In `v2/browser/pages/team.py`, delete line 86 (`per60_suffix = ...`) and change the two list items to:

```python
            html.Li(f"xG faced/60: {r['mean_xg_faced_per60']:.2f}"),
```

```python
            html.Li(f"Cross-ice/60: {r['crossice_per60']:.2f}"),
```

- [ ] **Step 5: Correct the situation blurb and glossary**

In `v2/browser/app.py`, change the sentence at line 205 from:

```python
                "4v4 and 3v3 excluded). GP and TOI always count all situations. "
```

to:

```python
                "4v4 and 3v3 excluded), including TOI and every per-60 rate. GP "
                "counts appearances in all situations. "
```

Replace the GSAx/60 glossary entry with:

```python
            html.Dt("GSAx/60"),
            html.Dd(
                "GSAx per 60 minutes of ice time — the workload-dependent rate form. Read it "
                "against GSAx/100: a goalie who rates well per shot but poorly per 60 faced a "
                "light shot load, and one who rates well per 60 but poorly per shot was busy."
            ),
```

And add an xGA/60 entry directly after the existing xGA entry:

```python
            html.Dt("xGA/60"),
            html.Dd(
                "Expected goals against per 60 minutes — how much danger the team in front "
                "served up. This is the term that makes GSAx/100 and GSAx/60 disagree."
            ),
```

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest v2/ -q`
Expected: 316 passed

- [ ] **Step 7: Verify both cuts render**

```bash
cd v2/browser && python -c "
import app
from pages.goalies import update_goalies
for sit in ('all','5v5'):
    t = update_goalies('2025', sit).children[-1].children
    cols = [c['name'] for c in t.columns]
    assert 'GSAx/60' in cols and 'xGA/60' in cols, (sit, cols)
    r = t.data[0]
    print(sit, 'GSAx/60', round(r['gsax_per60'],2), '| xGA/60', round(r['xga_per60'],2))
"; cd -
```

Expected: both cuts print populated numbers, and the 5v5 figures are roughly a quarter larger than the all-situations ones for the same goalie.

- [ ] **Step 8: Confirm no disclaimer strings survive**

Run: `grep -rn "all sit\|per 60 total TOI" v2/browser/pages/`
Expected: no matches.

- [ ] **Step 9: Commit**

```bash
git add v2/browser/pages/goalies.py v2/browser/pages/goalie.py v2/browser/pages/team.py v2/browser/app.py
git commit -m "feat(browser): GSAx/60 and xGA/60 in both cuts; drop mixed-base caveats"
```

---

### Task 8: Acceptance

**Files:** none modified — this task verifies the spec's acceptance criteria.

- [ ] **Step 1: Re-confirm the shot layer never moved**

```bash
for f in /tmp/shotlayer-before/*.csv; do diff -q "$f" "data/generated/goalies/$(basename $f)" || echo "DRIFT: $f"; done
for f in /tmp/shotlayer-before/5v5/*.csv; do diff -q "$f" "data/generated/goalies/5v5/$(basename $f)" || echo "DRIFT: 5v5/$f"; done
echo "shot layer verified"
```

Expected: no `DRIFT:` lines. This is what protects the conclusions in `docs/plans/2026-07-21-goalie-5v5-recheck-report.md`.

- [ ] **Step 2: Check the eligibility-gate shift**

```bash
python3 -c "
import pandas as pd
d = pd.read_csv('data/generated/goalies/5v5/game_difficulty.csv')
d = d[d['season'] == 2025]
print('2025 5v5 goalie-games:', len(d))
print('with a difficulty percentile:', int(d['difficulty_pct'].notna().sum()))
"
```

Expected: roughly 2651 of 2765 eligible, about 46 fewer than the 2697 the old gate admitted.

- [ ] **Step 3: Verify all five seasons populate on the detail page**

```bash
cd v2/browser && python -c "
import app, sqlite3, pandas as pd
from db import goalies_query
df = goalies_query('SELECT season, situation, COUNT(*) n, SUM(toi_s IS NULL) nulls '
                   'FROM goalie_seasons GROUP BY 1,2 ORDER BY 1,2')
print(df.to_string(index=False))
"; cd -
```

Expected: ten rows, five seasons by two situations. `nulls` zero everywhere **except season 2021 / situation 5v5, which must show exactly 1** — Keith Kinkaid (`8476234`) played a single 2021 game and it is `2021020452`, one of the five with no timeline (Task 3 Step 1). Any other null is unexplained; stop and investigate.

Task 2's `load_toi` will also print `note: 10 2021 goalie-games have no timeline` during the 5v5 build. That is expected and correct — 10 of 2818 goalie-games across 8 goalies. It must not appear for any other season.

- [ ] **Step 4: Full suite**

Run: `python -m pytest v2/ -v`
Expected: 316 passed.

- [ ] **Step 5: Sync runtime data**

Run: `./tools/sync-runtime-data.sh`
Expected: `goalies.db situation coverage OK`, burst coverage 100%, and the file listing.

- [ ] **Step 6: Hand off**

Deployment is oiler's call and is done manually — `flyctl deploy --remote-only` from the repo root, per `docs/fly-deploy-runbook.md`. Report the branch, the task commits, and the acceptance results; do not deploy or push.
