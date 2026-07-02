"""situationCode parsing for goalie-perspective strength states.

Format: [away goalie][away skaters][home skaters][home goalie], e.g. 1551.
"""

PENALTY_SHOT_CODES = {"0101", "1010"}


def parse_situation(code: str) -> tuple[int, int, int, int]:
    a_g, a_s, h_s, h_g = (int(c) for c in code)
    return a_g, a_s, h_s, h_g


def strength_for_goalie(code: str, goalie_is_home: bool) -> str:
    """Strength state of the GOALIE'S team: EV, PP (his team up a skater), SH."""
    _, a_s, h_s, _ = parse_situation(code)
    own, opp = (h_s, a_s) if goalie_is_home else (a_s, h_s)
    if own == opp:
        return "EV"
    return "PP" if own > opp else "SH"
