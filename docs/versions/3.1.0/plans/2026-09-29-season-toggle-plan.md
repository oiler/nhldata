# Season toggle Implementation Plan

> Build this plan task by task, in order, in one session. Run the task's tests after each task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Dash browser switch between 2025-26 and 2026-27, show "not available yet" for a season without verified data, and keep the deploy guard strict for the default season only.

**Architecture:** A new dependency-free `seasons.py` holds the season list, the default, and small helpers, so pages stop hard-coding `"2025"` without a circular import through `app.py`. `runtime_paths.season_ready()` decides whether a season has data to show, and each season-aware page returns a "not available yet" message when it doesn't. The sync script splits seasons into two tiers. The required tier (2025) blocks deploys, and the optional tier (2026) ships only when its checks pass.

**Tech Stack:** Python 3.12 (browser image and CI) and 3.11 (orchestrator and local builds), Plotly Dash 4, dash-bootstrap-components 2, pandas, SQLite, pytest, Bash.

**Spec:** `docs/versions/3.1.0/specs/2026-09-29-season-toggle-design.md`

## Global Constraints

- Season values are 4-digit start-year strings (`"2025"`, `"2026"`) everywhere: stores, queries, paths. Only user-facing text uses `season_label()`.
- `SEASONS = ["2025", "2026"]` and `DEFAULT_SEASON = "2025"`. 2024 stays out of `SEASONS`.
- User-facing not-available text is exactly `f"{season_label(season)} data isn't available yet."`, and for goalies `f"{season_label(season)} goalie data isn't available yet."`.
- Missing numeric values render as `—` (U+2014) through `Format(...).nully("—")`. Never write the string `"—"` into a numeric column.
- Tests use synthetic data only (the pattern in `v2/browser/tests/test_player_metrics.py`). Every test goes red before the code that makes it pass.
- Run tests from the repo root with `python -m pytest`. Browser test files add `v2/browser` to `sys.path` the way existing test files do.
- Pages can be imported in tests only after `import app` (it registers the page registry). Dash callbacks are directly callable in tests.
- Git: trunk-based, as `AGENTS.md` section "Project rules" says. Build in the main checkout on `master`. Commit each task once its tests pass, and push it. Each commit leaves `master` working, because the 08:00 orchestrator runs from this checkout. Never deploy without oiler's approval.
- Review: Tasks 6, 8, and 12 change the database build and the deploy guard. Before pushing each of them, run an independent review in a fresh-context subagent on the task's diff, and fix or report its findings. Other tasks push once their tests pass.
- Don't touch `v2/browser/runtime_data/` contents except through `tools/sync-runtime-data.sh`.
- The early-season `build_league_db.py` fix (empty `player_metrics` and `constants`) is committed to master in Task 0. Don't redo it.
- Test runs in Tasks 1–12 use `python -m pytest v2/ -q -m "not requires_data"`, the CI command, so each pushed commit passes CI. Task 13 rebuilds the data and runs the full suite.
- New imports in an existing test file go in that file's top import block, not beside the appended tests.
- A test that guards existing behavior passes before the change. Where a task marks a test as a guard, prove it can fail by temporarily breaking the code it covers, then restore the code (the `coding-defaults` skill, "Existing code with no test").

## Review Focus

1. A session-persisted radio value that's no longer in `SEASONS` (after a future rollover) must fall back to `DEFAULT_SEASON`, not reach queries. Pinned in Task 11 (`sync_season("2019")`).
2. A junk or hostile `/elites?season=` value (`"../x"`, `"2024"`) must query only `DEFAULT_SEASON`. Pinned in Task 9.
3. An empty-string or null `birthDate` must give no age (em dash), not a crash. Pinned in Task 2.
4. A team missing from `goalies.db` in a season that has goalie data must omit the goalie section, not claim the season is unavailable. Pinned in Task 9.
5. An optional season that synced before but now fails a check must be removed from `runtime_data/`, never left stale. Pinned in Task 12 (`test_optional_season_bursts_missing_removes_stale_copy` starts with a pre-existing `runtime_data/2026/`).

---

### Task 0: Preconditions (oiler, before branching)

Done before 2026-11-17. The paths below predate the move of these documents into `docs/versions/3.1.0/`.

The main checkout's working tree holds uncommitted work this plan depends on. A branch cut from the current HEAD (`78ce20f`) has none of it, and Task 6 edits two of the same files, so a later merge would fail.

- [ ] **Step 1: Commit the season-rollover work on master (oiler)**

Commit these working-tree changes on master:
- `v2/browser/build_league_db.py` and `v2/browser/tests/test_player_metrics.py` (the early-season fix)
- `v2/orchestrator/config.py`, `v2/orchestrator/com.nhl.orchestrator.plist`, and `v1/nhlgame.py` (the 2026 season switch)
- `docs/superpowers/` (this plan, its spec, and the reviews) and `BACKLOG.md`
- `CLAUDE.md` (the `docs/superpowers/` directory tree)

Don't `git stash` instead: the 08:00 orchestrator runs from this working tree, and stashing reverts it to `NHL_SEASON=2025`.

- [ ] **Step 2: Confirm and branch**

Run: `git show HEAD:v2/browser/build_league_db.py | grep -q _write_empty_player_metrics && echo ok`
Expected: `ok`.

---

### Task 1: Season config module

**Files:**
- Create: `v2/browser/seasons.py`
- Test: `v2/browser/tests/test_seasons.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SEASONS: list[str]`, `DEFAULT_SEASON: str`, `normalize_season(value) -> str`, `season_label(season: str) -> str`, `age_cutoff(season: str) -> datetime.date`.

- [x] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_seasons.py
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from seasons import DEFAULT_SEASON, SEASONS, age_cutoff, normalize_season, season_label


def test_seasons_and_default():
    assert SEASONS == ["2025", "2026"]
    assert DEFAULT_SEASON == "2025"


def test_normalize_season_keeps_known_values():
    assert normalize_season("2025") == "2025"
    assert normalize_season("2026") == "2026"


def test_normalize_season_rejects_unknown_values():
    for bad in ("2024", "2019", "../x", "", None, 2026):
        assert normalize_season(bad) == DEFAULT_SEASON


def test_season_label():
    assert season_label("2025") == "2025-26"
    assert season_label("2026") == "2026-27"
    assert season_label("2099") == "2099-00"


def test_age_cutoff():
    assert age_cutoff("2026") == date(2026, 9, 15)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_seasons.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'seasons'`

- [x] **Step 3: Write the implementation**

```python
# v2/browser/seasons.py
"""Seasons the browser offers, keyed by 4-digit start year.

Kept free of app and page imports so every module can use it: pages can't
import from app.py, because app.py loads the pages.
"""

from datetime import date

SEASONS = ["2025", "2026"]
DEFAULT_SEASON = "2025"


def normalize_season(value) -> str:
    """Return `value` if it's an offered season, else DEFAULT_SEASON.

    Season values arrive from the client (store, radio, query string) and end
    up in file paths and int() calls, so unknown values never pass through.
    """
    return value if value in SEASONS else DEFAULT_SEASON


def season_label(season: str) -> str:
    y = int(season)
    return f"{y}-{(y + 1) % 100:02d}"


def age_cutoff(season: str) -> date:
    """NHL convention: age as of Sept 15 of the season's start year."""
    return date(int(season), 9, 15)
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_seasons.py -v`
Expected: PASS (5 tests)

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass. Commit and push the task.

---

### Task 2: Age helper

**Files:**
- Modify: `v2/browser/utils.py`
- Test: `v2/browser/tests/test_utils.py` (append)

**Interfaces:**
- Consumes: `seasons.age_cutoff`.
- Produces: `utils.age_in_season(birth_date, season: str) -> int | None`.

- [x] **Step 1: Write the failing test** (append to `v2/browser/tests/test_utils.py`; add the import beside the file's existing `from utils import ...` line)

```python
from utils import age_in_season


def test_age_in_season_cutoff_boundary():
    assert age_in_season("2000-09-16", "2026") == 25
    assert age_in_season("2000-09-15", "2026") == 26


def test_age_in_season_missing_birth_date():
    assert age_in_season(None, "2026") is None
    assert age_in_season("", "2026") is None
    assert age_in_season(float("nan"), "2026") is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_utils.py -v`
Expected: ERROR at collection, `ImportError: cannot import name 'age_in_season'` (the file's existing tests also error until Step 3)

- [x] **Step 3: Write the implementation** (append to `v2/browser/utils.py`; add the imports at the top)

```python
from datetime import date

from seasons import age_cutoff


def age_in_season(birth_date, season: str):
    """Integer age at the season's Sept 15 cutoff, or None when the birth date is missing."""
    if birth_date is None or birth_date == "" or pd.isna(birth_date):
        return None
    birth = date.fromisoformat(birth_date)
    cutoff = age_cutoff(season)
    age = cutoff.year - birth.year
    if (cutoff.month, cutoff.day) < (birth.month, birth.day):
        age -= 1
    return age
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_utils.py -v`
Expected: PASS

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass.

---

### Task 3: Season readiness

**Files:**
- Modify: `v2/browser/runtime_paths.py`
- Test: `v2/browser/tests/test_runtime_paths.py` (append)

**Interfaces:**
- Consumes: existing `league_db`, `player_bursts_csv`, `_runtime_mode`.
- Produces: `runtime_paths.season_ready(season: str) -> bool`.

- [x] **Step 1: Write the failing test** (append; add `season_ready` to the file's `from runtime_paths import ...` line)

```python
def test_season_ready_production_needs_both_files(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "2026").mkdir()
    assert season_ready("2026") is False
    (tmp_path / "2026" / "player_bursts.csv").write_text("playerId\n1\n")
    assert season_ready("2026") is False  # CSV alone isn't enough
    (tmp_path / "2026" / "player_bursts.csv").unlink()
    (tmp_path / "2026" / "league.db").write_bytes(b"x")
    assert season_ready("2026") is False  # league.db alone isn't enough
    (tmp_path / "2026" / "player_bursts.csv").write_text("playerId\n1\n")
    assert season_ready("2026") is True


