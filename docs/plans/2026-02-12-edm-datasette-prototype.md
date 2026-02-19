# EDM Datasette Prototype Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a SQLite database with all Oilers 2025 game data and browse it with Datasette to discover what views and aggregations matter for the final static site.

**Architecture:** Single Python script reads existing CSV/JSON data files, filters to EDM's 58 games, and loads 6 tables into a SQLite database. Datasette provides instant web browsing.

**Tech Stack:** Python 3, sqlite3 (stdlib), pandas, datasette

---

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `v2/browser/build_edm_db.py`
- Create: `v2/browser/requirements.txt`

**Step 1: Create directory and requirements file**

Create `v2/browser/requirements.txt`:
```
pandas
datasette
```

**Step 2: Create build script skeleton**

Create `v2/browser/build_edm_db.py`:
```python
"""
Build a SQLite database of Edmonton Oilers 2025 season data for Datasette browsing.

Usage:
    python v2/browser/build_edm_db.py

Output:
    data/2025/generated/browser/edm.db
"""

import json
import os
import sqlite3
import pandas as pd

TEAM_ABBREV = "EDM"
SEASON_DIR = "data/2025"
OUTPUT_DB = os.path.join(SEASON_DIR, "generated", "browser", "edm.db")

# Source paths
FLAT_BOXSCORES = os.path.join(SEASON_DIR, "generated", "flatboxscores", "boxscores.csv")
PLAYERS_CSV = os.path.join(SEASON_DIR, "generated", "players", "csv", "players.csv")
BOXSCORES_DIR = os.path.join(SEASON_DIR, "boxscores")
FLATPLAYS_DIR = os.path.join(SEASON_DIR, "generated", "flatplays")
SHIFTS_DIR = os.path.join(SEASON_DIR, "shifts")
TIMELINES_DIR = os.path.join(SEASON_DIR, "generated", "timelines", "csv")


def main():
    os.makedirs(os.path.dirname(OUTPUT_DB), exist_ok=True)

    # Remove existing db to rebuild from scratch
    if os.path.exists(OUTPUT_DB):
        os.remove(OUTPUT_DB)

    conn = sqlite3.connect(OUTPUT_DB)

    edm_game_ids = build_games_table(conn)
    build_players_table(conn)
    build_player_game_stats_table(conn, edm_game_ids)
    build_plays_table(conn, edm_game_ids)
    build_shifts_table(conn, edm_game_ids)
    build_timelines_table(conn, edm_game_ids)

    conn.close()
    print(f"\nDone. Database written to {OUTPUT_DB}")
    print(f"Run: datasette {OUTPUT_DB}")


if __name__ == "__main__":
    main()
```

**Step 3: Verify skeleton runs**

Run: `cd /Users/jrf1039/files/projects/nhl && python v2/browser/build_edm_db.py`
Expected: Fails with `NameError: name 'build_games_table' is not defined`

**Step 4: Commit**

```
git add v2/browser/build_edm_db.py v2/browser/requirements.txt
git commit -m "scaffold: edm datasette prototype build script"
```

---

### Task 2: Build `games` table

**Files:**
- Modify: `v2/browser/build_edm_db.py`

**Context:** The flat boxscores CSV has these columns:
```
id,gameDate,startTimeUTC,easternUTCOffset,venueUTCOffset,periodDescriptor_number,
periodDescriptor_periodType,periodDescriptor_maxRegulationPeriods,awayTeam_id,
awayTeam_abbrev,awayTeam_score,awayTeam_sog,homeTeam_id,homeTeam_abbrev,
homeTeam_score,homeTeam_sog,awayTeam_playerIds,homeTeam_playerIds
```

The flat boxscores file has one row per period per game. We need to aggregate to one row per game and derive: opponent, homeAway, edmGoals, oppGoals, result, periodCount.

**Step 1: Implement `build_games_table`**

Add this function to `build_edm_db.py` above `main()`:

