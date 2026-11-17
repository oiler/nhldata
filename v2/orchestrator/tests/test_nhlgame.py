# v2/orchestrator/tests/test_nhlgame.py
"""The fetcher's range loop: a failed game must not cost the games after it."""
import importlib.util
from unittest.mock import patch

import pytest

from v2.orchestrator.config import SCRIPTS

_spec = importlib.util.spec_from_file_location("nhlgame", SCRIPTS["fetch_games"])
nhlgame = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nhlgame)


def _run_range(start, end, failing):
    """Run main() over a range; games whose number is in `failing` lose their shifts."""
    attempted = []

    def fake_download(game_id, paths):
        num = int(game_id[-4:])
        attempted.append(num)
        return (0, 2, True) if num in failing else (5, 0, False)

    with patch.object(nhlgame, "download_game", fake_download), \
         patch.object(nhlgame, "setup_directories", lambda season: {}), \
         patch.object(nhlgame.time, "sleep", lambda s: None), \
         patch.object(nhlgame.sys, "argv", ["nhlgame.py", str(start), str(end)]):
        with pytest.raises(SystemExit) as exit_info:
            nhlgame.main()
    return attempted, exit_info.value.code


def test_one_failed_game_does_not_stop_the_range():
    attempted, code = _run_range(263, 268, failing={263})
    assert attempted == [263, 264, 265, 266, 267, 268]
    assert code == 1


def test_consecutive_failures_stop_the_range():
    attempted, code = _run_range(263, 270, failing={264, 265, 266, 267})
    assert attempted == [263, 264, 265, 266]
    assert code == 1