def test_season_ready_local_dev_needs_only_league_db(monkeypatch, tmp_path):
    import runtime_paths
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setattr(runtime_paths, "data_root", lambda: tmp_path)
    assert season_ready("2026") is False
    db = tmp_path / "2026" / "generated" / "browser" / "league.db"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"x")
    assert season_ready("2026") is True
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_runtime_paths.py -v`
Expected: ERROR at collection, `ImportError: cannot import name 'season_ready'` (the file's existing tests also error until Step 3)

- [x] **Step 3: Write the implementation** (append to `v2/browser/runtime_paths.py`)

```python
def season_ready(season: str) -> bool:
    """True when the season has data to show.

    Production: tools/sync-runtime-data.sh ships a non-default season only
    after its files pass every check, so both files being present means the
    season is verified. Local dev needs only league.db; burst columns show
    em dashes without the Edge CSV.
    """
    if _runtime_mode():
        return league_db(season).exists() and player_bursts_csv(season).exists()
    return league_db(season).exists()
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_runtime_paths.py -v`
Expected: PASS

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass.

---

### Task 4: Player metadata lookup and `db.py` defaults

**Files:**
- Modify: `v2/browser/db.py`
- Modify: `v2/browser/pages/player.py:19-22` (remove `_META_SQL`), `:105-116` (the metadata lookup in `layout()`, replaced by `player_meta`)
- Test: `v2/browser/tests/test_player_meta.py` (new)

**Interfaces:**
- Consumes: `seasons.SEASONS`, `seasons.DEFAULT_SEASON`.
- Produces: `db.player_meta(pid: int, seasons=SEASONS) -> pd.Series | None` with fields `firstName, lastName, currentTeamAbbrev, position`. `league_query(..., season=DEFAULT_SEASON)` and `all_teams(season=DEFAULT_SEASON)` defaults.

- [x] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_player_meta.py
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import player_meta


def _players_db(root, season, rows):
    path = root / season / "league.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    pd.DataFrame(rows).to_sql("players", conn, index=False)
    conn.close()


def _row(pid, team):
    return {"playerId": pid, "firstName": "A", "lastName": "B",
            "currentTeamAbbrev": team, "position": "C"}


def test_player_meta_prefers_newest_season(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _players_db(tmp_path, "2025", [_row(1, "EDM"), _row(3, "EDM")])
    _players_db(tmp_path, "2026", [_row(1, "VAN"), _row(2, "CGY")])
    assert player_meta(1)["currentTeamAbbrev"] == "VAN"
    assert player_meta(2)["currentTeamAbbrev"] == "CGY"
    # In 2025 only, while the 2026 DB exists: falls back to the older season.
    assert player_meta(3)["currentTeamAbbrev"] == "EDM"


def test_player_meta_unknown_player(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _players_db(tmp_path, "2025", [_row(1, "EDM")])
    assert player_meta(999) is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_player_meta.py -v`
