# v3.4.4: The wordmark links home

**Created:** 2026-11-27 20:11
**Last modified:** 2026-11-27 20:13

A fix within the `ROADMAP.md` entry "Browser improvements, in parallel with the move to mininet." oiler asked on 2026-11-27 for the "NHL Data" wordmark to link to the home page, since on a phone the links now sit behind the Menu button. Everything stays inside `browser/`.

## What the release changes

- `browser/app.py`: the header's `H1` wraps "NHL Data" in a link to `/`. The `H1` keeps `id="top"`, so the glossary's "Back to top" link still works.
- `browser/assets/style.css`: the link keeps the wordmark's white text with no underline, and shows a white focus ring for the keyboard.
- `browser/tests/test_nav_menu.py`: a test that the wordmark links to `/`.

## Human test

1. On the iPhone, open a page other than Home and tap "NHL Data". The home page opens.

## Results

### Machine-led tests, 2026-11-27

- **Run by:** Claude, on the laptop, with the local app in Chrome.
- **Result:** Passed. The full suite gives 457 passed.
- **Found:** On `/skaters` the wordmark is white with no underline; clicking it opens the home page. The "Back to top" link's target, `id="top"`, is still on the page.
- **Changed:** Nothing.

### Deploy, 2026-11-27

- **Run by:** Claude, with oiler's approval.
- **Result:** Deployed as Fly release v39, built with `--no-cache`.
- **Found:** On app.nhldata.org, clicking "NHL Data" on `/teams` opens the home page, and the data date reads "Games through Nov 25, 2026". The iPhone check is still to run.
- **Changed:** Nothing.

## Close-out

A patch release skips the close-out, except for its `CHANGELOG.md` entry and its tag.
