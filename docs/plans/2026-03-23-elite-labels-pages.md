# Elite Labels — Team / Skaters / Game Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the "vs Top Fwd %" and "vs Top Def %" column headers on the Team, Skaters, and Game pages to "vs Elite Fwd %" and "vs Elite Def %" to match the elite classification model that now backs those values.

**Architecture:** The underlying data in `competition.pct_vs_top_fwd` and `competition.pct_vs_top_def` was already overwritten by the elite model during `build_league_db.py` (via `recompute_pct_vs_elite_fwd` and `recompute_pct_vs_elite_def`). The elites page already uses the correct labels. This plan is purely 6 label renames across 3 page files — no SQL, no logic, no new columns, no DB changes.

**Tech Stack:** Python, Plotly Dash

**Design doc:** `docs/elite-classification-model.md`

**Git:** Do not commit. oiler handles all git operations manually.

---

## File Map

| File | Change |
|------|--------|
| `v2/browser/pages/team.py:92-93` | Rename 2 column headers |
| `v2/browser/pages/skaters.py:142-143` | Rename 2 column headers |
| `v2/browser/pages/game.py:77-78` | Rename 2 column headers |

No test files need to change — the existing smoke tests verify page registration, and CLAUDE.md policy is "test computations, not callbacks." Label renames have no computation to test.

---

### Task 1: Rename labels in `team.py`

**Files:**
- Modify: `v2/browser/pages/team.py:92-93`

The `_make_position_table` function defines column headers. Lines 92-93 currently read "vs Top Fwd %" and "vs Top Def %".

- [ ] **Step 1: Apply the rename**

In `v2/browser/pages/team.py`, inside `_make_position_table`, change:

```python
        {"name": "vs Top Fwd %", "id": "avg_pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Top Def %", "id": "avg_pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
```

to:

```python
        {"name": "vs Elite Fwd %", "id": "avg_pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Elite Def %", "id": "avg_pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
```

- [ ] **Step 2: Run the test suite**

Run: `python -m pytest v2/ -v`

Expected: All 110 tests PASS, no regressions.

---

### Task 2: Rename labels in `skaters.py`

**Files:**
- Modify: `v2/browser/pages/skaters.py:142-143`

The `update_skaters` callback builds the DataTable inline. Lines 142-143 currently read "vs Top Fwd %" and "vs Top Def %".

- [ ] **Step 1: Apply the rename**

In `v2/browser/pages/skaters.py`, inside the `columns` list in `update_skaters`, change:

```python
        {"name": "vs Top Fwd %", "id": "avg_pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Top Def %", "id": "avg_pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
```

to:

```python
        {"name": "vs Elite Fwd %", "id": "avg_pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Elite Def %", "id": "avg_pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
```

- [ ] **Step 2: Run the test suite**

Run: `python -m pytest v2/ -v`

Expected: All 110 tests PASS.

---

### Task 3: Rename labels in `game.py`

**Files:**
- Modify: `v2/browser/pages/game.py:77-78`

The `_make_position_table` function defines column headers. Lines 77-78 currently read "vs Top Fwd %" and "vs Top Def %".

- [ ] **Step 1: Apply the rename**

In `v2/browser/pages/game.py`, inside `_make_position_table`, change:

```python
        {"name": "vs Top Fwd %", "id": "pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Top Def %", "id": "pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
```

to:

```python
        {"name": "vs Elite Fwd %", "id": "pct_vs_top_fwd", "type": "numeric", "format": FormatTemplate.percentage(2)},
        {"name": "vs Elite Def %", "id": "pct_vs_top_def", "type": "numeric", "format": FormatTemplate.percentage(2)},
```

- [ ] **Step 2: Run the full test suite one final time**

Run: `python -m pytest v2/ -v`

Expected: All 110 tests PASS.