Expected: ERROR at collection, `ImportError: cannot import name 'player_meta'` (the file's existing tests also error until Step 3)

- [x] **Step 3: Write the implementation**

In `v2/browser/db.py`, add `from seasons import DEFAULT_SEASON, SEASONS` under the existing imports, change `def league_query(sql: str, params=(), season: str = "2025")` to `season: str = DEFAULT_SEASON`, change `def all_teams(season: str = "2025")` to `season: str = DEFAULT_SEASON`, then append:

```python
_META_SQL = """
SELECT firstName, lastName, currentTeamAbbrev, position
FROM players WHERE playerId = ?
"""


def player_meta(pid: int, seasons=SEASONS):
    """Newest season's players row for `pid`, or None if no season has it."""
    for season in reversed(seasons):
        df = league_query(_META_SQL, params=(pid,), season=season)
        if not df.empty:
            return df.iloc[0]
    return None
```

In `v2/browser/pages/player.py`, delete the `_META_SQL` constant, change the import to `from db import league_query, player_meta`, and replace the lookup block in `layout()`:

```python
    m = player_meta(pid)
    if m is None:
        name = f"Player {pid}"
        subtitle = ""
        pos_code = "F"
    else:
        name = f"{m['firstName']} {m['lastName']}"
        subtitle = f"{m['currentTeamAbbrev']} · {m['position']}"
        pos_code = "D" if m["position"] == "D" else "F"
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_player_meta.py -v`
Expected: PASS

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass.

---

### Task 5: Per-season burst loader

**Files:**
- Modify: `v2/browser/burst_data.py`
- Test: `v2/browser/tests/test_burst_data.py` (append)

**Interfaces:**
- Consumes: `runtime_paths.player_bursts_csv`, `seasons.DEFAULT_SEASON`.
- Produces: `burst_data.bursts_for(season: str) -> pd.DataFrame` indexed by `playerId` with columns `bursts_per_60, speed_max_mph, birth_date`; `lru_cache`d (call `bursts_for.cache_clear()` in tests). `burst_data.preload_ready_seasons(seasons) -> None`, which Task 10 calls from `skaters.py` at import.
- Also consumes: `runtime_paths.season_ready` (Task 3).

- [x] **Step 1: Write the failing test** (reuse the file's `_write_csv` and `_VALID_ROW`)

Add `import burst_data` and `from burst_data import bursts_for, preload_ready_seasons` to the file's top import block, then append:

```python
@pytest.fixture
def clear_bursts_cache():
    bursts_for.cache_clear()
    yield
    bursts_for.cache_clear()


def test_bursts_for_missing_season_is_empty_in_dev(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setattr(burst_data, "player_bursts_csv", lambda s: tmp_path / f"{s}.csv")
    df = bursts_for("2026")
    assert df.empty
    assert df.index.name == "playerId"
    assert {"bursts_per_60", "speed_max_mph"} <= set(df.columns)


def test_bursts_for_reads_each_seasons_own_csv(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.delenv("DATA_DIR", raising=False)
    _write_csv(tmp_path / "2025.csv", [_VALID_ROW])
    _write_csv(tmp_path / "2026.csv", [{**_VALID_ROW, "speed_max_mph": 25.1}])
    monkeypatch.setattr(burst_data, "player_bursts_csv", lambda s: tmp_path / f"{s}.csv")
    assert bursts_for("2025").loc[8478402, "speed_max_mph"] == 24.6
    assert bursts_for("2026").loc[8478402, "speed_max_mph"] == 25.1


def test_preload_fails_boot_on_empty_csv_for_ready_season(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "2026").mkdir()
    (tmp_path / "2026" / "league.db").write_bytes(b"x")
    _write_csv(tmp_path / "2026" / "player_bursts.csv", [])  # header only
    with pytest.raises(RuntimeError):
        preload_ready_seasons(["2026"])


def test_preload_skips_season_not_in_image(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    preload_ready_seasons(["2026"])  # no files: skipped with a warning, no raise


def test_preload_does_nothing_in_local_dev(tmp_path, monkeypatch, clear_bursts_cache):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setattr(burst_data, "player_bursts_csv", lambda s: tmp_path / f"{s}.csv")
    preload_ready_seasons(["2026"])
    assert bursts_for.cache_info().currsize == 0
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_burst_data.py -v`
Expected: ERROR at collection, `ImportError: cannot import name 'bursts_for'` (the file's existing tests also error until Step 3)

- [x] **Step 3: Write the implementation**

In `v2/browser/burst_data.py`:

1. Replace the module docstring with:

```python
"""Loads the speed-burst dataset behind the skaters leaderboard's SB/a60 and
Max MPH columns. (Age comes from the players table, not this file.)

The CSV is baked into the deployed image by tools/sync-runtime-data.sh, so a
missing or empty file for a season the image ships is a deploy mistake, not
missing upstream data. In production the skaters page loads every ready
season at import, so a bad file fails boot and the deploy fails loudly. On
this single-machine app that means production is down until you roll back
(see the deploy runbook), which is why the sync script and the Dockerfile
guard check these files first. Local dev (DATA_DIR unset) degrades
gracefully so the app still runs without the edge pipeline output.
"""
```

2. Add `import functools` and `from seasons import DEFAULT_SEASON` to the imports, and change `def load_bursts(season: str = "2025", csv_path=None)` to `season: str = DEFAULT_SEASON`.
3. Change the `detail` line to `detail = f"{reason} — skater SB/a60 and Max MPH depend on it."`.
4. Add `season_ready` to the existing `from runtime_paths import ...` line, then append:

```python
@functools.lru_cache(maxsize=None)
def bursts_for(season: str) -> pd.DataFrame:
    """load_bursts(season) indexed by playerId, cached for the process lifetime.

    Burst CSVs change only on a manual Edge run; restart the app after one.
    """
    return load_bursts(season).set_index("playerId")


def preload_ready_seasons(seasons) -> None:
    """Production only: load each ready season's bursts now, so a present-but-empty
    CSV fails boot rather than a request. Seasons left out of the image are logged
    and skipped; the browser shows them as not available."""
    if not is_runtime_mode():
        return
    for season in seasons:
        if season_ready(season):
            bursts_for(season)
        else:
            logger.warning("season %s not in image; the browser shows it as not available", season)
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_burst_data.py -v`
Expected: PASS (existing tests included)

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass.

---

### Task 6: `birthDate` in the players table

**Files:**
- Modify: `v2/browser/build_league_db.py` (`build_players_table` `keep` list; `_recover_missing_players` row dict)
- Test: `v2/browser/tests/test_player_metrics.py` (append; update `_setup_recovery_db`)

**Interfaces:**
- Consumes: `players.csv` column `birthDate` (ISO `YYYY-MM-DD`), player JSON field `birthDate`.
- Produces: `league.db` `players.birthDate` (TEXT, nullable).

- [x] **Step 1: Write the failing tests**

In `_setup_recovery_db()`, add `"birthDate": "1990-01-01"` to the existing players row, so the table has the column the recovery path appends to. Then append:

```python
def test_players_table_carries_birth_date(tmp_path, monkeypatch):
    import build_league_db
    csv = tmp_path / "players.csv"
    pd.DataFrame([{
        "playerId": 1, "firstName": "A", "lastName": "B", "currentTeamAbbrev": "EDM",
        "position": "C", "shootsCatches": "L", "heightInInches": 72,
        "weightInPounds": 198, "birthDate": "1997-01-13", "extra": "ignored",
    }]).to_csv(csv, index=False)
    monkeypatch.setattr(build_league_db, "PLAYERS_CSV", str(csv))
    conn = sqlite3.connect(":memory:")
    build_league_db.build_players_table(conn)
    row = conn.execute("SELECT birthDate FROM players WHERE playerId = 1").fetchone()
    assert row == ("1997-01-13",)


def test_recover_missing_players_carries_birth_date(tmp_path, monkeypatch):
    import build_league_db
    conn = _setup_recovery_db()
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    (players_dir / "99999.json").write_text(json.dumps({
        "firstName": {"default": "New"}, "lastName": {"default": "Guy"},
        "currentTeamAbbrev": "FLA", "position": "C", "shootsCatches": "R",
        "heightInInches": 70, "weightInPounds": 180, "birthDate": "2004-02-29",
    }))
    monkeypatch.setattr(build_league_db, "SEASON_DIR", str(tmp_path))
    _recover_missing_players(conn)
    row = conn.execute("SELECT birthDate FROM players WHERE playerId = 99999").fetchone()
    assert row == ("2004-02-29",)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -v -k "birth_date or recover"`
Expected: the two new tests FAIL (`no such column: birthDate` for the first; `None` birthDate or a missing-column error for the second). The existing recovery tests still pass.

- [x] **Step 3: Write the implementation**

In `build_players_table()`, add `"birthDate"` to `keep`:

```python
    keep = [
        "playerId", "firstName", "lastName",
        "currentTeamAbbrev", "position", "shootsCatches",
        "heightInInches", "weightInPounds", "birthDate",
    ]
```

In `_recover_missing_players()`, add to the `recovered.append({...})` dict:

```python
            "birthDate": d.get("birthDate"),
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -v`
Expected: PASS (all, including the two early-season tests already there)

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass.

- [x] **Step 6: Rebuild both seasons' databases**

From Task 8 on, the sync refuses a `league.db` without `players.birthDate`. Rebuild now, after this task's commit, so a deploy stays possible during the rest of the build. Back up first.

Run: `cp data/2025/generated/browser/league.db "$TMPDIR/league-2025-pre-birthdate.db" && python v2/browser/build_league_db.py 2025 && python v2/browser/build_league_db.py 2026`
Expected: both end with `Done.`, and `sqlite3 data/2025/generated/browser/league.db "select count(birthDate) from players"` is close to the row count. If the 2025 build fails, restore the backup.

---

### Task 6b: Opening-night build creates every table and column the pages read

The early-season fix covers `player_metrics` and `constants`. Two more gaps break pages early in a season:
- `build_points_5v5_table()` returns without creating `points_5v5` when the season has no 5v5 goals yet, and `build_elite_forwards_table()` then crashes reading it.
- `recompute_pct_vs_elite_fwd()` and `recompute_pct_vs_elite_def()` return before adding `pct_any_elite_fwd` and `pct_any_elite_def` to `competition` when there are no elites. Elites need 10 GP (forwards) and 20 GP (defensemen), and `pages/skaters.py` selects both columns, so `/skaters` raises for roughly the first six weeks of 2026-27.

**Files:**
- Modify: `v2/browser/build_league_db.py` (`build_points_5v5_table`, `recompute_pct_vs_elite_fwd`, `recompute_pct_vs_elite_def`)
- Test: `v2/browser/tests/test_build_opening_night.py` (new)

**Interfaces:**
- Consumes: the builders in `main()` order; the module path constants `SEASON_DIR`, `COMPETITION_DIR`, `PLAYERS_CSV`, `FLATBOXSCORES_CSV`, `FLATPLAYS_DIR`.
- Produces: after any build, `league.db` has every table in `verify_runtime_data.REQUIRED_TABLES` (Task 8), and `competition` has `pct_any_elite_fwd` and `pct_any_elite_def`.

- [x] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_build_opening_night.py
"""Spec Testing row 1: a full build in main() order on a season's first game."""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import build_league_db as b

_COMP_COLS = ["gameId", "playerId", "team", "position", "toi_seconds", "total_toi_seconds",
              "comp_fwd", "comp_def", "pct_vs_top_fwd", "pct_vs_top_def", "height_in", "weight_lbs",
              "heaviness", "weighted_forward_heaviness", "weighted_defense_heaviness",
              "weighted_team_heaviness", "line_number", "deployment_score"]
_SKATERS = [(1, "EDM", "C"), (2, "EDM", "D"), (3, "VAN", "C"), (4, "VAN", "D")]


def _opening_night(tmp_path, monkeypatch):
    """One game, four skaters, no flatplays (so no 5v5 goals), no timelines."""
    season = tmp_path / "2026"
    comp = season / "generated" / "competition"
    comp.mkdir(parents=True)
    pd.DataFrame([
        dict(zip(_COMP_COLS, [2026020004, pid, team, "D" if pos == "D" else "F", 900, 1100,
                              800.0, 900.0, 0.5, 0.5, 72, 198, 2.75, 2.7, 2.8, 2.75, 1, 100]))
        for pid, team, pos in _SKATERS
    ]).to_csv(comp / "2026020004.csv", index=False)
    (season / "generated" / "flatplays").mkdir(parents=True)
    (season / "generated" / "timelines" / "csv").mkdir(parents=True)
    box = season / "generated" / "flatboxscores"
    box.mkdir(parents=True)
    pd.DataFrame([{"id": 2026020004, "gameDate": "2026-09-29", "awayTeam_abbrev": "VAN",
                   "homeTeam_abbrev": "EDM", "awayTeam_score": 1, "homeTeam_score": 2,
                   "periodDescriptor_number": 3}]).to_csv(box / "boxscores.csv", index=False)
    (season / "players").mkdir()
    pcsv = season / "generated" / "players" / "csv" / "players.csv"
    pcsv.parent.mkdir(parents=True)
    pd.DataFrame([{"playerId": pid, "firstName": "F", "lastName": "L", "currentTeamAbbrev": team,
                   "position": pos, "shootsCatches": "L", "heightInInches": 72,
                   "weightInPounds": 198, "birthDate": "2000-01-01"}
                  for pid, team, pos in _SKATERS]).to_csv(pcsv, index=False)
    for name, val in [("SEASON_DIR", season), ("COMPETITION_DIR", comp), ("PLAYERS_CSV", pcsv),
                      ("FLATBOXSCORES_CSV", box / "boxscores.csv"),
                      ("FLATPLAYS_DIR", season / "generated" / "flatplays")]:
        monkeypatch.setattr(b, name, str(val))


def test_opening_night_build_creates_every_page_table(tmp_path, monkeypatch):
    _opening_night(tmp_path, monkeypatch)
    conn = sqlite3.connect(":memory:")
    for step in (b.build_competition_table, b.build_players_table, b._recover_missing_players,
                 b.build_games_table, b.build_points_5v5_table, b.build_events_5v5_table,
                 b.build_onice_5v5_table, b.build_elite_forwards_table, b.recompute_pct_vs_elite_fwd,
                 b.build_elite_defensemen_table, b.recompute_pct_vs_elite_def,
                 b.build_player_metrics_table, b.build_constants_table):
        step(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"competition", "players", "games", "points_5v5", "events_5v5", "onice_5v5",
            "elite_forwards", "elite_defensemen", "player_metrics", "constants"} <= tables
    cols = {r[1] for r in conn.execute("PRAGMA table_info(competition)")}
    assert {"pct_any_elite_fwd", "pct_any_elite_def"} <= cols
```

The step list mirrors `main()` minus `_log_elite_changes`, which writes a changelog file and reads no table the pages need.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_build_opening_night.py -v`
Expected: FAIL with `no such table: points_5v5`, raised from `build_elite_forwards_table`. (Verified against the current code in a scratch run on 2026-09-29.)

- [x] **Step 3: Write the implementation**

In `build_points_5v5_table()`, replace the `if not frames:` branch:

```python
    if not frames:
        # Downstream builders and pages read points_5v5 unconditionally.
        pd.DataFrame(columns=["gameId", "playerId", "goals", "assists", "points"]).to_sql(
            "points_5v5", conn, if_exists="replace", index=False
        )
        print("  points_5v5: 0 rows (no 5v5 goals found)")
        return
```

In `recompute_pct_vs_elite_fwd()`, move the "Ensure pct_any_elite_fwd column exists" block above the elite lookup, so the start of the function reads:

```python
    # Pages select pct_any_elite_fwd, so the column must exist before any early
    # return (no elites until forwards reach 10 GP).
    cols = {r[1] for r in conn.execute("PRAGMA table_info(competition)").fetchall()}
    if "pct_any_elite_fwd" not in cols:
        conn.execute("ALTER TABLE competition ADD COLUMN pct_any_elite_fwd REAL DEFAULT 0.0")
        conn.commit()

    elite_rows = conn.execute("SELECT playerId FROM elite_forwards").fetchall()
    if not elite_rows:
        print("  pct_vs_elite_fwd: skipped (no elite forwards)")
        return
    elite_set = {r[0] for r in elite_rows}
```

Make the matching change in `recompute_pct_vs_elite_def()`:

```python
    # Pages select pct_any_elite_def, so the column must exist before any early
    # return (no elites until defensemen reach 20 GP).
    cols = {r[1] for r in conn.execute("PRAGMA table_info(competition)").fetchall()}
    if "pct_any_elite_def" not in cols:
        conn.execute("ALTER TABLE competition ADD COLUMN pct_any_elite_def REAL DEFAULT 0.0")
        conn.commit()

    elite_rows = conn.execute(
        "SELECT playerId FROM elite_defensemen"
    ).fetchall()
    if not elite_rows:
        print("  pct_vs_elite_def: skipped (no elite defensemen)")
        return
    elite_set = {r[0] for r in elite_rows}
```

Delete the original "Ensure ... column exists" blocks that followed `elite_set = ...` in both functions.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_build_opening_night.py v2/browser/tests/test_player_metrics.py -v`
Expected: PASS. The existing `recompute_pct_vs_elite_*` tests still pass.

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass.

---

### Task 7: Date-range fallback and the not-ready message

**Files:**
- Modify: `v2/browser/filters.py:9-19` (`season_date_range`), `:97` (callback default), imports
- Test: `v2/browser/tests/test_filters_season.py` (new)

**Interfaces:**
- Consumes: `seasons.normalize_season`, `seasons.season_label`, `seasons.DEFAULT_SEASON`, `runtime_paths.season_ready`.
- Produces: `filters.season_date_range(season: str = DEFAULT_SEASON) -> tuple[str, str]`; `filters.season_not_ready(season: str) -> html.P | None`.

- [x] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_filters_season.py
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from filters import season_date_range, season_not_ready


def test_fallback_range_for_missing_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert season_date_range("2026") == ("2026-09-01", "2027-06-30")


def test_fallback_range_when_no_scored_games(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    db = tmp_path / "2026" / "league.db"
    db.parent.mkdir()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE games (gameDate TEXT, awayTeam_score INTEGER)")
    conn.execute("INSERT INTO games VALUES ('2026-09-29', NULL)")
    conn.commit()
    conn.close()
    assert season_date_range("2026") == ("2026-09-01", "2027-06-30")


def test_not_ready_message(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    msg = season_not_ready("2026")
    assert msg is not None
    assert msg.children == "2026-27 data isn't available yet."


def test_ready_season_has_no_message(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "2026").mkdir()
    (tmp_path / "2026" / "league.db").write_bytes(b"x")
    (tmp_path / "2026" / "player_bursts.csv").write_text("playerId\n1\n")
    assert season_not_ready("2026") is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_filters_season.py -v`
Expected: ERROR at collection, `ImportError: cannot import name 'season_not_ready'` (the file's existing tests also error until Step 3)

- [x] **Step 3: Write the implementation**

In `v2/browser/filters.py`, add imports:

```python
from runtime_paths import season_ready
from seasons import DEFAULT_SEASON, normalize_season, season_label
```

Replace `season_date_range`:

```python
def season_date_range(season: str = DEFAULT_SEASON) -> tuple[str, str]:
    """Return (min_date, max_date) from the games table.

    Falls back to Sept 1 of the start year through June 30 of the next when the
    season has no scored games yet. Sept 1 covers a late-September opener.
    """
    season = normalize_season(season)
    df = league_query(
        "SELECT MIN(gameDate) AS min_d, MAX(gameDate) AS max_d FROM games WHERE awayTeam_score IS NOT NULL",
        season=season,
    )
    if df.empty or pd.isna(df.iloc[0]["min_d"]):
        yr = int(season)
        return (f"{yr}-09-01", f"{yr + 1}-06-30")
    return (df.iloc[0]["min_d"], df.iloc[0]["max_d"])


def season_not_ready(season: str):
    """The not-available message when `season` has no data to show, else None."""
    if season_ready(season):
        return None
    return html.P(f"{season_label(season)} data isn't available yet.")
```

In the `register_season_callback` inner function, change `season_date_range(season or "2025")` to `season_date_range(season)`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_filters_season.py -v`
Expected: PASS

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass.

---

### Task 8: Table and `birthDate` checks in `verify_runtime_data.py`

**Files:**
- Modify: `v2/browser/verify_runtime_data.py`
- Test: `v2/browser/tests/test_verify_runtime_data.py` (append)

**Interfaces:**
- Consumes: a `league.db` with `competition(playerId, position)` and `players(playerId, birthDate)`.
- Produces: `verify_tables(db_path) -> tuple[bool, str]` and `verify_birthdates(db_path, min_coverage=0.95) -> tuple[bool, str]`; `main()` fails when any check fails and runs `verify_tables` first. CLI unchanged: `verify_runtime_data.py <burst_csv> <league_db> [min_overlap]`. Task 12's sync script relies on the `FAIL:` lines naming the check.

- [x] **Step 1: Write the failing test** (add `verify_birthdates, verify_tables, main` to the file's existing `from verify_runtime_data import ...` line, then append)

```python
_BROWSER_TABLES = ["games", "points_5v5", "events_5v5", "onice_5v5", "elite_forwards",
                   "elite_defensemen", "player_metrics", "constants"]


def _add_browser_tables(path, skip=()):
    con = sqlite3.connect(path)
    for t in _BROWSER_TABLES:
        if t not in skip:
            con.execute(f"CREATE TABLE {t} (x INTEGER)")
    con.commit()
    con.close()


def _make_players(path, rows, with_column=True):
    con = sqlite3.connect(path)
    if with_column:
        con.execute("CREATE TABLE players (playerId INTEGER, birthDate TEXT)")
        con.executemany("INSERT INTO players VALUES (?, ?)", rows)
    else:
        con.execute("CREATE TABLE players (playerId INTEGER)")
        con.executemany("INSERT INTO players VALUES (?)", [(r[0],) for r in rows])
    con.commit()
    con.close()


def test_birthdates_ok(tmp_path):
    db = _make_db(tmp_path / "l.db", list(range(20)))
    _make_players(db, [(i, "2000-01-01") for i in range(20)])
    ok, _ = verify_birthdates(db)
    assert ok


def test_birthdates_missing_column(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, None), (2, None)], with_column=False)
    ok, msg = verify_birthdates(db)
    assert not ok
    assert "birthDate" in msg


def test_birthdates_low_coverage(tmp_path):
    db = _make_db(tmp_path / "l.db", list(range(20)))
    _make_players(db, [(i, "2000-01-01") for i in range(18)] + [(18, None), (19, "")])
    ok, msg = verify_birthdates(db)
    assert not ok
    assert "90.0%" in msg


def test_tables_all_present(tmp_path):
    db = _make_db(tmp_path / "l.db", [1])
    _make_players(db, [(1, "2000-01-01")])
    _add_browser_tables(db)
    ok, _ = verify_tables(db)
    assert ok


def test_tables_missing_one(tmp_path):
    db = _make_db(tmp_path / "l.db", [1])
    _make_players(db, [(1, "2000-01-01")])
    _add_browser_tables(db, skip=("points_5v5",))
    ok, msg = verify_tables(db)
    assert not ok
    assert "points_5v5" in msg


def test_main_passes_complete_db(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, "2000-01-01"), (2, "2000-01-01")])
    _add_browser_tables(db)
    csv = _make_csv(tmp_path / "b.csv", [1, 2])
    assert main([str(csv), str(db)]) == 0


