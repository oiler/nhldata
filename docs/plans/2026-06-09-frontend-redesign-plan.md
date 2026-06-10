# Front-End Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stock Bootstrap look of the `v2/browser` Dash app with the `DESIGN.md` visual system — light Vercel-derived canvas, Oilers-navy brand bar, self-hosted Geist, tabular-figure tables — across all 8 pages, with no data/logic changes.

**Architecture:** A single design-token CSS file (`assets/style.css`) plus self-hosted Geist fonts declared in `app.index_string` drive the global look. A new shared module `table_style.py` is the one source of truth for every `DataTable`'s appearance; all 8 pages drop their ad-hoc style dicts and splat the shared kwargs, each table wrapped in a `.table-wrap` shadow-border container. The shell (`app.py`) restyles the header/nav/footer to token classes.

**Tech Stack:** Plotly Dash 4.0, dash-bootstrap-components 2.0, Geist + Geist Mono (self-hosted woff2), pure CSS custom properties, pytest. Spec: `docs/plans/2026-06-09-frontend-redesign-design.md`. Design system: `/DESIGN.md`.

---

## Project rules that override the skill defaults

- **Git is manual.** oiler commits. Do **not** run `git commit`. Where this plan says "Checkpoint," run `git add` to stage and report what would be committed — nothing more.
- **Plans/specs live in `docs/plans/`**, not `docs/superpowers/`.
- **Test computations, not callbacks.** Only `table_style.py` gets a unit test (pure config dicts). CSS, fonts, and shell changes are verified visually by running the app.
- **No logic changes.** The full suite (`python -m pytest v2/ -v`, currently 82 tests) must stay green after every page edit — a failure means an import/structure regression, not a feature change.

## File structure

| File | Responsibility |
|---|---|
| `v2/browser/assets/fonts/geist-latin.woff2` (new) | Self-hosted Geist Sans variable |
| `v2/browser/assets/fonts/geist-mono-latin.woff2` (new) | Self-hosted Geist Mono variable |
| `v2/browser/app.py` (modify) | `index_string` with `@font-face`; restyle header/nav/footer to classes |
| `v2/browser/assets/style.css` (rewrite) | The full token system: variables + every component |
| `v2/browser/table_style.py` (new) | Shared DataTable style kwargs — the table look |
| `v2/browser/tests/test_table_style.py` (new) | Unit test for the shared style dicts |
| `v2/browser/pages/{home,games,game,skaters,teams,team,player,elites}.py` (modify) | Use `table_styles()`, wrap tables in `.table-wrap` |

---

## Task 1: Self-host the Geist fonts

**Files:**
- Create: `v2/browser/assets/fonts/geist-latin.woff2`
- Create: `v2/browser/assets/fonts/geist-mono-latin.woff2`

- [ ] **Step 1: Create the fonts directory**

Run:
```bash
mkdir -p v2/browser/assets/fonts
```

- [ ] **Step 2: Download the two variable woff2 files from the fontsource CDN**

Run:
```bash
curl -fsSL -o v2/browser/assets/fonts/geist-latin.woff2 \
  https://cdn.jsdelivr.net/npm/@fontsource-variable/geist/files/geist-latin-wght-normal.woff2
curl -fsSL -o v2/browser/assets/fonts/geist-mono-latin.woff2 \
  https://cdn.jsdelivr.net/npm/@fontsource-variable/geist-mono/files/geist-mono-latin-wght-normal.woff2
```

- [ ] **Step 3: Verify both files downloaded and are non-trivial woff2**

Run:
```bash
ls -l v2/browser/assets/fonts/
file v2/browser/assets/fonts/geist-latin.woff2
```
Expected: two files, each > 20 KB; `file` reports "Web Open Font Format (Version 2)". If a download is empty or the URL 404s, fall back to the official release assets at https://github.com/vercel/geist-font/releases (download `Geist[wght].woff2` / `GeistMono[wght].woff2`, rename to the paths above).

- [ ] **Step 4: Checkpoint (oiler commits)**

Run:
```bash
git add v2/browser/assets/fonts/
```
Report: "Staged self-hosted Geist + Geist Mono woff2."

---

## Task 2: Declare the fonts via `app.index_string`

**Files:**
- Modify: `v2/browser/app.py` (after `server = app.server`, before blueprint registration)

- [ ] **Step 1: Add the `index_string` with `@font-face` declarations**

