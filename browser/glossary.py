"""Stat definitions: the glossary footer and the column-header tooltips both read these.

Each entry is (term, definition). A term that names several columns, such as
"G, A, P", is split into its columns by `COLUMN_TERMS`.
"""

SKATERS = [
    ('Age',
     "Player's age in years as of Sept 15 of the season's start year (Sept 15, 2025 for the 2025-26 season)."),
    ('PPI',
     "Pounds Per Inch — a player's weight (lbs) divided by height (inches). A purely physical build metric."),
    ('PPI+',
     'PPI indexed to the league average (100 = average). 110 means 10% heavier build than average; 90 means 10% lighter.'),
    ('wPPI',
     "Weighted PPI — PPI scaled by a player's average 5v5 TOI share relative to their team. Measures deployment-adjusted physical presence per game."),
    ('wPPI+',
     'wPPI indexed to the league average (100 = average). Accounts for both build and 5v5 deployment rate.'),
    ('SB/a60',
     "Speed Bursts per all-situation 60 — count of NHL EDGE skating bursts above 20 mph per 60 minutes of total ice time (all strengths). A pure speed-attribute metric; high values indicate explosive skaters. Among 2025-26 skaters with 500+ minutes, forwards had a median near 5 and the top 10% above 10.7; defensemen had a median near 1.7 and the top 10% above 3.5. Computed from season totals, so it doesn't change with the date filter."),
    ('Max MPH',
     "Top season skating speed in mph, recorded by the NHL EDGE tracking system. A single peak value across one season's regular-season ice time."),
    ('G, A, P',
     '5v5 goals, assists, and points.'),
    ('P/60',
     '5v5 points per 60 minutes of 5v5 ice time.'),
    ('iSA/60',
     "Individual shot attempts per 60 minutes of 5v5 ice time — shots on goal, missed shots, and the player's own attempts that were blocked, plus goals. Measures how much shot volume a skater generates himself."),
    ('P/100iSA',
     "5v5 points (goals + assists) per 100 individual shot attempts. Measures how productive each attempt is; playmakers score high. On the leaderboard, shown only for skaters with at least 50 attempts in the window so small samples don't distort the sort."),
    ('tTOI%',
     "Share of the team's 5v5 ice time played by this skater per game. Computed as 5 × player_toi / team_total_5v5_toi per game, then averaged across the season. 20% means the skater played 1/5 of all available 5v5 ice time."),
    ('iTOI%',
     "Fraction of a player's total ice time (all situations) spent at 5v5. Lower values indicate power play or penalty kill specialists."),
    ('5v5 TOI/GP',
     'Average 5-on-5 time on ice per game played.'),
    ('5v5 TOI',
     '5-on-5 time on ice in one game.'),
    ('Line / Pair',
     'The forward line (1–4) or defense pair a skater played on in one game, detected from the 5v5 combinations that played together most. 1 is the top unit.'),
    ('Dep Score',
     'Raw deployment score for one game, the input to DPS+. Each 5v5 second adds points for the opposition faced: a defenseman gets 12 minus the line numbers of the three opposing forwards, and a forward gets 8 minus the pair numbers of the two opposing defensemen. More ice time against top units gives a higher score.'),
    ('DPS+',
     "Deployment Score Plus — a skater's raw deployment score (Dep Score) indexed to the league average for their position (100 = average). For a defenseman the raw score reflects the opposing forward lines faced; for a forward, the opposing defense pairs. 110 means 10% tougher deployment than average."),
    ('DPL',
     "Deployment Line — a skater's average line (forwards) or pair (defensemen) across games played, where 1 is the top unit. Lower values indicate higher deployment; 1.0 means used only on the top unit."),
]

TEAMS_AND_GAMES = [
    ('P%',
     'Points percentage — standings points (2 for a win, 1 for an overtime or shootout loss) divided by the maximum possible, 2 per game played.'),
    ('RW',
     'Regulation wins — wins decided in the first three periods.'),
    ('5v5 GF, GA, GD',
     'Goals for, goals against, and goal differential with both goalies in at 5v5 (situation 1551).'),
    ('FWD, DEF, Team PPI',
     "Average PPI of a team's forwards, defensemen, or all skaters in one game, weighted by their 5v5 ice time."),
    ('FWD, DEF, Team wPPI',
     "Average season PPI+ of a team's forwards, defensemen, or all skaters, weighted by their 5v5 ice time in one game."),
    ('Team Heaviness, OPP Heaviness',
     "Team PPI for a team and for its opponent in one game, on the team page's game log."),
    ('Game wPPI+',
     "A skater's wPPI+ for one game: PPI+ times that game's 5v5 ice time, divided by the league mean wPPI, times 100. It uses the season's league mean, so it compares directly with season wPPI+."),
]

