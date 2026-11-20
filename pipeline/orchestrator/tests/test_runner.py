# pipeline/orchestrator/tests/test_runner.py
from pipeline.orchestrator.runner import to_ranges


def test_to_ranges_groups_consecutive_game_numbers():
    assert to_ranges([17, 18, 19, 56, 70, 71]) == [(17, 19), (56, 56), (70, 71)]
    assert to_ranges([]) == []