Insert this block in `app.py` immediately after line `server = app.server  # for gunicorn`:

```python
app.index_string = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    <style>
      @font-face {
        font-family: "Geist";
        src: url("/assets/fonts/geist-latin.woff2") format("woff2");
        font-weight: 100 900;
        font-display: swap;
      }
      @font-face {
        font-family: "Geist Mono";
        src: url("/assets/fonts/geist-mono-latin.woff2") format("woff2");
        font-weight: 100 900;
        font-display: swap;
      }
    </style>
    {%css%}
  </head>
  <body>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
  </body>
</html>"""
```

- [ ] **Step 2: Boot the app and confirm it starts without template errors**

Run:
```bash
cd v2/browser && python -c "import app; print('index_string set:', 'Geist' in app.app.index_string)"
```
Expected: prints `index_string set: True` and no exception. (The `{%...%}` placeholders are required by Dash; a missing one raises at startup.)

- [ ] **Step 3: Checkpoint (oiler commits)**

Run:
```bash
git add v2/browser/app.py
```
Report: "Staged @font-face declarations in app.index_string."

---

## Task 3: Rewrite `assets/style.css` to the token system

**Files:**
- Modify (full rewrite): `v2/browser/assets/style.css`

- [ ] **Step 1: Replace the entire file with the token-based stylesheet**

Overwrite `v2/browser/assets/style.css` with:

```css
/* v2/browser/assets/style.css — NHL Data design system. Source of truth: /DESIGN.md */

:root {
  /* Surfaces */
  --canvas: #ffffff;
  --tint: #fafafa;
  --navy: #00205B;
  --navy-hover: #0a2f7a;
  --orange: #FF4C00;

  /* Text */
  --text: #171717;
  --text-2: #4d4d4d;
  --text-3: #666666;
  --text-4: #808080;
  --on-navy: #ffffff;
  --on-navy-muted: rgba(255, 255, 255, 0.72);

  /* Status */
  --pos: #0a7d5a;
  --neg: #c43c33;

  /* Borders & shadows */
  --divider: #ebebeb;
  --divider-2: #f0f0f0;
  --shadow-border: 0 0 0 1px rgba(0, 0, 0, 0.08);
  --shadow-card: 0 0 0 1px rgba(0, 0, 0, 0.08), 0 2px 2px rgba(0, 0, 0, 0.04),
    0 8px 8px -8px rgba(0, 0, 0, 0.04);

  /* Type */
  --font-sans: "Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, "SF Mono", Menlo, monospace;

  /* Radius */
  --radius-sm: 6px;
  --radius: 8px;
}

* { box-sizing: border-box; }

body {
  font-family: var(--font-sans);
  font-feature-settings: "liga" 1;
  background-color: var(--canvas);
  color: var(--text);
  margin: 0;
  -webkit-font-smoothing: antialiased;
}

/* ---- Header / brand bar ---- */
.app-header {
  background-color: var(--navy);
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.06);
}
.app-header h1 {
  color: var(--on-navy);
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

/* ---- Nav (dbc.NavLink renders a.nav-link) ---- */
.app-nav { display: flex; align-items: center; }
.app-nav .nav-link {
  color: var(--on-navy-muted);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  padding: 0.2rem 0.1rem;
  margin-left: 1.25rem;
  border-bottom: 2px solid transparent;
  transition: color 0.12s ease;
}
.app-nav .nav-link:hover { color: var(--on-navy); }
.app-nav .nav-link.active {
  color: var(--on-navy);
  border-bottom-color: var(--orange);
}

/* ---- Filter bar ---- */
.filter-bar {
  background-color: var(--canvas);
  border-bottom: 1px solid var(--divider);
  padding: 0.6rem 1.5rem;
  display: flex;
  gap: 2rem;
  align-items: center;
}
.filter-bar label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-right: 0.5rem;
}

/* ---- Page content ---- */
.page-content { padding: 1.5rem; max-width: 1100px; margin: 0 auto; }
.page-content h1 {
  font-size: 1.875rem;
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1.15;
}
.page-content h2 {
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.page-content a { color: var(--navy); text-decoration: none; }
.page-content a:hover { color: var(--navy-hover); text-decoration: underline; }

/* ---- Card ---- */
.card {
  background: var(--canvas);
  border: none;
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  padding: 1.25rem;
}

/* ---- Table container ---- */
.table-wrap {
  box-shadow: var(--shadow-border);
  border-radius: var(--radius);
  overflow: hidden;
  margin: 1.5rem 0;
}
.table-wrap .dash-spreadsheet-container { border-radius: var(--radius); }

/* Row-number gutter — preserve technique, restyle to tokens */
.dash-spreadsheet-container { counter-reset: row-number; }
.dash-spreadsheet-container td:first-child::before {
  counter-increment: row-number;
  content: counter(row-number);
  display: inline-block;
  min-width: 1.5em;
  text-align: right;
  margin-right: 0.5em;
  color: var(--text-4);
  font-size: 0.85em;
  font-family: var(--font-mono);
}

/* ---- Footer / glossary ---- */
.app-footer { max-width: 860px; margin: 3rem auto 2rem; padding: 0 1rem; }
.app-footer hr { border: none; border-top: 1px solid var(--divider); margin-bottom: 1rem; }
.app-footer .glossary {
  display: grid;
  grid-template-columns: max-content 1fr;
  column-gap: 1.5rem;
  row-gap: 0.35rem;
  font-size: 0.82rem;
  color: var(--text-3);
}
.app-footer .glossary dt { font-weight: 600; color: var(--text-2); }
.app-footer .glossary-note { font-size: 0.82rem; color: var(--text-3); margin-bottom: 0.6rem; }

/* ---- dbc / Bootstrap overrides ---- */
.btn-primary {
  --bs-btn-bg: var(--navy);
  --bs-btn-border-color: var(--navy);
  --bs-btn-hover-bg: var(--navy-hover);
  --bs-btn-hover-border-color: var(--navy-hover);
}
a { color: var(--navy); }
code { font-family: var(--font-mono); }
```

