# Team Deployment Analysis

How to analyze how a team's forwards and defense are deployed by competition difficulty, split by home and away.

## What the data captures

Each game produces a CSV at `data/2025/generated/competition/<gameId>.csv` with these columns:

| Column | Description |
|---|---|
| `gameId` | e.g. `2025020001` |
| `playerId` | NHL player ID |
| `team` | Team abbreviation (e.g. `EDM`) |
| `position` | `F` or `D` (goalies excluded) |
| `toi_seconds` | 5v5 time on ice for the game |
| `comp_fwd` | Mean 5v5 TOI of opposing forwards faced (raw seconds) |
| `comp_def` | Mean 5v5 TOI of opposing defensemen faced (raw seconds) |
| `pct_vs_top_fwd` | Fraction of 5v5 seconds spent against top-6 opposing forwards |
| `pct_vs_top_def` | Fraction of 5v5 seconds spent against top-4 opposing defensemen |

**Top competition definitions (per game, per team):**
- Top forwards: the 6 opposing forwards with the most 5v5 TOI in that game
- Top defensemen: the 4 opposing defensemen with the most 5v5 TOI in that game

`pct_vs_top_fwd = 0.70` means that on 70% of a player's 5v5 seconds, more than half the opposing forwards on ice were top-6 players (computed as a per-second fraction, averaged across the game).

## How to run it

Generate competition CSVs for the full season (or a range):

```bash
# Single game
python v2/competition/compute_competition.py <game_number> <season>

# Range of games
python v2/competition/compute_competition.py 1 900 2025
```

Output goes to `data/2025/generated/competition/`.

## Analysis script

Paste this into a Python script or shell, replacing `EDM` with the team abbreviation you want:

```python
import csv
import glob
import json
from collections import defaultdict
from pathlib import Path

TEAM = "EDM"   # <-- change this
SEASON = "2025"

# Load all competition files and tag home/away
rows = []

for path in sorted(glob.glob(f"data/{SEASON}/generated/competition/{SEASON}02*.csv")):
    game_id = Path(path).stem
    plays_path = f"data/{SEASON}/plays/{game_id}.json"
    try:
        with open(plays_path) as f:
            plays = json.load(f)
        home_team = plays["homeTeam"]["abbrev"]
        names = {
            spot["playerId"]: f"{spot.get('firstName',{}).get('default','')} {spot.get('lastName',{}).get('default','')}".strip()
            for spot in plays.get("rosterSpots", [])
        }
    except Exception:
        continue

    with open(path) as f:
        for row in csv.DictReader(f):
            if row["team"] == TEAM:
                row["game_id"] = game_id
                row["edm_side"] = "home" if home_team == TEAM else "away"
                row["player_name"] = names.get(int(row["playerId"]), row["playerId"])
                rows.append(row)

# Aggregate per player per side
def agg():
    return {"games": 0, "toi": [], "pf": [], "pd": []}

player_stats = defaultdict(lambda: {"home": agg(), "away": agg(), "pos": "", "name": ""})

for r in rows:
    pid = r["playerId"]
    side = r["edm_side"]
    player_stats[pid]["pos"] = r["position"]
    player_stats[pid]["name"] = r["player_name"]
    d = player_stats[pid][side]
    d["games"] += 1
    d["toi"].append(int(r["toi_seconds"]))
    d["pf"].append(float(r["pct_vs_top_fwd"]))
    d["pd"].append(float(r["pct_vs_top_def"]))

def mean(vals):
    return sum(vals) / len(vals) if vals else 0.0

for pos in ["F", "D"]:
    label = "FORWARDS" if pos == "F" else "DEFENSE"
    players = [(pid, d) for pid, d in player_stats.items() if d["pos"] == pos]
    players.sort(key=lambda x: -(mean(x[1]["home"]["pf"]) + mean(x[1]["away"]["pf"])) / 2)

    print(f"\n{'='*70}")
    print(f"{label}")
    print(f"{'='*70}")
    print(f"{'Player':<22} {'Pos':>3}  {'Home G':>6} {'H-TOI':>6} {'H-pctF':>7} {'H-pctD':>7}  {'Away G':>6} {'A-TOI':>6} {'A-pctF':>7} {'A-pctD':>7}")
    print(f"{'-'*90}")

    for pid, d in players:
        h, a = d["home"], d["away"]
        if not h["games"] and not a["games"]:
            continue
        print(
            f"{d['name']:<22} {pos:>3}  "
            f"{h['games']:>6} {f'{mean(h[\"toi\"])/60:.1f}m' if h['games'] else '—':>6} "
            f"{f'{mean(h[\"pf\"]):.3f}' if h['games'] else '—':>7} "
            f"{f'{mean(h[\"pd\"]):.3f}' if h['games'] else '—':>7}  "
            f"{a['games']:>6} {f'{mean(a[\"toi\"])/60:.1f}m' if a['games'] else '—':>6} "
            f"{f'{mean(a[\"pf\"]):.3f}' if a['games'] else '—':>7} "
            f"{f'{mean(a[\"pd\"]):.3f}' if a['games'] else '—':>7}"
        )
```

## What to look for

**Line tiers** — players naturally cluster into 3 tiers by `pct_vs_top_fwd`. Top lines face 0.60–0.75, middle 0.50–0.65, bottom liners 0.38–0.55. The gaps between tiers tell you how differentiated the deployment is.

**Home vs away gap** — home teams have last change, so they can shelter bottom liners or target opponents' stars. A large drop in `pct_vs_top_fwd` from away→home for bottom-liners means the coaching staff actively manages matchups at home. A small gap means the opponent is dictating play.

**pctD vs pctF** — `pct_vs_top_def` tends to run 0.10–0.15 higher than `pct_vs_top_fwd` for the same player because there are only 4 top-D slots (vs 6 top-F), leaving less room to shelter anyone on the defensive side.

**Defense TOI vs competition** — defensemen who play the most minutes don't always face the hardest competition. High TOI can reflect penalty kill usage or garbage-time deployment rather than strict matching against the opponent's top lines.

**Defense pairs** — individual defenseman numbers are less meaningful than pair-level numbers, since partners always share ice time. Average the two partners' `pct_vs_top_fwd` for a cleaner comparison across pairs.

## Notes

- Only regular season games (`020` game type) are included
- Goalies are excluded from all outputs
- Missing games (no timeline CSV) are skipped silently by the pipeline
- Player names are pulled from the plays JSON `rosterSpots` field — occasionally a player who appeared in the timeline won't have a name entry if they were a late scratch
