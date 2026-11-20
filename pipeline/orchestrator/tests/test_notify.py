from unittest.mock import patch

from pipeline.orchestrator.tools.notify import send_notification


@patch("pipeline.orchestrator.tools.notify.subprocess.run")
def test_send_notification(mock_run):
    send_notification("NHL Pipeline", "4 games processed")
    assert mock_run.called
    cmd = mock_run.call_args[0][0]
    assert "osascript" in cmd[0]
    assert "NHL Pipeline" in cmd[-1]