- [ ] **Step 2: Run the app and visually verify the shell**

Run:
```bash
cd v2/browser && python app.py
```
Open http://127.0.0.1:8050. Expected: navy header bar, white body, Geist font (not system serif), tables present (still old table styling until Task 6). No console CSS errors.

- [ ] **Step 3: Checkpoint (oiler commits)**

Run:
```bash
git add v2/browser/assets/style.css
```
Report: "Staged token-based style.css."

---

## Task 4: Restyle the shell in `app.py` (nav active state + footer classes)

**Files:**
- Modify: `v2/browser/app.py` — the nav block (`app.py:38-43`), the filter `labelStyle` inline colors, and the footer (`app.py:69-142`)

- [ ] **Step 1: Switch the nav to `dbc.NavLink` with automatic active state**

Replace the nav `html.Div([...], className="app-nav")` block (currently `app.py:38-43`) with:

```python
        dbc.Nav(
            [
                dbc.NavLink(
                    page["name"],
                    href=page["relative_path"],
                    active="exact",
                )
                for page in dash.page_registry.values()
                if page["path_template"] is None
                and page["relative_path"] != "/elites"
            ],
            className="app-nav",
        ),
```
(`dbc.NavLink` renders `<a class="nav-link">` and adds `active` on the matching route — the CSS in Task 3 styles `.app-nav .nav-link.active` with the orange underline. No callback needed.)

- [ ] **Step 2: Replace the footer inline styles with token classes**

Replace the `html.Footer([...], style={...})` block (currently `app.py:69-142`) with:

