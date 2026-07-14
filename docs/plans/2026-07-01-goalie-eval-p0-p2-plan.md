# Goalie Evaluation P0–P2 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Acquire the two missing raw seasons and build the tested goalie-shot foundation: per-season all-strength goalie-shot tables with freeze/rebound outcomes and rink-bias-adjusted geometry.

**Architecture:** Raw API JSON stays verbatim under `data/<season>/`; a new `v2/goalies/` package holds pure, tested computation modules (situation parsing, event windows, geometry, extraction, rink adjustment) plus thin CLI builders that write derived CSVs under `data/generated/goalies/`. Spec: `docs/plans/2026-06-11-goalie-evaluation-design.md` (P0–P2).

**Tech Stack:** Python 3.11 (pyenv system python — NOT `uv run`; pandas 3.0 and numpy 2.4 live there), pytest, existing `v1/nhlgame.py` downloader, existing `v2/players/get_players.py`.

## Global Constraints

- Work on a feature branch `goalie-eval-p1`; local per-task commits are authorized on this branch only; NEVER push, never commit to master/main (oiler merges manually).
- Raw files under `data/<season>/{plays,meta,boxscores,players}/` are never modified — read-only inputs.
- No new dependencies: pandas/numpy/pytest only, all already in the system python.
- Run tests with `python3 -m pytest v2/goalies/tests/ -v`; before calling the plan done, `python3 -m pytest v2/ -v` must be fully green.
- pandas 3.x gotcha: `pd.Series.get()` is removed — use `s[col] if col in s.index else None`.
- Season dirs are named by start year: `data/2021/` = 2021-22, `data/2022/` = 2022-23. Regular-season game IDs run `<season>020001`–`<season>021312` (1,312 games, 32 teams).
- All derived tables must be rebuildable from raw by re-running the builder CLIs.

---

### Task 1: Download raw seasons 2021-22 and 2022-23

**Files:**
- No repo files created (data only: `data/2021/`, `data/2022/`).
- Read (do not modify): `v1/nhlgame.py`, `v2/players/get_players.py`

**Interfaces:**
- Consumes: `v1/nhlgame.py` range mode — `NHL_SEASON=<yr> python3 v1/nhlgame.py <start> <end>` downloads plays (`gamecenter/{id}/play-by-play`), meta (`landing`), boxscores per game into `data/<yr>/`. `v2/players/get_players.py <season>` downloads player-landing JSONs into `data/<yr>/players/`.
- Produces: `data/2021/{plays,meta,boxscores,players}/` and `data/2022/{...}` — 1,312 game files per game dir, ~1,000+ player files. Later tasks read `data/<season>/plays/*.json`.

- [ ] **Step 1: Check whether range mode also fetches shifts**

Run: `sed -n "$(grep -n 'def download_game' v1/nhlgame.py | cut -d: -f1),+40p" v1/nhlgame.py`
If `download_game` (or the range-mode loop) calls `download_shifts`, we do NOT want to skip it (raw-first: keep whatever it fetches), but set `NHL_SHIFT_DELAY=2` in the commands below so the run doesn't take 5 s per request. If it only fetches the three API endpoints, run as-is.

- [ ] **Step 2: Download both seasons in the background**

```bash
cd /Users/jrf1039/files/projects/nhl
NHL_SEASON=2021 NHL_SHIFT_DELAY=2 python3 v1/nhlgame.py 1 1312 > /tmp/dl_2021.log 2>&1 &
NHL_SEASON=2022 NHL_SHIFT_DELAY=2 python3 v1/nhlgame.py 1 1312 > /tmp/dl_2022.log 2>&1 &
wait
```

Expected: hours-scale runtime. Monitor with `ls data/2021/plays | wc -l`.

- [ ] **Step 3: Verify counts and schema**

```bash
for s in 2021 2022; do for d in plays meta boxscores; do echo "$s/$d: $(ls data/$s/$d | wc -l)"; done; done
```

Expected: 1312 for every dir. If a handful are missing, re-run the specific ranges and check the error logs. COVID note (oiler): 2021-22 had many postponements but the season was played out nearly in full — rescheduled games kept their original game IDs, so all 1312 files should exist. MONITOR: after download, also verify no game is a placeholder (e.g., `gameState` not final, or empty `plays`) — list any such IDs:

```bash
python3 - <<'EOF'
import json, pathlib
for s in ("2021", "2022"):
    bad = []
    for f in sorted(pathlib.Path(f"data/{s}/plays").glob("*.json")):
        g = json.loads(f.read_text())
        if len(g.get("plays", [])) < 50:
            bad.append((f.stem, len(g.get("plays", []))))
    print(s, "suspicious games:", bad or "none")
EOF
```

Any suspicious game gets re-downloaded before proceeding. Rescheduling also means game IDs are not in chronological order for 2021-22 — harmless now, but flag it in the task notes for P4 (back-to-back computation must sort by `game_date`, not game ID).

Then schema probe:

