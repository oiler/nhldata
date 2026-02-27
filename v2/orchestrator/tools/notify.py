"""macOS native notifications via osascript."""

import subprocess


def send_notification(title: str, message: str):
    """Send a macOS notification. Fails silently on non-macOS."""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ], capture_output=True, timeout=10)
    except Exception:
        pass  # non-macOS or osascript unavailable
