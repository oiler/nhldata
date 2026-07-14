# Data Limitations & Snapshot Discipline

## Player height/weight is not season-accurate for historical backfills

PPI (`weight_lbs / height_in`) and the competition "heaviness" columns depend on each
player's listed height/weight. The source matters:

- **NHL Edge** (`/v1/edge/skater-detail/{id}/{season}/{type}`) is **season-scoped** — the
  speed/burst data is point-in-time and correct for any season we fetch.
- **Player bio** (`/v1/player/{id}/landing`, used by `v2/players/get_players.py`) returns
  only the player's **current** height/weight — there is no historical bio endpoint.

So when a past season's players are fetched *late* (e.g. 2023-24 built in 2026), their
height/weight are **today's** measurements, not that season's. Listed weight drifts year to
year (e.g. Skinner 206 → 230 → 215 lb across 2021-22 / 2024-25 / current), so historical
PPI/heaviness are approximate.

**Partial recovery exists but wasn't pursued:** the season-scoped roster endpoint
(`/v1/roster/{team}/{season}`) *does* carry point-in-time height/weight, but it's a roster
snapshot covering only ~59% of players who actually appear in a season (call-ups and
mid-season trades are missing). Decision (2026-07): accept approximate historical h/w rather
than build a 59%-coverage recovery path. Historical seasons already backfilled (2023-24,
and partly 2024-25) carry this caveat.

## Snapshot discipline (going forward)

The fix for *future* seasons is timing, not new data sources: capture bio while it is still
current, then freeze it.

- Each season's raw player files live in `data/<season>/players/`. Fetched during the active
  season, they are an accurate point-in-time snapshot for everyone who played.
- The orchestrator already keeps the active season current: daily `fetch_players` +
  `backfill_players` (after `compute_competition`) catch new IDs and call-ups.
- **Freeze on completion.** A completed season's players dir carries a `.snapshot_frozen`
  marker. `get_players` full/targeted mode refuses to overwrite a frozen season (graceful
  skip). `backfill` stays allowed (additive). Override with `NHL_FORCE_REFETCH=1`.
- **At season rollover:** bump `NHL_SEASON` to the new season, let the orchestrator populate
  it, and drop a `.snapshot_frozen` marker into the prior season once it's complete.

Frozen as of 2026-07: 2023-24, 2024-25, 2025-26.
