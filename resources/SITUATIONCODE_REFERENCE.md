# NHL SituationCode Format - DEFINITIVE REFERENCE

## Format Structure
```
[Away Goalie][Away Skaters][Home Skaters][Home Goalie]
```

**CRITICAL: AWAY COMES FIRST, NOT HOME!**

## Terminology

* **Power Play** (PP): When one team has MORE skaters than the other (advantage)
* **Short Handed** (SH/PK): When one team has FEWER skaters than the other (penalized)

## Critical Rules

### **1541 = AWAY TEAM HAS POWER PLAY**
- Format: `1-5-4-1`
- Away: 5 skaters (POWER PLAY - advantage)
- Home: 4 skaters (SHORT-HANDED - penalized)
- Result: Away has advantage, Home is penalized

### **1451 = HOME TEAM HAS POWER PLAY**
- Format: `1-4-5-1`
- Away: 4 skaters (SHORT-HANDED - penalized)
- Home: 5 skaters (POWER PLAY - advantage)
- Result: Home has advantage, Away is penalized


## Common SituationCodes

### Even Strength
- **1551** = 5v5 standard play (both teams full strength)
- **1441** = 4v4 (both teams have 1 penalty each)
- **1331** = 3v3 (both teams have 2 penalties each)

### Home Team Power Play (Away Short)
- **1451** = Home 5v4 (away has 1 penalty)
- **1351** = Home 5v3 (away has 2 penalties)

### Away Team Power Play (Home Short)
- **1541** = Away 5v4 (home has 1 penalty)
- **1531** = Away 5v3 (home has 2 penalties)

### Goalie Pulled Scenarios
- **0651** = Away goalie pulled (6v5, away has 6 skaters)
- **1560** = Home goalie pulled (6v5, home has 6 skaters)

## Memory Aid

**The team with FEWER skaters is SHORT-HANDED.**

If home has 4 and away has 5:
- Home is short-handed (penalized)
- Away has power play (advantage)
- Code: **1541** (Away=1-5, Home=4-1)

If home has 5 and away has 4:
- Away is short-handed (penalized)
- Home has power play (advantage)
- Code: **1451** (Away=1-4, Home=5-1)

## Example Scenario

**12:49** - Away team gets penalty
- Away: 4 skaters (short)
- Home: 5 skaters (PP)
- SituationCode: **1451** (away=1-4, home=5-1) ✓

**14:15** - Home team also gets penalty
- Away: 4 skaters (short)
- Home: 4 skaters (short)
- SituationCode: **1441** (away=1-4, home=4-1) ✓

**14:49** - Away penalty expires
- Away: 5 skaters (full strength)
- Home: 4 skaters (still short)
- SituationCode: **1541** (away=1-5, home=4-1) ✓ AWAY PP

**16:15** - Home penalty expires
- Away: 5 skaters (full strength)
- Home: 5 skaters (full strength)
- SituationCode: **1551** (away=1-5, home=5-1) ✓
