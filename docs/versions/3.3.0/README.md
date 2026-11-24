# v3.3.0: Move the daily pipeline to mininet

**Created:** 2026-11-23 11:02
**Last modified:** 2026-11-24 08:37

The current milestone in `ROADMAP.md`. The daily pipeline moves from the laptop's launchd job to mininet, an always-on Mac mini running Ubuntu. mininet becomes the machine that fetches from the NHL and builds each season's data, and the laptop keeps a read-only mirror for research and deploys. Nothing a user of the browser sees changes, and the pipeline's output must match the laptop's.

Rulings: Decision Queue D36 (move to an always-on Linux machine), D75 (mininet), D76 (who writes which data), D77 (systemd timer, pull before each run, `uv`), D78 (notifications wait in `BACKLOG.md`), D79 (deploys stay on the laptop), D80 (numpy stays on the 2.3 series), D81 (the run starts at 05:00 Eastern), and D82 (re-checking recent games for corrections is its own milestone, after this one).

**Status:** design accepted. Every decision it depends on is answered. No code has changed.

## What the release changes

Filled in as the work lands.

## Design

### What the machine check found

Read-only checks on mininet, 2026-11-22 and 2026-11-23:

- **Machine.** Macmini4,1 (mid-2010): Core 2 Duo P8600 with 2 cores, 1.7 GB of memory and 2 GB of swap, gigabit Ethernet. Ubuntu 24.04.5, Python 3.12.3, `git`, and `rsync` are installed. `uv` and Python's venv module aren't.
- **Always on.** Suspend is disabled. The time zone is `America/New_York`. Automatic updates install between 06:00 and 07:00, and the machine restarts at 04:00 when an update needs it. After a power cut it stays off until someone presses the button; oiler is putting it on a battery backup.
- **Network.** One schedule call, one HTML shift report, and one boxscore each returned in under 0.3 seconds. The Anthropic API and GitHub are reachable. The repository is public, so `git pull` needs no credentials.
- **Access.** Tailscale SSH, as user `jrf1039`, with a direct link to the laptop. Tailscale sometimes asks for a browser check before a connection. `sudo` needs a password, so oiler runs every `sudo` step.
- **The numpy limit.** numpy 2.4.2, the laptop's version, refuses to import: it needs SSE4.2 and POPCNT, which this CPU lacks. numpy 2.3.5 with pandas 3.0.0, `requests`, `beautifulsoup4`, `lxml`, and `anthropic` imports and runs (D80).
- **Speed.** mininet is 6 to 7 times slower than the laptop on a small benchmark. On the laptop the heaviest daily step, `build_league_db.py`, takes 41 seconds and peaks at 126 MB with 372 games; the other steps take under a second each. By that ratio the build takes 4 to 5 minutes on mininet now. That's an estimate until step 3 times it.
- **Disk.** The original 320 GB, 5400 rpm drive, with 272 GB free. It passed its SMART health check with no reallocated or pending sectors, but its load-cycle count is about six times the usual rating. oiler turned off the aggressive head parking that causes it. `BACKLOG.md`, "mininet follow-ups," holds the checks still to run.

### Who writes which data (D76)

Ownership follows the kind of work, not the season.

- **mininet is the ingest machine.** It's the only writer of every `data/<season>/` folder: everything fetched from the NHL, and the standard build on top of it (flattened plays, timelines, competition, `league.db`). That covers the daily run, and the jobs started by hand that write into a season folder: the Edge fetch, a season rebuild, a season backfill, and `edm.db`. Those run on mininet over SSH.
- **The laptop is the analysis machine.** It keeps a read-only mirror of the season folders, and it's the only writer of `data/generated/`, the cross-season research outputs such as `goalies.db`. It pushes `data/generated/` to mininet, so mininet holds every file a deploy needs.
- **The laptop never writes to its mirror.** Work on the laptop that needs to write season data points `NHL_DATA_DIR` at a scratch copy.
- **Every file exists on two machines.** mininet's disk is old, so mininet never holds the only copy of anything. If it's lost, the daily run's catch-up fetches the current season again from the NHL, and the laptop's mirror has the rest.

### Layout on mininet

Everything lives in the home folder of `jrf1039`, so setup needs `sudo` only once.