def test_main_fails_when_birthdates_fail(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, None), (2, None)], with_column=False)
    _add_browser_tables(db)
    csv = _make_csv(tmp_path / "b.csv", [1, 2])
    assert main([str(csv), str(db)]) == 1


def test_main_fails_on_partial_db(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, "2000-01-01"), (2, "2000-01-01")])
    _add_browser_tables(db, skip=("player_metrics",))
    csv = _make_csv(tmp_path / "b.csv", [1, 2])
    assert main([str(csv), str(db)]) == 1
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_verify_runtime_data.py -v`
Expected: ERROR at collection, `ImportError: cannot import name 'verify_birthdates'` (the file's existing tests also error until Step 3)

- [x] **Step 3: Write the implementation**

In `v2/browser/verify_runtime_data.py`, replace the module docstring (lines 1-11) with:

```python
"""Pre-deploy checks on a season's synced runtime files.

tools/sync-runtime-data.sh runs this against each season's staged files so a
bad season fails the sync *before* `fly deploy`:

- league.db has every table the browser reads (a build that died partway
  leaves a file that passes the other checks but breaks pages);
- player_bursts.csv covers the season's skaters (an empty, stale, or
  mismatched CSV would ship blank SB/a60 and Max MPH columns);
- players.birthDate exists and covers the skaters (the skaters Age column
  reads it).

CLI:  python verify_runtime_data.py <burst_csv> <league_db> [min_overlap]
Exit 0 if every check passes, 1 otherwise.
"""
```

Add after `DEFAULT_MIN_OVERLAP`:

```python
DEFAULT_MIN_BIRTHDATE_COVERAGE = 0.95

# Every table a browser page reads. Keep in sync with FROM/JOIN targets under pages/.
REQUIRED_TABLES = ("competition", "players", "games", "points_5v5", "events_5v5", "onice_5v5",
                   "elite_forwards", "elite_defensemen", "player_metrics", "constants")


def verify_tables(db_path):
    """Return (ok, message). ok is False when any table the browser reads is
    missing: a build that died partway (timeout, exception, or a sync during
    the 08:00 rebuild) leaves a file that passes the coverage checks."""
    con = sqlite3.connect(db_path)
    try:
        have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    missing = [t for t in REQUIRED_TABLES if t not in have]
    if missing:
        return False, f"league.db missing tables {', '.join(missing)}: {db_path} — partial or failed build"
    return True, "all browser tables present"
```

Add after `verify_burst_csv`:

```python
def verify_birthdates(db_path, min_coverage: float = DEFAULT_MIN_BIRTHDATE_COVERAGE):
    """Return (ok, message). ok is False when players has no birthDate column
    (a league.db built before the column existed) or fewer than `min_coverage`
    of competition skaters have one."""
    db_path = Path(db_path)
    con = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(players)")}
        if "birthDate" not in cols:
            return False, f"players table has no birthDate column: {db_path} — rebuild with build_league_db.py"
        skaters = set(pd.read_sql_query(
            "SELECT DISTINCT playerId FROM competition WHERE position IN ('F', 'D')", con
        )["playerId"])
        have = set(pd.read_sql_query(
            "SELECT playerId FROM players WHERE birthDate IS NOT NULL AND birthDate != ''", con
        )["playerId"])
    finally:
        con.close()

    if not skaters:
        return False, f"no skaters in competition: {db_path}"
    cov = len(skaters & have) / len(skaters)
    if cov < min_coverage:
        return False, f"birthDate coverage {cov:.1%} below required {min_coverage:.0%} ({db_path})"
    return True, f"birthDate coverage {cov:.1%}"
