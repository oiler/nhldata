import pytest

from v2.goalies.geometry import attack_flip, normalize, parse_time, shot_angle, shot_distance


def test_parse_time():
    assert parse_time("01:16") == 76
    assert parse_time("19:59") == 1199


def test_attack_flip_home_defends_right_attacks_left():
    # home defends +x, so home attacks -x: flip -1 rotates attack onto +x
    assert attack_flip("right", shooter_is_home=True) == -1
    assert attack_flip("right", shooter_is_home=False) == 1


def test_attack_flip_home_defends_left():
    assert attack_flip("left", shooter_is_home=True) == 1
    assert attack_flip("left", shooter_is_home=False) == -1


def test_normalize_rotates_180():
    assert normalize(-58, -22, flip=-1) == (58, 22)
    assert normalize(58, 22, flip=1) == (58, 22)


def test_distance_and_angle():
    assert shot_distance(79, 0) == pytest.approx(10.0)
    assert shot_distance(89, 10) == pytest.approx(10.0)
    assert shot_angle(79, 0) == pytest.approx(0.0)
    assert shot_angle(89, 10) == pytest.approx(90.0)


def test_defensive_zone_shot_normalizes_toward_positive_x():
    # shooter is home, home defends left (-x): attack is +x, no flip;
    # a D-zone shot from x=-60 stays at -60 (129 ft out) rather than flipping
    flip = attack_flip("left", shooter_is_home=True)
    xn, yn = normalize(-60, 5, flip)
    assert (xn, yn) == (-60, 5)
    assert shot_distance(xn, yn) == pytest.approx(149.08, abs=0.01)
