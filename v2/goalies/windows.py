"""Post-save event windows: freeze (Cane 2s stoppage) and rebound generation (3s)."""

FREEZE_WINDOW_S = 2
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