```python
    # Glossary footer
    html.Footer([
        html.Hr(),
        html.Div([
            html.H6("Stat Glossary", id="glossary", className="glossary-note",
                    style={"fontWeight": "bold", "display": "inline", "marginRight": "0.75rem"}),
            html.A("↑ Back to top", href="#top", className="glossary-note",
                   style={"display": "inline"}),
        ], style={"marginBottom": "0.75rem"}),
        html.P(
            [
                "All metrics are computed at ",
                html.B("5v5"),
                " unless otherwise noted. Any stat ending in ",
                html.Code("/a60"),
                " is computed across ",
                html.B("all-situation"),
                " ice time (5v5, PP, PK, OT).",
            ],
            className="glossary-note",
        ),
        html.Dl([
            html.Dt("Age"),
            html.Dd("Player's age in years as of Sept 15 of the season's start year (Sept 15, 2025 for the 2025-26 season)."),
            html.Dt("PPI"),
            html.Dd("Pounds Per Inch — a player's weight (lbs) divided by height (inches). A purely physical build metric."),
            html.Dt("PPI+"),
            html.Dd("PPI indexed to the league average (100 = average). 110 means 10% heavier build than average; 90 means 10% lighter."),
            html.Dt("wPPI"),
            html.Dd("Weighted PPI — PPI scaled by a player's average 5v5 TOI share relative to their team. Measures deployment-adjusted physical presence per game."),
            html.Dt("wPPI+"),
            html.Dd("wPPI indexed to the league average (100 = average). Accounts for both build and 5v5 deployment rate."),
            html.Dt("SB/a60"),
            html.Dd(
                "Speed Bursts per all-situation 60 — count of NHL EDGE skating bursts above 20 mph "
                "per 60 minutes of total ice time (all strengths). A pure speed-attribute metric; "
                "high values indicate explosive skaters. Top-line forwards typically sit in the 5–10 range; "
                "defensemen usually 1–4."
            ),
            html.Dt("Max MPH"),
            html.Dd(
                "Top season skating speed in mph, recorded by the NHL EDGE tracking system. "
                "A single peak value across all 2025-26 regular-season ice time. "
                "League average ≈ 22.2; McDavid leads at 24.6."
            ),
            html.Dt("tTOI%"),
            html.Dd(
                "Share of the team's 5v5 ice time played by this skater per game. "
                "Computed as 5 × player_toi / team_total_5v5_toi per game, then averaged "
                "across the season. 20% means the skater played 1/5 of all available 5v5 ice time."
            ),
            html.Dt("iTOI%"),
            html.Dd(
                "Fraction of a player's total ice time (all situations) spent at 5v5. "
                "Lower values indicate power play or penalty kill specialists."
            ),
            html.Dt("5v5 TOI/GP"),
            html.Dd("Average 5-on-5 time on ice per game played."),
            html.Dt("DPS+"),
            html.Dd("Deployment Score Plus — a defenseman's raw deployment score indexed to the league average (100 = average). The raw score accumulates points each 5v5 second based on the opposing forward line faced (line 1 opponents score highest). DPS+ normalizes across the league so 110 means a defenseman faces 10% tougher forward deployment than average."),
            html.Dt("DPL"),
            html.Dd("Deployment Line — a forward's average line assignment (1–4) across games played, where line 1 is the top line. Lower values indicate higher deployment; 1.0 means exclusively used as a first-line forward, 4.0 exclusively as a fourth-liner."),
        ], className="glossary"),
    ], className="app-footer"),
```
(All visual values now come from `.app-footer`, `.glossary`, `.glossary-note` in style.css. The grid/colors/sizes were moved out of inline styles.)

- [ ] **Step 3: Remove the now-redundant inline colors on the season filter label**

