# v2/orchestrator/log_writer.py
"""Write pipeline run logs as markdown files."""

from datetime import datetime
from pathlib import Path

from v2.orchestrator.config import log_dir


class LogWriter:
    def __init__(self, season: str):
        self.season = season
        self.lines: list[str] = []
        self.start_time = datetime.now()
        self._add(f"# Pipeline Run — {self.start_time.strftime('%Y-%m-%d %H:%M')}\n")

    def section(self, title: str):
        self._add(f"\n## {title}\n")

    def item(self, text: str):
        self._add(f"- {text}")

    def _add(self, line: str):
        self.lines.append(line)

    def save(self) -> Path:
        out_dir = log_dir(self.season)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = self.start_time.strftime("%Y-%m-%d") + ".md"
        path = out_dir / filename
        path.write_text("\n".join(self.lines) + "\n")
        return path

    def summary(self) -> str:
        """Return the last section's content as a short string for notifications."""
        for i in range(len(self.lines) - 1, -1, -1):
            if self.lines[i].startswith("## Summary"):
                return "\n".join(self.lines[i + 1:]).strip()
        return "Pipeline run complete."
