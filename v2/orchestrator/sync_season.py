#!/usr/bin/env python3
"""One-time full season sync — generate all derived data from raw files.

Assumes raw data (boxscores, plays, meta, shifts) is already downloaded.

Usage:
    python v2/orchestrator/sync_season.py 2024
"""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from v2.orchestrator.config import SCRIPTS

STEPS = [
    ("flatten_boxscores", "flatten_boxscore", lambda s, n: [s]),
    ("flatten_plays", "flatten_plays", lambda s, n: ["1", str(n), s]),
    ("fetch_players", "get_players", lambda s, n: [s]),
    ("generate_timelines", "generate_timeline", lambda s, n: ["1", str(n), s]),
    ("compute_competition", "compute_competition", lambda s, n: ["1", str(n), s]),
    ("backfill_players", "get_players", lambda s, n: ["backfill", s]),
    ("build_league_db", "build_league_db", lambda s, n: [s]),
]


def count_games(season: str) -> int:
    game_dir = Path("data") / season / "boxscores"
    if not game_dir.exists():
        return 0
    return len(list(game_dir.glob("*.json")))


def run_step(name: str, script_key: str, args: list[str]) -> bool:
    script = SCRIPTS[script_key]
    cmd = [sys.executable, str(script)] + args
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  cmd: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    start = time.time()
    result = subprocess.run(cmd, timeout=7200)
    elapsed = time.time() - start
    mins, secs = divmod(int(elapsed), 60)
    if result.returncode != 0:
        print(f"\n  FAILED ({mins}m {secs}s)")
        return False
    print(f"\n  OK ({mins}m {secs}s)")
    return True


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    season = sys.argv[1]
    num_games = count_games(season)
    if num_games == 0:
        print(f"No boxscore files found in data/{season}/boxscores/")
        sys.exit(1)

    print(f"Season sync: {season} ({num_games} games)")
    print(f"Steps: {', '.join(s[0] for s in STEPS)}")
    overall_start = time.time()

    for name, script_key, args_fn in STEPS:
        args = args_fn(season, num_games)
        ok = run_step(name, script_key, args)
        if not ok:
            print(f"\nSync aborted at step: {name}")
            sys.exit(1)

    elapsed = time.time() - overall_start
    mins, secs = divmod(int(elapsed), 60)
    hrs, mins = divmod(mins, 60)
    print(f"\n{'='*60}")
    print(f"  Season {season} sync complete ({hrs}h {mins}m {secs}s)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