```python
def build_games_table(conn):
    """Load flat boxscores CSV, filter to EDM games, aggregate to one row per game."""
    df = pd.read_csv(FLAT_BOXSCORES)

    # Filter to games involving EDM
    edm_mask = (df["awayTeam_abbrev"] == TEAM_ABBREV) | (df["homeTeam_abbrev"] == TEAM_ABBREV)
    edm_df = df[edm_mask].copy()

    # Aggregate: one row per game (flat boxscores have one row per period)
    games = []
    for game_id, gdf in edm_df.groupby("id"):
        row = gdf.iloc[0]
        is_home = row["homeTeam_abbrev"] == TEAM_ABBREV
        home_away = "home" if is_home else "away"
        opponent = row["awayTeam_abbrev"] if is_home else row["homeTeam_abbrev"]
        edm_goals = int(gdf["homeTeam_score"].max() if is_home else gdf["awayTeam_score"].max())
        opp_goals = int(gdf["awayTeam_score"].max() if is_home else gdf["homeTeam_score"].max())
        period_count = int(gdf["periodDescriptor_number"].max())

        # Determine result
        if edm_goals > opp_goals:
            result = "W"
        elif period_count > 3:
            result = "OTL"
        else:
            result = "L"

        games.append({
            "gameId": int(game_id),
            "gameDate": row["gameDate"],
            "opponent": opponent,
            "homeAway": home_away,
            "edmGoals": edm_goals,
            "oppGoals": opp_goals,
            "result": result,
            "periodCount": period_count,
        })

    games_df = pd.DataFrame(games)
    games_df.to_sql("games", conn, index=False, if_exists="replace")

    edm_game_ids = set(games_df["gameId"].astype(int))
    print(f"games: {len(games_df)} rows")
    return edm_game_ids
```

**Step 2: Run and verify**

Run: `cd /Users/jrf1039/files/projects/nhl && python v2/browser/build_edm_db.py`
Expected: Prints `games: 58 rows` then fails on next undefined function.

**Step 3: Spot-check with sqlite3**

Run: `sqlite3 data/2025/generated/browser/edm.db "SELECT gameDate, opponent, homeAway, edmGoals, oppGoals, result FROM games ORDER BY gameDate LIMIT 5"`
Expected: 5 rows of EDM game data with correct opponents and results.

**Step 4: Commit**

```
git add v2/browser/build_edm_db.py
git commit -m "feat: build games table from flat boxscores"
```

---

### Task 3: Build `players` table

**Files:**
- Modify: `v2/browser/build_edm_db.py`

**Context:** The players CSV has these columns:
```
playerId,currentTeamId,currentTeamAbbrev,firstName,lastName,sweaterNumber,position,
heightInInches,weightInPounds,birthDate,birthCountry,shootsCatches,draftYear,
draftTeam,draftRound,draftPick,draftOverall,gameIds,teamIds
```

We filter to EDM and keep the useful columns (drop gameIds and teamIds — those are for linkage, not browsing).

**Step 1: Implement `build_players_table`**

Add this function to `build_edm_db.py`:

```python
def build_players_table(conn):
    """Load players CSV, filter to EDM roster."""
    df = pd.read_csv(PLAYERS_CSV)
    edm = df[df["currentTeamAbbrev"] == TEAM_ABBREV].copy()

    keep_cols = [
        "playerId", "firstName", "lastName", "sweaterNumber", "position",
        "heightInInches", "weightInPounds", "birthDate", "birthCountry",
        "shootsCatches", "draftYear", "draftTeam", "draftRound", "draftPick",
        "draftOverall",
    ]
    edm = edm[keep_cols]
    edm.to_sql("players", conn, index=False, if_exists="replace")
    print(f"players: {len(edm)} rows")
```

**Step 2: Run and verify**

Run: `cd /Users/jrf1039/files/projects/nhl && python v2/browser/build_edm_db.py`
Expected: Prints `games: 58 rows` then `players: 34 rows` (approximately), then fails on next function.

**Step 3: Spot-check**

Run: `sqlite3 data/2025/generated/browser/edm.db "SELECT firstName, lastName, position, sweaterNumber FROM players ORDER BY lastName LIMIT 5"`
Expected: 5 EDM players sorted by last name.

**Step 4: Commit**

```
git add v2/browser/build_edm_db.py
git commit -m "feat: build players table from players CSV"
```

---

### Task 4: Build `player_game_stats` table

**Files:**
- Modify: `v2/browser/build_edm_db.py`

**Context:** Raw boxscore JSONs have this structure:
```json
{
  "playerByGameStats": {
    "awayTeam": { "forwards": [...], "defense": [...], "goalies": [...] },
    "homeTeam": { "forwards": [...], "defense": [...], "goalies": [...] }
  }
}
```