```

Replace the body of `main` after `min_overlap = ...`:

```python
    ok, msg = verify_tables(argv[1])
    if not ok:
        print("FAIL: " + msg, file=sys.stderr)
        return 1
    results = [verify_burst_csv(argv[0], argv[1], min_overlap), verify_birthdates(argv[1])]
    for ok, msg in results:
        print(("OK: " if ok else "FAIL: ") + msg, file=sys.stdout if ok else sys.stderr)
    return 0 if all(ok for ok, _ in results) else 1
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_verify_runtime_data.py -v`
Expected: PASS, existing tests included. Don't loosen a check to make a test pass.

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass.

---

### Task 9: Season-aware pages (games, teams, team, player, goalies, elites)

**Files:**
- Modify: `v2/browser/pages/games.py`, `pages/teams.py`, `pages/team.py`, `pages/player.py`, `pages/goalies.py`, `pages/elites.py`
- Test: `v2/browser/tests/test_season_pages.py` (new)

**Interfaces:**
- Consumes: `seasons.normalize_season`, `seasons.season_label`, `filters.season_not_ready`.
- Produces: page behavior only.

- [x] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_season_pages.py
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import app  # noqa: F401 — registers pages so they can be imported
import pages.elites as elites
import pages.games as games
import pages.goalies as goalies
import pages.player as player
import pages.team as team
import pages.teams as teams

NOT_READY = "2026-27 data isn't available yet."


@pytest.mark.parametrize("call", [
    lambda d0, d1: games.update_games(d0, d1, "2026"),
    lambda d0, d1: teams.update_teams(d0, d1, "all", "2026"),
    lambda d0, d1: team.update_team(d0, d1, "all", "EDM", "2026", "all"),
    lambda d0, d1: player.update_player(d0, d1, "all", 1, "F", "2026"),
], ids=["games", "teams", "team", "player"])
def test_season_aware_page_says_not_ready(call, monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert call("2026-10-01", "2026-10-31").children == NOT_READY


def _goalies_db(root, season_rows):
    conn = sqlite3.connect(root / "goalies.db")
    pd.DataFrame(season_rows).to_sql("team_environment", conn, index=False)
    pd.DataFrame(columns=["goalie_id", "name", "teams", "gp", "toi_s", "shots_faced", "ga",
                          "xga", "gsax", "gsax_per100", "freeze_rate", "freeze_pct",
                          "mean_difficulty_pct", "mean_perf_z", "season", "situation"]
                 ).to_sql("goalie_seasons", conn, index=False)
    conn.close()


_ENV_ROW = {"season": 2025, "team_abbrev": "EDM", "situation": "all",
            "mean_difficulty_pct": 50.0, "mean_xg_faced_per60": 2.5, "hd_share": 0.2,
            "crossice_per60": 1.0, "b2b_games": 10}


def test_goalies_page_message_for_season_without_goalie_data(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _goalies_db(tmp_path, [_ENV_ROW])
    out = goalies.update_goalies("2026", "all")
    assert out.children == "2026-27 goalie data isn't available yet."


def test_team_goalie_section_season_absent_shows_message(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _goalies_db(tmp_path, [_ENV_ROW])
    section = team._goalie_environment_section("2026", "EDM", "all")
    assert "2026-27 goalie data isn't available yet." in str(section)


def test_team_goalie_section_team_absent_is_omitted(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _goalies_db(tmp_path, [_ENV_ROW])
    assert team._goalie_environment_section("2025", "XXX", "all") is None
    assert team._goalie_environment_section("2025", "EDM", "all") is not None


def test_elites_normalizes_query_string_season(monkeypatch):
    seen = []

    def fake_query(sql, params=(), season=None):
        seen.append(season)
        return pd.DataFrame()

    monkeypatch.setattr(elites, "league_query", fake_query)
    for bad in ("../x", "2024", None):
        elites.layout(season=bad)
    assert set(seen) == {"2025"}
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_season_pages.py -v`
Expected: FAIL. The page callbacks return date-range messages ("No games found in this range." and similar), the goalie texts differ, the season-absent team section is `None`, and elites queries `"../x"` and `"2024"`.

`test_team_goalie_section_team_absent_is_omitted` passes before the change: it guards today's behavior. After Step 3, prove it can fail by temporarily making the new empty branch return the message `Div` unconditionally, confirm it goes red, then restore.

- [x] **Step 3: Write the implementation**

For each of `games.py`, `teams.py`, `team.py`, and `player.py`:
1. Add imports `from filters import season_not_ready` (merge into the existing `from filters import ...` line) and `from seasons import normalize_season`.
2. In the update callback, replace `season = season or "2025"` with:

```python
    season = normalize_season(season)
    not_ready = season_not_ready(season)
    if not_ready:
        return not_ready
```

The block goes before the existing `if not date_start ...` check. The page's date pickers and Home/Away buttons stay visible but inert while the message shows. That's intended: they come back to life when the user picks a ready season.

3. Make the content region announce changes: change `html.Div(id="<page>-content")` in `layout()` to `html.Div(id="<page>-content", **{"aria-live": "polite"})`. Do the same for `goalies-content` in `goalies.py`.

In `goalies.py`: import `normalize_season, season_label` from `seasons`; replace `season = season or "2025"` with `season = normalize_season(season)`; replace the empty-result return with:

```python
    if df.empty:
        return html.P(f"{season_label(season)} goalie data isn't available yet.")
```

In `team.py`, import `season_label` too, and replace `_goalie_environment_section`'s empty branch. Add the SQL constant beside `_ENV_SQL`:

```python
_ENV_SEASON_SQL = "SELECT 1 FROM team_environment WHERE season = ? LIMIT 1"
```

```python
def _goalie_environment_section(season, team, situation):
    env = goalies_query(_ENV_SQL, params=(int(season), team, situation))
    if env.empty:
        # Only a season missing from goalies.db gets the message; a team missing
        # from a season that has goalie data keeps the section omitted.
        if goalies_query(_ENV_SEASON_SQL, params=(int(season),)).empty:
            heading = "Goalie environment (5v5)" if situation == "5v5" else "Goalie environment"
            return html.Div([
                html.H3(heading),
                html.P(f"{season_label(season)} goalie data isn't available yet."),
            ])
        return None
```

The rest of the function after that branch stays as is.

In `elites.py`: add `from seasons import normalize_season` and change `season = season or "2025"` to `season = normalize_season(season)`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_season_pages.py -v`
Expected: PASS

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"` and `grep -rn '"2025"' v2/browser/pages/ v2/browser/filters.py v2/browser/db.py v2/browser/burst_data.py`
Expected: all tests pass. The grep returns nothing except `skaters.py` (Task 10 handles it).

---

### Task 10: Skaters and game pages (per-season bursts, age from `birthDate`, em dashes)

**Files:**
- Modify: `v2/browser/pages/skaters.py`, `v2/browser/pages/game.py`, `v2/browser/pages/team.py`, `v2/browser/pages/teams.py`
- Test: `v2/browser/tests/test_season_pages.py` (append)

**Interfaces:**
- Consumes: `burst_data.bursts_for`, `utils.age_in_season`, `runtime_paths.is_runtime_mode`, `runtime_paths.season_ready`, `seasons.SEASONS`, `seasons.normalize_season`, `filters.season_not_ready`, `league.db` `players.birthDate` (Task 6), `competition.pct_any_elite_*` (Task 6b).
- Produces: `pages.skaters.attach_bursts_and_age(grouped: pd.DataFrame, season: str) -> pd.DataFrame` (adds `bursts_per_60`, `speed_max_mph`, `age`); `pages.game._league_mean_wppi(season: str) -> float | None`; page behavior otherwise.

The spec says `game.py` needs no change, but its "Pages ... don't raise" rule covers it: `game.py` runs `float()` on `AVG(wppi)`, which is `None` while `player_metrics` is empty, so every 2026-27 game page raises in the opening weeks. This task fixes that too.

