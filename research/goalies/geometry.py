"""Attack-direction-aware shot geometry.

homeTeamDefendingSide semantics (verified empirically against zoneCode):
"right" = home defends positive x, so home attacks -x. flip = -1 rotates the
rink 180 degrees so the shooter always attacks +x; net at (NET_X, 0).
"""

import math

NET_X = 89.0


def parse_time(mmss: str) -> int:
    m, s = mmss.split(":")
    return int(m) * 60 + int(s)


def attack_flip(home_defending_side: str, shooter_is_home: bool) -> int:
    home_attacks = -1 if home_defending_side == "right" else 1
    return home_attacks if shooter_is_home else -home_attacks


def normalize(x: float, y: float, flip: int) -> tuple[float, float]:
    return (flip * x, flip * y)


def shot_distance(x_norm: float, y_norm: float) -> float:
    return math.hypot(NET_X - x_norm, y_norm)


def shot_angle(x_norm: float, y_norm: float) -> float:
    return math.degrees(math.atan2(abs(y_norm), NET_X - x_norm))