Each player object has: `playerId`, `sweaterNumber`, `name.default`, `position`, `goals`, `assists`, `points`, `plusMinus`, `pim`, `hits`, `powerPlayGoals`, `sog`, `faceoffWinningPctg`, `toi` (string "MM:SS"), `blockedShots`, `shifts`, `giveaways`, `takeaways`.

Goalies have different fields: `evenStrengthShotsAgainst`, `powerPlayShotsAgainst`, `shorthandedShotsAgainst`, `saveShotsAgainst`, `savePctg`, `evenStrengthGoalsAgainst`, `powerPlayGoalsAgainst`, `shorthandedGoalsAgainst`, `pim`, `goalsAgainst`, `toi`.

We need to handle skaters and goalies with different column sets. Simplest approach: store them in the same table with NULL for inapplicable fields.

**Step 1: Implement `build_player_game_stats_table`**

Add this function to `build_edm_db.py`:

```python
def build_player_game_stats_table(conn, edm_game_ids):
    """Parse raw boxscore JSONs, extract EDM player stats."""
    rows = []
    for game_id in sorted(edm_game_ids):
        path = os.path.join(BOXSCORES_DIR, f"{game_id}.json")
        if not os.path.exists(path):
            print(f"  warning: boxscore missing for {game_id}")
            continue

        with open(path) as f:
            data = json.load(f)

        stats = data.get("playerByGameStats", {})

        # Determine which side is EDM
        away_abbrev = data.get("awayTeam", {}).get("abbrev", "")
        home_abbrev = data.get("homeTeam", {}).get("abbrev", "")

        if home_abbrev == TEAM_ABBREV:
            team_key = "homeTeam"
        elif away_abbrev == TEAM_ABBREV:
            team_key = "awayTeam"
        else:
            continue

        team_stats = stats.get(team_key, {})
        for group in ["forwards", "defense", "goalies"]:
            for player in team_stats.get(group, []):
                row = {
                    "gameId": int(game_id),
                    "playerId": player.get("playerId"),
                    "name": player.get("name", {}).get("default", ""),
                    "position": player.get("position", ""),
                    "toi": player.get("toi", ""),
                }
                if group in ("forwards", "defense"):
                    row.update({
                        "goals": player.get("goals"),
                        "assists": player.get("assists"),
                        "points": player.get("points"),
                        "plusMinus": player.get("plusMinus"),
                        "pim": player.get("pim"),
                        "hits": player.get("hits"),
                        "sog": player.get("sog"),
                        "faceoffWinningPctg": player.get("faceoffWinningPctg"),
                        "blockedShots": player.get("blockedShots"),
                        "shifts": player.get("shifts"),
                        "giveaways": player.get("giveaways"),
                        "takeaways": player.get("takeaways"),
                        "powerPlayGoals": player.get("powerPlayGoals"),
                    })
                else:
                    row.update({
                        "goalsAgainst": player.get("goalsAgainst"),
                        "savePctg": player.get("savePctg"),
                        "saveShotsAgainst": player.get("saveShotsAgainst"),
                        "pim": player.get("pim"),
                    })
                rows.append(row)

    df = pd.DataFrame(rows)
    df.to_sql("player_game_stats", conn, index=False, if_exists="replace")
    print(f"player_game_stats: {len(df)} rows")
```

**Step 2: Run and verify**

Run: `cd /Users/jrf1039/files/projects/nhl && python v2/browser/build_edm_db.py`
Expected: Prints `player_game_stats: ~1100-1300 rows` (roughly 20 players × 58 games), then fails on next function.

**Step 3: Spot-check**

Run: `sqlite3 data/2025/generated/browser/edm.db "SELECT name, position, goals, assists, toi FROM player_game_stats WHERE gameId = 2025020006 ORDER BY toi DESC LIMIT 5"`
Expected: EDM player stats from game 2025020006 (CGY @ EDM).

**Step 4: Commit**

```
git add v2/browser/build_edm_db.py
git commit -m "feat: build player_game_stats table from raw boxscores"
```

---

### Task 5: Build `plays` table

**Files:**
- Modify: `v2/browser/build_edm_db.py`

**Context:** Flat play CSVs have 48 columns. One file per game. We load all 58 EDM game files and concatenate. The gameId is in the filename, not in the CSV itself — we need to add it.