- [x] **Step 1: Write the failing test** (add `import burst_data`, `import pages.game as game`, and `import pages.skaters as skaters` to the file's top import block, then append)

```python
def test_skaters_not_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert skaters.update_skaters("2026-10-01", "2026-10-31", "all", "2026").children == NOT_READY


def test_attach_bursts_and_age_uses_the_seasons_own_bursts(monkeypatch, tmp_path):
    monkeypatch.delenv("DATA_DIR", raising=False)
    pd.DataFrame({"playerId": [1], "bursts_per_60": [3.0], "speed_max_mph": [23.0],
                  "birth_date": ["2000-01-01"]}).to_csv(tmp_path / "2025.csv", index=False)
    monkeypatch.setattr(burst_data, "player_bursts_csv", lambda s: tmp_path / f"{s}.csv")
    burst_data.bursts_for.cache_clear()
    grouped = pd.DataFrame({"birthDate": ["2000-09-16", None, ""]},
                           index=pd.Index([1, 2, 3], name="playerId"))

    out26 = skaters.attach_bursts_and_age(grouped, "2026")  # no 2026 CSV
    assert out26["bursts_per_60"].isna().all()
    assert out26["speed_max_mph"].isna().all()
    assert out26.loc[1, "age"] == 25
    assert pd.isna(out26.loc[2, "age"]) and pd.isna(out26.loc[3, "age"])

    out25 = skaters.attach_bursts_and_age(grouped, "2025")
    assert out25.loc[1, "speed_max_mph"] == 23.0
    assert out25.loc[1, "age"] == 24
    burst_data.bursts_for.cache_clear()


def test_game_league_mean_wppi_is_none_while_metrics_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    db = tmp_path / "2026" / "league.db"
    db.parent.mkdir()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE player_metrics (playerId INTEGER, wppi REAL)")
    conn.commit()
    conn.close()
    assert game._league_mean_wppi("2026") is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_season_pages.py -v -k "skaters or game"`
Expected: FAIL. The skaters callback returns "No data found for this range.", and `skaters.attach_bursts_and_age` and `game._league_mean_wppi` don't exist.

- [x] **Step 3: Write the implementation**

In `v2/browser/pages/skaters.py`:

1. Imports: remove `from datetime import date` and `from burst_data import load_bursts`. Add:

```python
from burst_data import bursts_for, preload_ready_seasons
from seasons import SEASONS, normalize_season
from utils import age_in_season, seconds_to_mmss
```

Add `season_not_ready` to the `from filters import ...` line, and drop the old `from utils import seconds_to_mmss` line.

2. Delete `_AGE_CUTOFFS`, `_age_on()`, and `_BURSTS_DF = load_bursts("2025").set_index("playerId")`. Put this in their place:

```python
# Production loads every ready season's bursts at import, so a present-but-empty
# CSV fails boot and the deploy fails loudly. On this single-machine app that
# means production is down until a rollback, which is why the sync script and
# the Dockerfile guard check the files first.
preload_ready_seasons(SEASONS)


def attach_bursts_and_age(grouped, season):
    """Join the season's own Edge bursts and compute Age from birthDate at the season's cutoff."""
    out = grouped.join(bursts_for(season)[["bursts_per_60", "speed_max_mph"]])
    out["age"] = out["birthDate"].apply(lambda b: age_in_season(b, season))
    return out
```

3. In `_COMP_SQL`, change `c.position, p.shootsCatches, c.team, ...` to `c.position, p.shootsCatches, p.birthDate, c.team, ...`.
4. In `update_skaters`, replace `season = season or "2025"` with:

```python
    season = normalize_season(season)
    not_ready = season_not_ready(season)
    if not_ready:
        return not_ready
```

5. In the `comp_df.groupby("playerId").agg(...)` call, add `birthDate=("birthDate", "first"),` after `shoots=...`.
6. Replace the block from `grouped = grouped.join(_BURSTS_DF)` through the `else: grouped["age"] = None` branch with:

```python
    grouped = attach_bursts_and_age(grouped, season)
```

7. In `columns`, give every column that can be null early in a season an em dash:

```python
        {"name": "Age",          "id": "age",                "type": "numeric", "format": Format().nully("—")},
        {"name": "tTOI%",        "id": "avg_toi_share", "type": "numeric", "format": FormatTemplate.percentage(1).nully("—")},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed).nully("—")},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed).nully("—")},
        {"name": "SB/a60", "id": "bursts_per_60", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed).nully("—")},
        {"name": "Max MPH", "id": "speed_max_mph", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed).nully("—")},
        {"name": "DPS+", "id": "dps_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed).nully("—")},
```

8. In `layout()`, change `html.Div(id="skaters-content")` to `html.Div(id="skaters-content", **{"aria-live": "polite"})`.

In `v2/browser/pages/team.py`, in `_make_position_table`'s `columns`, append `.nully("—")` to the formats of the `tTOI%`, `PPI`, `PPI+`, `wPPI+`, and both `DPS+` entries. In `v2/browser/pages/teams.py`, in `update_teams`'s `columns`, append `.nully("—")` to the `PPI+` and `wPPI+` formats. Early in a season `player_metrics` is empty, so all of these are null.

In `v2/browser/pages/game.py`:

1. Add `import pandas as pd` and `from dash.dash_table.Format import Format, Scheme` to the imports.
2. Add below the imports:

```python
def _league_mean_wppi(season):
    """Season mean wPPI, or None while player_metrics is empty (a season's opening weeks)."""
    df = league_query("SELECT AVG(wppi) AS mean_wppi FROM player_metrics", season=season)
    v = df.iloc[0]["mean_wppi"] if not df.empty else None
    return float(v) if v is not None and pd.notna(v) else None
```

3. In the game wPPI+ block, replace the two lines that build `league_mean_df` and `league_mean_wppi` with `league_mean_wppi = _league_mean_wppi(season)`, and replace `players_df["ppi_plus"] = players_df["ppi_plus"].round(1)` with `players_df["ppi_plus"] = pd.to_numeric(players_df["ppi_plus"], errors="coerce").round(1)`.
4. Give the `PPI+` and `Game wPPI+` columns `"format": Format(precision=1, scheme=Scheme.fixed).nully("—")`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_season_pages.py -v`
Expected: PASS

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"` and `grep -rn '"2025"' v2/browser/pages/`
Expected: all pass; grep returns nothing.

---

### Task 11: App shell (visible filter, persistence, accessible group, styling, glossary)

**Files:**
- Modify: `v2/browser/app.py`, `v2/browser/assets/style.css`
- Test: `v2/browser/tests/test_app_season.py` (new)

**Interfaces:**
- Consumes: `seasons.SEASONS`, `DEFAULT_SEASON`, `normalize_season`, `season_label`.
- Produces: `app.toggle_season_bar(pathname) -> dict`; `app.sync_season(value) -> str`; DOM ids `season-bar`, `filter-season`; CSS classes `filter-bar-label`, `season-fieldset`, `season-options`.

Two decisions in this task:
- **`dbc.RadioItems` in a `fieldset`, not `dcc.RadioItems`.** Dash 4's `dcc.RadioItems` renders an unnamed `role="listbox"` with native radios nested in `role="option"`, and it takes no ARIA props. `dbc.RadioItems` renders native radios, and a `fieldset` and `legend` give the group its accessible name.
- **The season bar starts hidden.** It keeps `style={"display": "none"}` like `goalie-situation-bar`, and `toggle_season_bar` shows it. That departs from the spec's "loses its hard-coded `display:none`" to avoid a flash on pages that ignore the season.

- [x] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_app_season.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app


def _find(node, pred, out=None):
    out = [] if out is None else out
    if pred(node):
        out.append(node)
    kids = getattr(node, "children", None)
    for k in kids if isinstance(kids, list) else [kids]:
        if k is not None and not isinstance(k, str):
            _find(k, pred, out)
    return out


def _by_id(node, id_):
    return _find(node, lambda n: getattr(n, "id", None) == id_)


def test_season_bar_shows_on_season_aware_pages():
    for p in ["/games", "/teams", "/team/EDM", "/skaters", "/player/8478402", "/goalies"]:
        assert app.toggle_season_bar(p) == {}, p


def test_season_bar_hidden_elsewhere():
    for p in ["/", "/game/2026020001", "/goalie/8478406", "/elites", "/notes", None]:
        assert app.toggle_season_bar(p) == {"display": "none"}, p


def test_sync_season_normalizes():
    assert app.sync_season("2026") == "2026"
    assert app.sync_season("2019") == "2025"
    assert app.sync_season(None) == "2025"


def test_filter_labels_and_persistence():
    (r,) = _by_id(app.app.layout, "filter-season")
    assert [o["label"] for o in r.options] == ["2025-26", "2026-27"]
    assert r.value == "2025"
    assert r.persistence is True and r.persistence_type == "session"


def test_season_group_has_accessible_name():
    (bar,) = _by_id(app.app.layout, "season-bar")
    (fieldset,) = _find(bar, lambda n: type(n).__name__ == "Fieldset")
    legends = _find(fieldset, lambda n: type(n).__name__ == "Legend")
    assert [legend.children for legend in legends] == ["Season"]
    assert _by_id(fieldset, "filter-season")
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_app_season.py -v`
Expected: FAIL with `AttributeError: module 'app' has no attribute 'toggle_season_bar'`

- [x] **Step 3: Write the implementation**

In `v2/browser/app.py`:

1. Replace lines 6-8 (the `2024 temporarily disabled` comment, `SEASONS`, `DEFAULT_SEASON`) with:

```python
from seasons import DEFAULT_SEASON, SEASONS, normalize_season, season_label
```

2. Replace the store comment and store:

```python
    # Shared season state. store-season is memory-only; it follows the
    # filter-season radio, whose session persistence carries the choice across
    # full page loads (DataTable links reload the page).
    dcc.Store(id="store-season", storage_type="memory", data=DEFAULT_SEASON),
```

3. Replace the filter bar block (from its comment through `], className="filter-bar", style={"display": "none"}),`) with:

```python
    # Season filter. Starts hidden like goalie-situation-bar; toggle_season_bar
    # shows it on season-aware pages, which avoids a flash on the others.
    html.Div([
        html.Fieldset([
            html.Legend("Season", className="filter-bar-label"),
            dbc.RadioItems(
                id="filter-season",
                options=[{"label": season_label(s), "value": s} for s in SEASONS],
                value=DEFAULT_SEASON,
                inline=True,
                persistence=True,
                persistence_type="session",
                class_name="season-options",
            ),
        ], className="season-fieldset"),
    ], id="season-bar", className="filter-bar", style={"display": "none"}),
```

4. On the goalie situation bar's `html.Label("Situations")`, add `className="filter-bar-label"`.
5. Replace the Max MPH `html.Dd(...)` text with the following. The glossary shows on pages without the season filter, so the text doesn't refer to it:

```python
            html.Dd(
                "Top season skating speed in mph, recorded by the NHL EDGE tracking system. "
                "A single peak value across one season's regular-season ice time."
            ),
```

6. Change `sync_season` and add `toggle_season_bar` beside `toggle_goalie_situation_bar`:

```python
@callback(Output("store-season", "data"), Input("filter-season", "value"))
def sync_season(season):
    return normalize_season(season)


_SEASON_PAGES = ("/games", "/teams", "/skaters", "/goalies")
_SEASON_PAGE_PREFIXES = ("/team/", "/player/")


@callback(Output("season-bar", "style"), Input("url", "pathname"))
def toggle_season_bar(pathname):
    p = pathname or ""
    show = p in _SEASON_PAGES or p.startswith(_SEASON_PAGE_PREFIXES)
    return {} if show else {"display": "none"}
```

In `v2/browser/assets/style.css`, replace the `.filter-bar label { ... }` rule with the following. DESIGN.md sets primary text to `--text`. It makes the radio accent and the focus ring navy, and it asks for `40px` rows below `640px`.

Narrowing the eyebrow rule to `.filter-bar-label` also stops it from uppercasing the goalie situation dropdown's options, which Dash 4 renders inside `.filter-bar`. The last rule sets their size to body text. The Dash token overrides turn Dash 4's default purple (`#7f4bc4`) hover, focus, and active colors navy on both bars.

```css
.filter-bar {
  /* Dash 4 dcc controls read these tokens; the default is purple #7f4bc4. */
  --Dash-Fill-Interactive-Strong: var(--navy);
  --Dash-Text-Strong: var(--text);
}
.filter-bar .filter-bar-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-right: 0.5rem;
}
.season-fieldset {
  display: flex;
  align-items: center;
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
.season-fieldset legend {
  float: left;
  width: auto;
  margin: 0 0.5rem 0 0;
  padding: 0;
}
.season-options .form-check-label {
  color: var(--text);
  font-size: 0.9rem;
  cursor: pointer;
}
.season-options .form-check-input:checked {
  background-color: var(--navy);
  border-color: var(--navy);
}
.season-options .form-check-input:focus {
  border-color: var(--navy);
  box-shadow: 0 0 0 1px #00205B, 0 0 0 3px rgba(0, 32, 91, 0.15);
}
.filter-bar .dash-dropdown-content .dash-options-list-option { font-size: 0.9rem; }
@media (max-width: 639px) {
  .season-options .form-check { display: inline-flex; align-items: center; min-height: 40px; }
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_app_season.py v2/browser/tests/test_smoke.py -v -m "not requires_data"`
Expected: PASS

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"`
Expected: all pass.

