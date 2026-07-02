"""Post-save event windows: freeze (era-robust 5s stoppage) and rebound generation (3s).

FREEZE_WINDOW_S is an era-robust widening of Cane's original 2s window. NHL event
timestamps shifted ~1-2s later starting in 2023 (the "tracking era"): the save-to-
stoppage dt distribution moved right across seasons, even though the underlying share
of saves whose next event is a stoppage stayed stable (~0.36-0.38) across the same
seasons. A fixed 2s window therefore under-detects freezes in 2023+ relative to
2021-22, producing a spurious downward trend in freeze% that is a measurement
artifact of timestamping, not a change in on-ice behavior. Widening to 5s captures
~86% of save-adjacent stoppages on both sides of the era boundary, restoring
cross-season comparability.
"""

FREEZE_WINDOW_S = 5
REBOUND_WINDOW_S = 3
CORSI_EVENTS = {"goal", "shot-on-goal", "missed-shot", "blocked-shot"}
STOP_EVENTS = {"stoppage", "period-end", "game-end"}


def detect_freeze(events_after, save_time_s: int, period: int) -> bool:
    """True if play stops within FREEZE_WINDOW_S of the save, before any live-play event."""
    for t, kind, _owner, p in events_after:
        if p != period or t - save_time_s > FREEZE_WINDOW_S:
            return False
        if kind in STOP_EVENTS:
            return True
        return False  # first event was live play
    return False


def detect_rebound(events_after, save_time_s: int, period: int, shooting_team: int) -> bool:
    """True if the shooting team gets another attempt within REBOUND_WINDOW_S, play still live."""
    for t, kind, owner, p in events_after:
        if p != period or t - save_time_s > REBOUND_WINDOW_S:
            return False
        if kind in STOP_EVENTS or kind == "faceoff":
            return False
        if kind in CORSI_EVENTS:
            return owner == shooting_team
    return False