```bash
python3 - <<'EOF'
import json
for s in ("2021", "2022"):
    g = json.load(open(f"data/{s}/plays/{s}020100.json"))
    shot = next(p for p in g["plays"] if p["typeDescKey"] == "shot-on-goal")
    assert "situationCode" in shot and "homeTeamDefendingSide" in shot, s
    assert "goalieInNetId" in shot["details"] and "xCoord" in shot["details"], s
    print(s, "schema OK,", len(g["plays"]), "plays")
EOF
```

Expected: `2021 schema OK` / `2022 schema OK`.

- [ ] **Step 4: Download player-landing files**

```bash
python3 v2/players/get_players.py 2021
python3 v2/players/get_players.py 2022
ls data/2021/players | wc -l; ls data/2022/players | wc -l
```

Expected: ~1,000–1,050 files each.

- [ ] **Step 5: Commit**

Data dirs are not in git (verify with `git status --short data/ | head`; if data/ is untracked/ignored, nothing to commit — record completion in the task notes instead).

---

### Task 2: Package scaffold + situation/strength parsing

**Files:**
- Create: `v2/goalies/__init__.py` (empty), `v2/goalies/situations.py`
- Test: `v2/goalies/tests/__init__.py` (empty), `v2/goalies/tests/test_situations.py`

**Interfaces:**
- Produces: `parse_situation(code: str) -> tuple[int, int, int, int]` (away goalie, away skaters, home skaters, home goalie); `strength_for_goalie(code: str, goalie_is_home: bool) -> str` returning `"EV" | "PP" | "SH"` from the goalie's TEAM perspective; constant `PENALTY_SHOT_CODES = {"0101", "1010"}`. Task 5 imports all three.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_situations.py
import pytest

from v2.goalies.situations import PENALTY_SHOT_CODES, parse_situation, strength_for_goalie


def test_parse_situation():
    assert parse_situation("1551") == (1, 5, 5, 1)
    assert parse_situation("0651") == (0, 6, 5, 1)


@pytest.mark.parametrize(
    "code,goalie_is_home,expected",
    [
        ("1551", True, "EV"),   # 5v5
        ("1441", False, "EV"),  # 4v4
        ("1451", True, "PP"),   # home has 5 skaters vs away 4: home goalie's team on PP
        ("1451", False, "SH"),  # away goalie's team is shorthanded
        ("1541", True, "SH"),
        ("0651", True, "SH"),   # away pulled goalie for 6th skater; home goalie's team defends 5v6
    ],
)
def test_strength_for_goalie(code, goalie_is_home, expected):
    assert strength_for_goalie(code, goalie_is_home) == expected


def test_penalty_shot_codes():
    assert "0101" in PENALTY_SHOT_CODES and "1010" in PENALTY_SHOT_CODES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest v2/goalies/tests/test_situations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.goalies'`

- [ ] **Step 3: Write minimal implementation**

```python
# v2/goalies/situations.py
"""situationCode parsing for goalie-perspective strength states.

Format: [away goalie][away skaters][home skaters][home goalie], e.g. 1551.
"""

PENALTY_SHOT_CODES = {"0101", "1010"}


def parse_situation(code: str) -> tuple[int, int, int, int]:
    a_g, a_s, h_s, h_g = (int(c) for c in code)
    return a_g, a_s, h_s, h_g


def strength_for_goalie(code: str, goalie_is_home: bool) -> str:
    """Strength state of the GOALIE'S team: EV, PP (his team up a skater), SH."""
    _, a_s, h_s, _ = parse_situation(code)
    own, opp = (h_s, a_s) if goalie_is_home else (a_s, h_s)
    if own == opp:
        return "EV"
    return "PP" if own > opp else "SH"
```

Create empty `v2/goalies/__init__.py` and `v2/goalies/tests/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest v2/goalies/tests/test_situations.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/
git commit -m "feat(goalies): situation parsing and goalie-perspective strength"
```

---

### Task 3: Freeze and rebound window detection

**Files:**
- Create: `v2/goalies/windows.py`
- Test: `v2/goalies/tests/test_windows.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `detect_freeze(events_after, save_time_s: int, period: int) -> bool` and `detect_rebound(events_after, save_time_s: int, period: int, shooting_team: int) -> bool`, where `events_after` is an ordered iterable of `(time_s: int, type_desc: str, owner_team: int | None, period: int)` tuples for plays AFTER the save. Constants `FREEZE_WINDOW_S = 2`, `REBOUND_WINDOW_S = 3`, `CORSI_EVENTS = {"goal", "shot-on-goal", "missed-shot", "blocked-shot"}`, `STOP_EVENTS = {"stoppage", "period-end", "game-end"}`. Task 5 imports these.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_windows.py
from v2.goalies.windows import detect_freeze, detect_rebound


def test_freeze_stoppage_within_2s():
    events = [(101, "stoppage", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is True


def test_no_freeze_when_stoppage_late():
    events = [(103, "stoppage", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is False


def test_no_freeze_when_play_continues():
    events = [(101, "hit", 10, 1), (102, "stoppage", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is False


def test_period_end_counts_as_freeze():
    events = [(101, "period-end", None, 1)]
    assert detect_freeze(events, save_time_s=100, period=1) is True


def test_freeze_ignores_next_period_events():
    events = [(0, "faceoff", 10, 2)]
    assert detect_freeze(events, save_time_s=1199, period=1) is False


def test_rebound_same_team_corsi_within_3s():
    events = [(102, "shot-on-goal", 10, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is True


def test_no_rebound_when_other_team_shoots():
    events = [(102, "shot-on-goal", 20, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is False


def test_no_rebound_after_window():
    events = [(104, "shot-on-goal", 10, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is False


def test_no_rebound_after_stoppage():
    events = [(101, "stoppage", None, 1), (102, "shot-on-goal", 10, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is False


def test_rebound_skips_neutral_events():
    # a hit by either team inside the window does not end the chance
    events = [(101, "hit", 20, 1), (102, "missed-shot", 10, 1)]
    assert detect_rebound(events, save_time_s=100, period=1, shooting_team=10) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest v2/goalies/tests/test_windows.py -v`
