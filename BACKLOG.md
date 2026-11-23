# Backlog

Everything not promised yet. An item gains authority only when it moves into `ROADMAP.md`.

## Items

### Idea notes

- **Shooters:** off-wing and handedness effects on shot quality. A research direction. `research/shooters/docs/2026-05-10-shooters.md`
- **Lines:** forward roles (driver, shooter, complementer) and defense-pair shots against per 60, weighted by zone starts. `docs/context/ideas/lines.md`
- **Timeline viewer:** a read-only, row-by-row tool for browsing timeline data. `docs/context/ideas/timelines.md`

---

### Pipeline follow-ups from the 2026-11-17 catch-up fix

- `pipeline/orchestrator/tools/fetch.py` accepts a `season` argument and ignores it. The fetcher reads `NHL_SEASON` from the environment.
- `download_shifts_only` in `pipeline/nhlgame.py` still stops a range at the first game without shifts. The full-download loop no longer does.
- A game whose shift reports never become available is fetched again every morning. No 2026-27 game is in that state.
- The manual backfill left two things unchecked: `points_5v5` covers 319 of 325 games (six games with no 5v5 goals is plausible), and `elite_defensemen` held 2 rows against 40 `elite_forwards`.

---

### Found during the v3.2.0 restructure

- `fetch_players` times out in the daily run (2026-11-20 and 2026-11-22 logs, before and after the move). `backfill_players` recovers the new players, so no data is lost, but the step never finishes.
- A deploy check that loads a season. `/healthz` passed while Fly release v31 read no data. A post-deploy check, or a readiness field in `/healthz`, would catch that class of failure.

---

### Declare the pipeline's dependencies in `pyproject.toml`

- `pyproject.toml` lists `requests`, `beautifulsoup4`, `lxml`, and `anthropic`, but not `pandas` or `numpy`, which the pipeline and research code import. The pipeline works only because the pyenv 3.11.6 environment already has them.
- Found during the v3.2.0 restructure design (2026-11-18). The restructure's editable install uses `--no-deps`, so it doesn't change this.

---

### mininet follow-ups

mininet is the Mac mini (Macmini4,1, Ubuntu 24.04) that the daily pipeline is moving to. Found while checking the machine on 2026-11-22 and 2026-11-23.

- **Run the disk's full surface test.** No SMART self-test has ever run on its drive, the original 2010 Toshiba MK3255GSXF. `sudo smartctl -t long /dev/sda` takes about 2.5 hours in the background, and `sudo smartctl -l selftest /dev/sda` shows the result. The drive passed its health check with no reallocated or pending sectors.
- **Recheck `Load_Cycle_Count`.** It read 3,848,578 on 2026-11-23, about six times the usual rating for a laptop drive. `hdparm -B 254` turns off the aggressive head parking that causes it. A day or more after that change, confirm the count has stopped climbing.
- **Power loss needs a person.** The mini doesn't turn itself back on after a power cut; someone has to press the button. oiler is putting it on a battery backup. Until the run's notification covers a run that never started, a power cut shows up only as silence.

---

### Detect NHL Play-by-Play Data Corrections

