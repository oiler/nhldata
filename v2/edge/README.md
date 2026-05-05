# v2/edge — NHL EDGE skater data

## Scripts

- `fetch_skater_detail.py` — fetch + cache the EDGE `skater-detail` payload for
  every skater in `league.db`. Writes to `data/2025/edge/skater_detail/{pid}.json`.
  Re-runs are resume-safe (existing files are skipped). Treats HTTP 404 as
  "no EDGE data" and writes a `{}` marker so the player isn't retried.
- `compute_burst_rates.py` — read the cached JSONs + `total_toi_seconds` from
  `competition` and emit `data/2025/generated/edge/player_bursts.csv` with
  per-player season-total `bursts_per_60` (all-strengths TOI denominator).

## Run

```bash
.venv/bin/python -m v2.edge.fetch_skater_detail
.venv/bin/python -m v2.edge.compute_burst_rates
```

## Tests

```bash
python -m pytest v2/edge/ -v
```

## Notes

- The EDGE `skater-detail` payload includes more than bursts: max speed, total
  distance, zone time (with an `Ev` even-strength variant for zone time only),
  shot speed/location, and shots-on-goal summary. The raw JSON is kept on disk
  so future analyzers can mine those fields without re-fetching.
- The NHL-provided `burstsOver20.percentile` ranks **raw counts**, not rates,
  so it conflates ice time with skating speed. Use `bursts_per_60` for
  rate-based comparisons.
- Burst counts are **not strength-sliced**. A player's burst rate reflects all
  game situations (5v5, PP, PK, OT). For our team-level analysis this is a
  caveat to document; per-player attribute comparisons are still meaningful.
