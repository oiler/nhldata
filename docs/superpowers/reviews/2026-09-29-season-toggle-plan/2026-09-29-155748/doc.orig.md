# Season toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Dash browser switch between 2025-26 and 2026-27, show "not available yet" for a season without verified data, and keep the deploy guard strict for the default season only.

**Architecture:** A new dependency-free `seasons.py` holds the season list, the default, and small helpers, so pages stop hard-coding `"2025"` without a circular import through `app.py`. `runtime_paths.season_ready()` decides whether a season has data to show, and each season-aware page returns a "not available yet" message when it doesn't. The sync script splits seasons into two tiers. The required tier (2025) blocks deploys, and the optional tier (2026) ships only when its checks pass.

**Tech Stack:** Python 3.11, Plotly Dash 4, pandas, SQLite, pytest, Bash.

**Spec:** `docs/superpowers/specs/2026-09-29-season-toggle-design.md`

## Global Constraints

- Season values are 4-digit start-year strings (`"2025"`, `"2026"`) everywhere: stores, queries, paths. Only user-facing text uses `season_label()`.
- `SEASONS = ["2025", "2026"]` and `DEFAULT_SEASON = "2025"`. 2024 stays out of `SEASONS`.
- User-facing not-available text is exactly `f"{season_label(season)} data isn't available yet."`, and for goalies `f"{season_label(season)} goalie data isn't available yet."`.
- Missing numeric values render as `—` (U+2014) through `Format(...).nully("—")`. Never write the string `"—"` into a numeric column.
- Tests use synthetic data only (the pattern in `v2/browser/tests/test_player_metrics.py`). Every test goes red before the code that makes it pass.
- Run tests from the repo root with `python -m pytest`. Browser test files add `v2/browser` to `sys.path` the way existing test files do.
- Pages can be imported in tests only after `import app` (it registers the page registry). Dash callbacks are directly callable in tests.
- Git: never commit on master and never push. oiler commits. Under subagent-driven execution on a feature branch, one local commit per reviewed task is allowed.
- Don't touch `v2/browser/runtime_data/` contents except through `tools/sync-runtime-data.sh`.
- The early-season `build_league_db.py` fix (empty `player_metrics` and `constants`) already shipped on 2026-09-29. Don't redo it.

## Review Focus

1. A session-persisted radio value that's no longer in `SEASONS` (after a future rollover) must fall back to `DEFAULT_SEASON`, not reach queries. Pinned in Task 11 (`sync_season("2019")`).
2. A junk or hostile `/elites?season=` value (`"../x"`, `"2024"`) must query only `DEFAULT_SEASON`. Pinned in Task 9.
3. An empty-string or null `birthDate` must give no age (em dash), not a crash. Pinned in Task 2.
4. A team missing from `goalies.db` in a season that has goalie data must omit the goalie section, not claim the season is unavailable. Pinned in Task 9.
5. An optional season that synced before but now fails a check must be removed from `runtime_data/`, never left stale. Pinned in Task 12 (case 2 starts with a pre-existing `runtime_data/2026/`).

---

### Task 1: Season config module

**Files:**
- Create: `v2/browser/seasons.py`
- Test: `v2/browser/tests/test_seasons.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SEASONS: list[str]`, `DEFAULT_SEASON: str`, `normalize_season(value) -> str`, `season_label(season: str) -> str`, `age_cutoff(season: str) -> datetime.date`.

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_seasons.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'seasons'`

- [ ] **Step 3: Write the implementation**

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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_seasons.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q`
Expected: all pass. No commit on master.

---

### Task 2: Age helper

**Files:**
- Modify: `v2/browser/utils.py`
- Test: `v2/browser/tests/test_utils.py` (append)

**Interfaces:**
- Consumes: `seasons.age_cutoff`.
- Produces: `utils.age_in_season(birth_date, season: str) -> int | None`.

