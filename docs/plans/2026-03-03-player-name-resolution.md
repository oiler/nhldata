# Player Name Resolution: How It Works and How It Breaks

## The Pipeline

Player names appear in the browser via a chain of 4 steps:

```
1. get_players.py          Fetches raw JSON from NHL API per player
                           Saves to data/2025/players/{playerId}.json
                           Generates data/2025/generated/players/csv/players.csv

2. compute_competition.py  Processes play-by-play data per game
                           Outputs data/2025/generated/competition/{gameId}.csv
                           Uses player IDs from plays JSON (no name dependency)

3. build_league_db.py      Reads players.csv → `players` table
                           Reads competition CSVs → `competition` table
                           Players missing from players.csv have no name row

4. Browser SQL             LEFT JOIN competition → players
                           COALESCE(name, 'Player ' || playerId)
                           Missing players show as "Player XXXXXXX"
```

## Why Names Go Missing

`get_players.py` (step 1) fetches rosters for all 32 teams from the NHL API. Any player **not on a roster at fetch time** gets no raw JSON file. Common reasons:

- Mid-season call-ups from AHL
- Recent trades (player not yet on new team's API roster)
- Emergency recalls
- Players who appear in play-by-play before roster API updates

`compute_competition.py` (step 2) pulls player IDs directly from play-by-play JSON, which always includes the actual game participants. So competition data can reference players that step 1 never fetched.

## The Gap

Steps 1 and 2 are independent. Step 1 runs once (or periodically), while step 2 runs after every game. New players appear in competition data with no corresponding entry in players.csv.

## The Fix: Backfill Mode

```bash
python v2/players/get_players.py backfill 2025
```

This command:
1. Scans all competition CSVs for unique player IDs
2. Checks which IDs have no raw JSON file in `data/2025/players/`
3. Fetches those players from the NHL API
4. Merges new players into the existing `players.csv` (fixed 2026-03-02 — previously overwrote the file)

After backfill, rebuild the database:
```bash
python v2/browser/build_league_db.py
```

## Automating It

The backfill is not yet part of the orchestrator pipeline. Currently it must be run manually. To fully automate, `build_league_db.py` (or the orchestrator) should run the backfill check before building the database — detect any player IDs in competition data missing from players.csv and fetch them.

## Incident Log

| Date | Players | Team | Resolution |
|------|---------|------|------------|
| 2026-03-02 | 8 players (incl. Avery Hayes) | PIT, VGK, NSH, others | Manual backfill + rebuild |
| 2026-03-03 | Angus Booth, Kenny Connors, Jared Wright | LAK | Needs backfill + rebuild |
