# v3.1.2: Glossary entries

**Created:** 2026-11-18 18:48
**Last modified:** 2026-11-18 18:48

A patch release, approved by oiler on 2026-11-18. It adds glossary entries for columns that had none and corrects three existing entries. No data or behavior changes.

## What the release changes

| Path | What it is |
|---|---|
| `v2/browser/app.py` | New entries for G/A/P, P/60, 5v5 TOI, Line/Pair, Dep Score, and a "Teams and games" section. SB/a60's typical ranges come from 2025-26 data, and DPS+ and DPL cover both positions. |
| `GLOSSARY.md` | The same SB/a60 range correction |

## Results

### Machine-led tests, 2026-11-18

- **Run by:** Claude.
- **Result:** Passed. 397 tests passed with the CI selection.
- **Found:** Each new definition was checked against the code that computes it.
- **Changed:** Nothing.

## Close-out

A patch release skips the close-out. Tagged `v3.1.2`, with a GitHub Release.
