# v3.4.1: Browser improvements, continued

**Created:** 2026-11-27 18:22
**Last modified:** 2026-11-27 18:25

The second release of the `ROADMAP.md` entry "Browser improvements, in parallel with the move to mininet." oiler picked two items on 2026-11-27. Both stay inside `browser/`.

## What the release changes

- `browser/pages/*.py`: every `layout()` accepts extra keyword arguments.
- `browser/pages/home.py`: rewritten as a current-season start page, with `latest_games()`, `wppi_leaders()`, `score_line()`, and `result_label()`.
- `browser/assets/style.css`: the home page's section headings and two-column leader grid; the unused `.example-card-path` rule is removed.
- `BACKLOG.md`: the query-string item is removed.
- Tests: `browser/tests/test_page_registry.py` (every layout accepts query parameters) and `browser/tests/test_home.py` (latest games, leaders, score line).

## Design

### 1. Links with a query string show an empty page

A URL such as `/skaters?utm_source=x` renders an empty page. Dash passes a page's query parameters to its `layout()` as keyword arguments, and no layout accepts any, so the call raises. Shared links that pick up tracking parameters break. Found during v3.4.0 and listed in `BACKLOG.md`.

- Every page's `layout()` accepts and ignores extra keyword arguments. The parameters a page already reads, such as the elites page's `season`, keep working.
- A test checks that every registered page's layout accepts extra keyword arguments, so a new page can't bring the bug back.

### 2. A current-season home page

The home page is a welcome line, three links that repeat the navigation, and three example cards. One card links to a 2025-26 game, though the app opens on 2026-27.

The new page, for the default season:

- One sentence on what the site measures: 5v5 play, from a second-by-second record of every game.
- **Latest games:** every game on the latest date with a score, as cards linking to the game page, winner first ("CAR 5–2 NYR"), marked OT or SO when it went past regulation. The heading names the date.
- **wPPI+ leaders:** the top 5 forwards and top 5 defensemen by season wPPI+, among skaters with at least 5 games: the same rule and stored value the skaters leaderboard uses. Columns: rank, player (linked), team, GP, wPPI+. The wPPI+ header shows its definition on hover. A link leads to the full leaderboard.
  - Split by position because defensemen play more 5v5 minutes: a combined top 10 for 2026-27 was all defensemen. The first draft did that, and the split replaced it.
- A season with no data shows the not-available message the other pages use.
- The page reads `games`, `competition`, `players`, and `player_metrics`, which exist today. No schema change.

## Human test

1. Open `/skaters?utm_source=test`. The skaters table appears.
2. Open `/`. The latest games are from the latest date the season bar shows on `/games`, and each card opens its game.
3. The leaders' wPPI+ values match the same players on `/skaters` with the full season selected.

## Results

### Machine-led tests, 2026-11-27

- **Run by:** Claude, on the laptop, with the local app in Chrome.
- **Result:** Passed. The full suite gives 454 passed.
- **Found:**
  - `/skaters?utm_source=test` and `/player/8478402?ref=x` render their pages.
  - The home page shows the 14 games of November 25, 2026, and a card opens its game page.
  - The leaders' wPPI+ and GP match `/skaters` for the full 2026-27 season: Kaprizov 131.1 in 27 games, Werenski 173.1 in 23, Byram 158.0 in 6.
  - In a 390-pixel frame, neither leader table scrolls sideways; long names wrap.
- **Changed:**
  - The leaders split by position (see the design).
  - The leader tables use their own rank column instead of the shared row-number gutter, which separated from a wrapped name on a phone.

## Close-out

A patch release skips the close-out, except for its `CHANGELOG.md` entry and its tag.
