from v2.goalies.windows import detect_freeze, detect_rebound


def test_freeze_stoppage_within_window():
    events = [(101, "stoppage", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is True


def test_no_freeze_when_stoppage_late():
    events = [(106, "stoppage", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is False


def test_freeze_stoppage_at_window_boundary():
    events = [(105, "stoppage", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is True


def test_no_freeze_just_past_window_boundary():
    events = [(106, "stoppage", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is False


def test_no_freeze_when_play_continues():
    events = [(101, "hit", 10, 1), (102, "stoppage", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is False


def test_period_end_counts_as_freeze():
    events = [(101, "period-end", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is True


def test_freeze_ignores_next_period_events():
    events = [(0, "faceoff", 10, 2)]
    assert detect_freeze(events, save_time_s=1199, period=1) is False


def test_rebound_same_team_corsi_within_3s():
    events = [(102, "shot-on-goal", 10, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is True


def test_no_rebound_when_other_team_shoots():
    events = [(102, "shot-on-goal", 20, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is False


def test_no_rebound_after_window():
    events = [(104, "shot-on-goal", 10, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is False


def test_no_rebound_after_stoppage():
    events = [(101, "stoppage", None, 1), (102, "shot-on-goal", 10, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is False


def test_rebound_skips_neutral_events():
    # a hit by either team inside the window does not end the chance
    events = [(101, "hit", 20, 1), (102, "missed-shot", 10, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is True
