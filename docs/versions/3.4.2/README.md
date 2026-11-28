# v3.4.2: Phone menu

**Created:** 2026-11-27 19:09

A fix within the `ROADMAP.md` entry "Browser improvements, in parallel with the move to mininet." oiler reported on 2026-11-27, with a screenshot from an iPhone, that the header's links run off the screen and the page can't be scrolled to reach them. Everything stays inside `browser/`.

## What the release changes

- `browser/app.py`: the header holds the link row and a Menu button (`<details id="app-menu">`) with the same links; `_nav_links()` builds both.
- `browser/assets/style.css`: below 640px the link row hides and the Menu button shows, with the links as a full-width navy dropdown and 44-pixel tap targets. The link row may also wrap at wider widths.
- `browser/assets/menu.js`: new. Closes the menu after a link is followed or on a tap outside it.
- Tests: `browser/tests/test_nav_menu.py` (the menu has the desktop links) and `browser/tests/test_smoke.py` (the page declares a phone viewport).

## Design

### The cause

On the iPhone, the six links stay on one line. Skaters and Teams sit past the end of the navy bar, as white text on the white page, and the browser zooms out to fit the overflow, so the whole page looks narrower than the screen. Desktop Chrome wraps the same links onto two rows, which is why the v3.4.0 phone check, run in a 390-pixel frame in Chrome, missed it. Every iPhone browser uses WebKit, which sizes a wrapping flex row as if its items sat on one line unless the row's `min-width` is 0. That reading fits the screenshot; it wasn't reproduced, since no WebKit browser is available here.

### The fix (oiler's choice, option 1 of 2)

- Below 640px the bar shows the wordmark and a Menu button. Tapping it drops the six links down as a list under the bar, with the current page marked in orange.
- The menu is an HTML `<details>` element, so it opens without JavaScript and works with the keyboard and screen readers.
- Page changes are client-side, so the menu would stay open over the new page. Dash can't close it, because it never learns the menu was opened, so `menu.js` closes it when a link is followed or on a tap outside it.
- At 640px and wider nothing changes, except that the link row may wrap if a window is narrow enough to need it.
- The other option, letting the links wrap into two or three rows on a phone, was turned down because it uses a third of the screen before any content.

## Human test

1. On an iPhone, open https://app.nhldata.org/. The bar shows "NHL Data" and a Menu button, and the page fills the screen's width.
2. Tap Menu. Six links drop down, with Home marked.
3. Tap Skaters. The skaters page opens and the menu closes.
4. Open the menu and tap the page below it. The menu closes.

## Results

### Machine-led tests, 2026-11-27

- **Run by:** Claude, on the laptop, with the local app in Chrome.
- **Result:** Passed. The full suite gives 456 passed.
- **Found:**
  - At 1280 pixels the header is unchanged.
  - In a 390-pixel frame the page doesn't scroll sideways, the link row is hidden, and the Menu button shows. Opening it lists Home, Games, Goalies, Notes, Skaters, and Teams.
  - Following Teams from the menu opens `/teams` and closes the menu; reopening it and tapping the page closes it.
  - With the security headers on, the page loads `assets/menu.js`, which the policy's `script-src 'self'` allows.
  - The viewport test passed on its first run: the live site already sends the tag, so it guards against losing it rather than proving a fix.
- **Changed:** A first version closed the menu with a Dash callback on page change. It did nothing, since Dash's copy of the menu's state never changed, and `menu.js` replaced it.

## Close-out

A patch release skips the close-out, except for its `CHANGELOG.md` entry and its tag.