---

### Task 12: Two-tier deploy guard

**Files:**
- Modify: `tools/sync-runtime-data.sh` (rewrite), `Dockerfile` (a new comment plus a `birthDate` guard), `.gitignore:10-13`
- Test: `v2/browser/tests/test_sync_runtime_data.py` (new)

**Interfaces:**
- Consumes: the `verify_runtime_data.py` CLI (Task 8), which checks tables, burst coverage, and `birthDate` coverage. New env overrides `SYNC_SRC` and `SYNC_DST`, which default to the repo paths and exist for the tests.
- Produces: a required season's files are replaced in `runtime_data/` only after every check passes; any failure exits non-zero and leaves the last good copy. An optional season's files ship only when every check passes; otherwise the sync removes `runtime_data/<season>/`, prints one `WARNING: <season> not synced — <reason>` line, and exits 0. The last line is a `Seasons in image:` summary.

This task turns the spec's four manual sync runs into a permanent test. The deploy guard is a high-risk boundary (the `coding-defaults` skill, "Write tests where they pay off"), and the `SYNC_SRC`/`SYNC_DST` overrides exist only so the test can point the script at fixture trees. Update the spec's Testing section to match when you next edit it.

- [x] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_sync_runtime_data.py
import os
import sqlite3
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "sync-runtime-data.sh"
_OTHER_TABLES = ["games", "points_5v5", "events_5v5", "onice_5v5", "elite_forwards",
                 "elite_defensemen", "player_metrics", "constants"]


def _league_db(path, ids, birth=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE competition (playerId INTEGER, position TEXT)")
    con.executemany("INSERT INTO competition VALUES (?, 'F')", [(i,) for i in ids])
    con.execute("CREATE TABLE players (playerId INTEGER, birthDate TEXT)")
    con.executemany("INSERT INTO players VALUES (?, ?)",
                    [(i, "2000-01-01" if birth else None) for i in ids])
    for t in _OTHER_TABLES:
        con.execute(f"CREATE TABLE {t} (x INTEGER)")
    con.commit()
    con.close()


def _bursts(path, ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"playerId": ids, "bursts_per_60": 1.0, "speed_max_mph": 20.0,
                  "birth_date": "2000-01-01"}).to_csv(path, index=False)


def _src(tmp, league_2026=True, bursts_2026="full", birth_2025=True, birth_2026=True):
    """bursts_2026: "full", "none" (file absent), "header" (header only), or a list of ids."""
    src = tmp / "data"
    ids = list(range(10))
    _league_db(src / "2024/generated/browser/league.db", ids)
    _league_db(src / "2025/generated/browser/league.db", ids, birth=birth_2025)
    (src / "2025/generated/browser/edm.db").write_bytes(b"x" * 10)
    _bursts(src / "2025/generated/edge/player_bursts.csv", ids)
    g = src / "generated/browser/goalies.db"
    g.parent.mkdir(parents=True)
    con = sqlite3.connect(g)
    pd.DataFrame({"situation": ["all", "5v5"]}).to_sql("goalie_seasons", con, index=False)
    con.close()
    if league_2026:
        _league_db(src / "2026/generated/browser/league.db", ids, birth=birth_2026)
    csv_2026 = src / "2026/generated/edge/player_bursts.csv"
    if bursts_2026 == "full":
        _bursts(csv_2026, ids)
    elif bursts_2026 == "header":
        csv_2026.parent.mkdir(parents=True, exist_ok=True)
        csv_2026.write_text("playerId,bursts_per_60,speed_max_mph,birth_date\n")
    elif isinstance(bursts_2026, list):
        _bursts(csv_2026, bursts_2026)
    return src


def _run(src, dst):
    # The script calls `python3` from PATH, which must have pandas (same as a real sync).
    env = {**os.environ, "SYNC_SRC": str(src), "SYNC_DST": str(dst)}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


def _warning_line(stderr):
    lines = [l for l in stderr.splitlines() if l.startswith("WARNING: 2026 not synced")]
    assert len(lines) == 1, stderr
    return lines[0]


def test_optional_season_synced_when_passing(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path), dst)
    assert r.returncode == 0, r.stderr
    assert (dst / "2026/league.db").exists() and (dst / "2026/player_bursts.csv").exists()
    assert "Seasons in image: 2025 (required), 2026 (optional)" in r.stdout


def test_optional_season_bursts_missing_removes_stale_copy(tmp_path):
    dst = tmp_path / "rt"
    (dst / "2026").mkdir(parents=True)
    (dst / "2026/league.db").write_bytes(b"stale")
    r = _run(_src(tmp_path, bursts_2026="none"), dst)
    assert r.returncode == 0, r.stderr
    assert "missing" in _warning_line(r.stderr)
    assert not (dst / "2026").exists()
    assert "skipped: 2026" in r.stdout


def test_optional_season_low_coverage_names_check(tmp_path):
    dst = tmp_path / "rt"
    (dst / "2026").mkdir(parents=True)
    (dst / "2026/league.db").write_bytes(b"stale")
    r = _run(_src(tmp_path, bursts_2026=[0, 1]), dst)
    assert r.returncode == 0, r.stderr
    assert "burst coverage" in _warning_line(r.stderr)
    assert not (dst / "2026").exists()


def test_optional_season_header_only_csv_names_check(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path, bursts_2026="header"), dst)
    assert r.returncode == 0, r.stderr
    assert "empty burst CSV" in _warning_line(r.stderr)
    assert not (dst / "2026").exists()


def test_optional_season_without_birthdates_names_check(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path, birth_2026=False), dst)
    assert r.returncode == 0, r.stderr
    assert "birthDate" in _warning_line(r.stderr)
    assert not (dst / "2026").exists()


def test_required_season_without_birthdates_is_fatal(tmp_path):
    r = _run(_src(tmp_path, birth_2025=False), tmp_path / "rt")
    assert r.returncode != 0
    assert "birthDate" in r.stderr


def test_required_season_failure_is_fatal_and_keeps_last_good_copy(tmp_path):
    src = _src(tmp_path)
    (src / "2025/generated/edge/player_bursts.csv").unlink()
    dst = tmp_path / "rt"
    (dst / "2025").mkdir(parents=True)
    (dst / "2025/league.db").write_bytes(b"last good")
    r = _run(src, dst)
    assert r.returncode != 0
    assert "required season 2025" in r.stderr
    assert (dst / "2025/league.db").read_bytes() == b"last good"
```

- [x] **Step 2: Run test to verify it fails**

Never run this test in the main checkout before Step 3. The old script ignores `SYNC_SRC`/`SYNC_DST`, so there it would overwrite the real `runtime_data/`. Run it in a throwaway worktree, which has no `data/`. There the old script creates empty `runtime_data/2024/` and `2025/` directories (gitignored) and fails at its first `cp`.

Run:

```bash
git worktree add --detach "$TMPDIR/nhl-sync-red" HEAD
cp v2/browser/tests/test_sync_runtime_data.py "$TMPDIR/nhl-sync-red/v2/browser/tests/"
(cd "$TMPDIR/nhl-sync-red" && python -m pytest v2/browser/tests/test_sync_runtime_data.py -v)
git worktree remove --force "$TMPDIR/nhl-sync-red"
```

Expected: all seven FAIL. The required-season tests fail on `"required season 2025" in r.stderr`, because the old script exits at `cp` with a different message.

- [x] **Step 3: Write the implementation**

Replace `tools/sync-runtime-data.sh` with:

```bash
#!/usr/bin/env bash
# Copy the runtime files the deployed app reads from the data/ pipeline tree
# into v2/browser/runtime_data/ so the Docker build can pick them up.
#
# Seasons come in two tiers:
#   required — any missing or failing file refuses the deploy (exit non-zero),
#              and the last good copy in runtime_data/ stays untouched.
#   optional — a missing or failing file leaves the season out of the image
#              with one WARNING line; the browser shows it as not available.
# Rollover: a season leaving the required tier moves to OPTIONAL_SEASONS,
# never out of both lists.
#
# Run after rebuilding any of the source DBs/CSVs:
#   python v2/browser/build_league_db.py 2025
#   python v2/browser/build_league_db.py 2026
#   python v2/browser/build_edm_db.py
#   python v2/browser/build_goalies_db.py
#   ./tools/sync-runtime-data.sh
#   fly deploy
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# SYNC_SRC/SYNC_DST exist for the tests (tests/test_sync_runtime_data.py).
SRC="${SYNC_SRC:-$REPO_ROOT/data}"
DST="${SYNC_DST:-$REPO_ROOT/v2/browser/runtime_data}"
VERIFY="$REPO_ROOT/v2/browser/verify_runtime_data.py"
if [[ -n "${SYNC_SRC:-}${SYNC_DST:-}" ]]; then
    echo "NOTE: SYNC_SRC/SYNC_DST override in effect" >&2
fi
echo "sync: $SRC -> $DST"

REQUIRED_SEASONS=("2025")
OPTIONAL_SEASONS=("2026")

# Stage a season's league.db and player_bursts.csv in a temp dir and run every
# check there. On success print the temp dir; on failure print the reason and
# return 1.
stage_season() {
    local season="$1" stage out
    stage="$(mktemp -d)"
    if ! cp "$SRC/$season/generated/browser/league.db" "$stage/league.db" 2>/dev/null \
       || ! cp "$SRC/$season/generated/edge/player_bursts.csv" "$stage/player_bursts.csv" 2>/dev/null; then
        rm -rf "$stage"
        echo "league.db or player_bursts.csv is missing"
        return 1
    fi
    if [[ ! -s "$stage/league.db" || ! -s "$stage/player_bursts.csv" ]]; then
        rm -rf "$stage"
        echo "league.db or player_bursts.csv is empty"
        return 1
    fi
    if ! out="$(python3 "$VERIFY" "$stage/player_bursts.csv" "$stage/league.db" 2>&1)"; then
        rm -rf "$stage"
        echo "${out//$'\n'/; }"
        return 1
    fi
    echo "$stage"
}

for season in "${REQUIRED_SEASONS[@]}"; do
    if ! result="$(stage_season "$season")"; then
        echo "ERROR: required season $season failed: $result — refusing to ship. runtime_data/$season/ is unchanged." >&2
        exit 1
    fi
    mkdir -p "$DST/$season"
    mv "$result/league.db" "$result/player_bursts.csv" "$DST/$season/"
    rm -rf "$result"
