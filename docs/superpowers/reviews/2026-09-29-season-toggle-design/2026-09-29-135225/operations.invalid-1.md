---
lens: operations
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/specs/2026-09-29-season-toggle-design.md
---

# operations review

## Verdict

not ready

## Findings

### F-1 [blocker] Rollover is "one file" in Goal but three-plus files in the Rollover section

- Where: Goal, success criterion at line 28; "Rollover next season", lines 117–121; "Deploy guard", lines 95–96
- Evidence: Line 28: "Next season's rollover is a change to one file, `v2/browser/seasons.py`." Lines 119–121 list three steps across `seasons.py`, `tools/sync-runtime-data.sh`, and the Dockerfile. A fourth file is also needed and isn't named: `.gitignore:11-12` ignores only `v2/browser/runtime_data/2024/` and `v2/browser/runtime_data/2025/`, so after the first sync `runtime_data/2026/league.db` (about 8 MB by season end, going by `runtime_data/2025/league.db`) and `player_bursts.csv` show up as untracked files that oiler could commit by accident. `git ls-files v2/browser/runtime_data` shows only `.gitkeep` and `goalies.db` are tracked.
- Problem: The success criterion contradicts the design, so an implementer can't satisfy both. The per-season guard file lists are kept by hand in three places (SEASONS, the sync script, the Dockerfile), which invites drift at every rollover.
- Fix: Pick one of these and make lines 28 and 117–121 agree. (a) Make the guards derive from `seasons.py`: the Dockerfile runtime stage has Python and the app directory (`COPY v2/browser/ /app/`, and `.dockerignore` doesn't exclude `seasons.py`), so the guard can be `RUN python -c "from seasons import SEASONS; ..."` looping over `runtime_data/<s>/league.db` and `runtime_data/<s>/player_bursts.csv`. The sync script can read the list with `python3 -c "import sys; sys.path.insert(0,'v2/browser'); from seasons import SEASONS; print(' '.join(SEASONS))"` and loop over it for `mkdir`, `cp`, the non-empty check, and `verify_runtime_data.py`. Change `.gitignore` to `v2/browser/runtime_data/*/` so no per-season entry is needed. Then rollover really is one file. (b) Or keep the hand-maintained lists, delete the "one file" criterion, and add "add `v2/browser/runtime_data/<year>/` to `.gitignore`" as a rollover step (and add 2026 now).

### F-2 [major] The deploy guard blocks every deploy until 2026 data exists, then again whenever Edge coverage decays

- Where: "Deploy guard", lines 93–98
- Evidence: `tools/sync-runtime-data.sh:11` is `set -euo pipefail`, so adding a `cp` of `data/2026/generated/browser/league.db` fails the whole sync while that file is missing. `ls data/2026/generated` prints only `players`, so no 2026 `league.db` exists today; the first daily build is 2026-09-30. The Edge fetch needs that DB first: `v2/edge/fetch_skater_detail.py:34` reads `data/{_YEAR}/generated/browser/league.db`, and `:91` raises `SystemExit` if it's missing. BACKLOG.md says the Edge refresh is manual. `verify_runtime_data.py:19` sets `DEFAULT_MIN_OVERLAP = 0.80` against `SELECT DISTINCT playerId FROM competition WHERE position IN ('F','D')` (lines 47–49), so a burst CSV built on day N falls below 80% as new skaters debut. In October that happens fast: after one night of games, only the teams that played have skaters.
- Problem: Once the guard lands, no deploy can happen at all (not even the season-toggle code itself, or a security fix to a 2025 page) until the next daily run and a manual Edge run are done. After that, in October, most deploys need a fresh Edge run of about 800 requests first. The spec calls this a signal (line 98), but it works as a hard block, and the spec never states the window. I couldn't verify whether NHL Edge returns rows for players with only 1–2 GP. If it doesn't, the early-season CSV may never reach 80%, and the block lasts longer.
- Fix: State the no-deploy window explicitly in the Deploy guard section, and choose one: (a) for the in-progress season, pass a lower threshold through the CLI argument that already exists (`verify_runtime_data.py:66`, `min_overlap = float(argv[2])`), for example `0.5`, keeping 0.80 for completed seasons; (b) land the guard change and the `SEASONS` change together in one commit that isn't deployed until 2026 data exists, and say so; or (c) keep 2026 out of the deployed `SEASONS` until the freshness backlog item lands. Also name the escape hatch for an urgent deploy during the block (see F-6).

### F-3 [major] No guard catches a runtime `league.db` built without `birthDate`

- Where: "Age from player data", line 75 ("The skaters page doesn't guard against a missing column"); "Deploy guard"
- Evidence: The orchestrator now builds only 2026: the working-tree diff of `v2/orchestrator/config.py` sets `SEASON = os.environ.get("NHL_SEASON", "2026")`, and the plist sets `NHL_SEASON` to `2026`. So `data/2025/generated/browser/league.db` is rebuilt only when someone runs `build_league_db.py 2025` by hand. `sync-runtime-data.sh:20` copies whatever is there. `v2/browser/healthz.py` "Returns 200 unconditionally". The sync script already has a schema-level check of this kind for `goalies.db` (lines 34–44).
- Problem: A deploy after the code change, done without the 2025 rebuild (from another checkout, or with the rebuild skipped), ships a skaters page whose `_COMP_SQL` selects `p.birthDate` against a table that lacks it. Every `/skaters` request then fails, `/healthz` stays green, and nothing reports it. The spec treats "a build that hasn't been rerun" as out of scope, but the deploy path is exactly where that mistake shows up.
- Fix: Add to the Deploy guard section: "For each season in `SEASONS`, `sync-runtime-data.sh` asserts that `runtime_data/<s>/league.db` has a `players.birthDate` column and that the column is non-null for at least 95% of the `competition` skaters (use an inline `python3` heredoc like the goalies.db check)." Add a matching red/green verification: run the sync against a 2025 DB built before the change, and it must fail.

### F-4 [major] The lazy burst load removes the boot-time failure that the 2026-07-29 incident fix relies on

- Where: "Edge bursts per season", lines 80–82
- Evidence: `v2/browser/burst_data.py:4-9`: "Failing loudly there turns a silent 'blank columns' regression into a boot failure that Fly's deploy health check catches before the bad image takes traffic." `docs/fly-deploy-runbook.md:39` and `:50` record the incident: `skaters.py:35` raised at import and gunicorn failed to boot. The spec moves the raise to "the first request for the season" (line 82). `healthz.py` doesn't touch data. `functools.lru_cache` doesn't cache exceptions, so every request re-raises.
- Problem: With the change, an image that is missing a season's CSV boots, passes `/healthz`, takes traffic, and returns errors only on `/skaters` for that season. Only the gunicorn error log shows them. The spec's safeguard ("The sync guard ... keeps production from reaching it") covers only deploys that go through the sync script from this checkout. The Dockerfile guard helps only if it's kept in step with `SEASONS` (F-1). The docstring in `burst_data.py` would then describe behavior that no longer exists.
- Fix: Add to the Edge bursts section: "In runtime mode (`is_runtime_mode()`), `skaters.py` calls `_bursts_for(s)` for every `s` in `SEASONS` at import. This keeps the boot-time failure and fills the cache; local dev stays lazy." If the design instead accepts the new failure mode on purpose, say so and list the doc updates: the `burst_data.py` module docstring, and the runbook Gotchas line 39 ("`pages/skaters.py` loads the burst CSV at import").

### F-5 [minor] The guard verification passes for the wrong reason and never runs the Dockerfile guard

- Where: Testing, line 113
- Evidence: "run `./tools/sync-runtime-data.sh` ... once with the 2026 burst CSV missing. The second run must exit non-zero." Under `set -euo pipefail` (line 11), a missing source file makes `cp` fail first. The run exits non-zero before the non-empty loop or `verify_runtime_data.py` ever sees 2026. No step builds the image, so the Dockerfile `RUN` guard (the part the spec edits at line 96) goes untested. The "with the 2026 files present" run also can't happen before a 2026 `league.db` and a manual Edge run exist (F-2), so the implementation can't finish today.
- Fix: Replace line 113's verification with: (1) a run with a 2026 burst CSV that has only a header row, which must fail at the non-empty check or at `verify_runtime_data.py`; (2) a run with a CSV covering under 80% of 2026 skaters, which must fail with the coverage message; (3) `docker build .` (or `fly deploy --build-only`) with `v2/browser/runtime_data/2026/` absent, which must fail at the guard with "runtime data missing or empty: runtime_data/2026/...". Do these against copies in a temp directory, or restore the real files after each run. Say that the "files present" run is gated on the first 2026 build and an Edge run.

### F-6 [minor] No rollback section, and the one irreversible step isn't named

- Where: The document has no rollback section; "Age from player data", line 75
- Evidence: `docs/fly-deploy-runbook.md:43-46` documents the rollback: `fly releases -a nhl-browser`, then `fly deploy --image registry.fly.io/nhl-browser:deployment-<id>`. That path reuses a built image, so it skips the Dockerfile guard. It's the only way to ship anything during the F-2 block. The spec's `python v2/browser/build_league_db.py 2025` overwrites `data/2025/generated/browser/league.db` in place. If generated inputs have drifted since the last build (for example, the post-game play-by-play corrections noted in project memory), the previous 2025 DB is gone.
- Fix: Add a short Rollback section. Code: redeploy the prior image with `fly deploy --image ...`; this needs no data work, because each image carries its own `runtime_data`. Data: before rebuilding, `cp data/2025/generated/browser/league.db data/2025/generated/browser/league.db.pre-birthdate`, then compare row counts of `competition`, `games`, and `player_metrics` against the backup after the rebuild. Also note that the new DB stays compatible with a code rollback, because old code ignores the extra `birthDate` column and still reads `birth_date` from the burst CSV.

### F-7 [minor] `birthDate` comes from the players CSV, not "each player JSON"

- Where: "Age from player data", line 73
- Evidence: `v2/browser/build_league_db.py:64-76`: `build_players_table()` reads `PLAYERS_CSV` (`data/<season>/generated/players/csv/players.csv`, line 43) through a `keep` list. `head -1 data/2025/generated/players/csv/players.csv` shows `birthDate` as column 10. JSON is read only by `_recover_missing_players()` (lines 79–115), which builds its own dict without `birthDate`.
- Problem: If someone implements line 73 as written, the main path is never touched, and the rebuilt DB still has no `birthDate` for most players. The F-3 guard would then fail every deploy. If only `keep` is changed, the recovered rows have null `birthDate`.
- Fix: Replace line 73 with: "`build_players_table()` adds `birthDate` to its `keep` list (the players CSV already carries it), and `_recover_missing_players()` adds `"birthDate": d.get("birthDate")` to each recovered row."

### F-8 [minor] Whether this ships to production is ambiguous, and a deployed 2026-27 would be a silent snapshot

- Where: Goal, line 19 ("In local dev ..."); Non-goals, line 32; "Deploy guard", line 93
- Evidence: The Goal scopes success to local dev. The Deploy guard section says "the code in this design can still be deployed". BACKLOG.md "Keep the deployed browser current" option 2 proposes an "as of" date in the header because none exists today.
- Problem: If this deploys, `app.nhldata.org` offers a 2026-27 option frozen at the deploy date, with nothing on the page saying when. Visitors can't tell stale in-season numbers from current ones. The spec never decides whether deploying before the freshness item is intended.
- Fix: Add one line under Non-goals or Deploy guard: either "Not deployed until the freshness backlog item lands", or "May be deployed; the 2026-27 data is a snapshot as of the deploy date", and in the second case decide whether a minimal "data through <max gameDate>" label ships with it.

### F-9 [nit] Deploy docs and comments that name 2024/2025 explicitly aren't in scope

- Where: "Deploy guard"; "Rollover next season"
- Evidence: `README.md` "Refresh production data" builds only 2024 and 2025. `docs/fly-deploy-runbook.md:20` checks only `runtime_data/2025/`. The Dockerfile comment at lines 37–41 and `.github/workflows/fly-deploy.yml:3` say "runtime_data/2024/ and /2025/ are gitignored". The `sync-runtime-data.sh` header (line 6) lists only `build_league_db.py 2025`, and line 17 (`mkdir -p`) and line 52 (`ls -lh`) name only 2024/2025. `build_league_db.py:39` defaults to `"2025"` and isn't in the spec's list of `"2025"` defaults (line 62). The orchestrator passes the season explicitly, so that last one is cosmetic.
- Fix: Add a bullet to the Deploy guard section listing these edits (README refresh steps gain `build_league_db.py 2026`; runbook pre-flight checks each season directory; comments say "per-season directories"), and add "update deploy docs" to the rollover steps unless F-1 option (a) makes them season-agnostic.

### F-10 [nit] Whether `BURST_COLUMNS` keeps `birth_date` is unstated

- Where: "Age from player data", line 74; "Edge bursts per season"
- Evidence: `burst_data.py:21` `BURST_COLUMNS = [..., "birth_date"]`, and `:33` selects `pd.read_csv(path)[BURST_COLUMNS]`, which raises `KeyError` if a CSV lacks the column.
- Problem: After the change, nothing in the skaters page reads `birth_date`, but the loader still requires it. A future Edge output without that column would fail the load, and in production that is a `RuntimeError`-class outage on `/skaters` for no functional reason.
- Fix: State one of these: "`BURST_COLUMNS` drops `birth_date`" (check that `player.py`'s `_load_bursts` doesn't need it), or "`BURST_COLUMNS` is unchanged; the CSV contract still includes `birth_date`."

### F-11 [nit] The per-season burst test needs cache isolation to stay order-independent in CI

- Where: Testing table, row 6
- Evidence: A module-level `functools.lru_cache` keeps results for the life of the pytest process. CI runs the whole suite in one process (`.github/workflows/tests.yml:39`). `test_smoke.py:23-36` imports `app`, which imports `pages/skaters.py`.
- Problem: If a smoke test or another test calls `_bursts_for("2026")` first, the cache holds an empty frame, and a later "loads each season's own CSV" test can pass or fail depending on test order.
- Fix: Add to the test row: "monkeypatch `skaters.load_bursts` and call `_bursts_for.cache_clear()` before and after."

## Checked and sound

- The daily orchestrator rebuilds `league.db` for the active season: `v2/orchestrator/sync_season.py` STEPS end in `build_league_db`, `agent.py:34`/`:164` include it, and the working-tree config and plist set 2026. Line 75's "The daily orchestrator run keeps the 2026 database current" holds.
- `data/2025/generated/players/csv/players.csv` carries `birthDate`, and the 2025 player JSONs carry `"birthDate"` (for example `data/2025/players/8470613.json:33`). `data/2026/generated/players/csv/players.csv` exists and `data/2026/players/` has 778 JSONs, so a 2026 build can populate the column.
- `seasons.py` doesn't collide with any other module on the path (`find` found no other `seasons.py`, and nothing imports `seasons` today). It ships in the image, because `.dockerignore` excludes only the build scripts, not new app modules.
- CI can't deploy: `.github/workflows/fly-deploy.yml` is `workflow_dispatch`-only, and `tests.yml` runs `pytest -m "not requires_data"` on pushes and PRs. The synthetic-data tests the spec proposes fit that gate. Because deploys are local-only, the sync script and Dockerfile guard are the whole deploy gate, which is why F-1 through F-5 matter.
- `fly deploy --remote-only` tars the working tree minus `.dockerignore` (runbook line 27), and `.dockerignore` doesn't exclude `runtime_data/`, so gitignored per-season data reaches the build context. Adding `runtime_data/2026/` needs no `.dockerignore` change.
- `runtime_paths.player_bursts_csv()` and `league_db()` are already per-season in both modes, so no path code changes are needed for 2026.
- `load_bursts()` keeps the production raise, and `lru_cache` doesn't cache exceptions, so a missing CSV in production can't be masked by a cached empty frame (the production concern is visibility, F-4, not masking).
- The memory footprint is fine: two per-season burst frames (the 2025 CSV is 80 KB) cached in each of 2 gunicorn workers fit the 512 MB `shared-cpu-1x` VM in `fly.toml`. The image grows by one season's `league.db`.
- Moving `store-season` to `storage_type="session"` is safe to roll back: the older code uses `memory` storage and ignores session values. Each image carries its own data, so image rollback needs no data work.
- The `season_date_range()` fallback change affects local dev only in practice: in production, the guard ensures each `SEASONS` entry has a `league.db`.
- `edm.db` staying out of scope is safe for operations: `db.query()` has no callers, and the sync script keeps copying only the 2025 `edm.db`.
