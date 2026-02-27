# v2/orchestrator/agent.py
"""Claude-powered pipeline orchestrator agent."""

import json
from anthropic import Anthropic

from v2.orchestrator.tools.schedule import check_schedule
from v2.orchestrator.tools.validate import validate_game
from v2.orchestrator.tools.fetch import fetch_games, fetch_shifts
from v2.orchestrator.tools.generate import (
    flatten_boxscores, flatten_plays, fetch_players,
    generate_timelines, compute_competition,
)
from v2.orchestrator.tools.build import build_league_db
from v2.orchestrator.tools.notify import send_notification

SYSTEM_PROMPT = """\
You are the NHL data pipeline orchestrator. You manage three services:
1. FETCH — download raw game data from the NHL API (boxscores, plays, meta, shifts)
2. GENERATE — process raw data into derived outputs (timelines, competition scores, etc.)
3. BUILD — rebuild the SQLite database that powers the web browser app

PIPELINE ORDER (dependencies):
1. check_schedule → learn which games were played
2. fetch_games → download raw data for those games
3. validate_game → confirm files exist, JSON is valid
4. If shifts missing → fetch_shifts to retry, then validate again
5. flatten_boxscores → flatten all boxscores to master CSV (run for full season)
6. flatten_plays → flatten play-by-play for new games
7. fetch_players → update player metadata (catches new player IDs)
8. generate_timelines → build second-by-second timelines (requires shifts)
9. compute_competition → calculate competition scores (requires timelines)
10. build_league_db → rebuild league.db from all generated data
11. notify → send summary notification

RULES:
- If a game's shifts fail after retries, skip its timeline and competition but process other games.
- Always validate after fetching. Always rebuild the DB after any generation step succeeds.
- Game IDs are full NHL IDs like 2025020734. Game numbers are 1-1312 (the last 4 digits).
- To convert a game ID to a game number: int(game_id[-4:]).
- The season is provided in each tool call. Use it consistently.
- Report clearly what succeeded and what failed.
- You are an assistant, not an owner. Execute the requested work and report results.
"""

TOOLS = [
    {
        "name": "check_schedule",
        "description": "Query the NHL schedule API for games played on a given date. Returns game IDs and count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
            },
            "required": ["date"]
        }
    },
    {
        "name": "validate_game",
        "description": "Validate that all raw data files exist and parse as valid JSON for a game. Returns status (complete/incomplete/invalid), missing files, and errors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "game_id": {"type": "string", "description": "Full NHL game ID (e.g. 2025020734)"},
                "season": {"type": "string", "description": "Season year (e.g. 2025)"}
            },
            "required": ["game_id"]
        }
    },
    {
        "name": "fetch_games",
        "description": "Download all raw data (boxscores, plays, meta, shifts) for a range of game numbers. Rate-limited; may take several minutes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer", "description": "Start game number (1-1312)"},
                "end": {"type": "integer", "description": "End game number (1-1312)"},
                "season": {"type": "string"}
            },
            "required": ["start", "end"]
        }
    },
    {
        "name": "fetch_shifts",
        "description": "Retry/backfill shift data only for a range of game numbers. Use when shifts were empty on initial fetch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "season": {"type": "string"}
            },
            "required": ["start", "end"]
        }
    },
    {
        "name": "flatten_boxscores",
        "description": "Flatten all boxscore JSONs into a master CSV. Run for the full season (not per-game).",
        "input_schema": {
            "type": "object",
            "properties": {"season": {"type": "string"}},
            "required": ["season"]
        }
    },
    {
        "name": "flatten_plays",
        "description": "Flatten play-by-play JSONs for a range of game numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "season": {"type": "string"}
            },
            "required": ["start", "end", "season"]
        }
    },
    {
        "name": "fetch_players",
        "description": "Fetch/update all player metadata for the season.",
        "input_schema": {
            "type": "object",
            "properties": {"season": {"type": "string"}},
            "required": ["season"]
        }
    },
    {
        "name": "generate_timelines",
        "description": "Generate second-by-second timelines for a range of game numbers. Requires shifts data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "season": {"type": "string"}
            },
            "required": ["start", "end", "season"]
        }
    },
    {
        "name": "compute_competition",
        "description": "Compute competition scores for a range of game numbers. Requires timelines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "season": {"type": "string"}
            },
            "required": ["start", "end", "season"]
        }
    },
    {
        "name": "build_league_db",
        "description": "Rebuild the league SQLite database from all generated data.",
        "input_schema": {
            "type": "object",
            "properties": {"season": {"type": "string"}},
            "required": ["season"]
        }
    },
    {
        "name": "send_notification",
        "description": "Send a macOS desktop notification with a title and message.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["title", "message"]
        }
    },
]

# Map tool names to handler functions
TOOL_HANDLERS = {
    "check_schedule": lambda args: check_schedule(args["date"]),
    "validate_game": lambda args: validate_game(
        args["game_id"], season=args.get("season")),
    "fetch_games": lambda args: fetch_games(
        args["start"], args["end"], season=args.get("season", "2025")),
    "fetch_shifts": lambda args: fetch_shifts(
        args["start"], args["end"], season=args.get("season", "2025")),
    "flatten_boxscores": lambda args: flatten_boxscores(
        season=args["season"]),
    "flatten_plays": lambda args: flatten_plays(
        args["start"], args["end"], season=args["season"]),
    "fetch_players": lambda args: fetch_players(season=args["season"]),
    "generate_timelines": lambda args: generate_timelines(
        args["start"], args["end"], season=args["season"]),
    "compute_competition": lambda args: compute_competition(
        args["start"], args["end"], season=args["season"]),
    "build_league_db": lambda args: build_league_db(
        season=args["season"]),
    "send_notification": lambda args: send_notification(
        args["title"], args["message"]),
}


def run_agent(user_message: str, season: str = "2025",
              model: str = "claude-haiku-4-5-20251001") -> str:
    """Run the orchestrator agent with the given instruction.

    Returns the agent's final text response.
    """
    client = Anthropic()
    messages = [{"role": "user", "content": user_message}]
    system = SYSTEM_PROMPT + f"\n\nCurrent season: {season}"

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # Collect text and tool-use blocks
        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        if response.stop_reason == "end_turn" or not tool_calls:
            return "\n".join(text_parts)

        # Execute tool calls and build tool_result messages
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tc in tool_calls:
            handler = TOOL_HANDLERS.get(tc.name)
            if handler:
                try:
                    result = handler(tc.input)
                except Exception as e:
                    result = {"status": "error", "error": str(e)}
            else:
                result = {"status": "error", "error": f"Unknown tool: {tc.name}"}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})
