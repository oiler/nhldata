"""Fetch and cache NHL EDGE skater-detail JSON for every active skater.

Reads player IDs from data/<season>/generated/browser/league.db (competition table).
Writes one JSON per player to data/<season>/edge/skater_detail/{playerId}.json.

Season is the 4-digit start year from NHL_SEASON (default 2025).
Re-runs are safe: existing files are skipped (resume-on-rerun).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from v2.edge.compute_burst_rates import edge_season, list_skater_ids, season_year

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
SEASON      = edge_season()
GAME_TYPE   = 2
SLEEP_SEC   = 0.3       # ~3.3 req/s — empirically clean
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 5
HTTP_TIMEOUT_SEC  = 15

_YEAR      = season_year()
DB_PATH    = Path(f"data/{_YEAR}/generated/browser/league.db")
OUTPUT_DIR = Path(f"data/{_YEAR}/edge/skater_detail")


def build_url(player_id: int, season: str = SEASON, game_type: int = GAME_TYPE) -> str:
    return (
        f"https://api-web.nhle.com/v1/edge/skater-detail/"
        f"{player_id}/{season}/{game_type}"
    )


def target_path(output_dir: Path, player_id: int) -> Path:
    return output_dir / f"{player_id}.json"


def already_fetched(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


class FetchError(Exception):
    """Raised when a player can't be fetched after all retries."""


def fetch_one(player_id: int) -> dict | None:
    """Fetch one player's EDGE payload. Returns None on 404 (no EDGE data).

    Retries transient errors (5xx, timeouts) up to MAX_RETRIES with linear backoff.
    Raises FetchError on persistent failure.
    """
    url = build_url(player_id)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # no EDGE data for this player — expected for some
            if 500 <= e.code < 600 and attempt < MAX_RETRIES:
                last_err = e
                time.sleep(RETRY_BACKOFF_SEC * attempt)
                continue
            raise FetchError(f"HTTP {e.code} for player {player_id}: {e}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                last_err = e
                time.sleep(RETRY_BACKOFF_SEC * attempt)
                continue
            raise FetchError(f"network error for player {player_id}: {e}") from e

    raise FetchError(f"exhausted retries for player {player_id}: {last_err}")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"league.db not found at {DB_PATH}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    player_ids = list_skater_ids(DB_PATH)
    print(f"Found {len(player_ids)} skaters in league.db. "
          f"Output dir: {OUTPUT_DIR}")

    n_skipped = n_fetched = n_no_data = n_errors = 0

    for i, pid in enumerate(player_ids, start=1):
        path = target_path(OUTPUT_DIR, pid)
        if already_fetched(path):
            n_skipped += 1
            continue

        try:
            payload = fetch_one(pid)
        except FetchError as e:
            n_errors += 1
            print(f"  [{i}/{len(player_ids)}] {pid}: ERROR — {e}",
                  file=sys.stderr)
            time.sleep(SLEEP_SEC)
            continue

        if payload is None:
            # 404 — write an empty marker so we don't re-fetch on next run
            path.write_text("{}")
            n_no_data += 1
        else:
            path.write_text(json.dumps(payload))
            n_fetched += 1

        if i % 50 == 0 or i == len(player_ids):
            print(f"  [{i}/{len(player_ids)}] "
                  f"fetched={n_fetched} skipped={n_skipped} "
                  f"no_data={n_no_data} errors={n_errors}")

        time.sleep(SLEEP_SEC)

    print(
        f"\nDone. fetched={n_fetched} skipped={n_skipped} "
        f"no_data={n_no_data} errors={n_errors}"
    )


if __name__ == "__main__":
    main()