- `~/nhl/`: a clone of the repository, on `master`.
- `~/nhl-data/`: the data tree, outside the clone. `NHL_DATA_DIR` points here.
- `~/.config/nhl/pipeline.env`: the settings the job reads, with mode `600`. It holds `NHL_DATA_DIR`, `NHL_SEASON`, and `ANTHROPIC_API_KEY`. oiler creates the key and puts it in the file, so no session handles it. A separate key with a spend limit is best, because it can be revoked without touching the laptop's key.
- `~/.local/bin/uv`: `uv`, installed without `sudo`.

### Dependencies and Python (D80)

- `pyproject.toml` declares what the pipeline and research code import and don't list today: `pandas` and `numpy`. numpy is pinned `>=2.3,<2.4`, with a comment that names mininet's CPU as the reason. This closes the `BACKLOG.md` item "Declare the pipeline's dependencies in `pyproject.toml`."
- The service sets `UV_PYTHON=3.12`, so `uv` runs the pipeline on Python 3.12 there. CI and the Docker image already run 3.12, and mininet's system Python is 3.12. The laptop's daily run uses pyenv 3.11.6 until cutover, and that environment doesn't change. A `.python-version` file would have been simpler, but pyenv reads that file too, and it broke `python` in the laptop checkout, which has no pyenv 3.12.
- A `dev` dependency group adds `pytest`. The `uv` environment holds the pipeline's and research's packages, not the browser's, so under `uv` the tests to run are `pipeline` and `research`. The full suite still runs in the pyenv environment and in CI.
- `uv.lock` is refreshed, and mininet installs from it with `uv sync --frozen`, so it runs the same versions on every run.
- The browser image installs from `browser/requirements.txt` and isn't affected.

### Scheduler (D77, D81)

Two systemd user units, kept in the repository at `pipeline/orchestrator/systemd/` and linked into place with `systemctl --user link`. A link, not a copy, so the installed unit can't go stale the way the copied launchd plist could.

- `nhl-pipeline.service`, a one-shot service:
  - Reads `%h/.config/nhl/pipeline.env`, and works in `%h/nhl`. `%h` is the home folder, so the units name no user or absolute path.
  - Runs `git pull --ff-only` first. A failed pull doesn't stop the run: yesterday's code still fetches today's games.
  - Then `uv sync --frozen`. A failed sync stops the run, because the code and its packages may no longer match.
  - Then `uv run python pipeline/orchestrator/runner.py`.
  - A start timeout of three hours, so a hung run ends instead of blocking the next one.
- `nhl-pipeline.timer`:
  - `OnCalendar=*-*-* 05:00` (D81). The latest games end around 01:30 Eastern, the restart window is 04:00, and updates install from 06:00.
  - `Persistent=true`, so a run missed while the machine was off or restarting starts when it's back.
- The service waits up to five minutes for name lookups to work before it starts, because a run the timer missed starts as soon as the machine is back, which can be before the network is.
- `pipeline.env.example`, beside the units, shows the settings file's three lines.
- User units run without a login only when lingering is on. oiler runs `sudo loginctl enable-linger jrf1039` once.
- The run's output goes to the systemd journal (`journalctl --user -u nhl-pipeline`), and the run log goes to `~/nhl-data/<season>/logs/` as it does today.
- `pipeline/orchestrator/run.sh` and `com.nhl.orchestrator.plist` are deleted at cutover, not ported.

### The mirror

A new script, `pipeline/mirror-data.sh`, run on the laptop.

- **Pull.** `rsync` copies mininet's season folders into the laptop's `data/`. It doesn't delete: a file that exists only on the laptop stays, and the script lists such files so they can be looked at.
- **Push.** `rsync` copies the laptop's `data/generated/` to mininet.
- **Laptop-only files.** It lists files that exist only in the laptop's copy of a season folder mininet has, since those were written against the one-writer rule or predate the move.
- **Not during a run.** It first asks mininet whether `nhl-pipeline.service` is active, and stops if it is. `build_league_db.py` deletes `league.db` and rebuilds it, so a mirror taken mid-run could copy a partial database.
- **A stale mininet is visible.** It prints the date of mininet's newest run log, and warns when that isn't today. This is the only signal of a missed run until notifications are built (D78).
- It's started by hand, because Tailscale SSH can ask for a browser check.
- A deploy becomes: mirror, then `./browser/sync-runtime-data.sh`, then `fly deploy`, with oiler's approval as today.

### Notifications (D78)