Expected: FAIL — `ModuleNotFoundError` (windows module missing)

- [ ] **Step 3: Write minimal implementation**

```python
# v2/goalies/windows.py
"""Post-save event windows: freeze (Cane 2s stoppage) and rebound generation (3s)."""

FREEZE_WINDOW_S = 2
REBOUND_WINDOW_S = 3
CORSI_EVENTS = {"goal", "shot-on-goal", "missed-shot", "blocked-shot"}
STOP_EVENTS = {"stoppage", "period-end", "game-end"}


def detect_freeze(events_after, save_time_s: int, period: int) -> bool:
    """True if play stops within FREEZE_WINDOW_S of the save, before any live-play event."""
    for t, kind, _owner, p in events_after:
        if p != period or t - save_time_s > FREEZE_WINDOW_S:
            return False
        if kind in STOP_EVENTS:
            return True
        return False  # first event was live play
    return False


def detect_rebound(events_after, save_time_s: int, period: int, shooting_team: int) -> bool:
    """True if the shooting team gets another attempt within REBOUND_WINDOW_S, play still live."""
    for t, kind, owner, p in events_after:
        if p != period or t - save_time_s > REBOUND_WINDOW_S:
            return False
        if kind in STOP_EVENTS or kind == "faceoff":
            return False
        if kind in CORSI_EVENTS:
            return owner == shooting_team
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest v2/goalies/tests/test_windows.py -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/windows.py v2/goalies/tests/test_windows.py
git commit -m "feat(goalies): freeze and rebound window detection"
```

---

### Task 4: Geometry with true attack direction

**Files:**
- Create: `v2/goalies/geometry.py`
- Test: `v2/goalies/tests/test_geometry.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `parse_time(mmss: str) -> int`; `attack_flip(home_defending_side: str, shooter_is_home: bool) -> int` returning `+1`/`-1`; `normalize(x: float, y: float, flip: int) -> tuple[float, float]`; `shot_distance(x_norm, y_norm) -> float`; `shot_angle(x_norm, y_norm) -> float`; constant `NET_X = 89.0`. Task 5 imports all.
- Note: unlike the shooters-phase scripts (which used sign(x) and were O-zone-only), this uses `homeTeamDefendingSide` so shots from ANY zone normalize correctly. Empirical convention (verified in raw data): `homeTeamDefendingSide == "right"` means home defends positive x, so home attacks −x.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_geometry.py
import pytest

from v2.goalies.geometry import attack_flip, normalize, parse_time, shot_angle, shot_distance


def test_parse_time():
    assert parse_time("01:16") == 76
    assert parse_time("19:59") == 1199


def test_attack_flip_home_defends_right_attacks_left():
    # home defends +x, so home attacks -x: flip -1 rotates attack onto +x
    assert attack_flip("right", shooter_is_home=True) == -1
    assert attack_flip("right", shooter_is_home=False) == 1


def test_attack_flip_home_defends_left():
    assert attack_flip("left", shooter_is_home=True) == 1
    assert attack_flip("left", shooter_is_home=False) == -1


def test_normalize_rotates_180():
    assert normalize(-58, -22, flip=-1) == (58, 22)
    assert normalize(58, 22, flip=1) == (58, 22)


def test_distance_and_angle():
    assert shot_distance(79, 0) == pytest.approx(10.0)
    assert shot_distance(89, 10) == pytest.approx(10.0)
    assert shot_angle(79, 0) == pytest.approx(0.0)
    assert shot_angle(89, 10) == pytest.approx(90.0)


def test_defensive_zone_shot_normalizes_toward_positive_x():
    # shooter is home, home defends left (-x): attack is +x, no flip;
    # a D-zone shot from x=-60 stays at -60 (129 ft out) rather than flipping
    flip = attack_flip("left", shooter_is_home=True)
    xn, yn = normalize(-60, 5, flip)
    assert (xn, yn) == (-60, 5)
    assert shot_distance(xn, yn) == pytest.approx(149.08, abs=0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest v2/goalies/tests/test_geometry.py -v`
