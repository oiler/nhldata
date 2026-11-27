# v3.4.0: Browser improvements

**Created:** 2026-11-27 17:53
**Last modified:** 2026-11-27 18:06

The `ROADMAP.md` entry "Browser improvements, in parallel with the move to mininet." oiler approved browser work alongside v3.3.0 on 2026-11-27 and picked three items, built in this order. Every change stays inside `browser/`: no change to `browser/metrics.py`, `pipeline/`, a database schema, dependencies, or the deploy guards.

Rulings: Decision Queue D108 and D109 (play-by-play data) are open and not part of this release.

## What the release changes

- `browser/filters.py`: `data_through()` gives the season's latest game date; `home_away_styles()` defines the All/Home/Away styles once, with navy for the selected button; each date label wraps with its picker.
- `browser/app.py`: the season bar shows the date; the glossary footer renders from `browser/glossary.py`.
- `browser/glossary.py`: new. The glossary's terms and definitions, the column-name aliases, and `header_tooltips()`.
- `browser/table_style.py`: `table_styles(columns)` adds header tooltips and a dotted underline for columns with a definition.
- `browser/pages/*.py`: every table passes its columns to `table_styles()`.
- `browser/assets/style.css`: the date's style, the wordmark on one line, and the season bar wrapping at phone width.
- Tests: `browser/tests/test_filters_season.py` (data date, navy button) and `browser/tests/test_glossary.py` (tooltips).

## Design

### 1. How current the data is

The live site reads data baked into the image, so it can be days behind (on 2026-11-27 the image held games through 2026-11-22 and the laptop through 2026-11-25). Nothing on the page says so.

- The season bar shows "Games through Nov 22, 2026" beside the season choice, for the selected season.
- The date is the latest `gameDate` with a score in the season's `games` table, the same rows `season_date_range()` reads. No schema change.
- A season with no data, or no scored games, shows nothing.

### 2. Polish

- The selected All/Home/Away button uses navy (`#00205B`), the active-state color `DESIGN.md` sets, instead of Bootstrap blue (`#0d6efd`). The button styles are defined once instead of twice.
- At phone width the wordmark stays on one line, and each date label stays with its date picker.

### 3. Stat definitions in column headers

The definitions are in the glossary at the foot of each page, far from the numbers.

- The glossary's terms and definitions move from `browser/app.py` into `browser/glossary.py`. The footer renders from it, so each definition is written once.
- `table_styles()` takes the table's columns and adds a header tooltip for each column whose name is a glossary term. Combined terms map to their columns: "G, A, P" covers G, A, and P.
- A column with a definition gets a dotted underline on its header, so readers can tell it has one.
- Columns with no glossary entry, such as Player or Date, get no tooltip. Where one name means different things on different pages (goalie TOI/GP is all situations), it gets no tooltip.

## Human test

1. Open `/skaters` and switch seasons. The season bar shows the latest game date for each season.
2. Click Home on the skaters filter. The selected button is navy.
3. Hover the wPPI+ header on `/skaters`. Its glossary definition appears. Hover Player: nothing appears.
4. At phone width, "NHL Data" stays on one line and "To" stays beside its date picker.

## Results

### Machine-led tests, 2026-11-27

- **Run by:** Claude, on the laptop, with the local app in Chrome.
- **Result:** Passed. The full suite gives 449 passed.
- **Found:**
  - `/skaters` shows "Games through Nov 25, 2026" for 2026-27 and "Games through Apr 16, 2026" for 2025-26 from the laptop's data.
  - The selected Home button renders navy (`rgb(0, 32, 91)`).
  - In a 390-pixel frame, the page doesn't scroll sideways, the wordmark stays on one line, and the season choices stay on one row with the date below them.
  - Hovering P/60 shows its definition. Player, Team, and GP have no underline and no tooltip.
  - The footer's terms and definitions match `browser/glossary.py` exactly.
  - Unrelated to this release: any query string, such as `/skaters?x=1`, renders an empty page, because the page layouts take no query arguments. Added to `BACKLOG.md`.
- **Changed:** The season bar wraps at phone width, added after the first phone check showed its choices stacking.

### Human test, 2026-11-27

- **Run by:** Claude, in Chrome against the local app, at oiler's request.
- **Result:** Passed, all four steps.
- **Found:**
  1. Switching seasons on `/skaters` changes the date: "Games through Apr 16, 2026" for 2025-26, "Games through Nov 25, 2026" for 2026-27.
  2. Clicking Home turns it navy and All white.
  3. Hovering wPPI+ shows "wPPI indexed to the league average (100 = average). Accounts for both build and 5v5 deployment rate." Hovering Player shows nothing.
  4. In a 390-pixel frame, "NHL Data" stays on one line and "To" stays beside its date picker. Chrome can't size a window that narrow, so the check used a frame.
- **Changed:** Nothing.

## Close-out

- [ ] Every file in this folder listed under "This folder", and the human test recorded under "Results"
- [ ] The version added to `CHANGELOG.md`
- [ ] The milestone's row and log entry added to `docs/history.md`
- [ ] The milestone removed from `ROADMAP.md`, so the next milestone is first in its list
- [ ] The release commit tagged, with a GitHub Release: the commit that adds the version to `CHANGELOG.md`
