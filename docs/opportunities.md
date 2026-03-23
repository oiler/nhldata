# Opportunities

Ideas and improvements to investigate when time allows.

---

## 1. Detect NHL Play-by-Play Data Corrections

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

## 2. NHL EDGE Skating & Tracking Data

**Opportunity:** The free public NHL API exposes player-level EDGE tracking data (speed bursts, skating distance, zone time, shot speed) that we could incorporate into player profiles and team analysis.

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

## 3. Historical Season Replay for Elite Changelog

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