Nothing changes in this release. The agent's `send_notification` tool calls `osascript`, which doesn't exist on Linux, and the tool already fails silently there. Run results are in the run log and the journal. `BACKLOG.md` gains an item for a notification the runner sends itself.

### Shadow runs and the parity check

mininet runs a different numpy and a different Python from the laptop's daily run, so the release proves the numbers match before it switches over.

- For two or three mornings both machines run: the laptop's launchd job at 08:00 on its own `data/`, and mininet's timer on `~/nhl-data/`, seeded from the laptop.
- After each pair of runs, compare the two 2026 `league.db` files table by table and row by row, and compare the new games' raw files, timelines, and competition files by checksum.
- Counts, IDs, and text must match exactly. Any difference in a decimal column is recorded with its size. A difference beyond floating-point rounding stops the cutover until it's explained.
- The comparison is a scratch script, not a permanent test.

### Order of work

Each step is one commit on `master` with the full test suite passing, and each leaves the laptop's 08:00 run working until cutover.

1. Declare `pandas` and `numpy` with the numpy pin, add the `dev` group, and refresh `uv.lock`. Run the `pipeline` and `research` tests under `uv` on the laptop with numpy 2.3.
2. Add the systemd units and `pipeline/mirror-data.sh`. Nothing on the laptop uses them yet.
3. Set up mininet:
   - Install `uv`, clone the repository, run `uv sync --frozen`, and run the `pipeline` and `research` tests there with `-m "not requires_data"`.
   - oiler creates `pipeline.env` with the key, and runs `sudo loginctl enable-linger jrf1039`.
   - Seed `~/nhl-data/` from the laptop with `rsync`: every season folder and `data/generated/`, about 20 GB. `data/v1-data/` and the archive file stay on the laptop.
   - Run those tests again with the data, then time one daily run by hand.
   - Link and enable the timer.
4. Shadow runs and the parity check, two or three mornings.
5. Cutover, in one sitting:
   - Run the mirror, so the laptop holds mininet's latest.
   - Unload the laptop's launchd job and remove the installed plist.
   - Delete `run.sh` and the plist from the repository, and update `AGENTS.md`, `README.md`, `docs/commands.md`, and `ROADMAP.md`.
   - oiler updates the local deploy runbook, `docs/fly-deploy-runbook.md`, with the mirror step.

To roll back before cutover, disable the timer on mininet; the laptop never stopped. To roll back after it, reinstall the plist from the commit before the cutover commit and disable the timer.

### What this release doesn't do

- No deploy from mininet (D79). The layout allows it later: mininet holds every file a deploy needs.
- No notifications (D78).
- No second run or correction detection. D82 makes that the next milestone in `ROADMAP.md`.
- No Edge refresh timer. The Edge fetch stays a job started by hand, now on mininet.
- No change to what the pipeline fetches or computes.

## Human test

Claude runs steps 1 to 5. oiler runs step 6.

1. On mininet, the `pipeline` and `research` tests pass with `-m "not requires_data"`, and pass in full once the data is seeded.
2. One daily run started by hand on mininet completes, and its run log lists the same steps as the laptop's. Record how long it took, and the time and peak memory of `build_league_db.py`.
3. `systemctl --user list-timers` shows the next run at the chosen time, and `loginctl show-user jrf1039 -p Linger` shows `yes`.
4. Each shadow morning, the parity check passes as the section "Shadow runs and the parity check" defines it.
5. After cutover, the mirror runs from the laptop, `./browser/sync-runtime-data.sh` ends with the same `Seasons in image` line as before, and `launchctl print gui/$(id -u)/com.nhl.orchestrator` reports that the job doesn't exist.
6. The morning after cutover, oiler runs the mirror and confirms the laptop has that day's games. oiler deploys when ready.

Record each result under "Results."

## Results

### Machine-led tests, step 1, 2026-11-23

- **Run by:** Claude, on the laptop.
- **Result:** Passed. Under `uv` (Python 3.12.10, numpy 2.3.5, pandas 3.0.0) the `pipeline` and `research` tests give 309 passed. The full suite in the pyenv environment still gives 440 passed.
- **Found:** A `.python-version` file set to 3.12 made pyenv's `python` fail in the checkout. The file was removed, and the service sets `UV_PYTHON` instead.
- **Changed:** The design's "Dependencies and Python" section and steps, to match.