done

# Files outside the season tiers: named explicitly, all required.
mkdir -p "$DST/2024" "$DST/2025"
cp "$SRC/2024/generated/browser/league.db" "$DST/2024/league.db"
cp "$SRC/2025/generated/browser/edm.db"    "$DST/2025/edm.db"
cp "$SRC/generated/browser/goalies.db"     "$DST/goalies.db"
for f in "$DST/2024/league.db" "$DST/2025/edm.db" "$DST/goalies.db"; do
    if [[ ! -s "$f" ]]; then
        echo "ERROR: $f is missing or empty — refusing to ship." >&2
        exit 1
    fi
done

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

# Optional seasons: any earlier copy is removed first, so a stale season never
# ships beside a failed one.
shipped=""
skipped=""
for season in "${OPTIONAL_SEASONS[@]}"; do
    rm -rf "${DST:?}/$season"
    if result="$(stage_season "$season")"; then
        mkdir -p "$DST/$season"
        mv "$result/league.db" "$result/player_bursts.csv" "$DST/$season/"
        rm -rf "$result"
        shipped="$shipped, $season (optional)"
    else
        echo "WARNING: $season not synced — $result. The browser will show it as not available." >&2
        skipped="$skipped $season"
    fi
done

echo "Synced runtime_data:"
ls -lh "$DST"/*/
echo "Seasons in image: ${REQUIRED_SEASONS[*]} (required)${shipped}${skipped:+ | skipped:$skipped}"
```

The `shipped` and `skipped` values are strings, not arrays, because macOS `/bin/bash` 3.2 treats an empty array as unbound under `set -u`.

**Changed after the 2026-11-17 review.** The committed script differs from the listing above in three ways. It stages every required file, including `edm.db`, `goalies.db`, and the 2024 `league.db`, under one temp dir and checks them before `runtime_data/` changes, so a failed required check leaves every file untouched. Before, a bad `edm.db` or `goalies.db` left 2025 half-replaced. A `trap` removes the staging area on any exit. The season loops use `${arr[@]+"${arr[@]}"}` so an empty list runs on bash 3.2. Five tests cover these: required files arrive, a missing `edm.db` or a single-cut `goalies.db` leaves `runtime_data/` unchanged, a required failure leaves an earlier 2026 alone, and a zero-byte optional CSV is named.

In the `Dockerfile`, replace the comment block above the existing `RUN set -eu` guard with:

```dockerfile
# runtime_data/2024/, /2025/, and /2026/ are gitignored — they're built locally
# and baked in by tools/sync-runtime-data.sh. Any build from a bare git checkout
# (a CI runner, a fresh clone) silently produces an image whose skaters page
# raises at import (it preloads every ready season's bursts in production),
# which crash-loops the machine on deploy. Fail the *build* instead, before the
# image is ever pushed. Only required files are listed: optional seasons
# (2026) may be absent, and the browser then shows them as not available.
```

The file list in that guard doesn't change. Add a second guard right after it:

```dockerfile
# Each shipped league.db must carry players.birthDate (the skaters Age column
# reads it). A runtime_data/ copied without a fresh sync fails here, not in prod.
RUN set -eu; \
    for db in /app/runtime_data/2025/league.db /app/runtime_data/2026/league.db; do \
        [ -e "$db" ] || continue; \
        python -c "import sqlite3,sys; c={r[1] for r in sqlite3.connect(sys.argv[1]).execute('PRAGMA table_info(players)')}; sys.exit(0 if 'birthDate' in c else 'ERROR: players.birthDate missing in '+sys.argv[1]+' - rebuild league.db and rerun tools/sync-runtime-data.sh')" "$db"; \
    done
```

In `.gitignore`, add `v2/browser/runtime_data/2026/` after the `2025/` line.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_sync_runtime_data.py -v`
Expected: PASS (7 tests)

Then check the required-season guard: temporarily change `exit 1` in the required-season loop to `continue`, rerun, and confirm both required-season tests go red. Restore the line. (Changing it to `true`, as this step first said, survives: the next `mv` fails under `set -e` and exits non-zero anyway, so that mutation can't show the tests pin the exit.)

Check the Dockerfile guard's Python one-liner locally: run it against a `league.db` with and without a `birthDate` column (for example, the Task 8 test fixtures), and confirm it exits 0 and 1 respectively.

- [x] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q -m "not requires_data"` and `git check-ignore -v v2/browser/runtime_data/2026/league.db`
Expected: all pass; `check-ignore` prints the `.gitignore` line.

---

### Task 13: Rebuild and verify in the running app

This task runs on `master` in the main checkout, after Task 12 is pushed. Run it outside the 08:00 window. A failure found here gets fixed in a new commit.

From Task 8's commit until Step 2's rebuild of 2025, every sync is refused, because the old 2025 `league.db` has no `birthDate` column. That's the guard working.

**Files:** none changed, except oiler's local-only `docs/fly-deploy-runbook.md` in Step 7.

- [ ] **Step 1: Preconditions and backup**

Run: `ls data/2026/generated/competition/*.csv | head -1`, `ls data/2026/generated/flatboxscores/boxscores.csv`, and `cp data/2025/generated/browser/league.db /tmp/league-2025-pre-birthdate.db`
Expected: at least one 2026 competition CSV and the 2026 boxscores CSV (the orchestrator has processed a game), and the backup exists. Without them the 2026 build has no `competition` or `games` table; wait for the orchestrator to run.

- [ ] **Step 2: Rebuild both seasons**

Run: `python v2/browser/build_league_db.py 2025 && python v2/browser/build_league_db.py 2026`
Expected: both end with `Done.`; the 2026 build prints `player_metrics: 0 rows (no eligible players)` in the opening weeks. If the 2025 build fails, restore the backup to `data/2025/generated/browser/league.db`.

- [ ] **Step 2b: Run the 2026-27 Edge fetch (D51)**

Run: `NHL_SEASON=2026 python v2/edge/fetch_skater_detail.py && NHL_SEASON=2026 python v2/edge/compute_burst_rates.py`
Expected: `data/2026/generated/edge/player_bursts.csv` exists. The fetch makes about 800 requests and reads the skater list from the 2026 `league.db` that Step 2 rebuilt.

- [ ] **Step 3: Check the rebuilt databases**

Run: `python v2/browser/verify_runtime_data.py data/2025/generated/edge/player_bursts.csv data/2025/generated/browser/league.db`
Expected: `OK:` lines for the tables, burst coverage, and `birthDate coverage` at or near 100%.

Run: `cd v2/browser && python -c "from verify_runtime_data import verify_tables, verify_birthdates; db='../../data/2026/generated/browser/league.db'; print(verify_tables(db), verify_birthdates(db))"`
Expected: both `(True, ...)`. This covers the 2026 players who enter through the JSON recovery path.

Run: `python v2/browser/verify_runtime_data.py data/2026/generated/edge/player_bursts.csv data/2026/generated/browser/league.db`
Expected: the same `OK:` lines as 2025, with burst coverage of at least 80%.

- [ ] **Step 4: Run the real sync**

Run: `./tools/sync-runtime-data.sh`
Expected: exit 0, `runtime_data/2026/` holds both files, and the last line is `Seasons in image: 2025 (required), 2026 (optional)`. A `WARNING: 2026 not synced` line means a 2026 check failed; fix it before Step 5.

- [ ] **Step 5: Production-mode smoke test**

Run: `DATA_DIR=$PWD/v2/browser/runtime_data python v2/browser/app.py`, then open `http://127.0.0.1:8050`.
Expected: the app boots. `/skaters` shows Age on 2025-26, and on 2026-27 it shows Age, SB/a60, and Max MPH. Every season-aware page shows 2026-27 data.

- [ ] **Step 6: Manual checks in local dev**

Run: `cd v2/browser && python app.py`, then open `http://127.0.0.1:8050`.

- Switch seasons on games, teams, a team page, skaters, a player page, and goalies. 2026-27 shows its own data, or the not-available message.
- The season filter doesn't appear on home, a game page, a goalie page, or `/elites`.
- Open a 2026-27 game page from `/games`. It renders, with em dashes for PPI+ and Game wPPI+ in the opening weeks.
- Select 2026-27 on Skaters, click a player link, and confirm the player page shows 2026-27. Reload, and confirm the radio and content still agree.
- Open `/player/<id>` for a skater whose first NHL game is in 2026-27. The heading shows the player's name, not `Player <id>`.
- In 2026-27, PPI, PPI+, wPPI+, tTOI%, and DPS+ show em dashes while no skater has 5 games, and no page errors.
- SB/a60 and Max MPH show 2026-27 values, with em dashes only for skaters the Edge data doesn't cover. Age shows, and a skater with no `birthDate` shows `—`. The columns still sort numerically.
- At desktop width and at 375 px: the Season and Situations group labels keep the eyebrow style (0.75rem, uppercase, tertiary text), the `SEASON` label sits beside the options, the radios are navy, and the option text is `#171717`. They stay navy, never purple, on hover and on keyboard focus.
- Tab reaches the season group, and the arrow keys switch seasons. VoiceOver announces "Season" with the group.
- Under `640px`, each season option is a `40px`-tall target. On `/team/EDM` and `/goalies`, the Season and Situations bars stack without overflow.
- On `/goalies`, open the Situations dropdown: the options are sentence case, `#171717` text, and navy on hover.

- [ ] **Step 7: Update the local deploy runbook (oiler)**

In `docs/fly-deploy-runbook.md` (gitignored, local only): update the pre-flight test counts, add `2026` to the gitignored `runtime_data` list, and add a Verify bullet: "the season filter shows 2025-26 and 2026-27; 2026-27 shows data or the not-available message, matching the sync's `Seasons in image` line."

- [ ] **Step 8: Final suite**

Run: `python -m pytest v2/ -v`
Expected: all pass, including the `requires_data` tests.

This plan doesn't deploy. If you deploy afterward, use `./tools/sync-runtime-data.sh && fly deploy --remote-only`, run the runbook's Verify list, and roll back with `fly deploy --image registry.fly.io/nhl-browser:deployment-<previous id>` if needed.
