# Play-by-Play Data Reference

## File Location

```
data/{season}/plays/{gameId}.json
```

Example: `data/2025/plays/2025020001.json`

---

## Top-Level Keys

| Key | Description |
|-----|-------------|
| `id` | Full game ID (e.g. `2025020001`) |
| `season` | Season code (e.g. `20252026`) |
| `gameType` | `2` = regular season, `3` = playoffs |
| `gameDate` | Date string (`YYYY-MM-DD`) |
| `awayTeam` | Away team info (id, abbrev, score, etc.) |
| `homeTeam` | Home team info (id, abbrev, score, etc.) |
| `plays` | Array of play events (see below) |
| `rosterSpots` | Array of all skaters/goalies with playerId, teamId, position |
| `periodDescriptor` | Final period info |
| `gameOutcome` | Final outcome details |
| `summary` | Aggregated stats (shots, scoring, etc.) |

---

## Play Object — Common Fields

Every entry in the `plays` array contains:

| Field | Description |
|-------|-------------|
| `eventId` | Unique event ID within the game |
| `typeCode` | Numeric event type code |
| `typeDescKey` | String event type key (see table below) |
| `periodDescriptor.number` | Period number (4 = OT, 5+ = multiple OT) |
| `periodDescriptor.periodType` | `REG`, `OT`, or `SO` |
| `timeInPeriod` | Elapsed time in period (`MM:SS`) |
| `timeRemaining` | Time remaining in period (`MM:SS`) |
| `situationCode` | 4-digit strength code (e.g. `1551` = 5v5) |
| `homeTeamDefendingSide` | `left` or `right` |
| `sortOrder` | Tie-breaking sort order within a period-second |
| `details` | Event-specific fields (varies by type, may be absent) |

---

## Event Types (`typeDescKey`)

Fields listed below are from the `details` object only. `xCoord`, `yCoord`, and `zoneCode` are present on most event types and are omitted here for brevity — see the Notes section.

### Administrative / Game Flow

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `period-start` | 520 | *(none)* |
| `period-end` | 521 | *(none)* |
| `game-end` | 524 | *(none)* |
| `shootout-complete` | 523 | *(none)* |
| `stoppage` | 516 | `reason`, `secondaryReason` |
| `delayed-penalty` | 535 | `eventOwnerTeamId` |

### Faceoffs

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `faceoff` | 502 | `eventOwnerTeamId`, `winningPlayerId`, `losingPlayerId` |

### Shots & Scoring

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `shot-on-goal` | 506 | `eventOwnerTeamId`, `shootingPlayerId`, `goalieInNetId`, `shotType`, `awaySOG`, `homeSOG` |
| `missed-shot` | 507 | `eventOwnerTeamId`, `shootingPlayerId`, `goalieInNetId`, `shotType`, `reason` |
| `blocked-shot` | 508 | `eventOwnerTeamId`, `shootingPlayerId`, `blockingPlayerId`, `reason` |
| `failed-shot-attempt` | 537 | `eventOwnerTeamId`, `shootingPlayerId`, `goalieInNetId`, `awaySOG`, `homeSOG` |
| `goal` | 505 | `eventOwnerTeamId`, `scoringPlayerId`, `scoringPlayerTotal`, `assist1PlayerId`, `assist1PlayerTotal`, `assist2PlayerId`, `assist2PlayerTotal`, `goalieInNetId`, `shotType`, `awayScore`, `homeScore`, `highlightClip`, `highlightClipFr`, `highlightClipSharingUrl`, `highlightClipSharingUrlFr`, `discreteClip`, `discreteClipFr` |

### Physical Play

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `hit` | 503 | `eventOwnerTeamId`, `hittingPlayerId`, `hitteePlayerId` |

### Penalties

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `penalty` | 509 | `eventOwnerTeamId`, `committedByPlayerId`, `drawnByPlayerId`, `servedByPlayerId`, `typeCode`, `descKey`, `duration` |

### Puck Possession

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `giveaway` | 504 | `eventOwnerTeamId`, `playerId` |
| `takeaway` | 525 | `eventOwnerTeamId`, `playerId` |

---

## Notes

- **Coordinates** (`xCoord`, `yCoord`, `zoneCode`) are present on most event types with a location (shots, hits, faceoffs, penalties, possession events). They are omitted from the details tables above since they appear consistently. `zoneCode` values: `O` = offensive zone, `D` = defensive zone, `N` = neutral zone — always relative to `eventOwnerTeamId`.
- **`situationCode`** format: `[awayGoalie][awaySkaters][homeSkaters][homeGoalie]`. See `SITUATIONCODE_REFERENCE.md` for full details.
- **`details`** is absent entirely on some plays (e.g. `period-start`). Always use `.get("details", {})` when accessing.
- **Coordinates**: `xCoord` / `yCoord` are in feet from center ice. Rink is roughly ±100 ft on x-axis, ±42.5 ft on y-axis.
- **`failed-shot-attempt`** (typeCode 537) appears to be a penalty-shot or shootout attempt that did not result in a goal or registered shot-on-goal.
- **`rosterSpots`** at the top level is the source of truth for mapping `playerId` to player name, team, and position within a game.