Expected: FAIL — `ModuleNotFoundError` (geometry module missing)

- [ ] **Step 3: Write minimal implementation**

```python
# v2/goalies/geometry.py
"""Attack-direction-aware shot geometry.

homeTeamDefendingSide semantics (verified empirically against zoneCode):
"right" = home defends positive x, so home attacks -x. flip = -1 rotates the
rink 180 degrees so the shooter always attacks +x; net at (NET_X, 0).
"""

import math

NET_X = 89.0


def parse_time(mmss: str) -> int:
    m, s = mmss.split(":")
    return int(m) * 60 + int(s)


def attack_flip(home_defending_side: str, shooter_is_home: bool) -> int:
    home_attacks = -1 if home_defending_side == "right" else 1
    return home_attacks if shooter_is_home else -home_attacks


def normalize(x: float, y: float, flip: int) -> tuple[float, float]:
    return (flip * x, flip * y)


def shot_distance(x_norm: float, y_norm: float) -> float:
    return math.hypot(NET_X - x_norm, y_norm)


def shot_angle(x_norm: float, y_norm: float) -> float:
    return math.degrees(math.atan2(abs(y_norm), NET_X - x_norm))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest v2/goalies/tests/test_geometry.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/geometry.py v2/goalies/tests/test_geometry.py
git commit -m "feat(goalies): attack-direction-aware geometry"
```

---

### Task 5: Goalie-shot extractor

**Files:**
- Create: `v2/goalies/extract.py`
- Test: `v2/goalies/tests/test_extract.py`

**Interfaces:**
- Consumes: `parse_situation`, `strength_for_goalie`, `PENALTY_SHOT_CODES` (Task 2); `detect_freeze`, `detect_rebound`, `CORSI_EVENTS` (Task 3); `parse_time`, `attack_flip`, `normalize`, `shot_distance`, `shot_angle` (Task 4).
- Produces: `extract_goalie_shots(game: dict) -> list[dict]`. Each dict has keys: `game_id, game_date, home_abbrev, goalie_id, goalie_is_home, shooter_id, shooter_position` (`"F"|"D"`), `event, is_goal, on_net, strength, score_diff` (goalie team minus opponent at shot time), `period, time_s, x_norm, y_norm, distance, angle, shot_type, zone, dt_prev, prev_type, prev_same_team, prev_x_norm, prev_y_norm, froze, rebound_generated`. Prior-event coordinates get the same flip as the shot (P3's cross-ice proxy needs them). Task 6 (builder) and Task 7 (rink adjust) consume the resulting rows/CSV.
- Scope rules (from spec): unblocked shots only (`goal`, `shot-on-goal`, `missed-shot`); ALL strength states; requires `goalieInNetId` present (excludes empty-net); excludes `periodType == "SO"` and `PENALTY_SHOT_CODES`; requires coordinates. `froze`/`rebound_generated` are only computed for saves (`shot-on-goal` non-goal); they are `None` for goals and misses.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_extract.py
from v2.goalies.extract import extract_goalie_shots

HOME, AWAY = 10, 20
HOME_GOALIE, AWAY_GOALIE = 900, 901


def _play(type_desc, time="05:00", code="1551", x=-70, y=-20, shooter=1,
          goalie=HOME_GOALIE, owner=AWAY, shot_type="wrist", period=1,
          period_type="REG", defending="right"):
    details = {"xCoord": x, "yCoord": y, "zoneCode": "O", "eventOwnerTeamId": owner}
    if type_desc == "goal":
        details.update(scoringPlayerId=shooter, shotType=shot_type,
                       goalieInNetId=goalie, awayScore=1, homeScore=0)
    elif type_desc in ("shot-on-goal", "missed-shot"):
        details.update(shootingPlayerId=shooter, shotType=shot_type, goalieInNetId=goalie)
    return {
        "typeDescKey": type_desc,
        "situationCode": code,
        "homeTeamDefendingSide": defending,
        "periodDescriptor": {"number": period, "periodType": period_type},
        "timeInPeriod": time,
        "details": details,
    }


def _game(plays):
    return {
        "id": 2021020001,
        "gameDate": "2021-10-12",
        "homeTeam": {"id": HOME, "abbrev": "EDM"},
        "awayTeam": {"id": AWAY, "abbrev": "CGY"},
        "rosterSpots": [
            {"playerId": 1, "positionCode": "C", "teamId": AWAY},
            {"playerId": 2, "positionCode": "D", "teamId": AWAY},
            {"playerId": HOME_GOALIE, "positionCode": "G", "teamId": HOME},
            {"playerId": AWAY_GOALIE, "positionCode": "G", "teamId": AWAY},
        ],
        "plays": plays,
    }


def test_basic_save_row():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal"),
        _play("stoppage", time="05:01", owner=None, goalie=None),
    ]))
    assert len(rows) == 1
    r = rows[0]
    assert r["goalie_id"] == HOME_GOALIE and r["goalie_is_home"] is True
    assert r["is_goal"] is False and r["on_net"] is True
    assert r["strength"] == "EV"
    # away shooter, home defends right -> away attacks +x -> no flip
    assert (r["x_norm"], r["y_norm"]) == (-70, -20)
    assert r["froze"] is True and r["rebound_generated"] is False