- [ ] **Step 1: Write the failing test** (append to `v2/browser/tests/test_utils.py`; add the import beside the file's existing `from utils import ...` line)

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

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_utils.py -v`
Expected: FAIL with `ImportError: cannot import name 'age_in_season'`

- [ ] **Step 3: Write the implementation** (append to `v2/browser/utils.py`; add the imports at the top)

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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_utils.py -v`
Expected: PASS

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q`
Expected: all pass.

---

### Task 3: Season readiness

**Files:**
- Modify: `v2/browser/runtime_paths.py`
- Test: `v2/browser/tests/test_runtime_paths.py` (append)

**Interfaces:**
- Consumes: existing `league_db`, `player_bursts_csv`, `_runtime_mode`.
- Produces: `runtime_paths.season_ready(season: str) -> bool`.

- [ ] **Step 1: Write the failing test** (append; add `season_ready` to the file's `from runtime_paths import ...` line)

```python
def test_season_ready_production_needs_both_files(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "2026").mkdir()
    assert season_ready("2026") is False
    (tmp_path / "2026" / "league.db").write_bytes(b"x")
    assert season_ready("2026") is False
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

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_runtime_paths.py -v`
Expected: FAIL with `ImportError: cannot import name 'season_ready'`

- [ ] **Step 3: Write the implementation** (append to `v2/browser/runtime_paths.py`)

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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_runtime_paths.py -v`
Expected: PASS

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q`
Expected: all pass.

---

### Task 4: Player metadata lookup and `db.py` defaults

**Files:**
- Modify: `v2/browser/db.py`
- Modify: `v2/browser/pages/player.py:19-22` (remove `_META_SQL`), `:105-107` (use `player_meta`)
- Test: `v2/browser/tests/test_player_meta.py` (new)

**Interfaces:**
- Consumes: `seasons.SEASONS`, `seasons.DEFAULT_SEASON`.
- Produces: `db.player_meta(pid: int, seasons=SEASONS) -> pd.Series | None` with fields `firstName, lastName, currentTeamAbbrev, position`. `league_query(..., season=DEFAULT_SEASON)` and `all_teams(season=DEFAULT_SEASON)` defaults.

- [ ] **Step 1: Write the failing test**

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
    _players_db(tmp_path, "2025", [_row(1, "EDM")])
    _players_db(tmp_path, "2026", [_row(1, "VAN"), _row(2, "CGY")])
    assert player_meta(1)["currentTeamAbbrev"] == "VAN"
    assert player_meta(2)["currentTeamAbbrev"] == "CGY"


def test_player_meta_unknown_player(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _players_db(tmp_path, "2025", [_row(1, "EDM")])
    assert player_meta(999) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_player_meta.py -v`
Expected: FAIL with `ImportError: cannot import name 'player_meta'`

- [ ] **Step 3: Write the implementation**

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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_player_meta.py -v`
Expected: PASS

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q`
Expected: all pass.

---

### Task 5: Per-season burst loader

**Files:**
- Modify: `v2/browser/burst_data.py`
- Test: `v2/browser/tests/test_burst_data.py` (append)

**Interfaces:**
- Consumes: `runtime_paths.player_bursts_csv`, `seasons.DEFAULT_SEASON`.
- Produces: `burst_data.bursts_for(season: str) -> pd.DataFrame` indexed by `playerId` with columns `bursts_per_60, speed_max_mph, birth_date`; `lru_cache`d (call `bursts_for.cache_clear()` in tests).

- [ ] **Step 1: Write the failing test** (append; reuse the file's `_write_csv` and `_VALID_ROW`)

```python
import burst_data
from burst_data import bursts_for


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_burst_data.py -v`
Expected: FAIL with `ImportError: cannot import name 'bursts_for'`

- [ ] **Step 3: Write the implementation**

In `v2/browser/burst_data.py`:

1. Replace the module docstring with:

```python
"""Loads the speed-burst dataset behind the skaters leaderboard's SB/a60 and
Max MPH columns. (Age comes from the players table, not this file.)

The CSV is baked into the deployed image by tools/sync-runtime-data.sh, so a
missing or empty file for a season the image ships is a deploy mistake, not
missing upstream data. In production the skaters page loads every ready
season at import, so a bad file fails boot, and Fly's deploy health check
catches it before the image takes traffic. Local dev (DATA_DIR unset)
degrades gracefully so the app still runs without the edge pipeline output.
"""
```

2. Add `import functools` and `from seasons import DEFAULT_SEASON` to the imports, and change `def load_bursts(season: str = "2025", csv_path=None)` to `season: str = DEFAULT_SEASON`.
3. Change the `detail` line to `detail = f"{reason} — skater SB/a60 and Max MPH depend on it."`.
4. Append:

```python
@functools.lru_cache(maxsize=None)
def bursts_for(season: str) -> pd.DataFrame:
    """load_bursts(season) indexed by playerId, cached for the process lifetime.

    Burst CSVs change only on a manual Edge run; restart the app after one.
    """
    return load_bursts(season).set_index("playerId")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_burst_data.py -v`
Expected: PASS (existing tests included)

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q`
Expected: all pass.

---

### Task 6: `birthDate` in the players table

**Files:**
- Modify: `v2/browser/build_league_db.py` (`build_players_table` `keep` list; `_recover_missing_players` row dict)
- Test: `v2/browser/tests/test_player_metrics.py` (append; update `_setup_recovery_db`)

**Interfaces:**
- Consumes: `players.csv` column `birthDate` (ISO `YYYY-MM-DD`), player JSON field `birthDate`.
- Produces: `league.db` `players.birthDate` (TEXT, nullable).

- [ ] **Step 1: Write the failing tests**

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

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -v -k "birth_date or recover"`
Expected: the two new tests FAIL (`no such column: birthDate` for the first; `None` birthDate or a missing-column error for the second). The existing recovery tests still pass.

- [ ] **Step 3: Write the implementation**

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest v2/browser/tests/test_player_metrics.py -v`
Expected: PASS (all, including the two early-season tests already there)

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q`
Expected: all pass.

---

### Task 7: Date-range fallback and the not-ready message

**Files:**
- Modify: `v2/browser/filters.py:9-19` (`season_date_range`), `:97` (callback default), imports
- Test: `v2/browser/tests/test_filters_season.py` (new)

**Interfaces:**
- Consumes: `seasons.normalize_season`, `seasons.season_label`, `seasons.DEFAULT_SEASON`, `runtime_paths.season_ready`.
- Produces: `filters.season_date_range(season: str = DEFAULT_SEASON) -> tuple[str, str]`; `filters.season_not_ready(season: str) -> html.P | None`.

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_filters_season.py -v`
Expected: FAIL with `ImportError: cannot import name 'season_not_ready'`

- [ ] **Step 3: Write the implementation**

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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_filters_season.py -v`
Expected: PASS

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q`
Expected: all pass.

---

### Task 8: `birthDate` check in `verify_runtime_data.py`

**Files:**
- Modify: `v2/browser/verify_runtime_data.py`
- Test: `v2/browser/tests/test_verify_runtime_data.py` (append)

**Interfaces:**
- Consumes: a `league.db` with `competition(playerId, position)` and `players(playerId, birthDate)`.
- Produces: `verify_birthdates(db_path, min_coverage=0.95) -> tuple[bool, str]`; `main()` now fails when either check fails. CLI unchanged: `verify_runtime_data.py <burst_csv> <league_db> [min_overlap]`.

- [ ] **Step 1: Write the failing test** (append; import `verify_birthdates, main` beside the file's existing import)

```python
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


def test_main_fails_when_birthdates_fail(tmp_path):
    db = _make_db(tmp_path / "l.db", [1, 2])
    _make_players(db, [(1, None), (2, None)], with_column=False)
    csv = _make_csv(tmp_path / "b.csv", [1, 2])
    assert main([str(csv), str(db)]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_verify_runtime_data.py -v`
Expected: FAIL with `ImportError: cannot import name 'verify_birthdates'`

- [ ] **Step 3: Write the implementation**

In `v2/browser/verify_runtime_data.py`, change the docstring phrase "blank Age/SB-a60/Max-MPH columns" to "blank SB/a60 and Max MPH columns", and add a sentence: "It also checks that the players table carries birth dates, which the skaters Age column reads." Add after `DEFAULT_MIN_OVERLAP`:

```python
DEFAULT_MIN_BIRTHDATE_COVERAGE = 0.95
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
    results = [verify_burst_csv(argv[0], argv[1], min_overlap), verify_birthdates(argv[1])]
    for ok, msg in results:
        print(("OK: " if ok else "FAIL: ") + msg, file=sys.stdout if ok else sys.stderr)
    return 0 if all(ok for ok, _ in results) else 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_verify_runtime_data.py -v`
Expected: PASS. If an existing `main` test now fails because its fixture DB has no `players` table, add `_make_players(db, [(i, "2000-01-01") for i in ids])` to that fixture. Don't loosen the check.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q`
Expected: all pass.

---

### Task 9: Season-aware pages (games, teams, team, player, goalies, elites)

**Files:**
- Modify: `v2/browser/pages/games.py`, `pages/teams.py`, `pages/team.py`, `pages/player.py`, `pages/goalies.py`, `pages/elites.py`
- Test: `v2/browser/tests/test_season_pages.py` (new)

**Interfaces:**
- Consumes: `seasons.normalize_season`, `seasons.season_label`, `filters.season_not_ready`.
- Produces: page behavior only.

- [ ] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_season_pages.py
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import app  # noqa: F401 — registers pages so they can be imported
import pages.elites as elites
import pages.games as games
import pages.goalies as goalies
import pages.player as player
import pages.team as team
import pages.teams as teams

NOT_READY = "2026-27 data isn't available yet."


def test_season_aware_pages_say_not_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    d0, d1 = "2026-10-01", "2026-10-31"
    assert games.update_games(d0, d1, "2026").children == NOT_READY
    assert teams.update_teams(d0, d1, "all", "2026").children == NOT_READY
    assert team.update_team(d0, d1, "all", "EDM", "2026", "all").children == NOT_READY
    assert player.update_player(d0, d1, "all", 1, "F", "2026").children == NOT_READY


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

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_season_pages.py -v`
Expected: FAIL. The page callbacks return date-range messages ("No games found in this range." and similar), the goalie texts differ, the season-absent team section is `None`, and elites queries `"../x"` and `"2024"`.

- [ ] **Step 3: Write the implementation**

For each of `games.py`, `teams.py`, `team.py`, and `player.py`:
1. Add imports `from filters import season_not_ready` (merge into the existing `from filters import ...` line) and `from seasons import normalize_season`.
2. In the update callback, replace `season = season or "2025"` with:

```python
    season = normalize_season(season)
    not_ready = season_not_ready(season)
    if not_ready:
        return not_ready
```

The block goes before the existing `if not date_start ...` check.

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
            return html.Div([
                html.H3("Goalie environment"),
                html.P(f"{season_label(season)} goalie data isn't available yet."),
            ])
        return None
```

The rest of the function after that branch stays as is.

In `elites.py`: add `from seasons import normalize_season` and change `season = season or "2025"` to `season = normalize_season(season)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_season_pages.py -v`
Expected: PASS

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q` and `grep -rn '"2025"' v2/browser/pages/ v2/browser/filters.py v2/browser/db.py v2/browser/burst_data.py`
Expected: all tests pass. The grep returns nothing except `skaters.py` (Task 10 handles it).

---

### Task 10: Skaters page (per-season bursts, age from `birthDate`, em dashes)

**Files:**
- Modify: `v2/browser/pages/skaters.py`, `v2/browser/pages/team.py:117-119`, `v2/browser/pages/teams.py:239-242`
- Test: `v2/browser/tests/test_season_pages.py` (append)

**Interfaces:**
- Consumes: `burst_data.bursts_for`, `utils.age_in_season`, `runtime_paths.is_runtime_mode`, `runtime_paths.season_ready`, `seasons.SEASONS`, `seasons.normalize_season`, `filters.season_not_ready`.
- Produces: page behavior only.

- [ ] **Step 1: Write the failing test** (append to `test_season_pages.py`)

```python
import pages.skaters as skaters


def test_skaters_not_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert skaters.update_skaters("2026-10-01", "2026-10-31", "all", "2026").children == NOT_READY


def test_skaters_has_no_import_time_2025_bursts():
    assert not hasattr(skaters, "_BURSTS_DF")
    assert not hasattr(skaters, "_AGE_CUTOFFS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_season_pages.py -v -k skaters`
Expected: FAIL. The skaters callback returns "No data found for this range.", and `_BURSTS_DF` exists.

- [ ] **Step 3: Write the implementation**

In `v2/browser/pages/skaters.py`:

1. Imports: remove `from datetime import date` and `from burst_data import load_bursts`. Add:

```python
from burst_data import bursts_for
from runtime_paths import is_runtime_mode, season_ready
from seasons import SEASONS, normalize_season
from utils import age_in_season, seconds_to_mmss
```

Add `season_not_ready` to the `from filters import ...` line, and drop the old `from utils import seconds_to_mmss` line.

2. Delete `_AGE_CUTOFFS`, `_age_on()`, and `_BURSTS_DF = load_bursts("2025").set_index("playerId")`. Put this in their place:

```python
# Production loads every ready season's bursts at import, so a present-but-empty
# CSV fails boot (Fly's health check catches it) instead of 500ing on a request.
if is_runtime_mode():
    for _s in SEASONS:
        if season_ready(_s):
            bursts_for(_s)
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
    grouped = grouped.join(bursts_for(season)[["bursts_per_60", "speed_max_mph"]])
    grouped["age"] = grouped["birthDate"].apply(lambda b: age_in_season(b, season))
```

7. In `columns`, give these entries an em dash for missing values:

```python
        {"name": "Age",          "id": "age",                "type": "numeric", "format": Format().nully("—")},
        {"name": "PPI+",  "id": "ppi_plus",  "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed).nully("—")},
        {"name": "wPPI+", "id": "wppi_plus", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed).nully("—")},
        {"name": "SB/a60", "id": "bursts_per_60", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed).nully("—")},
        {"name": "Max MPH", "id": "speed_max_mph", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed).nully("—")},
```

In `team.py:118-119` and `teams.py:239-242`, append `.nully("—")` to the PPI+ and wPPI+ `Format(...)` calls. Early in a season `player_metrics` is empty, so those cells are null.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_season_pages.py -v`
Expected: PASS

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q` and `grep -rn '"2025"' v2/browser/pages/`
Expected: all pass; grep returns nothing.

---

### Task 11: App shell (visible filter, persistence, styling, glossary)

**Files:**
- Modify: `v2/browser/app.py`, `v2/browser/assets/style.css`
- Test: `v2/browser/tests/test_app_season.py` (new)

**Interfaces:**
- Consumes: `seasons.SEASONS`, `DEFAULT_SEASON`, `normalize_season`, `season_label`.
- Produces: `app.toggle_season_bar(pathname) -> dict`; `app.sync_season(value) -> str`; DOM ids `season-bar`, `filter-season`; CSS classes `filter-bar-label`, `season-options`.

- [ ] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_app_season.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app


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
    found = []

    def walk(node):
        if getattr(node, "id", None) == "filter-season":
            found.append(node)
        kids = getattr(node, "children", None)
        for k in kids if isinstance(kids, list) else [kids]:
            if k is not None and not isinstance(k, str):
                walk(k)

    walk(app.app.layout)
    (r,) = found
    assert [o["label"] for o in r.options] == ["2025-26", "2026-27"]
    assert r.persistence is True and r.persistence_type == "session"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_app_season.py -v`
Expected: FAIL with `AttributeError: module 'app' has no attribute 'toggle_season_bar'`

- [ ] **Step 3: Write the implementation**

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

3. Replace the filter bar block (comment through `], className="filter-bar", style={"display": "none"}),`) with:

```python
    # Season filter — shown only on season-aware pages (toggle_season_bar).
    html.Div([
        html.Div([
            html.Label("Season", className="filter-bar-label"),
            dcc.RadioItems(
                id="filter-season",
                options=[{"label": season_label(s), "value": s} for s in SEASONS],
                value=DEFAULT_SEASON,
                inline=True,
                persistence=True,
                persistence_type="session",
                className="season-options",
            ),
        ], style={"display": "flex", "alignItems": "center"}),
    ], id="season-bar", className="filter-bar", style={"display": "none"}),
```

4. On the goalie situation bar's `html.Label("Situations")`, add `className="filter-bar-label"`.
5. Replace the Max MPH `html.Dd(...)` text with:

```python
            html.Dd(
                "Top season skating speed in mph, recorded by the NHL EDGE tracking system. "
                "A single peak value across the selected season's regular-season ice time."
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

In `v2/browser/assets/style.css`, replace the `.filter-bar label { ... }` rule with the following (DESIGN.md: primary text `--text`, radio accent navy, `40px` rows below `640px`):

```css
.filter-bar .filter-bar-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-right: 0.5rem;
}
.season-options label {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-right: 1rem;
  color: var(--text);
  font-size: 0.9rem;
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  cursor: pointer;
}
.season-options input[type="radio"] { accent-color: var(--navy); margin: 0; }
@media (max-width: 639px) {
  .season-options label { min-height: 40px; }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_app_season.py v2/browser/tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q`
Expected: all pass.

---

### Task 12: Two-tier deploy guard

**Files:**
- Modify: `tools/sync-runtime-data.sh` (rewrite), `Dockerfile:37-41` (comment only), `.gitignore:10-13`
- Test: `v2/browser/tests/test_sync_runtime_data.py` (new)

**Interfaces:**
- Consumes: `verify_runtime_data.py` CLI (Task 8). New env overrides `SYNC_SRC` and `SYNC_DST` (default to the repo paths), used only by tests.
- Produces: `runtime_data/2026/{league.db,player_bursts.csv}` only when 2026 passes every check; a `WARNING: 2026 not synced` line and exit 0 otherwise; exit non-zero when a 2025 or shared file fails.

- [ ] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_sync_runtime_data.py
import os
import sqlite3
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "sync-runtime-data.sh"


def _league_db(path, ids, birth=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE competition (playerId INTEGER, position TEXT)")
    con.executemany("INSERT INTO competition VALUES (?, 'F')", [(i,) for i in ids])
    con.execute("CREATE TABLE players (playerId INTEGER, birthDate TEXT)")
    con.executemany("INSERT INTO players VALUES (?, ?)",
                    [(i, "2000-01-01" if birth else None) for i in ids])
    con.commit()
    con.close()


def _bursts(path, ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"playerId": ids, "bursts_per_60": 1.0, "speed_max_mph": 20.0,
                  "birth_date": "2000-01-01"}).to_csv(path, index=False)


def _src(tmp, with_2026=True, bursts_2026=None):
    src = tmp / "data"
    ids = list(range(10))
    _league_db(src / "2024/generated/browser/league.db", ids)
    _league_db(src / "2025/generated/browser/league.db", ids)
    (src / "2025/generated/browser/edm.db").write_bytes(b"x" * 10)
    _bursts(src / "2025/generated/edge/player_bursts.csv", ids)
    g = src / "generated/browser/goalies.db"
    g.parent.mkdir(parents=True)
    con = sqlite3.connect(g)
    pd.DataFrame({"situation": ["all", "5v5"]}).to_sql("goalie_seasons", con, index=False)
    con.close()
    if with_2026:
        _league_db(src / "2026/generated/browser/league.db", ids)
        _bursts(src / "2026/generated/edge/player_bursts.csv", ids if bursts_2026 is None else bursts_2026)
    return src


def _run(src, dst):
    # The script calls `python3` from PATH, which must have pandas (same as a real sync).
    env = {**os.environ, "SYNC_SRC": str(src), "SYNC_DST": str(dst)}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


def test_optional_season_synced_when_passing(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path), dst)
    assert r.returncode == 0, r.stderr
    assert (dst / "2026/league.db").exists() and (dst / "2026/player_bursts.csv").exists()


def test_optional_season_missing_is_removed_not_fatal(tmp_path):
    dst = tmp_path / "rt"
    (dst / "2026").mkdir(parents=True)
    (dst / "2026/league.db").write_bytes(b"stale")
    r = _run(_src(tmp_path, with_2026=False), dst)
    assert r.returncode == 0, r.stderr
    assert "WARNING: 2026 not synced" in r.stderr
    assert not (dst / "2026").exists()


def test_optional_season_failing_coverage_is_removed_not_fatal(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path, bursts_2026=[0, 1]), dst)
    assert r.returncode == 0, r.stderr
    assert "WARNING: 2026 not synced" in r.stderr
    assert "burst coverage" in r.stderr
    assert not (dst / "2026").exists()


def test_required_season_failure_is_fatal(tmp_path):
    src = _src(tmp_path)
    (src / "2025/generated/edge/player_bursts.csv").unlink()
    r = _run(src, tmp_path / "rt")
    assert r.returncode != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest v2/browser/tests/test_sync_runtime_data.py -v`
Expected: FAIL. The current script ignores `SYNC_SRC`/`SYNC_DST` and copies from the real repo `data/`. The optional-season tests fail on missing `WARNING` lines or 2026 files. Don't let the current script write into the real `runtime_data/`: if the old script runs during this step, rerun `./tools/sync-runtime-data.sh` afterward to restore it.

- [ ] **Step 3: Write the implementation**

Replace `tools/sync-runtime-data.sh` with:

```bash
#!/usr/bin/env bash
# Copy the runtime files the deployed app reads from the data/ pipeline tree
# into v2/browser/runtime_data/ so the Docker build can pick them up.
#
# Seasons come in two tiers:
#   required — any missing or failing file refuses the deploy (exit non-zero).
#   optional — a missing or failing file leaves the season out of the image
#              with a WARNING; the browser then shows it as not available.
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
# Overridable so tests can run the script against fixture trees.
SRC="${SYNC_SRC:-$REPO_ROOT/data}"
DST="${SYNC_DST:-$REPO_ROOT/v2/browser/runtime_data}"
VERIFY="$REPO_ROOT/v2/browser/verify_runtime_data.py"

REQUIRED_SEASON="2025"
OPTIONAL_SEASONS=("2026")

mkdir -p "$DST/2024" "$DST/$REQUIRED_SEASON"

cp "$SRC/2024/generated/browser/league.db"                   "$DST/2024/league.db"
cp "$SRC/$REQUIRED_SEASON/generated/browser/league.db"       "$DST/$REQUIRED_SEASON/league.db"
cp "$SRC/$REQUIRED_SEASON/generated/browser/edm.db"          "$DST/$REQUIRED_SEASON/edm.db"
cp "$SRC/generated/browser/goalies.db"                       "$DST/goalies.db"
cp "$SRC/$REQUIRED_SEASON/generated/edge/player_bursts.csv"  "$DST/$REQUIRED_SEASON/player_bursts.csv"

# Guard against shipping an image with missing/empty required files (the cause
# of silently-blank skater columns). set -e aborts the deploy prep on failure.
for f in "$DST/2024/league.db" "$DST/$REQUIRED_SEASON/league.db" "$DST/$REQUIRED_SEASON/edm.db" \
         "$DST/goalies.db" "$DST/$REQUIRED_SEASON/player_bursts.csv"; do
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

# Burst coverage and birthDate coverage for the required season.
python3 "$VERIFY" "$DST/$REQUIRED_SEASON/player_bursts.csv" "$DST/$REQUIRED_SEASON/league.db"

# Optional seasons: stage, check, and move into place only when every check
# passes. Any earlier copy is removed first, so a stale season never ships.
sync_optional_season() {
    local season="$1" stage
    stage="$(mktemp -d)"
    rm -rf "${DST:?}/$season"
    if ! cp "$SRC/$season/generated/browser/league.db" "$stage/league.db" 2>/dev/null \
       || ! cp "$SRC/$season/generated/edge/player_bursts.csv" "$stage/player_bursts.csv" 2>/dev/null; then
        echo "WARNING: $season not synced — league.db or player_bursts.csv is missing. The browser will show it as not available." >&2
        rm -rf "$stage"
        return 0
    fi
    if [[ ! -s "$stage/league.db" || ! -s "$stage/player_bursts.csv" ]]; then
        echo "WARNING: $season not synced — league.db or player_bursts.csv is empty. The browser will show it as not available." >&2
        rm -rf "$stage"
        return 0
    fi
    if ! python3 "$VERIFY" "$stage/player_bursts.csv" "$stage/league.db"; then
        echo "WARNING: $season not synced — failed the check named in the FAIL line above. The browser will show it as not available." >&2
        rm -rf "$stage"
        return 0
    fi
    mkdir -p "$DST/$season"
    mv "$stage/league.db" "$stage/player_bursts.csv" "$DST/$season/"
    rm -rf "$stage"
    echo "Synced optional season $season"
}

for season in "${OPTIONAL_SEASONS[@]}"; do
    sync_optional_season "$season"
done

echo "Synced runtime_data:"
ls -lh "$DST"/*/
```

In the `Dockerfile`, replace the comment block above the `RUN set -eu` guard with:

```dockerfile
# runtime_data/<season>/ folders are gitignored — they're built locally and
# baked in by tools/sync-runtime-data.sh. Any build from a bare git checkout
# (a CI runner, a fresh clone) silently produces an image whose skaters page
# raises at import (it preloads every ready season's bursts in production),
# which crash-loops the machine on deploy. Fail the *build* instead, before the
# image is ever pushed. Only required files are listed: optional seasons
# (2026) may be absent, and the browser then shows them as not available.
```

The file list in the guard doesn't change.

In `.gitignore`, add `v2/browser/runtime_data/2026/` after the `2025/` line.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest v2/browser/tests/test_sync_runtime_data.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest v2/ -q` and `git check-ignore -v v2/browser/runtime_data/2026/league.db`
Expected: all pass; `check-ignore` prints the `.gitignore` line.

---

### Task 13: Rebuild and verify in the running app

This task runs from the main checkout after oiler merges, because the orchestrator and the real `data/` tree live there (`data/` is gitignored, so a worktree has none).

**Files:** none changed.

- [ ] **Step 1: Rebuild both seasons**

Run: `python v2/browser/build_league_db.py 2025 && python v2/browser/build_league_db.py 2026`
Expected: both end with `Done.`; the 2026 build may print `player_metrics: 0 rows (no eligible players)` in the opening weeks.

- [ ] **Step 2: Check `birthDate` coverage**

Run: `python v2/browser/verify_runtime_data.py data/2025/generated/edge/player_bursts.csv data/2025/generated/browser/league.db`
Expected: two `OK:` lines, with `birthDate coverage` at or near 100%.

- [ ] **Step 3: Run the real sync**

Run: `./tools/sync-runtime-data.sh`
Expected: exit 0. Until a 2026 Edge run exists, a `WARNING: 2026 not synced` line, and no `runtime_data/2026/`.

- [ ] **Step 4: Manual checks in local dev**

Run: `cd v2/browser && python app.py`, then open `http://127.0.0.1:8050`.

- Switch seasons on games, teams, a team page, skaters, a player page, and goalies. 2026-27 shows its own data, or the not-available message.
- The season filter doesn't appear on home, a game page, a goalie page, or `/elites`.
- Select 2026-27 on Skaters, click a player link, and confirm the player page shows 2026-27. Reload, and confirm the radio and content still agree.
- In 2026-27, PPI+ and wPPI+ show em dashes while no skater has 5 games, and no page errors.
- SB/a60 and Max MPH show em dashes for 2026-27 without an Edge run, and Age still shows. The columns still sort numerically.
- At a width under `640px`, the season options are `40px` rows with navy radios and dark option text.

- [ ] **Step 5: Final suite**

Run: `python -m pytest v2/ -v`
Expected: all pass.
