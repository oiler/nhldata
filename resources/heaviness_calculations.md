# PPI, PPI+, wPPI, and wPPI+  
### Season-Based 5v5 “Heaviness” Metrics

All calculations are performed **per season** (e.g., 2025–26).  
Each season is independent. No cross-season normalization.

Eligible player pool per season:
- Skaters only
- Minimum **5 games played**
- All TOI values are **5v5 only**

---

# 1. PPI (Pounds Per Inch)

## Definition

For player *i* in a given season:

PPIᵢ = weight_lbsᵢ / height_inchesᵢ

Example:  
198 lbs / 72 inches = **2.75**

## Interpretation

Higher PPI → greater mass per unit height → “heavier build”  
Lower PPI → lighter build relative to height  

This is a purely physical metric.  
It does **not** include ice time.

---

# 2. PPI+ (Mean-Indexed to 100)

## Step 1: Compute league mean PPI

Across all eligible players in the season:

mean_PPI = average(PPIᵢ)

## Step 2: Index each player

PPI+ᵢ = 100 × (PPIᵢ / mean_PPI)

## Interpretation

100 = league average PPI  
110 = 10% above league-average build  
90 = 10% below league-average build  

Important:
- This index is **not weighted by ice time**
- Mean is computed from the eligible player pool only (GP ≥ 5)

---

# 3. wPPI (Time-on-Ice Adjusted Contribution)

All TOI values are 5v5.

## Step 1: Aggregate season TOI per player per team

For each player-season-team stint:

TOIᵢ,t = sum of 5v5 TOI across all games on team t

## Step 2: Compute per-game TOI averages

For each player-team stint:

avg_TOIᵢ,t = TOIᵢ,t / games_played_i,t

For each team-season:

avg_TOI_team,t = TOI_team,t / unique_games_team,t

where TOI_team,t = sum of 5v5 TOI for all eligible skaters on team t,
and unique_games_team,t = number of distinct games any eligible skater on that team appeared in.

## Step 3: Compute TOI share

shareᵢ,t = avg_TOIᵢ,t / avg_TOI_team,t

## Step 4: Compute wPPI as a games-weighted average across stints

For each team stint, compute the share and weight it by games played on that team:

wPPIᵢ = PPIᵢ × Σ_t (shareᵢ,t × games_i,t) / Σ_t (games_i,t)

where games_i,t = number of distinct games played on team t.
This weighted average ensures a traded player with the same deployment on each team
gets the same wPPI as a single-team player with identical deployment.

## Interpretation

wPPI reflects:
- Player build (PPI)
- Multiplied by how much 5v5 ice time they occupy per game relative to their team's average

This measures contribution to team on-ice “heaviness mix” based on deployment rate.
Games missed due to injury do not reduce a player's wPPI — only per-game deployment matters.
Mid-season trades are handled by weighting each team stint by games played, so a traded
player with identical deployment on both teams gets the same wPPI as a single-team player.

It is not a physical trait metric anymore.
It is a deployment-adjusted contribution metric.

---

# 4. wPPI+ (Mean-Indexed to 100)

## Step 1: Compute season mean wPPI

mean_wPPI = average(wPPIᵢ across eligible players)

## Step 2: Index

wPPI+ᵢ = 100 × (wPPIᵢ / mean_wPPI)

## Interpretation

100 = league-average deployment-adjusted heaviness contribution  
>100 = above average contribution  
<100 = below average contribution  

Indexing is unweighted (same structure as PPI+).

---

# Summary of System

PPI  
→ Physical mass-to-height ratio.

PPI+  
→ League-relative physical build index (mean = 100).

wPPI  
→ PPI scaled by 5v5 ice time share within team-season.

wPPI+  
→ League-relative deployment-adjusted heaviness index (mean = 100).

---

# Accuracy Verification

The framework is internally consistent:

• PPI+ uses a simple ratio index against season mean  
• wPPI correctly uses TOI share within team-season  
• Trade handling uses a games-weighted average across team stints
• wPPI+ mirrors the same indexing logic as PPI+  
• No cross-season contamination  
• 5v5-only TOI consistently applied  
