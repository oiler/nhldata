# v2/browser/utils.py


def seconds_to_mmss(seconds) -> str:
    """Convert numeric seconds to 'M:SS' string. Returns '0:00' for None/zero."""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "00:00"
    m, sec = divmod(abs(s), 60)
    return f"{m:02d}:{sec:02d}"