**Step 1: Implement `build_plays_table`**

Add this function to `build_edm_db.py`:

```python
def build_plays_table(conn, edm_game_ids):
    """Load flat play CSVs for EDM games."""
    frames = []
    for game_id in sorted(edm_game_ids):
        path = os.path.join(FLATPLAYS_DIR, f"{game_id}.csv")
        if not os.path.exists(path):
            print(f"  warning: flat plays missing for {game_id}")
            continue
        df = pd.read_csv(path)
        df.insert(0, "gameId", int(game_id))
        frames.append(df)

    if frames:
        all_plays = pd.concat(frames, ignore_index=True)
        all_plays.to_sql("plays", conn, index=False, if_exists="replace")
        print(f"plays: {len(all_plays)} rows")
    else:
        print("plays: 0 rows (no files found)")
```

**Step 2: Run and verify**

Run: `cd /Users/jrf1039/files/projects/nhl && python v2/browser/build_edm_db.py`
Expected: Prints `plays: ~18000-25000 rows`, then fails on next function.

**Step 3: Spot-check**

Run: `sqlite3 data/2025/generated/browser/edm.db "SELECT gameId, typeDescKey, COUNT(*) FROM plays GROUP BY gameId, typeDescKey ORDER BY gameId LIMIT 10"`
Expected: Event type counts for the first EDM game.

**Step 4: Commit**

```
git add v2/browser/build_edm_db.py
git commit -m "feat: build plays table from flat play CSVs"
```

---

### Task 6: Build `shifts` table

**Files:**
- Modify: `v2/browser/build_edm_db.py`

**Context:** Shift JSON files are named `{gameId}_home.json` and `{gameId}_away.json`. Structure:
```json
{
  "gameId": "2025020006",
  "teamType": "home",
  "team": { "abbrev": "EDM", "name": "EDMONTON OILERS" },
  "players": [
    {
      "number": 2,
      "name": "BOUCHARD, EVAN",
      "shifts": [
        { "shiftNumber": 1, "period": 1, "startTime": "00:00", "endTime": "00:35", "duration": "00:35", "event": null }
      ]
    }
  ]
}
```

