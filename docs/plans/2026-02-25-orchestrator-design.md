# NHL Pipeline Orchestrator — Design Document

## Problem

The NHL data pipeline has three services — fetch, generate, build — all manually invoked via CLI. With the season starting back up, new game data arrives nightly. There is no automation, no validation, and no visibility into what's been processed. The 2024 season data also remains unbuilt because scripts are hardcoded to 2025.

## Solution

A Claude-powered orchestrator (Service 4) that manages the existing three services via tool-use architecture. The agent reasons about what needs doing, calls existing scripts as tools, validates results, and reports status. It runs autonomously on a daily schedule and accepts manual natural-language commands for ad-hoc work.

## Core Principles

- **Agent is an assistant, not an owner.** You stay in charge. The agent executes and reports; it doesn't make policy decisions.
- **Existing scripts stay unchanged.** Tools are thin wrappers. You can always bypass the agent and run scripts directly.
- **State reconciles against disk.** If you process games manually, the agent picks up your work on its next run without duplicating effort.
- **Completed seasons are frozen.** The agent only fetches for the active/current season. Past seasons are served from existing data.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Scheduler (launchd)                        │
│  Triggers daily run at configured time      │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Orchestrator Agent (Claude + tool use)     │
│  Reasons about what to do, calls tools,     │
│  validates results, generates reports       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Tool Layer (thin Python wrappers)          │
│  Each tool wraps an existing script with    │
│  structured input/output + error handling   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Existing Scripts (unchanged)               │
│  nhlgame.py, generate_timeline.py,          │
│  compute_competition.py, etc.               │
└─────────────────────────────────────────────┘
```

## Agent Tools

| Tool | Wraps | Purpose |
|---|---|---|
| `check_schedule` | NHL Schedule API | Get games played on a given date or date range |
| `check_data_status` | `gamecheck.py` logic | Report which games have complete raw data vs gaps |
| `fetch_games` | `nhlgame.py <start> <end>` | Full fetch: boxscores, plays, meta, and shifts |
| `fetch_shifts` | `nhlgame.py shifts <start> <end>` | Retry/backfill shifts only for games with missing shift data |
| `flatten_boxscores` | `tools/flatten_boxscore.py` | Flatten boxscore JSON to CSV |
| `flatten_plays` | `tools/flatten_plays.py` | Flatten play-by-play JSON to CSV |
| `fetch_players` | `v2/players/get_players.py` | Fetch/update player metadata |
| `generate_timelines` | `v2/timelines/generate_timeline.py` | Build second-by-second timelines |
| `compute_competition` | `v2/competition/compute_competition.py` | Calculate competition scores |
| `build_league_db` | `v2/browser/build_league_db.py` | Rebuild the browser SQLite DB |
| `validate_game` | New | Deep validation — parse JSON, check structure, cross-ref schedule |
| `notify` | `osascript` | Send macOS notification with summary |

Each tool returns structured output (success/failure, row counts, file paths, errors) so the agent can reason about what happened and decide what to do next.

## Daily Pipeline Flow

```
1. CHECK SCHEDULE
   Query NHL Schedule API for yesterday's date
   → "4 games were played last night"

2. FETCH RAW DATA
   Call fetch_games for the new game IDs
   → Downloads boxscores, plays, meta, shifts for each game

3. VALIDATE RAW DATA
   Call validate_game for each new game
   → Confirm all 5 files exist and JSON parses correctly
   → Verify shift data has expected structure
   → Cross-reference against schedule: "4 expected, 4 complete"
   → If shifts missing: call fetch_shifts to retry
   → If still missing after retries: log it, continue with what we have

4. GENERATE DERIVED DATA (in dependency order)
   a. flatten_boxscores (all games — produces master CSV)
   b. flatten_plays (new games)
   c. fetch_players (backfill any new player IDs seen in boxscores)
   d. generate_timelines (new games — requires shifts)
   e. compute_competition (new games — requires timelines)

5. BUILD DATABASE
   Call build_league_db to rebuild league.db from all generated data

6. REPORT
   Write detailed log to data/{season}/logs/YYYY-MM-DD.md
   Send macOS notification with summary
