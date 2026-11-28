# v3.4.3: Phone fixes for the open menu and the game page

**Created:** 2026-11-27 19:56
**Last modified:** 2026-11-27 20:02

A fix within the `ROADMAP.md` entry "Browser improvements, in parallel with the move to mininet." oiler's iPhone check of v3.4.2 on 2026-11-27 found the closed menu correct and two faults. Everything stays inside `browser/`.

## What the release changes

- `browser/assets/style.css`: the open menu's links are a plain block list, not a flex row; a `.table-scroll` box and a wrapping `.game-teams` row for the game page.
- `browser/pages/game.py`: the team summary table sits in `.table-scroll`, and the two teams' player tables sit in `.game-teams`.

## Design

- **The open menu.** On the iPhone, the open menu laid its links out in a row, which ran past the screen and zoomed the page out again. In Chrome the same markup is a column. The list and its links are now `display: block`, which doesn't depend on the flex layout WebKit handled differently. The cause inside WebKit wasn't confirmed, since no WebKit browser is available here.
- **The game page.** The seven-column team summary table was wider than a phone, which zoomed the page out, and the two teams' player tables sat side by side at about 160 pixels each, cutting off names. The summary table now scrolls inside its own box, and the teams stack when there isn't room for both at 340 pixels.

## Human test

1. On the iPhone, open https://app.nhldata.org/ and tap Menu. Six links drop down as a list, and the page keeps the screen's width.
2. Open a game page. The page keeps the screen's width, the top table scrolls sideways inside its box, and the away team's tables come before the home team's.

## Results

### Machine-led tests, 2026-11-27

- **Run by:** Claude, on the laptop, with the local app in Chrome.
- **Result:** Passed. The full suite gives 456 passed.
- **Found:**
  - In a 390-pixel frame, the open menu lists the six links one under another, with no underline, and the page doesn't scroll sideways.
  - At 390 pixels, `/game/2026020388` doesn't scroll sideways; its summary table is 528 pixels wide inside a 317-pixel box that scrolls; the home team's tables start below the away team's.
  - At 1280 pixels the two teams still sit side by side.
- **Changed:** Nothing.

### Human test, 2026-11-27

- **Run by:** oiler, on an iPhone, against app.nhldata.org (Fly release v38).
- **Result:** Passed.
- **Found:** oiler loaded every page and opened the menu on the iPhone after v3.4.3 deployed: everything looks right.
- **Changed:** Nothing.

## Close-out

A patch release skips the close-out, except for its `CHANGELOG.md` entry and its tag.
