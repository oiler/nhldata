#!/usr/bin/env python3
# pipeline/orchestrator/runner.py
"""NHL Pipeline Orchestrator — entry point.

Usage:
    python pipeline/orchestrator/runner.py                        # Daily scheduled run
    python pipeline/orchestrator/runner.py "re-fetch game 734"    # Manual command
"""

import sys
from datetime import date, timedelta
from pathlib import Path


from pipeline.orchestrator.agent import run_agent
from pipeline.orchestrator.config import SEASON
from pipeline.orchestrator.log_writer import LogWriter
from pipeline.orchestrator.tools.schedule import played_game_ids
from pipeline.orchestrator.tools.validate import pending_games


def to_ranges(numbers: list[int]) -> list[tuple[int, int]]:
    """Group sorted game numbers into inclusive (start, end) runs."""
    ranges = []
    for n in numbers:
        if ranges and n == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], n)
        else:
            ranges.append((n, n))
    return ranges


def _format_ranges(numbers: list[int]) -> str:
    return ", ".join(f"{a}-{b}" for a, b in to_ranges(numbers)) or "none"


def daily_prompt(season: str, yesterday: str, pending: dict) -> str:
    header = (
        f"Run the daily pipeline. Season is {season} (the {season}-{int(season)+1} NHL season).\n"
        f"Every game played through {yesterday} has already been checked against the files on disk, "
        f"so do not call check_schedule.\n"
    )
    if not pending["generate"]:
        return header + (
            "No games are waiting to be fetched or generated. "
            "Just send a notification saying so."
        )
    return header + (
        f"Game-number ranges to fetch: {_format_ranges(pending['fetch'])}\n"
        f"Game-number ranges to generate: {_format_ranges(pending['generate'])}\n"
        f"These include any games earlier runs missed. Use the ranges exactly as given.\n"
        f"1. Call fetch_games once for each fetch range.\n"
        f"2. Validate all fetched data.\n"
        f"3. If shifts are missing, retry with fetch_shifts.\n"
        f"4. Run the generation steps, calling the per-range steps once for each generate range.\n"
        f"5. Rebuild the league database.\n"
        f"6. Send a notification summarizing what happened."
    )


def main():
    season = SEASON
    log = LogWriter(season)

    if len(sys.argv) > 1:
        # Manual mode — user provided a command
        user_message = " ".join(sys.argv[1:])
        # Inject season context
        user_message = f"[Season: {season}] {user_message}"
    else:
        # Scheduled daily mode
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        try:
            pending = pending_games(played_game_ids(yesterday, season), season=season)
        # The schedule is an external API: any failure here ends the run with a log entry.
        except Exception as e:
            log.section("Summary")
            log.item(f"Schedule error: {e}")
            print(f"Schedule error: {e}\nLog saved to: {log.save()}")
            return
        user_message = daily_prompt(season, yesterday, pending)

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
