"""Tests for the 5v5 off-wing vs strong-side split logic.

Synthetic data only — no dependency on real game files.
"""

import math

import pandas as pd
import pytest

from offwing_splits import (
    classify_wing,
    cmh_odds_ratio,
    distance_band,
    extract_shots,
    normalize_coords,
    parse_time,
    shot_angle,
    shot_distance,
    shot_side,
    split_table,
    two_prop_z,
)


# --- coordinate normalization -------------------------------------------------

def test_normalize_flips_when_attacking_negative_x():
    assert normalize_coords(-58, -22) == (58, 22)


def test_normalize_keeps_positive_x():
    assert normalize_coords(58, 22) == (58, 22)


def test_normalize_flips_y_sign_with_x():
    # 180-degree rotation, not a mirror: both axes flip together
    assert normalize_coords(-70, 15) == (70, -15)


# --- side / wing classification -----------------------------------------------

def test_shot_side_positive_y_is_left():
    # attacking +x, the +y half is on the shooter's left
    assert shot_side(10) == "left"


def test_shot_side_negative_y_is_right():
    assert shot_side(-10) == "right"


def test_shot_side_center_is_none():
    assert shot_side(0) is None


@pytest.mark.parametrize(
    "shoots,y_norm,expected",
    [
        ("L", 10, "strong"),   # left shot, left side
        ("L", -10, "off"),     # left shot, right side = off-wing
        ("R", 10, "off"),      # right shot, left side = off-wing
        ("R", -10, "strong"),  # right shot, right side
    ],
)
def test_classify_wing(shoots, y_norm, expected):
    assert classify_wing(shoots, y_norm) == expected


def test_classify_wing_center_is_none():
    assert classify_wing("L", 0) is None


# --- geometry -------------------------------------------------------------------

def test_shot_distance_straight_on():
    assert shot_distance(79, 0) == pytest.approx(10.0)


def test_shot_distance_diagonal():
    assert shot_distance(89, 10) == pytest.approx(10.0)


def test_shot_angle_straight_on_is_zero():
    assert shot_angle(79, 0) == pytest.approx(0.0)


def test_shot_angle_beside_net_is_ninety():
    assert shot_angle(89, 10) == pytest.approx(90.0)


def test_distance_bands():
    assert distance_band(10) == "00-15ft"
    assert distance_band(20) == "15-30ft"
    assert distance_band(44.9) == "30-45ft"
    assert distance_band(60) == "45ft+"


# --- statistics -----------------------------------------------------------------

def test_two_prop_z_equal_proportions():
    z, p = two_prop_z(5, 50, 10, 100)
    assert z == pytest.approx(0.0)
    assert p == pytest.approx(1.0)


def test_two_prop_z_known_value():
    # g1/n1 = 10%, g2/n2 = 5%, pooled p = 0.075
    z, p = two_prop_z(10, 100, 5, 100)
    assert z == pytest.approx(1.3423, abs=1e-3)
    assert p == pytest.approx(0.1796, abs=1e-3)


def test_cmh_single_stratum_matches_plain_odds_ratio():
    # (off goals, off misses, strong goals, strong misses)
    assert cmh_odds_ratio([(2, 8, 1, 9)]) == pytest.approx(2.25)


def test_cmh_pools_across_strata():
    # two identical strata pool to the same OR
    assert cmh_odds_ratio([(2, 8, 1, 9), (2, 8, 1, 9)]) == pytest.approx(2.25)


# --- time parsing -----------------------------------------------------------------

def test_parse_time():
    assert parse_time("01:16") == 76
    assert parse_time("00:00") == 0
    assert parse_time("19:59") == 1199


# --- extraction -----------------------------------------------------------------

def _play(type_desc, situation="1551", zone="O", x=70, y=-20, shooter=1,
          shot_type="wrist", period_type="REG", time="05:00", period=1, owner=10):
    details = {
        "xCoord": x,
        "yCoord": y,
        "zoneCode": zone,
        "eventOwnerTeamId": owner,
    }
    if type_desc == "goal":
        details["scoringPlayerId"] = shooter
        details["shotType"] = shot_type
    elif type_desc == "blocked-shot":
        details["shootingPlayerId"] = shooter
    elif type_desc in ("shot-on-goal", "missed-shot"):
        details["shootingPlayerId"] = shooter
        details["shotType"] = shot_type
    return {
        "typeDescKey": type_desc,
        "situationCode": situation,
        "periodDescriptor": {"number": period, "periodType": period_type},
        "timeInPeriod": time,
        "details": details,
    }


