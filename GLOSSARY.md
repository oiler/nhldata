# Glossary

## wPPI+ (individual skater)

**wPPI** (weighted PPI) is a player's average per-game build contribution, scaled by how much ice time they receive:

```
wPPI = mean over games of (PPI+ × toi_seconds)
```

Each second a player is on ice, their PPI+ accumulates. A player at 100 PPI+ playing average minutes scores exactly the league mean.

**wPPI+** normalizes wPPI to the league average:

```
wPPI+ = wPPI / league_mean(wPPI) × 100
```

The league mean is computed from all eligible skaters (GP >= 5) using full-season data and is recalculated each time the database is rebuilt. It does not shift when the date filter is changed — a player's wPPI+ of 110 always means 10% above the full-season league average, regardless of the selected date range.

**Example — Connor McDavid (2025-26):**

McDavid has a PPI+ of 97.3 — slightly below average build. But he averages 1,057 seconds of 5v5 ice time per game (~17:37), well above league average.

```
wPPI  = 97.3 × 1,057 = 102,873
wPPI+ = 102,873 / 79,548 × 100 = 129.3
```

Despite being a lighter player, his heavy deployment pushes his wPPI+ to 129.3 — 29% above the league average. A big physical player playing fourth-line minutes would score well below 100.

---

## wPPI+ (team)

Team wPPI+ uses the same raw ingredient — `PPI+ × toi_seconds` — aggregated at the team level:

```
team wPPI = mean over games of sum(PPI+ × toi_seconds) for all skaters on the team
team wPPI+ = team wPPI / league_mean_team_wPPI × 100
```

`league_mean_team_wPPI` is the mean of all 32 teams' wPPI values, computed from the full season and stored in the database at build time. Like the individual version, this denominator is fixed — the date and home/away filters change which games are included in the numerator, but the baseline stays constant.

This avoids double-counting deployment: individual wPPI+ already accounts for how much a player is used, so the team formula goes back to the raw score rather than averaging player wPPI+ values weighted by TOI again.

**Example — Edmonton Oilers (2025-26):**

```
team wPPI  = mean over games of sum(PPI+ × toi_seconds) = 1,519,486
league mean = 1,493,937
team wPPI+ = 1,519,486 / 1,493,937 × 100 = 101.7
```

EDM sits just above league average at 101.7 — the metric captures the net effect of each skater's build and how heavily they're deployed.