In the `dcc.RadioItems` `labelStyle` (currently `app.py:59-60`), the filter bar is `display:none`, so this is cosmetic only — leave it. No change required. (Documented here so the implementer doesn't hunt for it.)

- [ ] **Step 4: Boot and verify nav active underline + footer**

Run:
```bash
cd v2/browser && python app.py
```
Open http://127.0.0.1:8050 and click between pages. Expected: the current page's nav link is white with an orange underline; others are translucent white. Footer glossary renders as a two-column grid, muted, with a hairline rule above.

- [ ] **Step 5: Run the full test suite (no regressions)**

Run:
```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v
```
Expected: all 82 tests pass (no logic touched).

- [ ] **Step 6: Checkpoint (oiler commits)**

Run:
```bash
git add v2/browser/app.py
```
Report: "Staged shell restyle (dbc nav active state + footer token classes)."

---

## Task 5: Build the shared `table_style.py` (TDD)

**Files:**
- Create: `v2/browser/table_style.py`
- Test: `v2/browser/tests/test_table_style.py`

- [ ] **Step 1: Write the failing test**

Create `v2/browser/tests/test_table_style.py`:

```python
# v2/browser/tests/test_table_style.py
"""Tests for the shared DataTable styling in table_style.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from table_style import STYLE_CELL_CONDITIONAL, STYLE_HEADER, table_styles


def test_header_is_navy_on_white():
    assert STYLE_HEADER["color"] == "#00205B"
    assert STYLE_HEADER["backgroundColor"] == "#ffffff"


def test_numeric_columns_use_mono_tnum_right_aligned():
    rule = next(
        r for r in STYLE_CELL_CONDITIONAL
        if r["if"].get("column_type") == "numeric"
    )
    assert "Geist Mono" in rule["fontFamily"]
    assert rule["textAlign"] == "right"
    assert "tnum" in rule["fontFeatureSettings"]


def test_table_styles_exposes_all_kwargs():
    kw = table_styles()
    for key in (
        "style_table", "style_header", "style_cell",
        "style_cell_conditional", "style_data_conditional", "css",
    ):
        assert key in kw
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/browser/tests/test_table_style.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'table_style'`.

- [ ] **Step 3: Write the minimal implementation**

Create `v2/browser/table_style.py`:

```python
# v2/browser/table_style.py
"""Shared DataTable styling for the NHL Data design system. Source: /DESIGN.md

Single source of truth so every page's DataTable renders identically. Behavioral
props (columns, data, sort_action, filter_action, page_action) stay per-page;
this module owns only the visual style kwargs.
"""

STYLE_TABLE = {"overflowX": "auto"}

STYLE_HEADER = {
    "backgroundColor": "#ffffff",
    "color": "#00205B",
    "fontWeight": "600",
    "fontSize": "0.78rem",
    "letterSpacing": "0.04em",
    "textAlign": "left",
    "border": "none",
    "borderBottom": "1px solid #ebebeb",
    "padding": "8px 12px",
}

STYLE_CELL = {
    "fontFamily": '"Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    "fontSize": "0.88rem",
    "color": "#171717",
    "textAlign": "left",
    "padding": "8px 12px",
    "border": "none",
    "borderBottom": "1px solid #f0f0f0",
}

# Numeric columns get tabular mono, right-aligned. `column_type` matches any
# column whose definition sets "type": "numeric" (all numeric columns do).
STYLE_CELL_CONDITIONAL = [
    {
        "if": {"column_type": "numeric"},
        "fontFamily": '"Geist Mono", ui-monospace, "SF Mono", Menlo, monospace',
        "fontFeatureSettings": '"tnum" 1, "zero" 1',
        "textAlign": "right",
    },
]

STYLE_DATA_CONDITIONAL = [
    {
        "if": {"state": "active"},
        "backgroundColor": "rgba(0, 32, 91, 0.06)",
        "border": "1px solid #00205B",
    },
    {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
]

# Hide the case-sensitivity filter toggle (preserves prior behavior).
CSS = [{"selector": ".dash-filter--case", "rule": "display: none"}]


def table_styles() -> dict:
    """Style kwargs to splat into dash_table.DataTable(**table_styles(), ...)."""
    return {
        "style_table": STYLE_TABLE,
        "style_header": STYLE_HEADER,
        "style_cell": STYLE_CELL,
        "style_cell_conditional": STYLE_CELL_CONDITIONAL,
        "style_data_conditional": STYLE_DATA_CONDITIONAL,
        "css": CSS,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/browser/tests/test_table_style.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Checkpoint (oiler commits)**

Run:
```bash
git add v2/browser/table_style.py v2/browser/tests/test_table_style.py
```
Report: "Staged shared table_style.py + test (3 passing)."

---

## Task 6: Wire `table_styles()` into all 8 pages

Each page currently builds one or more `dash_table.DataTable(...)` with inline `style_header` / `style_cell` / `style_data_conditional` dicts (the `#f8f9fa` / `#dee2e6` pattern). For each page: import the helper, replace the inline style kwargs with `**table_styles()`, drop the now-duplicated `css=[{"selector": ".dash-filter--case"...}]` (it's inside `table_styles()`), and wrap the returned table in `html.Div(..., className="table-wrap")`.

> The transformation is identical per page. For a DataTable call like:
> ```python
> return dash_table.DataTable(
>     columns=columns,
>     data=...,
>     markdown_options={"link_target": "_self"},
>     sort_action="native",
>     filter_action="native",
>     css=[{"selector": ".dash-filter--case", "rule": "display: none"}],
>     page_action="native",
>     page_size=50,
>     style_table={"overflowX": "auto"},
>     style_header={...},
>     style_cell={...},
>     style_data_conditional=[...],
> )
> ```
> it becomes:
> ```python
> return html.Div(
>     dash_table.DataTable(
>         columns=columns,
>         data=...,
>         markdown_options={"link_target": "_self"},
>         sort_action="native",
>         filter_action="native",
>         page_action="native",
>         page_size=50,
>         **table_styles(),
>     ),
>     className="table-wrap",
> )
> ```
> Keep behavioral kwargs (`columns`, `data`, `markdown_options`, `sort_action`, `filter_action`, `page_action`, `page_size`, `tooltip_*`, etc.). Remove only `css`, `style_table`, `style_header`, `style_cell`, `style_data_conditional`. `html` is already imported in every page.

- [ ] **Step 1: `pages/skaters.py`** — add `from table_style import table_styles` (top, with the other imports). At the `dash_table.DataTable(` call (`skaters.py:198`), apply the transformation above (this page uses `page_action="native"`, `page_size=50` — keep them). Wrap in `.table-wrap`.

- [ ] **Step 2: `pages/elites.py`** — add `from table_style import table_styles`. This page defines module-level `_TABLE_STYLE_HEADER` / `_TABLE_STYLE_CELL` (`elites.py:33-41`) used by two tables (`_build_fwd_table` `elites.py:74`, `_build_def_table` `elites.py:118`). Delete those two constants, apply `**table_styles()` to both DataTable calls (keep `page_action="none"`), and wrap each returned table in `.table-wrap`.

- [ ] **Step 3: `pages/game.py`** — add the import. At `game.py:88` (`_build_table` returns a DataTable, `page_action` may be `"none"`), apply the transformation; wrap in `.table-wrap`.

- [ ] **Step 4: `pages/teams.py`** — add the import. At `teams.py:248`, apply the transformation; wrap in `.table-wrap`.

- [ ] **Step 5: `pages/games.py`** — add the import. At `games.py:74`, apply the transformation; wrap in `.table-wrap`.

- [ ] **Step 6: `pages/team.py`** — add the import. At `team.py:110` (`_build_table` per position group), apply the transformation; wrap in `.table-wrap`.

- [ ] **Step 7: `pages/player.py`** — add the import. At `player.py:360`, apply the transformation; wrap in `.table-wrap`.

- [ ] **Step 8: `pages/home.py`** — no DataTable here (it's a links landing page); no table change needed. One optional polish: change the example-list inline `style={"lineHeight": "2", "fontFamily": "monospace"}` (`home.py:25`) to `style={"lineHeight": "2", "fontFamily": "var(--font-mono)"}` so the example routes use Geist Mono. No import added.

- [ ] **Step 9: Run the full test suite**

Run:
```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v
```
Expected: all tests pass (82 prior + 3 new = 85), confirming no import/structure breakage across pages.

- [ ] **Step 10: Visual pass on every page**

Run:
```bash
cd v2/browser && python app.py
```
Visit each route: `/`, `/games`, a `/game/<id>`, `/skaters`, `/teams`, a `/team/<abbr>`, a `/player/<id>`, `/elites`. Expected on each table: white shadow-border rounded container; navy uppercase-tracked header; **numbers in Geist Mono, right-aligned, vertically aligned digits**; player/team name columns left-aligned in Geist Sans; `#fafafa` row striping; row-number gutter in muted mono. Confirm sorting and the markdown player/team links still work.

- [ ] **Step 11: Checkpoint (oiler commits)**

Run:
```bash
git add v2/browser/pages/
```
Report: "Staged all 8 pages on shared table_styles() + .table-wrap."

---

## Task 7: Full verification + security-headers/font check

**Files:** none (verification only)

- [ ] **Step 1: Run the complete suite one final time**

Run:
```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v
```
Expected: all 85 tests pass.

- [ ] **Step 2: Verify fonts load with security headers enabled (CSP unbroken)**

Run:
```bash
cd v2/browser && DASH_ENABLE_SECURITY_HEADERS=1 python app.py
```
Open the app, then in the browser devtools Network tab confirm `geist-latin.woff2` and `geist-mono-latin.woff2` return 200 from `/assets/fonts/`. In the Console, confirm there are **no** CSP violations (self-hosted fonts satisfy `font-src 'self'`). Headings/cells should render in Geist, not the system fallback.

- [ ] **Step 3: Confirm no `security.py` change was needed**

Run:
```bash
git status --short v2/browser/security.py
```
Expected: no output (file unchanged — self-hosting kept CSP intact, as the spec intended).

- [ ] **Step 4: Final checkpoint (oiler commits)**

Report to oiler: full suite green (85), fonts self-hosted and CSP-clean, all 8 pages on the design system. List every staged path and note that **oiler performs the commit and the `fly deploy`**.

---

## Out of scope (do not implement)

- Dark-mode toggle (token structure leaves room; not built now).
- Per-page bespoke layouts beyond applying the system.
- Any change to data, metrics, queries, or callback behavior.
- New charts/visualizations.