### Machine-led tests, step 2, 2026-11-23

- **Run by:** Claude, on the laptop.
- **Result:** Passed, as far as the laptop can show. The mirror script's `rsync` options were tried on scratch folders: the pull skips `generated/`, copies new files, deletes nothing, and the laptop-only listing names the right file. The full suite gives 440 passed.
- **Found:** The laptop's `rsync` is openrsync, which prints each laptop-only file twice in a dry run. The script removes the duplicates.
- **Changed:** Nothing else. The units and the script's calls to mininet are first exercised in step 3.

### Machine-led tests, step 3, 2026-11-23

- **Run by:** Claude, with oiler adding the API key to `pipeline.env`.
- **Result:** Passed, except that lingering isn't on yet, so the timer doesn't fire without a login.
- **Found:**
  - Setup: `uv` 0.13.9 installed in the home folder, the repository cloned to `~/nhl`, and `uv sync --frozen` gave Python 3.12.3, numpy 2.3.5, and pandas 3.0.0.
  - Tests on mininet: the `pipeline` and `research` tests gave 305 passed with 4 deselected before the data arrived, and 309 passed with it.
  - Seed: the laptop's six season folders and `data/generated/` copied in 13 minutes, 21 GB. File counts match folder by folder.
  - Timing on mininet with 377 games: `build_league_db.py` took 210 seconds and peaked at 94 MB. A timeline, a competition file, and the boxscore flatten each took about a second.
  - Parity: the timeline, competition file, and flattened boxscores for game 2026020372 match the laptop's by checksum. Of `league.db`'s 10 tables, 9 match the laptop's 08:00 build row for row. `competition` differs in one value of 13,571 rows: `pct_vs_top_fwd` for one player in one game is 0.0333 on mininet and 0.0332 on the laptop.
  - The cause is the Python version, not mininet's CPU or numpy. The same build on the laptop under Python 3.12 matches mininet in all 10 tables. Python 3.12 made `sum()` on decimals more accurate, and `build_league_db.py` rounds an average of such a sum to four places, so a value on a rounding boundary can move by 0.0001. Decision Queue D83 asks whether to accept that.
  - The service, started by hand, pulled, synced, found nothing pending through 2026-11-22, called the agent with the new key, and finished in 27 seconds with `Result=success`.
  - The timer is linked and enabled; its next run is 2026-11-24 05:00.
  - `./pipeline/mirror-data.sh --dry-run` from the laptop read the service state and the newest run log, and listed its pull and push.
- **Changed:**
  - The mirror script skips `.DS_Store` files, which the dry run listed as laptop-only.
  - The hand run replaced mininet's copy of the 2026-11-23 run log, which the seed had brought from the laptop. The laptop's own log is unchanged.

### Shadow run 1, 2026-11-24

- **Run by:** Claude. oiler turned lingering on the day before.
- **Result:** Passed. mininet's output matches the laptop's.
- **Found:**
  - mininet's timer started the service at 05:00 with no one logged in. It pulled, fetched and processed the seven games of 2026-11-23 (2026020378 to 2026020384), rebuilt `league.db` with 384 games, and exited 0 at 05:39. About 30 of those minutes are the `fetch_players` timeout that `BACKLOG.md` already lists; `backfill_players` added the two new players.
  - The laptop's launchd run did the same games from 08:00.
  - Raw files for the seven games: all 21 boxscore, play-by-play, and meta files match by checksum. The 14 shift files match in content and differ only in `fetchedAt`, the time each machine fetched them.
  - Derived files: all 29 match by checksum (the seven games' timelines in CSV and JSON, competition files, and flattened plays, plus the flattened boxscores).
  - `league.db`: all 10 tables match the laptop's real build on Python 3.11 row for row, and match a laptop build on Python 3.12. The one-value difference of 2026-11-23 didn't recur: that value depends on the day's elite set, and today it isn't on a rounding boundary. D83 still decides how to treat such a difference when one appears.
- **Changed:** Nothing.

## Close-out

- [ ] Every file in this folder listed under "This folder", and the human test recorded under "Results"
- [ ] The version added to `CHANGELOG.md`
- [ ] The milestone's row and log entry added to `docs/history.md`
- [ ] The milestone removed from `ROADMAP.md`, so the next milestone is first in its list
- [ ] The release commit tagged, with a GitHub Release: the commit that adds the version to `CHANGELOG.md`
