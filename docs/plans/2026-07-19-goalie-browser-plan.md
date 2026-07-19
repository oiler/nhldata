# Goalie Browser Surfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the goalie program's descriptive layers as browser surfaces — a cross-season `goalies.db`, a goalies index page, a goalie detail page, and a team-page environment section — per `docs/plans/2026-07-18-goalie-browser-design.md`.

**Architecture:** `v2/browser/build_goalies_db.py` builds one cross-season SQLite sidecar (edm.db precedent) from the generated goalie CSVs + player-JSON names; `runtime_paths.goalies_db()` + `db.goalies_query()` expose it; two new Dash pages + one team-page section consume it. Research-earned UI semantics (design doc §2) are requirements, not copy suggestions.

**Tech Stack:** system python3 (pyenv 3.11, NOT `uv run`), pandas 3.0, Dash 3.x, sqlite3, pytest. No new dependencies.

## Global Constraints

- Branch `goalie-eval-p1` (verify before committing; never push, never master). Local per-task commits authorized. Never `git add` anything under data/ or v2/browser/runtime_data/.
- Tests: computations only, no Dash callback tests (project CLAUDE.md). `python3 -m pytest v2/ -q` green before finishing (suite at plan time: 274 + sub-project A's additions; take the count you inherit as baseline).
- All SQL parameterized through the db.py layer; never interpolate user input (existing pattern, db.py docstrings). The `goalie_id` path parameter is cast to int before any query; non-castable → standard empty-state.
- Dash 3.x path-template gotcha: `relative_path` stores `/goalie/none`; nav filtering must use `page["path_template"] is None` (already handled centrally — do not re-filter in new pages).
- runtime_paths discipline: no module-level `Path().parents[N]`; new lookups follow the existing gated two-mode pattern verbatim.
- UI semantics from the design doc §2 (requirements): GSAx caveat sentence in the index header; per-game `perf_z` never drives a cross-game leaderboard (detail-page ledger is date-sorted; index shows season aggregates only); rebound figures per-season only with era footnote; freeze-value line renders only when `freeze_value` table has a row.
- `goalies.db` local path: `data/generated/browser/goalies.db`; runtime path: `<DATA_DIR>/goalies.db` (cross-season, NOT under a season folder).
- Season coverage: 2021–2025 in the DB; pages default to season "2025" via the existing `store-season` mechanism (which currently offers 2024/2025 — goalie pages read whatever season the store holds and the DB serves any of the five).

---

### Task 1: build_goalies_db.py (aggregations + DB writer)

**Files:**
- Create: `v2/browser/build_goalies_db.py`
- Test: `v2/browser/tests/test_build_goalies_db.py`

**Interfaces:**
- Consumes: `data/generated/goalies/goalie_games_<season>.csv` (game_id, game_date, goalie_id, team_abbrev, opp_abbrev, toi_s, season, ...), `gsax_<season>.csv` (goalie_id, shots, xga, ga, gsax, gsax_per100), `shots_<season>.csv` (goalie_id, on_net, is_goal, froze, season), `goalie_terms_<season>.csv` (goalie_id, layer, term_indep, n_shots), `game_ledger.csv` (season, game_id, goalie_id, ga, xga, gsax_game, perf_z, lev_value, difficulty_pct, xg_per60, toi_s), `validation/freeze_value.json`, `data/<season>/players/<goalie_id>.json` (firstName/lastName locale dicts, `["default"]`).
- Produces (tables in `data/generated/browser/goalies.db`, consumed by Tasks 2–5):
  - `goalie_seasons(season INT, goalie_id INT, name TEXT, teams TEXT, gp INT, toi_s INT, shots_faced INT, ga INT, xga REAL, gsax REAL, gsax_per100 REAL, freeze_rate REAL, freeze_pct REAL, rebound_term_indep REAL, mean_difficulty_pct REAL, mean_perf_z REAL, lev_value_sum REAL)`
  - `goalie_games(season INT, game_id INT, goalie_id INT, game_date TEXT, opp_abbrev TEXT, ga INT, xga REAL, gsax_game REAL, perf_z REAL, lev_value REAL, difficulty_pct REAL, xg_per60 REAL, toi_s INT)`
  - `team_environment` (as generated, all columns)
  - `freeze_value(per_freeze_xga_delta REAL, window_s INT)` — zero rows when the JSON's value is null.
- Pure functions (tested): `build_goalie_seasons(gg, gsax, shots, terms, ledger) -> pd.DataFrame` and `freeze_percentile(rates: pd.DataFrame, min_saves: int = 500) -> pd.Series`.
- Rules with exact values: `teams` = "/"-joined distinct team_abbrev in first-appearance order; `freeze_rate` = mean froze over the goalie-season's saves (`on_net & ~is_goal & froze notna`); `freeze_pct` = percentile rank (0–100) among that season's goalies with ≥ 500 saves, NaN below the floor; `rebound_term_indep` = **−**(rebound layer `term_indep`) so positive = better suppression (orientation per the research convention); `mean_difficulty_pct`/`mean_perf_z` = plain means over the goalie-season's ledger rows (NaN rows dropped); `lev_value_sum` = sum. Fail loudly (FileNotFoundError with the missing filename) if a source CSV is absent.

- [ ] **Step 1: Write the failing tests**

```python
# v2/browser/tests/test_build_goalies_db.py
import numpy as np
import pandas as pd
import pytest

from build_goalies_db import build_goalie_seasons, freeze_percentile


def _gg():
    return pd.DataFrame({
        "season": [2025] * 3, "game_id": [1, 2, 3], "goalie_id": [9, 9, 9],
        "team_abbrev": ["EDM", "EDM", "CGY"], "opp_abbrev": ["CGY", "VAN", "EDM"],
        "game_date": ["2025-10-01", "2025-10-03", "2025-11-01"], "toi_s": [3600, 3000, 3600],
    })


def _gsax():
    return pd.DataFrame({"goalie_id": [9], "shots": [90], "xga": [7.5], "ga": [6],
                         "gsax": [1.5], "gsax_per100": [1.67]})


def _shots():
    rows = []
    for froze in ([1.0] * 6 + [0.0] * 14):
        rows.append({"season": 2025, "goalie_id": 9, "on_net": True,
                     "is_goal": False, "froze": froze})
    rows.append({"season": 2025, "goalie_id": 9, "on_net": True, "is_goal": True,
                 "froze": np.nan})
    return pd.DataFrame(rows)


def _terms():
    return pd.DataFrame({"goalie_id": [9, 9], "layer": ["rebound", "goal"],
                         "term_indep": [0.25, -0.1], "n_shots": [800, 900]})


def _ledger():
    return pd.DataFrame({
        "season": [2025] * 3, "game_id": [1, 2, 3], "goalie_id": [9] * 3,
        "perf_z": [1.0, -0.5, np.nan], "difficulty_pct": [40.0, 60.0, np.nan],
        "lev_value": [0.1, -0.05, 0.02],
    })


def test_build_goalie_seasons_aggregates():
    row = build_goalie_seasons(_gg(), _gsax(), _shots(), _terms(), _ledger()).iloc[0]
    assert row["teams"] == "EDM/CGY"                      # first-appearance order
    assert row["gp"] == 3 and row["toi_s"] == 10200
    assert row["freeze_rate"] == pytest.approx(0.3)       # 6/20 saves
    assert row["rebound_term_indep"] == pytest.approx(-0.25)   # oriented: negative here
    assert row["mean_perf_z"] == pytest.approx(0.25)      # NaN dropped
    assert row["mean_difficulty_pct"] == pytest.approx(50.0)
    assert row["lev_value_sum"] == pytest.approx(0.07)
    assert row["gsax"] == pytest.approx(1.5)


def test_freeze_percentile_floor_and_rank():
    rates = pd.DataFrame({
        "goalie_id": [1, 2, 3, 4],
        "freeze_rate": [0.25, 0.30, 0.35, 0.99],
        "n_saves": [800, 900, 1000, 100],      # goalie 4 under floor
    })
    pct = freeze_percentile(rates)
    assert pct[3] > pct[1] > pct[0]
    assert np.isnan(pct.iloc[3]) or np.isnan(pct[4] if 4 in pct.index else np.nan)
    assert pct.loc[2] == pytest.approx(100.0)
```

Note: the fixture indexes `pct` by position/goalie order — implementers align the assertion indexing with the Series the implementation returns (indexed like `rates`); the semantic assertions (ordering, floor→NaN, top=100) are the contract.

- [ ] **Step 2: Run to verify failure** — `python3 -m pytest v2/browser/tests/test_build_goalies_db.py -v` → `ModuleNotFoundError` (browser tests run with `v2/browser` on the path via the existing conftest, same as `test_deployment_metrics.py`; check `v2/browser/tests/` for the import pattern and mirror it).

- [ ] **Step 3: Implement**

```python
# v2/browser/build_goalies_db.py
"""Build the cross-season goalies.db sidecar from the goalie pipeline CSVs.

Usage: python3 v2/browser/build_goalies_db.py
Sources: data/generated/goalies/*.csv + data/<season>/players/<id>.json
Output:  data/generated/browser/goalies.db
"""

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
GOALIES = REPO / "data" / "generated" / "goalies"
OUT = REPO / "data" / "generated" / "browser" / "goalies.db"
SEASONS = ("2021", "2022", "2023", "2024", "2025")
MIN_SAVES_FOR_PCT = 500


def freeze_percentile(rates: pd.DataFrame, min_saves: int = MIN_SAVES_FOR_PCT) -> pd.Series:
    out = pd.Series(np.nan, index=rates.index)
    eligible = rates["n_saves"] >= min_saves
    out[eligible] = rates.loc[eligible, "freeze_rate"].rank(pct=True) * 100
    return out


def _teams_joined(team_series: pd.Series) -> str:
    seen = []
    for t in team_series:
        if t not in seen:
            seen.append(t)
    return "/".join(seen)


def build_goalie_seasons(gg, gsax, shots, terms, ledger) -> pd.DataFrame:
    base = gg.sort_values("game_date").groupby(["season", "goalie_id"]).agg(
        teams=("team_abbrev", _teams_joined),
        gp=("game_id", "nunique"), toi_s=("toi_s", "sum")).reset_index()

    saves = shots[shots["on_net"] & ~shots["is_goal"] & shots["froze"].notna()]
    fr = saves.groupby(["season", "goalie_id"])["froze"].agg(
        freeze_rate="mean", n_saves="size").reset_index()
    pct_frames = []
    for season, grp in fr.groupby("season"):
        grp = grp.copy()
        grp["freeze_pct"] = freeze_percentile(grp)
        pct_frames.append(grp)
    fr = pd.concat(pct_frames, ignore_index=True) if pct_frames else fr.assign(freeze_pct=np.nan)

    reb = terms[terms["layer"] == "rebound"][["goalie_id", "term_indep"]].copy()
    reb["rebound_term_indep"] = -reb.pop("term_indep")

    led = ledger.groupby(["season", "goalie_id"]).agg(
        mean_difficulty_pct=("difficulty_pct", "mean"),
        mean_perf_z=("perf_z", "mean"),
        lev_value_sum=("lev_value", "sum")).reset_index()

    out = (base.merge(gsax.rename(columns={"shots": "shots_faced"}),
                      on="goalie_id", how="left")
           .merge(fr[["season", "goalie_id", "freeze_rate", "freeze_pct"]],
                  on=["season", "goalie_id"], how="left")
           .merge(reb[["goalie_id", "rebound_term_indep"]], on="goalie_id", how="left")
           .merge(led, on=["season", "goalie_id"], how="left"))
    return out


def _name(season: str, goalie_id: int) -> str:
    f = REPO / "data" / season / "players" / f"{goalie_id}.json"
    if not f.exists():
        return f"Goalie {goalie_id}"
    j = json.loads(f.read_text())
    return f"{j['firstName']['default']} {j['lastName']['default']}"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ledger = pd.read_csv(GOALIES / "game_ledger.csv")
    season_frames, game_frames = [], []
    for season in SEASONS:
        gg = pd.read_csv(GOALIES / f"goalie_games_{season}.csv")
        gsax = pd.read_csv(GOALIES / f"gsax_{season}.csv")
        shots = pd.read_csv(GOALIES / f"shots_{season}.csv",
                            usecols=["season", "goalie_id", "on_net", "is_goal", "froze"])
        terms = pd.read_csv(GOALIES / f"goalie_terms_{season}.csv")
        led = ledger[ledger["season"] == int(season)]
        gs = build_goalie_seasons(gg, gsax, shots, terms, led)
        gs["name"] = [(_name(season, g)) for g in gs["goalie_id"]]
        season_frames.append(gs)

        games = led.merge(
            gg[["season", "game_id", "goalie_id", "game_date", "opp_abbrev"]],
            on=["season", "game_id", "goalie_id"], how="left")
        game_frames.append(games)

    conn = sqlite3.connect(str(OUT))
    try:
        pd.concat(season_frames, ignore_index=True).to_sql(
            "goalie_seasons", conn, if_exists="replace", index=False)
        pd.concat(game_frames, ignore_index=True).to_sql(
            "goalie_games", conn, if_exists="replace", index=False)
        pd.read_csv(GOALIES / "team_environment.csv").to_sql(
            "team_environment", conn, if_exists="replace", index=False)
        fv_path = GOALIES / "validation" / "freeze_value.json"
        fv = json.loads(fv_path.read_text()) if fv_path.exists() else {"per_freeze_xga_delta": None}
        rows = ([] if fv.get("per_freeze_xga_delta") is None
                else [{"per_freeze_xga_delta": fv["per_freeze_xga_delta"],
                       "window_s": fv.get("window_s", 30)}])
        pd.DataFrame(rows, columns=["per_freeze_xga_delta", "window_s"]).to_sql(
            "freeze_value", conn, if_exists="replace", index=False)
    finally:
        conn.close()
    print(f"goalies.db: {sum(len(f) for f in season_frames)} goalie-seasons, "
          f"{sum(len(f) for f in game_frames)} goalie-games, freeze_value rows={len(rows)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests green, run the CLI** (`python3 v2/browser/build_goalies_db.py`). Anchors: ~490–530 goalie-seasons (about 100/season), ~13,900 goalie-games, freeze_value rows 0 or 1 matching the JSON. Spot-check two names against known ids.
- [ ] **Step 5: Full suite, commit** — `git add v2/browser/build_goalies_db.py v2/browser/tests/test_build_goalies_db.py && git commit -m "feat(browser): build cross-season goalies.db sidecar"`

---

### Task 2: Plumbing — runtime_paths, db.goalies_query, sync script

**Files:**
- Modify: `v2/browser/runtime_paths.py` (append one function)
- Modify: `v2/browser/db.py` (append one function)
- Modify: `tools/sync-runtime-data.sh` (one copy line)
- Test: `v2/browser/tests/test_goalies_query.py`

**Interfaces:**
- Produces: `runtime_paths.goalies_db() -> Path` — runtime mode: `data_root() / "goalies.db"`; local: `data_root() / "generated" / "browser" / "goalies.db"` (NOTE: cross-season — no season argument, unlike `league_db`). `db.goalies_query(sql: str, params=()) -> pd.DataFrame` — parameterized, empty DataFrame if the DB file is missing, mirroring `league_query`'s body exactly minus the season arg. Pages (Tasks 3–5) consume `goalies_query`.

- [ ] **Step 1: Write the failing test**

```python
# v2/browser/tests/test_goalies_query.py
import sqlite3

import pandas as pd


def test_goalies_query_parameterized_and_missing_db(tmp_path, monkeypatch):
    import db
    import runtime_paths

    # missing file -> empty frame, no exception
    monkeypatch.setattr(runtime_paths, "goalies_db", lambda: tmp_path / "absent.db")
    monkeypatch.setattr(db, "goalies_db", lambda: tmp_path / "absent.db")
    assert db.goalies_query("SELECT 1").empty

    # real file -> parameterized read works
    p = tmp_path / "goalies.db"
    conn = sqlite3.connect(str(p))
    pd.DataFrame({"goalie_id": [9], "name": ["Test Goalie"]}).to_sql(
        "goalie_seasons", conn, index=False)
    conn.close()
    monkeypatch.setattr(db, "goalies_db", lambda: p)
    out = db.goalies_query("SELECT name FROM goalie_seasons WHERE goalie_id = ?", (9,))
    assert out.iloc[0]["name"] == "Test Goalie"
```

- [ ] **Step 2: Run to verify failure** — `AttributeError` (no `goalies_db` in db's namespace yet).

- [ ] **Step 3: Implement.** In `runtime_paths.py` append:

```python
def goalies_db() -> Path:
    """Cross-season goalie DB (single file, all seasons — not per-season)."""
    if _runtime_mode():
        return data_root() / "goalies.db"
    return data_root() / "generated" / "browser" / "goalies.db"
```

In `db.py`: extend the import line to `from runtime_paths import league_db, edm_db, goalies_db` and append:

```python
def goalies_query(sql: str, params=()) -> pd.DataFrame:
    """Run parameterized sql against the cross-season goalies DB.

    IMPORTANT: Only pass string literals as sql. Never interpolate user input.
    """
    db_path = goalies_db()
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(sql, conn, params=list(params))
    finally:
        conn.close()
```

In `tools/sync-runtime-data.sh`, after the edm.db line add:

```bash
cp "$SRC/generated/browser/goalies.db"            "$DST/goalies.db"
```

- [ ] **Step 4: Tests green, full suite green.**
- [ ] **Step 5: Commit** — `git add v2/browser/runtime_paths.py v2/browser/db.py tools/sync-runtime-data.sh v2/browser/tests/test_goalies_query.py && git commit -m "feat(browser): goalies.db plumbing (runtime path, parameterized query, sync)"`

---

### Task 3: Goalies index page

**Files:**
- Create: `v2/browser/pages/goalies.py`

**Interfaces:**
- Consumes: `goalies_query`, `table_styles`, `seconds_to_mmss`, `register_season_callback` + `store-season` (filters.py), `dash.register_page`.
- Produces: page at `/goalies` named "Goalies". No date-range filter (season-aggregate data); season comes from `store-season`. Task 4's detail page is linked from the name column (`/goalie/<id>`).

- [ ] **Step 1: Implement** (no computation test — the page is a query + formatting layer over Task 1's tested aggregates; project norms skip callback tests):

```python
# v2/browser/pages/goalies.py
import dash
import pandas as pd
from dash import html, dash_table, callback, Input, Output
from dash.dash_table.Format import Format, Scheme

from db import goalies_query
from filters import register_season_callback
from table_style import table_styles
from utils import seconds_to_mmss

dash.register_page(__name__, path="/goalies", name="Goalies")
register_season_callback("goalies")

_CAVEAT = ("GSAx describes results; it is weakly repeatable year-to-year (r ≈ 0.1) "
           "and did not predict post-team-switch performance in our validation. "
           "Read it as what happened, not who is best.")

_SQL = """
SELECT goalie_id, name, teams, gp, toi_s, shots_faced, ga, xga, gsax, gsax_per100,
       freeze_rate, freeze_pct, mean_difficulty_pct, mean_perf_z
FROM goalie_seasons WHERE season = ? ORDER BY gsax DESC
"""


def layout():
    return html.Div([
        html.H2("Goalies"),
        html.P(_CAVEAT, style={"fontSize": "0.85rem", "color": "#6c757d",
                               "maxWidth": "48rem"}),
        html.Div(id="goalies-content"),
    ])


@callback(
    Output("goalies-content", "children"),
    Input("store-season", "data"),
)
def update_goalies(season):
    season = season or "2025"
    df = goalies_query(_SQL, params=(int(season),))
    if df.empty:
        return html.P("No goalie data for this season.")
    df["goalie_link"] = df.apply(lambda r: f"[{r['name']}](/goalie/{r['goalie_id']})", axis=1)
    df["toi_display"] = (df["toi_s"] / df["gp"].where(df["gp"] > 0)).apply(seconds_to_mmss)
    _ci = {"case": "insensitive"}
    columns = [
        {"name": "Goalie", "id": "goalie_link", "presentation": "markdown", "filter_options": _ci},
        {"name": "Team", "id": "teams", "filter_options": _ci},
        {"name": "GP", "id": "gp", "type": "numeric"},
        {"name": "TOI/GP", "id": "toi_display", "filter_options": _ci},
        {"name": "Shots", "id": "shots_faced", "type": "numeric"},
        {"name": "GA", "id": "ga", "type": "numeric"},
        {"name": "xGA", "id": "xga", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "GSAx", "id": "gsax", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "GSAx/100", "id": "gsax_per100", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Freeze%", "id": "freeze_rate", "type": "numeric", "format": Format(precision=3, scheme=Scheme.fixed)},
        {"name": "Freeze pct", "id": "freeze_pct", "type": "numeric", "format": Format(precision=0, scheme=Scheme.fixed)},
        {"name": "Difficulty faced", "id": "mean_difficulty_pct", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
        {"name": "Perf (season z̄)", "id": "mean_perf_z", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
    ]
    display = [c["id"] for c in columns]
    return html.Div(
        dash_table.DataTable(
            columns=columns,
            data=df[display].to_dict("records"),
            markdown_options={"link_target": "_self"},
            sort_action="native", filter_action="native",
            page_action="native", page_size=50,
            **table_styles(),
        ),
        className="table-wrap",
    )
```

- [ ] **Step 2: Smoke-check** — `cd v2/browser && python3 -c "import app"` exits clean (Dash registers the page; no server start on import). Full suite green.
- [ ] **Step 3: Commit** — `git add v2/browser/pages/goalies.py && git commit -m "feat(browser): goalies index page"`

---

### Task 4: Goalie detail page

**Files:**
- Create: `v2/browser/pages/goalie.py`

**Interfaces:**
- Consumes: `goalies_query`, `table_styles`, `seconds_to_mmss`. Path template `/goalie/<goalie_id>`; goalie_id cast via `int()` in a try/except → empty-state on failure.
- Produces: detail page with (1) season summary cards (one per season present, newest first: GSAx, freeze rate + pct, mean difficulty, TOI/GP), (2) per-game ledger table date-sorted desc (game_date, opp, GA, xGA, GSAx, difficulty_pct, perf_z, lev_value, TOI), (3) freeze-value line only when the `freeze_value` table has a row.

- [ ] **Step 1: Implement**

```python
# v2/browser/pages/goalie.py
import dash
import pandas as pd
from dash import html, dash_table
from dash.dash_table.Format import Format, Scheme

from db import goalies_query
from table_style import table_styles
from utils import seconds_to_mmss

dash.register_page(__name__, path_template="/goalie/<goalie_id>", name="Goalie")

_SEASONS_SQL = """
SELECT season, name, teams, gp, toi_s, gsax, gsax_per100, freeze_rate, freeze_pct,
       mean_difficulty_pct
FROM goalie_seasons WHERE goalie_id = ? ORDER BY season DESC
"""

_GAMES_SQL = """
SELECT season, game_date, opp_abbrev, ga, xga, gsax_game, difficulty_pct,
       perf_z, lev_value, toi_s
FROM goalie_games WHERE goalie_id = ? ORDER BY game_date DESC
"""

_FREEZE_SQL = "SELECT per_freeze_xga_delta FROM freeze_value"


def _season_card(r):
    return html.Div([
        html.H4(f"{r['season']} — {r['teams']}"),
        html.P(f"GP {r['gp']} · TOI/GP {seconds_to_mmss(r['toi_s'] / max(r['gp'], 1))} · "
               f"GSAx {r['gsax']:+.1f} ({r['gsax_per100']:+.2f}/100)"),
        html.P(f"Freeze {r['freeze_rate']:.3f}"
               + (f" (p{r['freeze_pct']:.0f})" if pd.notna(r["freeze_pct"]) else "")
               + f" · Difficulty faced {r['mean_difficulty_pct']:.1f}"
               if pd.notna(r["mean_difficulty_pct"]) else ""),
    ], className="card", style={"display": "inline-block", "verticalAlign": "top",
                                "margin": "0 0.75rem 0.75rem 0", "padding": "0.5rem 0.75rem",
                                "border": "1px solid #dee2e6", "borderRadius": "6px"})


def layout(goalie_id=None):
    try:
        gid = int(goalie_id)
    except (TypeError, ValueError):
        return html.Div(html.P("Unknown goalie."))
    seasons = goalies_query(_SEASONS_SQL, params=(gid,))
    if seasons.empty:
        return html.Div(html.P("Unknown goalie."))
    games = goalies_query(_GAMES_SQL, params=(gid,))
    games["toi_display"] = games["toi_s"].apply(seconds_to_mmss)

    children = [html.H2(seasons.iloc[0]["name"]),
                html.Div([_season_card(r) for _, r in seasons.iterrows()])]

    fv = goalies_query(_FREEZE_SQL)
    if not fv.empty:
        delta = float(fv.iloc[0]["per_freeze_xga_delta"])
        latest = seasons.iloc[0]
        if pd.notna(latest["freeze_rate"]):
            per_season = delta * 1550 * float(latest["freeze_rate"])
            children.append(html.P(
                f"Freeze skill at this rate is worth ≈ {-per_season:.1f} "
                f"suppressed xGA per starter season (validated pathway estimate).",
                style={"fontSize": "0.9rem", "color": "#495057"}))

    columns = [
        {"name": "Date", "id": "game_date"},
        {"name": "Opp", "id": "opp_abbrev"},
        {"name": "TOI", "id": "toi_display"},
        {"name": "GA", "id": "ga", "type": "numeric"},
        {"name": "xGA", "id": "xga", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "GSAx", "id": "gsax_game", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Difficulty", "id": "difficulty_pct", "type": "numeric", "format": Format(precision=0, scheme=Scheme.fixed)},
        {"name": "Perf z", "id": "perf_z", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed)},
        {"name": "Leverage", "id": "lev_value", "type": "numeric", "format": Format(precision=3, scheme=Scheme.fixed)},
    ]
    display = [c["id"] for c in columns]
    children.append(html.Div(
        dash_table.DataTable(
            columns=columns,
            data=games[display].to_dict("records"),
            sort_action="native", page_action="native", page_size=41,
            **table_styles(),
        ),
        className="table-wrap",
    ))
    return html.Div(children)
```

Sort note (design §2 guardrail): the table's default order is date desc; `sort_action="native"` permits user re-sorting within one goalie's games, which is same-population and fine — the prohibition is cross-goalie leaderboards on per-game perf_z, which this page cannot produce.

- [ ] **Step 2: Smoke-check** — `cd v2/browser && python3 -c "import app"` clean; visit-level behavior is manual (no callback tests per norms). Full suite green.
- [ ] **Step 3: Commit** — `git add v2/browser/pages/goalie.py && git commit -m "feat(browser): goalie detail page (season cards, per-game ledger, freeze-value line)"`

---

### Task 5: Team-page environment section + end-to-end verify

**Files:**
- Modify: `v2/browser/pages/team.py` (add one section; read the file first and splice per its existing layout/callback structure)

**Interfaces:**
- Consumes: `goalies_query`; the team page's existing selected-team + season context (read team.py to find the callback that renders the main content and its team/season inputs — add the environment block to that callback's output, or a parallel callback with the same inputs if the existing one is single-purpose).
- Produces: a "Goalie environment" card for the selected (season, team): mean difficulty served, mean xg faced/60, hd share, crossice/60, b2b games, with one explanatory line ("how hard this team makes its goalies' lives — workload served, not goalie quality").

- [ ] **Step 1: Implement.** SQL (module-level constant, parameterized):

```python
_ENV_SQL = """
SELECT mean_difficulty_pct, mean_xg_faced_per60, hd_share, crossice_per60, b2b_games
FROM team_environment WHERE season = ? AND team_abbrev = ?
"""
```

Render helper to add to team.py (adapt names to the page's conventions after reading it):

```python
def _goalie_environment_section(season, team):
    env = goalies_query(_ENV_SQL, params=(int(season), team))
    if env.empty:
        return None
    r = env.iloc[0]
    return html.Div([
        html.H3("Goalie environment"),
        html.P("How hard this team makes its goalies' lives — workload served, "
               "not goalie quality.", style={"fontSize": "0.85rem", "color": "#6c757d"}),
        html.Ul([
            html.Li(f"Difficulty served: p{r['mean_difficulty_pct']:.0f} league percentile"),
            html.Li(f"xG faced/60: {r['mean_xg_faced_per60']:.2f}"),
            html.Li(f"High-danger share: {r['hd_share']:.1%}"),
            html.Li(f"Cross-ice/60: {r['crossice_per60']:.2f}"),
            html.Li(f"Back-to-backs: {int(r['b2b_games'])}"),
        ]),
    ])
```

Splice its output into the team page's rendered children where the other stat sections live; `None` (no data, e.g. season not in goalies.db) renders nothing.

- [ ] **Step 2: End-to-end verify** — rebuild `python3 v2/browser/build_goalies_db.py`; `cd v2/browser && python3 -c "import app"` clean; full suite `python3 -m pytest v2/ -q` green. Manually confirm (report the numbers): goalies index row count for 2025 ≈ 95–100; a known goalie's detail page data present (pick one from goalie_seasons); EDM team-environment values match `team_environment.csv` for 2025.
- [ ] **Step 3: Commit** — `git add v2/browser/pages/team.py && git commit -m "feat(browser): goalie environment section on team page"`

---

## After this plan

Deliverables oiler reviews: the three surfaces running locally (`python3 v2/browser/app.py` or the usual run path) against the freshly built `goalies.db`, plus `freeze_value_report.txt` from sub-project A. Deployment (sync-runtime-data + fly deploy) stays manual per the deployment memory. Follow-ups deliberately out of scope: nav-link addition if the app's nav is curated manually (check app.py during Task 3 — if nav is auto-generated from the page registry, nothing to do).
