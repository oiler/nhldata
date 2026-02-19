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

### Administrative / Game Flow

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `period-start` | 520 | *(none)* |
| `period-end` | 521 | *(none)* |
| `game-end` | 524 | *(none)* |
| `shootout-complete` | 523 | *(none)* |
| `stoppage` | 516 | `reason` |
| `delayed-penalty` | 535 | `eventOwnerTeamId` |

### Faceoffs

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `faceoff` | 502 | `xCoord`, `yCoord`, `zoneCode`, `winningPlayerId`, `losingPlayerId`, `eventOwnerTeamId` |

### Shots & Scoring

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `shot-on-goal` | 506 | `xCoord`, `yCoord`, `zoneCode`, `shotType`, `shootingPlayerId`, `goalieInNetId`, `eventOwnerTeamId`, `awaySOG`, `homeSOG` |
| `goal` | 505 | `xCoord`, `yCoord`, `zoneCode`, `shotType`, `scoringPlayerId`, `scoringPlayerTotal`, `assist1PlayerId`, `assist1PlayerTotal`, `assist2PlayerId`, `assist2PlayerTotal`, `goalieInNetId`, `eventOwnerTeamId`, `awayScore`, `homeScore`, highlight clip fields |
| `missed-shot` | 507 | `xCoord`, `yCoord`, `zoneCode`, `shotType`, `reason`, `shootingPlayerId`, `goalieInNetId`, `eventOwnerTeamId` |
| `blocked-shot` | 508 | `xCoord`, `yCoord`, `zoneCode`, `shootingPlayerId`, `blockingPlayerId`, `eventOwnerTeamId`, `reason` |
| `failed-shot-attempt` | 537 | `xCoord`, `yCoord`, `zoneCode`, `shootingPlayerId`, `goalieInNetId`, `eventOwnerTeamId`, `awaySOG`, `homeSOG` |

### Physical Play

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `hit` | 503 | `xCoord`, `yCoord`, `zoneCode`, `hittingPlayerId`, `hitteePlayerId`, `eventOwnerTeamId` |

### Penalties

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `penalty` | 509 | `xCoord`, `yCoord`, `zoneCode`, `typeCode` (MIN/MAJ/etc.), `descKey` (infraction name), `duration` (minutes), `committedByPlayerId`, `drawnByPlayerId`, `eventOwnerTeamId` |

### Puck Possession

| typeDescKey | typeCode | details fields |
|-------------|----------|----------------|
| `giveaway` | 504 | `xCoord`, `yCoord`, `zoneCode`, `playerId`, `eventOwnerTeamId` |
| `takeaway` | 525 | `xCoord`, `yCoord`, `zoneCode`, `playerId`, `eventOwnerTeamId` |

---

## Notes

- **`zoneCode`** values: `O` = offensive zone, `D` = defensive zone, `N` = neutral zone. Zone is relative to the `eventOwnerTeamId`.
- **`situationCode`** format: `[awayGoalie][awaySkaters][homeSkaters][homeGoalie]`. See `SITUATIONCODE_REFERENCE.md` for full details.
- **`details`** is absent entirely on some plays (e.g. `period-start`). Always use `.get("details", {})` when accessing.
- **Coordinates**: `xCoord` / `yCoord` are in feet from center ice. Rink is roughly ±100 ft on x-axis, ±42.5 ft on y-axis.
- **`failed-shot-attempt`** (typeCode 537) appears to be a penalty-shot or shootout attempt that did not result in a goal or registered shot-on-goal.
- **`rosterSpots`** at the top level is the source of truth for mapping `playerId` to player name, team, and position within a game.
