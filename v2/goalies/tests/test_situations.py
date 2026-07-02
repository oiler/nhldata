import pytest

from v2.goalies.situations import PENALTY_SHOT_CODES, parse_situation, strength_for_goalie


def test_parse_situation():
    assert parse_situation("1551") == (1, 5, 5, 1)
    assert parse_situation("0651") == (0, 6, 5, 1)


@pytest.mark.parametrize(
    "code,goalie_is_home,expected",
    [
        ("1551", True, "EV"),   # 5v5
        ("1441", False, "EV"),  # 4v4
        ("1451", True, "PP"),   # home has 5 skaters vs away 4: home goalie's team on PP
        ("1451", False, "SH"),  # away goalie's team is shorthanded
        ("1541", True, "SH"),
        ("0651", True, "SH"),   # away pulled goalie for 6th skater; home goalie's team defends 5v6
    ],
)
def test_strength_for_goalie(code, goalie_is_home, expected):
    assert strength_for_goalie(code, goalie_is_home) == expected


def test_penalty_shot_codes():
    assert "0101" in PENALTY_SHOT_CODES and "1010" in PENALTY_SHOT_CODES