def test_home_shot_flips_coordinates():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal", owner=HOME, goalie=AWAY_GOALIE, x=-70, y=-20),
    ]))
    # home defends right -> home attacks -x -> flip=-1
    assert (rows[0]["x_norm"], rows[0]["y_norm"]) == (70, 20)
    assert rows[0]["goalie_is_home"] is False


def test_rebound_and_no_freeze():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal", time="05:00"),
        _play("missed-shot", time="05:02"),
    ]))
    assert rows[0]["rebound_generated"] is True and rows[0]["froze"] is False


def test_goal_updates_score_diff_and_skips_windows():
    rows = extract_goalie_shots(_game([
        _play("goal", time="05:00"),
        _play("shot-on-goal", time="10:00"),
    ]))
    goal, save = rows
    assert goal["is_goal"] is True and goal["froze"] is None
    assert goal["score_diff"] == 0          # tied when the shot was taken
    assert save["score_diff"] == -1         # home goalie's team now trails
    assert save["dt_prev"] == 300 and save["prev_type"] == "goal"
    # prior-event coords carry the same flip as the shot (away shooter, no flip)
    assert (save["prev_x_norm"], save["prev_y_norm"]) == (-70, -20)


def test_exclusions():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal", goalie=None),                    # empty net
        _play("shot-on-goal", code="0101"),                    # penalty shot
        _play("shot-on-goal", period_type="SO", period=5),     # shootout
        _play("shot-on-goal", x=None),                         # missing coords
        _play("blocked-shot"),                                 # blocked
    ]))
    assert rows == []


def test_shooter_position_and_pk_strength():
    rows = extract_goalie_shots(_game([
        _play("shot-on-goal", shooter=2, code="1451"),  # away D shoots while away is SH
    ]))
    assert rows[0]["shooter_position"] == "D"
    assert rows[0]["strength"] == "PP"  # home goalie's team has 5 v 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest v2/goalies/tests/test_extract.py -v`
Expected: FAIL — `ModuleNotFoundError` (extract module missing)

- [ ] **Step 3: Write the implementation**

```python
# v2/goalies/extract.py
"""Extract every unblocked shot faced by a goalie, all strength states.

Raw-first: reads a single game's play-by-play dict, returns flat rows.
Freeze/rebound outcomes are computed only for saves (on-net non-goals).
"""

from v2.goalies.geometry import (attack_flip, normalize, parse_time,
                                 shot_angle, shot_distance)
from v2.goalies.situations import PENALTY_SHOT_CODES, strength_for_goalie
from v2.goalies.windows import detect_freeze, detect_rebound

SHOT_EVENTS = {"goal", "shot-on-goal", "missed-shot"}


def _event_stream(plays):
    """(time_s, typeDescKey, ownerTeamId, period) for every play with a timestamp."""
    out = []
    for p in plays:
        if "timeInPeriod" not in p:
            continue
        d = p.get("details", {})
        out.append((parse_time(p["timeInPeriod"]), p["typeDescKey"],
                    d.get("eventOwnerTeamId"), p["periodDescriptor"]["number"]))
    return out


def extract_goalie_shots(game: dict) -> list[dict]:
    home_id = game["homeTeam"]["id"]
    positions = {rs["playerId"]: rs["positionCode"] for rs in game["rosterSpots"]}
    stream = _event_stream(game["plays"])
    rows = []
    away_score = home_score = 0
    prev_event = None  # (time_s, type, owner, period)
    stream_idx = 0

    for play in game["plays"]:
        d = play.get("details", {})
        period = play["periodDescriptor"]["number"]
        t = parse_time(play["timeInPeriod"]) if "timeInPeriod" in play else None
        if t is not None:
            stream_idx += 1  # stream position of THIS play (events after = stream[stream_idx:])

        code = play.get("situationCode")
        is_shot = (
            play["typeDescKey"] in SHOT_EVENTS
            and play["periodDescriptor"]["periodType"] in ("REG", "OT")
            and code is not None and code not in PENALTY_SHOT_CODES
            and d.get("goalieInNetId") is not None
            and d.get("xCoord") is not None and d.get("yCoord") is not None
        )
        if is_shot:
            goalie_id = d["goalieInNetId"]
            shooter_team = d["eventOwnerTeamId"]
            goalie_is_home = shooter_team != home_id
            shooter = d.get("shootingPlayerId") or d.get("scoringPlayerId")
            pos = positions.get(shooter)
            if pos is not None and pos != "G":
                flip = attack_flip(play["homeTeamDefendingSide"], not goalie_is_home)
                xn, yn = normalize(d["xCoord"], d["yCoord"], flip)
                is_goal = play["typeDescKey"] == "goal"
                on_net = play["typeDescKey"] in ("goal", "shot-on-goal")
                own = home_score if goalie_is_home else away_score
                opp = away_score if goalie_is_home else home_score
                froze = rebound = None
                if on_net and not is_goal:
                    after = stream[stream_idx:]
                    froze = detect_freeze(after, t, period)
                    rebound = detect_rebound(after, t, period, shooter_team)
                row = {
                    "game_id": game["id"],
                    "game_date": game.get("gameDate"),
                    "home_abbrev": game["homeTeam"]["abbrev"],
                    "goalie_id": goalie_id,
                    "goalie_is_home": goalie_is_home,
                    "shooter_id": shooter,
                    "shooter_position": "D" if pos == "D" else "F",
                    "event": play["typeDescKey"],
                    "is_goal": is_goal,
                    "on_net": on_net,
                    "strength": strength_for_goalie(code, goalie_is_home),
                    "score_diff": own - opp,
                    "period": period,
                    "time_s": t,
                    "x_norm": xn,
                    "y_norm": yn,
                    "distance": shot_distance(xn, yn),
                    "angle": shot_angle(xn, yn),
                    "shot_type": d.get("shotType"),
                    "zone": d.get("zoneCode"),
                    "dt_prev": t - prev_event[0] if prev_event and prev_event[3] == period else None,
                    "prev_type": prev_event[1] if prev_event and prev_event[3] == period else None,
                    "prev_same_team": (prev_event[2] == shooter_team)
                                      if prev_event and prev_event[3] == period else None,
                    "prev_x_norm": flip * prev_event[4] if prev_event and prev_event[3] == period else None,
                    "prev_y_norm": flip * prev_event[5] if prev_event and prev_event[3] == period else None,
                    "froze": froze,
                    "rebound_generated": rebound,
                }
                rows.append(row)

        if play["typeDescKey"] == "goal" and "awayScore" in d:
            away_score, home_score = d["awayScore"], d["homeScore"]
        if t is not None and d.get("xCoord") is not None and d.get("yCoord") is not None:
            prev_event = (t, play["typeDescKey"], d.get("eventOwnerTeamId"), period,
                          d["xCoord"], d["yCoord"])

    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest v2/goalies/tests/test_extract.py -v`
