# Teams Division & Conference Columns

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Division and Conference columns to the teams leaderboard DataTable.

**Architecture:** Add a hardcoded dict mapping all 32 team abbreviations to their division in `teams.py`. Conference is derived from division. Map onto the DataFrame before building the DataTable. Place Div and Conf columns after Team so users can filter/sort by them.

**Tech Stack:** Python dict, pandas `map()`, Dash DataTable.

---

### Task 1: Add division/conference mapping and columns to teams.py

**Files:**
- Modify: `v2/browser/pages/teams.py`

---

**Step 1: Add division dict and conference lookup after the SQL constants (after line 31)**

```python
_DIVISIONS = {
    "BOS": "ATL", "BUF": "ATL", "DET": "ATL", "FLA": "ATL",
    "MTL": "ATL", "OTT": "ATL", "TBL": "ATL", "TOR": "ATL",
    "CAR": "MET", "CBJ": "MET", "NJD": "MET", "NYI": "MET",
    "NYR": "MET", "PHI": "MET", "PIT": "MET", "WSH": "MET",
    "CHI": "CEN", "COL": "CEN", "DAL": "CEN", "MIN": "CEN",
    "NSH": "CEN", "STL": "CEN", "WPG": "CEN", "UTA": "CEN",
    "ANA": "PAC", "CGY": "PAC", "EDM": "PAC", "LAK": "PAC",
    "SJS": "PAC", "SEA": "PAC", "VAN": "PAC", "VGK": "PAC",
}
_CONFERENCES = {"ATL": "East", "MET": "East", "CEN": "West", "PAC": "West"}
```

Note: Utah (UTA) moved to Central division for 2024-2025 season (formerly Arizona Coyotes).

**Step 2: Map division and conference onto the DataFrame**

After `df = df.reset_index()` and before `df = df.sort_values(...)` (around line 150), add:

```python
    df["division"] = df["team"].map(_DIVISIONS)
    df["conference"] = df["division"].map(_CONFERENCES)
```

**Step 3: Add Div and Conf columns to the DataTable definition**

Insert after the Team column and before GP:

```python
        {"name": "Div",   "id": "division",   "filter_options": _ci},
        {"name": "Conf",  "id": "conference",  "filter_options": _ci},
```

Update `display_cols` to include the new columns after `team_link`:

```python
    display_cols = ["team_link", "division", "conference", "gp", "pct", "rw", "ppi_plus", "gd_5v5"]
```

---

### Task 2: Run tests and verify

```bash
cd /Users/jrf1039/files/projects/nhl && python -m pytest v2/ -v
```

Expected: All 68 tests pass.

**Manual verification:**

```bash
cd /Users/jrf1039/files/projects/nhl/v2/browser && python app.py
```

Open http://127.0.0.1:8050/teams — verify:
- Div column shows ATL/MET/CEN/PAC
- Conf column shows East/West
- All 32 teams have correct division assignments
- Filtering by division works (e.g., type "Atlantic")
- Filtering by conference works (e.g., type "East")
- Sorting by Div/Conf works