GOALIES = [
    ('Shots',
     'Unblocked shot attempts faced (shots on goal plus misses), all strength states by default.'),
    ('xGA',
     "Expected goals against — the sum of each shot's goal probability from our goalie-blind shot model (rink-adjusted location, shot type, strength, score state, pre-shot context). What an average goalie would concede on the same shots."),
    ('xGA/60',
     'Expected goals against per 60 minutes — how much danger the team in front served up. This is the term that makes GSAx/100 and GSAx/60 disagree.'),
    ('GSAx',
     "Goals Saved Above Expected: xGA − GA. Positive means fewer goals conceded than the shot mix predicted. Descriptive, not predictive — it is weakly repeatable year over year (r ≈ 0.1) and did not predict goalies' post-trade results in our validation."),
    ('GSAx/100',
     'GSAx per 100 unblocked shots faced — the workload-independent rate form.'),
    ('GSAx/60',
     'GSAx per 60 minutes of ice time — the workload-dependent rate form. Read it against GSAx/100: a goalie who rates well per shot but poorly per 60 faced a light shot load, and one who rates well per 60 but poorly per shot was busy.'),
    ('Freeze rate',
     'Share of saves frozen for a stoppage within 5 seconds. The most repeatable goalie skill in our data (year-over-year r ≈ 0.6–0.7) — it travels with the goalie, not the team.'),
    ('Freeze pct',
     'League percentile (0–100) of freeze rate within the season, among goalies with 500+ saves.'),
    ('Freeze impact',
     'Goals per starter season attributable to freeze skill, relative to the league-median freeze rate. From our pricing study: each freeze suppresses ≈ 0.02 expected goals over the next 30 seconds of play versus playing the puck on.'),
    ('Difficulty',
     "Per-game workload percentile (0–100): the game's xG faced per 60 ranked against all goalie-games of 20+ minutes league-wide. 90 means a harder night than 90% of goalie starts. In 5v5 mode, the rate is 5v5 xG faced per 60 of total ice time."),
    ('Difficulty faced',
     "Season average of per-game Difficulty — how hard this goalie's slate of games actually was."),
    ('Perf z',
     "Difficulty-adjusted single-game score: (xGA − GA) scaled by the game's shot-quality variance. 0 = as expected for that workload; +2 is an excellent night. Noisy for short relief stints."),
    ('Perf (season z̄)',
     'Season mean of per-game Perf z. Compare goalies on this aggregate, not on single games.'),
    ('Leverage',
     'Win-probability value added: each shot outcome weighted by how much win probability a goal would have swung in that game state — a save in a tied third period counts more than one up 5-0. Descriptive by design.'),
    ('Difficulty served',
     'Team page — the average per-game Difficulty a team hands its own goalies, the “o-line grade.” Measures workload served, not goalie quality.'),
    ('xG faced/60',
     "Team page — expected goals against per 60 minutes served to the team's goalies."),
    ('High-danger share',
     'Team page — share of shots faced from inside 15 feet (rink-adjusted).'),
    ('Cross-ice/60',
     'Team page — cross-ice quick plays against per 60: shots within 3 seconds of a same-team attempt from the other side of the ice, the highest-conversion pattern we measure.'),
    ('Back-to-backs',
     'Team page — games played on the second night of consecutive team game days.'),
]

# Column names that differ from their glossary term.
COLUMN_TERMS = {
    "G": "G, A, P",
    "A": "G, A, P",
    "P": "G, A, P",
    "5v5 GF": "5v5 GF, GA, GD",
    "5v5 GA": "5v5 GF, GA, GD",
    "5v5 GD": "5v5 GF, GA, GD",
    "Line": "Line / Pair",
}

_DEFINITIONS = dict(SKATERS + TEAMS_AND_GAMES + GOALIES)


def header_tooltips(columns) -> dict:
    """DataTable `tooltip_header` for the columns whose name is a glossary term."""
    tips = {}
    for col in columns:
        definition = _DEFINITIONS.get(COLUMN_TERMS.get(col["name"], col["name"]))
        if definition:
            tips[col["id"]] = {"value": definition, "type": "text"}
    return tips