```

On failure at any step, the agent does not stop the whole pipeline. If one game's shifts fail, the other games still get processed through the full pipeline. The report calls out what succeeded and what needs attention.

## Manual Commands

Run the agent directly with a natural-language instruction:

```bash
python v2/orchestrator/runner.py                              # Daily scheduled mode
python v2/orchestrator/runner.py "Re-fetch game 734"          # Ad-hoc command
python v2/orchestrator/runner.py "Retry shifts for 700-710"   # Backfill shifts
python v2/orchestrator/runner.py "Process games from Jan 15-17"
python v2/orchestrator/runner.py "What games are missing data?"
python v2/orchestrator/runner.py "Rebuild the 2024 database"
```

You can also bypass the agent entirely and run scripts directly — same as today. The agent reconciles state against what's on disk on its next run.

## State Tracking

A single JSON file per season tracks pipeline progress:

```
data/{season}/pipeline_state.json
```

```json
{
  "season": "2025",
  "last_schedule_check": "2026-02-26T06:00:00",
  "games": {
    "2024020734": {
      "scheduled_date": "2026-01-15",
      "fetch": {"status": "complete", "timestamp": "2026-01-16T06:02:14"},
      "shifts": {"status": "complete", "timestamp": "2026-01-16T06:02:38"},
      "flatten_boxscore": {"status": "complete", "timestamp": "2026-01-16T06:03:01"},
      "flatten_plays": {"status": "complete", "timestamp": "2026-01-16T06:03:02"},
      "timeline": {"status": "complete", "timestamp": "2026-01-16T06:03:15"},
      "competition": {"status": "complete", "timestamp": "2026-01-16T06:03:28"}
    },
    "2024020735": {
      "scheduled_date": "2026-01-15",
      "fetch": {"status": "complete", "timestamp": "2026-01-16T06:02:45"},
      "shifts": {"status": "failed", "timestamp": "2026-01-16T06:02:52", "error": "Empty response after 5 retries"},
      "flatten_boxscore": {"status": "complete", "timestamp": "2026-01-16T06:03:01"},
      "timeline": {"status": "skipped", "reason": "shifts missing"}
    }
  }
}
```

Key behaviors:
- Each game tracks status per pipeline stage independently
- `"failed"` and `"skipped"` stages get retried on the next run
- The agent reconciles against disk on each run — it doesn't blindly trust the state file
- The DB rebuild step runs whenever any upstream data changed

## Notifications and Logging

**Detailed log** — one markdown file per run at `data/{season}/logs/YYYY-MM-DD.md`:

```markdown
# Pipeline Run — 2026-02-26 06:00

## Schedule Check
- Date: 2026-02-25
- Games found: 4 (734, 735, 736, 737)

## Fetch
- 734: ✓ boxscore, plays, meta, shifts (home + away)
- 735: ✓ boxscore, plays, meta | ⚠ shifts empty, retry 1/3...
- 735: ✓ shifts recovered on retry 2
- 736: ✓ all files
- 737: ✓ all files

## Validation
- All 4 games: JSON valid, structure correct
- Schedule cross-ref: 4 expected, 4 complete ✓

## Generation
- flatten_boxscores: ✓ (908 total games)
- flatten_plays: ✓ (4 new games)
- players: ✓ (2 new player IDs backfilled)
- timelines: ✓ (4 new games)
- competition: ✓ (4 new games)

## Database
- league.db rebuilt: 32,597 competition rows, 913 games ✓

## Summary
4/4 games processed successfully.
```

**macOS notification** — short summary after each run:

```
NHL Pipeline ✓ — 4 games processed (Feb 25), league.db updated
```

Or on partial failure:

```
NHL Pipeline ⚠ — 3/4 games (Feb 25), game 735 shifts missing
```

## Project Structure

```
v2/orchestrator/
├── agent.py              # Claude agent with tool definitions + system prompt
├── tools/
│   ├── schedule.py       # check_schedule (NHL Schedule API)
│   ├── fetch.py          # fetch_games, fetch_shifts
│   ├── generate.py       # flatten_boxscores, flatten_plays,
│   │                     #   fetch_players, generate_timelines,
│   │                     #   compute_competition
│   ├── build.py          # build_league_db
│   ├── validate.py       # validate_game, check_data_status
│   └── notify.py         # macOS notification
├── state.py              # Read/write pipeline_state.json
├── runner.py             # Entry point — scheduled or manual
├── config.py             # Season, paths, schedule time, API key ref
└── tests/
    ├── test_state.py
    ├── test_tools.py
    └── test_validate.py
```

**Scheduling:** A `launchd` plist at `~/Library/LaunchAgents/com.nhl.orchestrator.plist` triggers `runner.py` daily at a configured time (e.g. 10am, well after overnight games finish and data is posted).

## Season Support

The orchestrator is season-aware throughout. `config.py` defines the active season; all tool wrappers pass it to underlying scripts. This solves the 2024 blockers:

1. `build_league_db.py` gets parameterized to accept a season argument
2. `db.py` gets 2024 added to `_LEAGUE_DB_PATHS`
3. Generating 2024 data becomes a one-time manual command to the agent
4. The browser app's season selector gets wired up separately

The daily scheduled run only processes the active season. Completed seasons are frozen — no fetching, just served from existing data.

## Dependencies

**New:** `anthropic` (Claude Agent SDK)

**Existing:** `requests`, `beautifulsoup4`, `lxml`, `pandas`, `sqlite3` — already installed.

**API key:** Read from `ANTHROPIC_API_KEY` environment variable.

## Cost Estimate

Using Claude Haiku for the orchestrator agent:
- ~$0.01-0.02 per daily run (~10-15 tool calls per pipeline execution)
- ~$5-10 per full season (~300 game days)
- Manual commands similarly cheap — single conversation with a handful of tool calls
