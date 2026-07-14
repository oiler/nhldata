"""Tests for the get_players snapshot-freeze guard.

A completed season's player snapshot captures point-in-time height/weight. A full
(`all`) or `targeted` run overwrites raw player files with *current* bio data, which
would corrupt that snapshot. The guard blocks those modes for a frozen season;
`backfill` is additive and always allowed.
"""

from pathlib import Path

import pytest


def test_freeze_marker_path_is_dotfile_in_players_dir():
    from v2.players.get_players import freeze_marker_path

    assert freeze_marker_path(Path("data/2024/players")) == Path(
        "data/2024/players/.snapshot_frozen"
    )


def test_is_snapshot_frozen_reflects_marker(tmp_path):
    from v2.players.get_players import freeze_marker_path, is_snapshot_frozen

    assert is_snapshot_frozen(tmp_path) is False
    freeze_marker_path(tmp_path).write_text("")
    assert is_snapshot_frozen(tmp_path) is True


@pytest.mark.parametrize(
    "mode,frozen,force,expected",
    [
        ("all", True, False, True),        # full run on a frozen season -> block
        ("all", True, True, False),        # force overrides the freeze
        ("all", False, False, False),      # not frozen -> allowed
        ("targeted", True, False, True),   # targeted also overwrites -> block
        ("backfill", True, False, False),  # backfill is additive -> always allowed
    ],
)
def test_should_block_overwrite(mode, frozen, force, expected):
    from v2.players.get_players import should_block_overwrite

    assert should_block_overwrite(mode, frozen, force) is expected
