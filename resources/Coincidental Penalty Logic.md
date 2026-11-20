# Coincidental Penalty Logic - NHL Rules

## Source
NHL Official Rules 2025-2026, Table 13 (Rule 19 - Coincidental Penalties)

All penalties must be assessed at the same stoppage to be considered coincidental.

## Core Principle

**After coincidental penalties are matched and removed 1-for-1, the NHL checks whether any remaining penalties require players to be removed from the ice.**

- If remaining penalties are **equal on both sides** → Reduce on-ice strength equally (4v4, 3v3)
- If remaining penalties are **unequal** → Power play for team with fewer penalties
- If **no remaining penalties** → Full strength (5v5)

## Step-by-Step Process

### Step 1: Count Total Penalties Per Team

Each penalty counts separately:
- A player with 2+2 = **2 penalties**
- A player with 2+5 = **2 penalties** 
- A player with 5+5 = **2 penalties**

**Important:** Penalty type (roughing, fighting, etc.) does NOT matter for coincidental matching.

### Step 2: Cancel Coincidentals 1-for-1

```
coincidental_count = min(team_a_penalties, team_b_penalties)
net_team_a = team_a_penalties - coincidental_count
net_team_b = team_b_penalties - coincidental_count
```

### Step 3: Determine Which Penalties Require Box Time

Not all penalties remove a player from on-ice strength:

| Penalty Type | Box Time? | Affects On-Ice Strength? |
|--------------|-----------|--------------------------|
| Minor (2 min) | Yes | Yes - player in box |
| Major (5 min) | Yes | Yes - player in box |
| Misconduct (10 min) | No* | No - player to locker room |
| Game Misconduct | No | No - player ejected |

*Player goes to locker room, team continues at full strength

### Step 4: Calculate On-Ice Strength

```python
# Count penalties that require box time (minors and majors only)
team_a_box_penalties = count_minors_and_majors(net_team_a_penalties)
team_b_box_penalties = count_minors_and_majors(net_team_b_penalties)

if team_a_box_penalties == team_b_box_penalties == 0:
    # No net penalties requiring box time
    result = "Full strength (5v5)"
    
elif team_a_box_penalties == team_b_box_penalties:
    # Equal penalties on both sides
    skaters_per_side = 5 - team_a_box_penalties
    skaters_per_side = max(3, skaters_per_side)  # Minimum 3 skaters
    result = f"{skaters_per_side}v{skaters_per_side}"
    
else:
    # Unequal penalties - power play
    team_a_skaters = max(3, 5 - team_a_box_penalties)
    team_b_skaters = max(3, 5 - team_b_box_penalties)
    result = f"{team_a_skaters}v{team_b_skaters}"
```

## Examples from NHL Rulebook

### Example 1: Simple Unequal
```
Team A: A3(2)           = 1 penalty
Team B: B10(2+2)        = 2 penalties

Cancel: 1 from each
Net: Team A = 0, Team B = 1 (minor, requires box)

Result: Team B shorthanded (4v5)
SituationCode: 1541 (home 5, away 4, assuming B is away)
```

### Example 2: Equal Cancellation to Zero
```
Team A: A3(2) + A5(2+2)     = 3 penalties
Team B: B10(2+2) + B12(2)   = 3 penalties

Cancel: 3 from each
Net: Team A = 0, Team B = 0

Result: Full strength (5v5)
SituationCode: 1551
```

### Example 30: Misconduct Creates 4v4
```
Team A: A3(2+10)    = 1 minor (requires box) + 1 misconduct (no box)
Team B: B5(2)       = 1 minor (requires box)

Step 1: Count total penalties
  Team A: 2 penalties total
  Team B: 1 penalty total

Step 2: Cancel coincidentals 1-for-1
  coincidental = min(2, 1) = 1
  Net: Team A = 1 penalty (the misconduct)
       Team B = 0 penalties

Step 3: Which penalties require box time?
  Team A remaining: 1 misconduct (NO box time)
  Team B remaining: 0 penalties

Step 4: Calculate strength
  Wait... if Team A has no box penalties and Team B has no penalties,
  shouldn't this be 5v5?
  
But the NHL says 4v4. This means...

REVISED UNDERSTANDING:
The 2+10 means BOTH penalties are assessed simultaneously.
When canceling coincidentals, you can't split a multi-penalty.
You cancel WHOLE penalty events, not individual penalties.

Actually, re-reading more carefully:
- A3(2+10) means player A3 gets a 2-minute minor AND a 10-minute misconduct
- B5(2) means player B5 gets a 2-minute minor
- The 2-minute minors DO cancel out as coincidental
- But BOTH teams still have a player in the box serving time
- A3 serves his 2 minutes (the misconduct runs concurrently but he's in box)
- B5 serves his 2 minutes
- Result: Both teams down by 1 = 4v4

KEY INSIGHT: When a player gets 2+10, they serve the 2 minutes in the box.
The misconduct runs concurrently. The player is still in the box for 2 minutes,
affecting on-ice strength, even though one of the penalties is a misconduct.
```

