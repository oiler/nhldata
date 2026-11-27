# v3.4.1: Browser improvements, continued

**Created:** 2026-11-27 18:22

The second release of the `ROADMAP.md` entry "Browser improvements, in parallel with the move to mininet." oiler picked two items on 2026-11-27. Both stay inside `browser/`.

## What the release changes

Filled in as the work lands.

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
- **wPPI+ leaders:** the top 10 skaters by season wPPI+ among those with at least 5 games, the same rule and stored value the skaters leaderboard uses. Columns: rank, player (linked), team, position, GP, wPPI+. The wPPI+ header shows its definition on hover. A link leads to the full leaderboard.
- A season with no data shows the not-available message the other pages use.
- The page reads `games`, `competition`, `players`, and `player_metrics`, which exist today. No schema change.

## Human test

1. Open `/skaters?utm_source=test`. The skaters table appears.
2. Open `/`. The latest games are from the latest date the season bar shows on `/games`, and each card opens its game.
3. The leaders' wPPI+ values match the same players on `/skaters` with the full season selected.

## Results

## Close-out

A patch release skips the close-out, except for its `CHANGELOG.md` entry and its tag.