Expected: 6 PASS. If `test_basic_save_row` fails on `froze`, check that `_event_stream` skips plays without `timeInPeriod` while `stream_idx` only advances for plays that have one (they must stay in lockstep).

- [ ] **Step 5: Run the whole goalie suite and commit**

Run: `python3 -m pytest v2/goalies/tests/ -v` — all pass.

```bash
git add v2/goalies/extract.py v2/goalies/tests/test_extract.py
git commit -m "feat(goalies): all-strength goalie-shot extractor with freeze/rebound outcomes"
```

---

### Task 6: Per-season shots table builder

**Files:**
- Create: `v2/goalies/build_shots.py`
- Test: `v2/goalies/tests/test_build_shots.py`

**Interfaces:**
- Consumes: `extract_goalie_shots` (Task 5).
- Produces: CLI `python3 v2/goalies/build_shots.py <season>` writing `data/generated/goalies/shots_<season>.csv`; function `build_season(plays_dir: Path) -> pd.DataFrame` (all extract columns plus `season`). Task 7 reads these CSVs.

- [ ] **Step 1: Write the failing test**

```python
# v2/goalies/tests/test_build_shots.py
import json

from v2.goalies.build_shots import build_season
from v2.goalies.tests.test_extract import _game, _play


def test_build_season_reads_dir_and_adds_season(tmp_path):
    plays = tmp_path / "2021" / "plays"
    plays.mkdir(parents=True)
    (plays / "2021020001.json").write_text(json.dumps(_game([_play("shot-on-goal")])))
    df = build_season(plays)
    assert len(df) == 1
    assert df.iloc[0]["season"] == "2021"
    assert df.iloc[0]["goalie_id"] == 900
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest v2/goalies/tests/test_build_shots.py -v`
Expected: FAIL — `ModuleNotFoundError` (build_shots missing)

- [ ] **Step 3: Write the implementation**

```python
# v2/goalies/build_shots.py
"""Build data/generated/goalies/shots_<season>.csv from raw plays. Rebuildable, raw untouched.

Usage: python3 v2/goalies/build_shots.py <season>   # e.g. 2021
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from v2.goalies.extract import extract_goalie_shots  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent


def build_season(plays_dir: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(plays_dir.glob("*.json")):
        rows.extend(extract_goalie_shots(json.loads(f.read_text())))
    df = pd.DataFrame(rows)
    df["season"] = plays_dir.parent.name
    # None/True/False mixed columns round-trip badly through CSV; store as nullable floats
    for c in ("froze", "rebound_generated"):
        df[c] = df[c].map({True: 1.0, False: 0.0})
    return df


def main() -> None:
    season = sys.argv[1]
    df = build_season(ROOT / "data" / season / "plays")
    out_dir = ROOT / "data" / "generated" / "goalies"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"shots_{season}.csv"
    df.to_csv(out, index=False)
    print(f"{season}: {len(df)} shots, {df['goalie_id'].nunique()} goalies, "
          f"{int(df['is_goal'].sum())} goals -> {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test, then build all five seasons**

Run: `python3 -m pytest v2/goalies/tests/test_build_shots.py -v` — PASS.

```bash
for s in 2021 2022 2023 2024 2025; do python3 v2/goalies/build_shots.py $s; done
```

Expected per season: ~95,000–110,000 shots, 85–105 goalies, ~7,400–8,100 goals (league scored ~8,000/season; empty-net and shootout goals are excluded here). If a season is >10% outside these ranges, STOP and investigate before continuing.

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/build_shots.py v2/goalies/tests/test_build_shots.py
git commit -m "feat(goalies): per-season goalie-shot table builder"
```