def _game(plays):
    return {
        "id": 2025020001,
        "rosterSpots": [
            {"playerId": 1, "positionCode": "C"},
            {"playerId": 2, "positionCode": "D"},
            {"playerId": 3, "positionCode": "G"},
        ],
        "plays": plays,
    }


def test_extract_shots_keeps_qualifying_unblocked_5v5_ozone_shots():
    game = _game([
        _play("shot-on-goal"),
        _play("goal", shooter=2, x=-60, y=30),
    ])
    rows = extract_shots(game)
    assert len(rows) == 2
    sog, goal = rows
    assert sog["is_goal"] is False
    assert sog["position"] == "F"
    assert goal["is_goal"] is True
    assert goal["position"] == "D"
    assert (goal["x_norm"], goal["y_norm"]) == (60, -30)


def test_extract_shots_prior_event_fields():
    game = _game([
        _play("faceoff", time="05:00", x=-69, y=22, owner=10),
        _play("shot-on-goal", time="05:02", x=-70, y=20, owner=10),
    ])
    rows = extract_shots(game)
    assert len(rows) == 1
    shot = rows[0]
    assert shot["dt_prev"] == 2
    assert shot["prev_type"] == "faceoff"
    assert shot["prev_same_team"] is True
    # prior coords rotated with the SAME flip as the shot (shot x<0, so both negate)
    assert (shot["prev_x_norm"], shot["prev_y_norm"]) == (69, -22)
    assert shot["time_s"] == 302
    assert shot["period"] == 1


def test_extract_shots_cross_period_prior_ignored():
    game = _game([
        _play("hit", time="19:59", period=1, owner=99),
        _play("shot-on-goal", time="00:03", period=2),
    ])
    shot = extract_shots(game)[0]
    assert shot["dt_prev"] is None
    assert shot["prev_type"] is None


def test_extract_shots_first_event_has_no_prior():
    shot = extract_shots(_game([_play("shot-on-goal")]))[0]
    assert shot["dt_prev"] is None
    assert shot["prev_same_team"] is None


def test_extract_shots_opponent_prior_event():
    game = _game([
        _play("giveaway", time="10:00", x=60, y=5, owner=99),
        _play("missed-shot", time="10:01", x=70, y=-20, owner=10),
    ])
    shot = extract_shots(game)[0]
    assert shot["dt_prev"] == 1
    assert shot["prev_same_team"] is False
    assert (shot["prev_x_norm"], shot["prev_y_norm"]) == (60, 5)


def test_extract_shots_excludes_non_qualifying():
    game = _game([
        _play("shot-on-goal", situation="1441"),       # 4v4
        _play("blocked-shot"),                         # blocked: no shotType, block location
        _play("shot-on-goal", zone="N"),               # outside O zone
        _play("shot-on-goal", shooter=3),              # goalie shooter
        _play("shot-on-goal", shooter=99),             # not in rosterSpots
        _play("missed-shot", x=None),                  # missing coords
        _play("goal", period_type="SO"),               # shootout
        _play("faceoff"),                              # not a shot
    ])
    assert extract_shots(game) == []


# --- split table ----------------------------------------------------------------

def test_split_table_counts_and_percentages():
    df = pd.DataFrame({
        "wing": ["off"] * 10 + ["strong"] * 20,
        "is_goal": [True] * 2 + [False] * 8 + [True] * 2 + [False] * 18,
        "distance": [20.0] * 30,
        "angle": [30.0] * 30,
    })
    row = split_table(df).iloc[0]
    assert row["off_att"] == 10
    assert row["off_goals"] == 2
    assert row["off_sh%"] == pytest.approx(20.0)
    assert row["strong_att"] == 20
    assert row["strong_goals"] == 2
    assert row["strong_sh%"] == pytest.approx(10.0)
    assert row["diff_pp"] == pytest.approx(10.0)


def test_split_table_grouped():
    df = pd.DataFrame({
        "position": ["F"] * 4 + ["D"] * 4,
        "wing": ["off", "off", "strong", "strong"] * 2,
        "is_goal": [True, False, False, False, False, False, False, False],
        "distance": [20.0] * 8,
        "angle": [30.0] * 8,
    })
    out = split_table(df, ["position"]).set_index("position")
    assert out.loc["F", "off_goals"] == 1
    assert out.loc["D", "off_goals"] == 0
