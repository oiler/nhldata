# v2/browser/utils.py


def seconds_to_mmss(seconds) -> str:
    """Convert numeric seconds to 'M:SS' string. Returns '0:00' for None/zero."""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "0:00"
    m, sec = divmod(abs(s), 60)
    return f"{m}:{sec:02d}"
