#!/usr/bin/env python3
# v2/orchestrator/runner.py
"""NHL Pipeline Orchestrator — entry point.

Usage:
    python v2/orchestrator/runner.py                        # Daily scheduled run
    python v2/orchestrator/runner.py "re-fetch game 734"    # Manual command
"""

import sys
from datetime import date, timedelta
from pathlib import Path

# Allow running as `python v2/orchestrator/runner.py` (not just -m)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from v2.orchestrator.agent import run_agent
from v2.orchestrator.config import SEASON
from v2.orchestrator.log_writer import LogWriter


def daily_prompt(season: str) -> str:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return (
        f"Run the daily pipeline. Season is {season} (the {season}-{int(season)+1} NHL season).\n"
        f"Yesterday's date is {yesterday}. Do not second-guess the date — use it as given.\n"
        f"1. Call check_schedule with date {yesterday}.\n"
        f"2. If games were found, fetch them with fetch_games.\n"
        f"3. Validate all fetched data.\n"
        f"4. If shifts are missing, retry with fetch_shifts.\n"
        f"5. Run all generation steps for new games.\n"
        f"6. Rebuild the league database.\n"
        f"7. Send a notification summarizing what happened.\n"
        f"If no games were played yesterday, just send a notification saying so."
    )


def main():
    season = SEASON

    if len(sys.argv) > 1:
        # Manual mode — user provided a command
        user_message = " ".join(sys.argv[1:])
        # Inject season context
        user_message = f"[Season: {season}] {user_message}"
    else:
        # Scheduled daily mode
        user_message = daily_prompt(season)

    log = LogWriter(season)
    log.section("Agent Input")
    log.item(user_message)

    print(f"Running orchestrator (season {season})...")
    print(f"Prompt: {user_message}\n")

    try:
        result = run_agent(user_message, season=season)
    except Exception as e:
        result = f"Agent error: {e}"

    log.section("Agent Output")
    log.item(result)

    log.section("Summary")
    log.item(f"Completed at {log.start_time.strftime('%H:%M')}")

    log_path = log.save()
    print(f"\nAgent response:\n{result}")
    print(f"\nLog saved to: {log_path}")


if __name__ == "__main__":
    main()