---

### Task 7: Rink-bias adjustment

**Files:**
- Create: `v2/goalies/rink_adjust.py`
- Test: `v2/goalies/tests/test_rink_adjust.py`

**Interfaces:**
- Consumes: `shots_<season>.csv` files (Task 6) — columns `home_abbrev`, `distance`.
- Produces: `fit_quantile_map(arena_distances: np.ndarray, reference_distances: np.ndarray) -> np.ndarray` (shape `(99, 2)`: arena quantile value, reference quantile value); `apply_quantile_map(distances: np.ndarray, qmap: np.ndarray) -> np.ndarray`; `fit_all_arenas(df: pd.DataFrame) -> dict[str, np.ndarray]`; CLI `python3 v2/goalies/rink_adjust.py` writing `data/generated/goalies/arena_adjustments.csv` and rewriting each `shots_<season>.csv` with a `distance_adj` column appended. P3 consumes `distance_adj`.
- Method (from spec): for each arena, quantile-map that arena's recorded shot distances onto the pooled distribution of all shots recorded at OTHER arenas. Fit on all five seasons pooled.

- [ ] **Step 1: Write the failing tests**

```python
# v2/goalies/tests/test_rink_adjust.py
import numpy as np
import pandas as pd
import pytest

from v2.goalies.rink_adjust import apply_quantile_map, fit_all_arenas, fit_quantile_map


def test_quantile_map_corrects_scaled_bias():
    rng = np.random.default_rng(7)
    reference = rng.uniform(5, 65, 20000)
    arena = reference[:5000] * 0.8          # arena records everything 20% short
    qmap = fit_quantile_map(arena, reference)
    adjusted = apply_quantile_map(arena, qmap)
    assert adjusted.mean() == pytest.approx(reference[:5000].mean(), rel=0.02)


def test_unbiased_arena_is_roughly_identity():
    rng = np.random.default_rng(7)
    reference = rng.uniform(5, 65, 20000)
    arena = rng.uniform(5, 65, 5000)
    qmap = fit_quantile_map(arena, reference)
    adjusted = apply_quantile_map(arena, qmap)
    assert np.abs(adjusted - arena).mean() < 1.5


def test_fit_all_arenas_keys_and_leave_one_out():
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "home_abbrev": ["AAA"] * 1000 + ["BBB"] * 1000,
        "distance": np.concatenate([rng.uniform(5, 65, 1000) * 0.8,
                                    rng.uniform(5, 65, 1000)]),
    })
    maps = fit_all_arenas(df)
    assert set(maps) == {"AAA", "BBB"}
    adj = apply_quantile_map(df[df.home_abbrev == "AAA"]["distance"].to_numpy(), maps["AAA"])
    # AAA's short-recorded distances stretch back toward the unbiased reference
    assert adj.mean() > df[df.home_abbrev == "AAA"]["distance"].mean() * 1.1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest v2/goalies/tests/test_rink_adjust.py -v`
Expected: FAIL — `ModuleNotFoundError` (rink_adjust missing)

- [ ] **Step 3: Write the implementation**

```python
# v2/goalies/rink_adjust.py
"""Arena scorer-bias correction via distance quantile mapping.

Each arena's recorded shot-distance distribution is mapped onto the pooled
distribution of shots recorded at all OTHER arenas (leave-one-out reference).
This is the load-bearing correction for every downstream repeatability claim.

Usage: python3 v2/goalies/rink_adjust.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

QUANTILES = np.linspace(0.01, 0.99, 99)
ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"


def fit_quantile_map(arena_distances: np.ndarray, reference_distances: np.ndarray) -> np.ndarray:
    a_q = np.quantile(arena_distances, QUANTILES)
    r_q = np.quantile(reference_distances, QUANTILES)
    return np.column_stack([a_q, r_q])


def apply_quantile_map(distances: np.ndarray, qmap: np.ndarray) -> np.ndarray:
    return np.interp(distances, qmap[:, 0], qmap[:, 1])


def fit_all_arenas(df: pd.DataFrame) -> dict[str, np.ndarray]:
    maps = {}
    for arena in sorted(df["home_abbrev"].unique()):
        at_arena = df.loc[df["home_abbrev"] == arena, "distance"].to_numpy()
        elsewhere = df.loc[df["home_abbrev"] != arena, "distance"].to_numpy()
        maps[arena] = fit_quantile_map(at_arena, elsewhere)
    return maps


def main() -> None:
    files = sorted(GEN.glob("shots_*.csv"))
    pooled = pd.concat([pd.read_csv(f, usecols=["home_abbrev", "distance"]) for f in files])
    maps = fit_all_arenas(pooled)

    long = [{"arena": a, "q": q, "arena_dist": row[0], "ref_dist": row[1]}
            for a, m in maps.items() for q, row in zip(QUANTILES, m)]
    pd.DataFrame(long).to_csv(GEN / "arena_adjustments.csv", index=False)

    for f in files:
        df = pd.read_csv(f)
        df["distance_adj"] = [
            float(apply_quantile_map(np.array([d]), maps[a])[0])
            for a, d in zip(df["home_abbrev"], df["distance"])
        ]
        df.to_csv(f, index=False)
        shift = (df["distance_adj"] - df["distance"]).abs().mean()
        print(f"{f.name}: mean |adjustment| = {shift:.2f} ft")


if __name__ == "__main__":
    main()
```