Wait, I need to understand this better. Let me look at Example 32...

## Official NHL Rule 19.1 - The KEY Rule (VERY SPECIFIC)

**"When one minor penalty is assessed to one player of each team at the same stoppage in play, these penalties will be served without substitution provided there are no other penalties in effect and visible on the penalty clocks. Both teams will therefore play four skaters against four skaters for the duration of the minor penalties."**

### Critical Details:

This rule ONLY applies when ALL of these conditions are met:
1. **Exactly ONE minor penalty per team** (not 2v2, not 3v3, just 1v1)
2. **ONE player per team** (not multiple players)
3. **No majors involved**
4. **No other penalties already on the clock**

If ANY of these conditions are NOT met, use Rule 19.5 (normal cancellation).

### Examples Where Rule 19.1 APPLIES (Result: 4v4):

**Example 30:** A3(2+10) vs B5(2)
- 1 minor per team ✓
- 1 player per team ✓
- No majors ✓
- No other penalties ✓
- **Result: 4v4**

**Example 32:** A3(2) + A4(10) vs B5(2) + B7(10)
- 1 minor per team ✓ (misconducts don't count)
- No majors ✓
- No other penalties ✓
- **Result: 4v4**

### Examples Where Rule 19.1 DOES NOT APPLY (Result: 5v5 via cancellation):

**Example 28:** A3(2+5+5) vs B5(2+5) + B7(5)
- Each team has 1 minor + 2 majors
- NOT the 1v1 minor case
- Use Rule 19.5: Cancel 1 minor from each, cancel 2 majors from each
- Net: 0 remaining
- **Result: 5v5 (full strength)**

**Example 29:** A5(2) + A6(5+5) + A7(5) vs B12(5+5) + B13(2) + B14(5)
- Each team has 1 minor + 4 majors
- NOT the 1v1 minor case (too many penalties)
- Use Rule 19.5: Cancel 1 minor from each, cancel 4 majors from each
- Net: 0 remaining
- **Result: 5v5 (full strength)**

**Example 2:** A3(2) + A5(2+2) vs B10(2+2) + B12(2)
- Team A has 3 minors, Team B has 3 minors
- NOT the 1v1 minor case (3v3, not 1v1)
- Use Rule 19.5: Cancel 3 minors from each
- Net: 0 remaining
- **Result: 5v5 (full strength)**

## Rule 19.5 - Applying Coincidental Penalty Rule

When multiple penalties are assessed at the same stoppage:

**(i) Cancel as many major and/or match penalties as possible**

**(ii) Cancel as many minor, bench minor and/or double-minor penalties as possible**

### Key Points:

1. **Majors cancel first**, then minors
2. **Cancel as many as possible** - this is 1-for-1 cancellation
3. Misconduct penalties (10 min) are served but **do NOT affect on-ice strength**
4. When a player has 2+10:
   - They serve the 2-minute minor in the box (team is shorthanded)
   - The 10-minute misconduct runs concurrently
   - After 2 minutes, they go to locker room (team back to strength)
   - Total: 12 minutes (2 in box + 10 in locker room)

## Updated Algorithm (CORRECT)

```python
def process_coincidental_penalties(penalties_at_same_time):
    """
    Process penalties assessed at the same stoppage.
    
    Returns penalties to track for expiration.
    """
    # Step 1: Parse and separate penalties by team and type
    team_a_minors = []
    team_a_majors = []
    team_a_misconducts = []
    
    team_b_minors = []
    team_b_majors = []
    team_b_misconducts = []
    
    for penalty in penalties_at_same_time:
        # Parse duration field (e.g., 2, 5, 10)
        # Parse typeCode (e.g., MIN, MAJ, MIS)
        # A player with 2+10 creates TWO entries: one MIN, one MIS
        # A player with 5+5 creates TWO entries: both MAJ
        pass
    
    # Step 2: Check for Rule 19.1 exception (VERY SPECIFIC)
    if (len(team_a_minors) == 1 and 
        len(team_b_minors) == 1 and
        len(team_a_majors) == 0 and 
        len(team_b_majors) == 0 and
        no_other_penalties_on_clock()):
        # Special case: Both minors are served (4v4)
        # Track both, don't cancel
        return team_a_minors + team_b_minors + team_a_misconducts + team_b_misconducts
    
    # Step 3: Apply Rule 19.5 - Normal Coincidental Cancellation
    
    # Cancel majors first
    major_coincidental = min(len(team_a_majors), len(team_b_majors))
    net_a_majors = team_a_majors[major_coincidental:]
    net_b_majors = team_b_majors[major_coincidental:]
    
    # Cancel minors second
    minor_coincidental = min(len(team_a_minors), len(team_b_minors))
    net_a_minors = team_a_minors[minor_coincidental:]
    net_b_minors = team_b_minors[minor_coincidental:]
    
    # Step 4: Track remaining penalties
    penalties_to_track = (net_a_majors + net_b_majors + 
                          net_a_minors + net_b_minors +
                          team_a_misconducts + team_b_misconducts)
    
    # Flag misconducts as not affecting strength
    for penalty in team_a_misconducts + team_b_misconducts:
        penalty['affects_strength'] = False
    
    return penalties_to_track
```

### Key Points:

1. **Rule 19.1 check MUST be exact:** 1 minor vs 1 minor, no majors, no other penalties
2. **If Rule 19.1 applies:** Track both minors (4v4), don't cancel
3. **Otherwise:** Cancel majors first, then minors (Rule 19.5)
4. **Misconducts:** Always tracked but flagged as not affecting strength
5. **Equal cancellation to zero:** Full strength (5v5)

## Verification Against NHL Table 13 Examples

### Example 1: A3(2) vs B10(2+2)
```
Team A minors: 1
Team B minors: 2

Step 1: Cancel majors → None
Step 2: Cancel minors → 1 from each
Net: A=0 minors, B=1 minor

Result: Team B shorthanded by 1
✓ Matches NHL result
```

### Example 2: A3(2) + A5(2+2) vs B10(2+2) + B12(2)
```
Team A minors: 3 total
Team B minors: 3 total

Step 1: Cancel majors → None
Step 2: Cancel minors → 3 from each
Net: A=0, B=0

Result: Full strength (5v5)
✓ Matches NHL result
```

### Example 8: A9(2) + A24(2) vs B2(2+2) + B18(2)
```
Team A minors: 2 total
Team B minors: 3 total

Cancel: 2 from each
Net: A=0, B=1 minor

Result: Team B shorthanded by 1
✓ Matches NHL result
```

### Example 9: A3(5) vs B5(5)
```
Team A majors: 1
Team B majors: 1

Step 1: Cancel majors → 1 from each
Net: A=0, B=0

Result: Full strength (5v5)
✓ Matches NHL result
```

### Example 30: A3(2+10) vs B5(2)
```
Team A: 1 minor + 1 misconduct
Team B: 1 minor

Step 1: Cancel majors → None
Step 2: Cancel minors → 1 from each
Net: A=0 minors (plus 1 misconduct), B=0 minors

Special Rule 19.1 Check:
- Do we have 1 minor vs 1 minor BEFORE cancellation? YES
- Are there other penalties on the clocks? NO
- Therefore: BOTH minors are served WITHOUT cancellation

Result: 4v4 (NOT full strength)
✓ Matches NHL result

Note: The misconduct is served but doesn't affect on-ice strength
```

### Example 31: A3(2+10) vs B5(2+10)
```
Team A: 1 minor + 1 misconduct
Team B: 1 minor + 1 misconduct

Special Rule 19.1:
- 1 minor vs 1 minor
- No other penalties on clocks
- Both minors served without cancellation

Result: 4v4
✓ Matches NHL result

Misconducts: Both served (12 minutes total each) but don't affect strength
```

### Example 32: A3(2) + A4(10) vs B5(2) + B7(10)
```
Team A: 1 minor + 1 misconduct (different players)
Team B: 1 minor + 1 misconduct (different players)

Special Rule 19.1:
- 1 minor vs 1 minor
- No other penalties on clocks
- Both minors served without cancellation

Result: 4v4
✓ Matches NHL result
```

## Key Insights

1. **Rule 19.1 trumps normal coincidental cancellation** when you have exactly 1 minor vs 1 minor
2. **Misconducts are completely separate** - they're served but don't affect on-ice strength
3. **The order matters:**
   - First, check if this is a 1v1 minor situation (Rule 19.1)
   - If yes → 4v4, track both minors
   - If no → Apply normal coincidental cancellation (Rule 19.5)
4. **When a player gets 2+10:**
   - Track the 2-minute minor for expiration (affects on-ice strength)
   - Track the 10-minute misconduct for expiration (doesn't affect on-ice strength)
   - Player serves 2 in box, then 10 in locker room

## Implementation Requirements

### What We Need to Change in `generate_timeline.py`:

1. **Parse penalty notation correctly**
   - `2` = single minor
   - `2+2` = double minor (same player, consecutive)
   - `5` = major
   - `2+10` = minor + misconduct
   - `5+5` = double major

2. **Separate penalties by type**
   - Minors (2 min)
   - Majors (5 min)
   - Misconducts (10 min)
   - Game misconducts

3. **Apply Rule 19.1 check FIRST**
   ```python
   # Before doing any cancellation, check for 1v1 minor case
   if (team_a_minors == 1 and team_b_minors == 1 and 
       team_a_majors == 0 and team_b_majors == 0 and
       no_other_penalties_on_clock):
       # Both minors are served, track both
       # Result: 4v4
   ```

4. **Apply Rule 19.5 cancellation**
   - Cancel majors first (as many as possible)
   - Cancel minors second (as many as possible)
   - Track remaining penalties

5. **Handle misconducts**
   - Always track for expiration
   - Flag as `affects_strength = False`
   - Don't include in coincidental cancellation
   - Don't reduce on-ice strength

6. **Track consecutive penalties on same player**
   - Player A gets 2+2 → Two separate penalty objects
   - First expires at time+120s
   - Second expires at time+240s (consecutive)

### Data Structure for Penalties:

```python
penalty = {
    'eventId': 106,
    'teamId': 14,
    'playerId': 8476878,
    'startTime': 205,  # seconds
    'expiresAt': 325,  # seconds
    'duration': 2,  # minutes
    'durationSeconds': 120,
    'desc': 'cross-checking',
    'severity': 'MIN',  # MIN, MAJ, MIS, GMI
    'affects_strength': True,  # False for misconducts
    'active': True
}
```

### Current vs Required Logic:

**Current (WRONG):**
```python
# Group by penalty description (roughing, fighting, etc.)
# Cancel by type
```

**Required (CORRECT):**
```python
# 1. Parse all penalties, separate minors/majors/misconducts
# 2. Check Rule 19.1 (1v1 minor exception)
# 3. Apply Rule 19.5 (cancel majors, then minors)
# 4. Track remaining penalties (including misconducts)
# 5. Flag misconducts as not affecting strength
```

## Action Items

1. ✅ Document the correct coincidental penalty logic
2. ⏸️ Clarify misconduct penalty handling (Example 30)
3. ⏸️ Update `process_penalties_at_time()` to NOT group by penalty type
4. ⏸️ Implement proper 1-for-1 cancellation logic
5. ⏸️ Add logic to distinguish minors/majors (box time) vs misconducts (no box time)
6. ⏸️ Handle equal remaining penalties → reduced strength (4v4, 3v3)
7. ⏸️ Test against known examples from Table 13

## Reference Examples to Test Against

| Example | Team A | Team B | Expected Result |
|---------|--------|--------|-----------------|
| 1 | A3(2) | B10(2+2) | B shorthanded 1 |
| 2 | A3(2), A5(2+2) | B10(2+2), B12(2) | Full strength |
| 8 | A9(2), A24(2) | B2(2+2), B18(2) | B shorthanded 1 |
| 9 | A3(5) | B5(5) | Full strength |
| 11 | A3(5), A4(5) | B5(5), B7(5) | Full strength |
| 30 | A3(2+10) | B5(2) | **4v4** ⚠️ |
| 32 | A3(2), A4(10) | B5(2), B7(10) | **4v4** ⚠️ |

⚠️ = Needs clarification on misconduct handling

## Notes

- The NHL API provides the correct `situationCode` in the play-by-play data
- Our job is to determine which penalties to **track for expiration**
- Coincidental penalties that cancel out should NOT be tracked
- Only net penalties after cancellation need expiration tracking