**Problem:** Our 5v5 goal counts occasionally differ by 1-2 goals from NHL.com official stats (e.g., LAK 5v5 GF: 113 vs NHL's 114 for 2025 season). The NHL likely makes post-game corrections to play-by-play data, but we only download each game once.

**Research findings (2026-03-15):**

- The public NHL API (`api-web.nhle.com`) has no changelog, no `Last-Modified` header, and no `updatedAt` field in the JSON response.
- HTTP ETags are request-time-based (not content-based), so they can't detect changes.
- The `gameState` transition from `FINAL` to `OFF` is the best proxy for "data is probably stable," but corrections may still happen after.
- Cache TTLs on completed games are only 3-5 seconds, suggesting the NHL expects clients to re-fetch and that data can change.
- No open-source library (Hockey-Scraper, chickenstats, nhl-api-py) implements automatic staleness detection.
- chickenstats maintains a 570-line manual corrections file (`_fixes.py`) for known NHL data errors spanning 2010-2025, confirming that errors are real and persistent.
- The commercial Sportradar NHL API has a "Daily Change Log" endpoint, but the free public API does not.

**Possible approaches:**

1. **Hash-and-compare** — Store a checksum of each game's play-by-play JSON at download time. Periodically re-fetch and flag games where the checksum changed.
2. **Scheduled re-download window** — Re-fetch play-by-play for games played within the last N days as part of the daily pipeline, since corrections are most likely shortly after games.
3. **Accept small discrepancies** — Document that our 5v5 data uses strict `1551` situation codes from a single point-in-time download and may differ slightly from NHL.com.

---

### NHL EDGE Skating & Tracking Data

**Opportunity:** The free public NHL API exposes player-level EDGE tracking data (speed bursts, skating distance, zone time, shot speed) that we could incorporate into player profiles and team analysis.

**Status (2026-11-17):** speed bursts shipped in May 2026 (`pipeline/edge/`, SB/a60 and Max MPH in the browser; plan in `docs/plans/2026-05-04-edge-player-data-and-burst-per-60.md`). The other endpoints below are unused.

**Research findings (2026-03-15):**

- Endpoints live at `api-web.nhle.com/v1/edge/{endpoint}/{playerId}/{season}/{gameType}`
- Parameters: `playerId`, `season` (e.g., `20252026`), `gameType` (`2` = regular season, `3` = playoffs)
- Originally built for NHL broadcast graphics — may be less stable than core stats endpoints
- `nhl-api-py` (which we already use) has a dedicated `client.edge.*` module wrapping these

**Available skater endpoints:**

| Endpoint | Data |
|----------|------|
| `skater-skating-speed-detail` | Top 10 speeds, max speed, burst counts (22+ mph, 20-22 mph, 18-20 mph) |
| `skater-skating-distance-detail` | Skating distance per game/period |
| `skater-zone-time` | Time spent in offensive/defensive/neutral zones |
| `skater-shot-speed-detail` | Shot velocity data |
| `skater-shot-location-detail` | Shot location data |
| `skater-detail` | General EDGE overview for a player |

**Also available:** Team-level rollups (`team-skating-speed-detail`, etc.), top-10 leaderboards (`skater-speed-top-10`, etc.), and goalie tracking data.

**Possible uses:**

1. **Player profiles** — Add speed/burst stats to the player page in the browser
2. **Team averages** — Aggregate skating metrics on the teams leaderboard
3. **PPI correlation** — Explore relationship between physical size (PPI) and skating speed/deployment

**References:**
- [NHL EDGE endpoints discovery (Issue #69)](https://github.com/Zmalski/NHL-API-Reference/issues/69)
- [nhl-api-py EDGE module](https://github.com/coreyjs/nhl-api-py)
- [Zmalski/NHL-API-Reference](https://github.com/Zmalski/NHL-API-Reference)

---

### Historical Season Replay for Elite Changelog

**Opportunity:** Once the 2025-26 season is complete, replay the full season day-by-day to retroactively populate the elite changelog and stress-test the pipeline.

**Concept:** Download the complete season's data from the NHL API, then simulate the nightly build process incrementally — day 1 processes only games from opening night, day 2 adds the next day's games, and so on through the final game. Each simulated day rebuilds the league DB and diffs the elite sets, appending any additions, removals, or type changes to `elite_changelog.csv`.

**Value:**

1. **Full elite changelog** — Produces a complete history of when players entered and exited elite status throughout the season, useful for understanding how the model responds to real data over time
2. **Pipeline regression testing** — Running 180+ sequential builds against real data is likely to surface edge cases and bugs that synthetic tests miss (traded players mid-season, injury absences dropping below GP thresholds, late-season threshold crossings)
3. **Model tuning** — The changelog would reveal how volatile the elite thresholds are — if players are churning in and out daily, the thresholds may need adjustment

**Implementation sketch:**

- Collect full-season play-by-play, shifts, boxscores, and timelines
- Write a replay script that filters data by game date, copies the subset into the working directories, and runs `build_league_db.py` for each day
- The existing `_read_old_elites` / `_log_elite_changes` machinery handles the diffing automatically
- Output: a single `elite_changelog.csv` spanning the entire season
