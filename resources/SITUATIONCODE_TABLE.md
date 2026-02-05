# NHL SituationCode Reference Table

Canonical lookup table for all 30 valid NHL situationCodes.

## Key Concepts

### SituationCode

The raw 4-digit code from NHL data, always ordered **away team first**:

```
[Away Goalie][Away Skaters][Home Skaters][Home Goalie]
```

- **Goalie values**: 1 = in net, 0 = pulled
- **Skater values**: 3-6 skaters on ice

Example: `1451` = Away goalie in (1), Away 4 skaters, Home 5 skaters, Home goalie in (1)

### Strength

A normalized representation of skater counts, **not team-specific**. The larger number always comes first.

- `5v4` means one team has 5 skaters, the other has 4
- Both `1451` (home PP) and `1541` (away PP) have Strength `5v4`

This allows filtering by game situation (e.g., "all 5v4 power plays") regardless of which team has the advantage.

## Penalty Shots

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 0101 | N/A | Penalty Shot | Penalty Shot | Away |
| 1010 | N/A | Penalty Shot | Penalty Shot | Home |

## Both Goalies In

### Even Strength

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 1331 | 3v3 | 3v3, both goalies in | Even Strength | None |
| 1441 | 4v4 | 4v4, both goalies in | Even Strength | None |
| 1551 | 5v5 | 5v5, both goalies in | Even Strength | None |

### Power Play - Away Advantage

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 1431 | 4v3 | Away power play | Power Play | Away |
| 1531 | 5v3 | Away power play | Power Play | Away |
| 1541 | 5v4 | Away power play | Power Play | Away |

### Power Play - Home Advantage

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 1341 | 4v3 | Home power play | Power Play | Home |
| 1351 | 5v3 | Home power play | Power Play | Home |
| 1451 | 5v4 | Home power play | Power Play | Home |

## Away Goalie Pulled

### Even Strength

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 0431 | 3v3 | Away goalie pulled at even strength | Even Strength | None |
| 0541 | 4v4 | Away goalie pulled at even strength | Even Strength | None |
| 0651 | 5v5 | Away goalie pulled at even strength | Even Strength | None |

### Power Play - Away Advantage

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 0531 | 4v3 | Away goalie pulled on power play | Power Play | Away |
| 0631 | 5v3 | Away goalie pulled on power play | Power Play | Away |
| 0641 | 5v4 | Away goalie pulled on power play | Power Play | Away |

### Power Play - Home Advantage (Away Shorthanded)

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 0441 | 4v3 | Away goalie pulled while shorthanded | Power Play | Home |
| 0451 | 5v3 | Away goalie pulled while shorthanded | Power Play | Home |
| 0551 | 5v4 | Away goalie pulled while shorthanded | Power Play | Home |

## Home Goalie Pulled

### Even Strength

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 1340 | 3v3 | Home goalie pulled at even strength | Even Strength | None |
| 1450 | 4v4 | Home goalie pulled at even strength | Even Strength | None |
| 1560 | 5v5 | Home goalie pulled at even strength | Even Strength | None |

### Power Play - Home Advantage

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 1350 | 4v3 | Home goalie pulled on power play | Power Play | Home |
| 1360 | 5v3 | Home goalie pulled on power play | Power Play | Home |
| 1460 | 5v4 | Home goalie pulled on power play | Power Play | Home |

### Power Play - Away Advantage (Home Shorthanded)

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 1440 | 4v3 | Home goalie pulled while shorthanded | Power Play | Away |
| 1540 | 5v3 | Home goalie pulled while shorthanded | Power Play | Away |
| 1550 | 5v4 | Home goalie pulled while shorthanded | Power Play | Away |

## Both Goalies Pulled

| Code | Strength | Meaning | Type | Advantage |
|------|----------|---------|------|-----------|
| 0660 | 6v6 | Delayed penalty edge case when goalie already pulled | Edge Case | None |

## Summary

| Category | Count |
|----------|-------|
| Penalty Shots | 2 |
| Both Goalies In | 9 |
| Away Goalie Pulled | 9 |
| Home Goalie Pulled | 9 |
| Both Goalies Pulled | 1 |
| **Total** | **30** |

## Constraints

The theoretical 64 combinations (2×4×4×2) are reduced to 30 by these rules:

1. **No 6 skaters with goalie in** - Delayed penalties are recorded as goalie pulled
2. **No 3 skaters when goalie is pulled** - Pulling the goalie adds a skater (minimum 4)
3. **Both goalies pulled is rare** - Only occurs as 0660 edge case during delayed penalty

## Notes

- **SituationCode** is away-first: `[Away Goalie][Away Skaters][Home Skaters][Home Goalie]`
- **Strength** is normalized (larger first): both `1451` and `1541` are `5v4`
- Some codes are theoretically valid but rarely or never observed in actual games