Performance note: if the per-row loop in `main` is slow (5 seasons × ~100k rows), vectorize per arena: `for a, g in df.groupby("home_abbrev"): df.loc[g.index, "distance_adj"] = apply_quantile_map(g["distance"].to_numpy(), maps[a])` — same result, one interp call per arena.

- [ ] **Step 4: Run tests, then run the adjustment**

Run: `python3 -m pytest v2/goalies/tests/test_rink_adjust.py -v` — 3 PASS.

```bash
python3 v2/goalies/rink_adjust.py
```

Expected: 32 arenas in `arena_adjustments.csv`; mean |adjustment| typically 0.5–3 ft per season file; no arena should shift its mean by more than ~6 ft (if one does, print its per-quantile table and eyeball before accepting — it may be real, MSG-scale bias).

- [ ] **Step 5: Commit**

```bash
git add v2/goalies/rink_adjust.py v2/goalies/tests/test_rink_adjust.py
git commit -m "feat(goalies): leave-one-out arena distance quantile adjustment"
```

---

### Task 8: Foundation verification report

**Files:**
- Create: `v2/goalies/verify_foundation.py`
- Test: none (report script; all computation it uses is already tested)

**Interfaces:**
- Consumes: `shots_<season>.csv` with `distance_adj` (Tasks 6–7).
- Produces: `data/generated/goalies/foundation_report.txt` — the P0–P2 exit artifact oiler reviews before P3 planning begins.

- [ ] **Step 1: Write the report script**

```python
# v2/goalies/verify_foundation.py
"""Cross-season sanity report for the goalie-shot foundation (P0-P2 exit gate).

Usage: python3 v2/goalies/verify_foundation.py
"""

from pathlib import Path

import pandas as pd

GEN = Path(__file__).resolve().parent.parent.parent / "data" / "generated" / "goalies"

lines = []
for f in sorted(GEN.glob("shots_*.csv")):
    df = pd.read_csv(f)
    saves = df[(df["on_net"]) & (~df["is_goal"])]
    lines.append(
        f"{f.stem}: shots={len(df)} goalies={df['goalie_id'].nunique()} "
        f"goals={int(df['is_goal'].sum())} "
        f"sv%={1 - df['is_goal'].sum() / max(df['on_net'].sum(), 1):.4f} "
        f"freeze%={saves['froze'].mean():.3f} rebound%={saves['rebound_generated'].mean():.3f} "
        f"EV/PP/SH={df['strength'].value_counts(normalize=True).round(3).to_dict()} "
        f"arenas={df['home_abbrev'].nunique()} "
        f"mean|adj|={(df['distance_adj'] - df['distance']).abs().mean():.2f}ft"
    )
report = "\n".join(lines)
print(report)
(GEN / "foundation_report.txt").write_text(report + "\n")
```

- [ ] **Step 2: Run it and check the sanity anchors**

Run: `python3 v2/goalies/verify_foundation.py`
Expected anchors (STOP and investigate if violated): all-situations sv% between .888 and .912 per season (league save% has been ~.897–.905 in this window); freeze% between 0.30 and 0.55; rebound% between 0.05 and 0.15; arenas = 32 for 2021 onward; EV share of shots ≈ 0.78–0.85.

- [ ] **Step 3: Run the FULL test suite**

Run: `python3 -m pytest v2/ -v`
Expected: all green (new goalie tests + all existing browser/competition/orchestrator tests).

- [ ] **Step 4: Commit**

```bash
git add v2/goalies/verify_foundation.py
git commit -m "feat(goalies): P0-P2 foundation verification report"
```

---

## After this plan

P3 (difficulty model + IRLS solver + goalie terms) gets its own plan, written after oiler reviews `foundation_report.txt` — its feature set depends on what the foundation data actually shows (e.g., freeze-rate base rates, strength-state shot mixes). P4–P6 follow the P3 phase gate per the spec.
