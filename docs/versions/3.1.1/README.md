# v3.1.1: Default to 2026-27

A patch release, requested by oiler on 2026-11-18. The browser opens on 2026-27 instead of 2025-26. This is step 3 of the season-toggle spec's "Rollover next season" section (`docs/versions/3.1.0/specs/2026-09-29-season-toggle-design.md`).

## What the release changes

| Path | What it is |
|---|---|
| `v2/browser/seasons.py` | `DEFAULT_SEASON` becomes `"2026"` |
| `tools/sync-runtime-data.sh` | 2026 moves to the required tier and 2025 to the optional tier |
| `Dockerfile` | The build guard requires the 2026 `league.db` and `player_bursts.csv` instead of 2025's |
| `tools/sync-runtime-data.sh` (cleanup) | A failing optional season removes only its `league.db` and `player_bursts.csv`, not its whole folder, so a failing 2025 can't delete the required `2025/edm.db` |
| `v2/browser/tests/` | Tests that pinned 2025 as the default or 2026 as optional, and a test that a failing optional 2025 keeps `edm.db` |

## Design

- **Default season.** `DEFAULT_SEASON = "2026"`. The season filter opens on 2026-27, and an unknown `?season=` or stored value falls back to it.
- **Deploy tiers follow the default.** The guard exists so the default season always ships. With 2026 as the default, a failing 2026 check refuses the deploy, and a failing 2025 check leaves 2025-26 out of the image with a warning. `edm.db` (stored under 2025) and the 2024 `league.db` stay required, as before.
- **Consequence.** The 2026-27 Edge CSV is a manual snapshot from 2026-11-17. When new skaters push its coverage under 80%, the sync refuses until the Edge fetch is rerun: `NHL_SEASON=2026 python -m v2.edge.fetch_skater_detail`, then `NHL_SEASON=2026 python -m v2.edge.compute_burst_rates`. The roadmap's "Scheduled and on-demand Edge refresh" item removes that manual step.

## Human test

1. In local dev, open `/skaters` in a new tab. The season filter shows 2026-27 selected, and the table shows 2026-27.
2. Switch to 2025-26, click a player link, and confirm the player page shows 2025-26.

## Results

### Machine-led tests, 2026-11-18

- **Run by:** Claude.
- **Result:** Passed. The full suite gave 402 passed.
- **Found:** Swapping the tiers would have let a failing 2025 delete the required `2025/edm.db`, because the optional cleanup removed the whole season folder. Fixed by removing only the season's two files, with a test that goes red under the old cleanup.
- **Changed:** The real sync ended `Seasons in image: 2026 (required), 2025 (optional)`. In production mode the season radio and store open on 2026, and the 2026 date range is 2026-09-29 to 2026-11-17.

### Human test

Not run yet.

### Deploy, 2026-11-18

- **Run by:** Claude, from the repo root, after oiler's own `fly deploy` failed outside it (no `fly.toml` there).
- **Result:** Passed. Fly release v29 is live, and the health check passes.
- **Found:** The live layout opens with the season radio and store on 2026. The sync ended `Seasons in image: 2026 (required), 2025 (optional)`.
- **Changed:** Nothing. To roll back: `fly deploy --image registry.fly.io/nhl-browser:deployment-01M7QK1G8CPZR3JYPG716NRNFC` (release v28).