We load both home and away shift files for each EDM game (both teams' shifts).

**Step 1: Implement `build_shifts_table`**

Add this function to `build_edm_db.py`:

```python
def build_shifts_table(conn, edm_game_ids):
    """Parse shift JSONs for EDM games (both teams)."""
    rows = []
    for game_id in sorted(edm_game_ids):
        for team_type in ["home", "away"]:
            path = os.path.join(SHIFTS_DIR, f"{game_id}_{team_type}.json")
            if not os.path.exists(path):
                print(f"  warning: shifts missing for {game_id}_{team_type}")
                continue

            with open(path) as f:
                data = json.load(f)

            team_abbrev = data.get("team", {}).get("abbrev", "")

            for player in data.get("players", []):
                player_name = player.get("name", "")
                sweater_number = player.get("number")

                for shift in player.get("shifts", []):
                    rows.append({
                        "gameId": int(game_id),
                        "teamType": team_type,
                        "teamAbbrev": team_abbrev,
                        "playerName": player_name,
                        "sweaterNumber": sweater_number,
                        "shiftNumber": shift.get("shiftNumber"),
                        "period": shift.get("period"),
                        "startTime": shift.get("startTime"),
                        "endTime": shift.get("endTime"),
                        "duration": shift.get("duration"),
                        "event": shift.get("event"),
                    })

    df = pd.DataFrame(rows)
    df.to_sql("shifts", conn, index=False, if_exists="replace")
    print(f"shifts: {len(df)} rows")
```

**Step 2: Run and verify**

Run: `cd /Users/jrf1039/files/projects/nhl && python v2/browser/build_edm_db.py`
Expected: Prints `shifts: ~25000-35000 rows`, then fails on next function.

**Step 3: Spot-check**

Run: `sqlite3 data/2025/generated/browser/edm.db "SELECT playerName, COUNT(*) as shift_count FROM shifts WHERE gameId = 2025020006 AND teamAbbrev = 'EDM' GROUP BY playerName ORDER BY shift_count DESC LIMIT 5"`
Expected: Top EDM players by shift count in game 2025020006.

**Step 4: Commit**

```
git add v2/browser/build_edm_db.py
git commit -m "feat: build shifts table from shift JSONs"
```

---

### Task 7: Build `timelines` table

**Files:**
- Modify: `v2/browser/build_edm_db.py`

**Context:** Timeline CSVs have these columns:
```
period,secondsIntoPeriod,secondsElapsedGame,situationCode,strength,awayGoalie,
awaySkaterCount,awaySkaters,homeSkaterCount,homeGoalie,homeSkaters
```

One file per game, 3600 rows each (one per second). We add gameId from the filename.

**Step 1: Implement `build_timelines_table`**

Add this function to `build_edm_db.py`:

```python
def build_timelines_table(conn, edm_game_ids):
    """Load timeline CSVs for EDM games."""
    frames = []
    for game_id in sorted(edm_game_ids):
        path = os.path.join(TIMELINES_DIR, f"{game_id}.csv")
        if not os.path.exists(path):
            print(f"  warning: timeline missing for {game_id}")
            continue
        df = pd.read_csv(path)
        df.insert(0, "gameId", int(game_id))
        frames.append(df)

    if frames:
        all_timelines = pd.concat(frames, ignore_index=True)
        all_timelines.to_sql("timelines", conn, index=False, if_exists="replace")
        print(f"timelines: {len(all_timelines)} rows")
    else:
        print("timelines: 0 rows (no files found)")
```

**Step 2: Run and verify — full build**

Run: `cd /Users/jrf1039/files/projects/nhl && python v2/browser/build_edm_db.py`
Expected output (approximate):
```
games: 58 rows
players: 34 rows
player_game_stats: ~1200 rows
plays: ~20000 rows
shifts: ~29000 rows
timelines: ~209000 rows

Done. Database written to data/2025/generated/browser/edm.db
Run: datasette data/2025/generated/browser/edm.db
```

**Step 3: Verify db file size and table counts**

Run: `ls -lh data/2025/generated/browser/edm.db && sqlite3 data/2025/generated/browser/edm.db "SELECT name, (SELECT COUNT(*) FROM games) as games, (SELECT COUNT(*) FROM players) as players, (SELECT COUNT(*) FROM player_game_stats) as pgs, (SELECT COUNT(*) FROM plays) as plays, (SELECT COUNT(*) FROM shifts) as shifts, (SELECT COUNT(*) FROM timelines) as timelines FROM sqlite_master LIMIT 1"`
Expected: DB file ~30-60 MB, row counts matching the build output.

**Step 4: Commit**

```
git add v2/browser/build_edm_db.py
git commit -m "feat: build timelines table, complete EDM database builder"
```

---

### Task 8: Install datasette and test browse

**Step 1: Install datasette**

Run: `pip install datasette`

**Step 2: Launch datasette**

Run: `cd /Users/jrf1039/files/projects/nhl && datasette data/2025/generated/browser/edm.db`
Expected: Server starts at http://127.0.0.1:8001 (or similar port). Open in browser.

**Step 3: Verify all 6 tables are browsable**

In the browser, confirm you can see and click into: games, players, player_game_stats, plays, shifts, timelines.

**Step 4: Test a sample SQL query**

Use the Datasette SQL editor to run:
```sql
SELECT p.firstName, p.lastName, p.position, p.heightInInches, p.weightInPounds,
       COUNT(DISTINCT pgs.gameId) as games_played,
       SUM(CASE WHEN pgs.goals IS NOT NULL THEN pgs.goals ELSE 0 END) as total_goals,
       SUM(CASE WHEN pgs.assists IS NOT NULL THEN pgs.assists ELSE 0 END) as total_assists
FROM players p
JOIN player_game_stats pgs ON p.playerId = pgs.playerId
GROUP BY p.playerId
ORDER BY total_goals + total_assists DESC
LIMIT 10
```
Expected: Top 10 EDM players by points.

---

### Summary

**6 tables, ~260,000 rows, built from existing data files with one Python script.**

| Table | Rows | Source |
|-------|------|--------|
| games | 58 | flat boxscores CSV |
| players | ~34 | players CSV |
| player_game_stats | ~1,200 | raw boxscore JSONs |
| plays | ~20,000 | flat play CSVs |
| shifts | ~29,000 | shift JSONs |
| timelines | ~209,000 | timeline CSVs |
