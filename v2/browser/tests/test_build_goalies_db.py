# v2/browser/tests/test_build_goalies_db.py
"""Tests for build_goalies_db.build_goalie_seasons() and freeze_percentile()."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_goalies_db import build_goalie_seasons, freeze_percentile, resolve_name


def _gg():
    return pd.DataFrame({
        "season": [2025] * 3, "game_id": [1, 2, 3], "goalie_id": [9, 9, 9],
        "team_abbrev": ["EDM", "EDM", "CGY"], "opp_abbrev": ["CGY", "VAN", "EDM"],
        "game_date": ["2025-10-01", "2025-10-03", "2025-11-01"], "toi_s": [3600, 3000, 3600],
    })


def _gsax():
    return pd.DataFrame({"goalie_id": [9], "shots": [90], "xga": [7.5], "ga": [6],
                         "gsax": [1.5], "gsax_per100": [1.67]})


def _shots():
    rows = []
    for froze in ([1.0] * 6 + [0.0] * 14):
        rows.append({"season": 2025, "goalie_id": 9, "on_net": True,
                     "is_goal": False, "froze": froze})
    rows.append({"season": 2025, "goalie_id": 9, "on_net": True, "is_goal": True,
                 "froze": np.nan})
    return pd.DataFrame(rows)


def _terms():
    return pd.DataFrame({"goalie_id": [9, 9], "layer": ["rebound", "goal"],
                         "term_indep": [0.25, -0.1], "n_shots": [800, 900]})


def _ledger():
    return pd.DataFrame({
        "season": [2025] * 3, "game_id": [1, 2, 3], "goalie_id": [9] * 3,
        "perf_z": [1.0, -0.5, np.nan], "difficulty_pct": [40.0, 60.0, np.nan],
        "lev_value": [0.1, -0.05, 0.02],
    })


def test_build_goalie_seasons_aggregates():
    row = build_goalie_seasons(_gg(), _gsax(), _shots(), _terms(), _ledger()).iloc[0]
    assert row["teams"] == "EDM/CGY"                      # first-appearance order
    assert row["gp"] == 3 and row["toi_s"] == 10200
    assert row["freeze_rate"] == pytest.approx(0.3)       # 6/20 saves
    assert row["rebound_term_indep"] == pytest.approx(-0.25)   # oriented: negative here
    assert row["mean_perf_z"] == pytest.approx(0.25)      # NaN dropped
    assert row["mean_difficulty_pct"] == pytest.approx(50.0)
    assert row["lev_value_sum"] == pytest.approx(0.07)
    assert row["gsax"] == pytest.approx(1.5)


def test_freeze_percentile_floor_and_rank():
    # freeze_percentile returns a Series indexed like `rates` (its default
    # RangeIndex here: 0->goalie1, 1->goalie2, 2->goalie3, 3->goalie4).
    rates = pd.DataFrame({
        "goalie_id": [1, 2, 3, 4],
        "freeze_rate": [0.25, 0.30, 0.35, 0.99],
        "n_saves": [800, 900, 1000, 100],      # goalie 4 (index 3) under floor
    })
    pct = freeze_percentile(rates)
    assert pct[2] > pct[1] > pct[0]            # ordering among eligible goalies
    assert np.isnan(pct[3])                    # below the 500-save floor -> NaN
    assert pct[2] == pytest.approx(100.0)      # highest eligible rate -> top percentile


def test_resolve_name_cross_season_fallback(tmp_path):
    """Test resolve_name finds player JSON across multiple seasons."""
    # Create 2022 players dir with goalie 77's data
    players_2022 = tmp_path / "2022" / "players"
    players_2022.mkdir(parents=True)
    (players_2022 / "77.json").write_text(
        '{"firstName":{"default":"Igor"},"lastName":{"default":"Shesterkin"}}'
    )

    # Create 2021 players dir but leave it empty (no 77 there)
    players_2021 = tmp_path / "2021" / "players"
    players_2021.mkdir(parents=True)

    # Resolve with 2021 first in search order: should find it via 2022 fallback
    name = resolve_name(77, ("2021", "2022"), tmp_path)
    assert name == "Igor Shesterkin"

    # Resolve nonexistent goalie: should fallback to generic
    name = resolve_name(88, ("2021", "2022"), tmp_path)
    assert name == "Goalie 88"


@pytest.mark.requires_data
def test_5v5_toi_is_strictly_less_than_all_situations_toi():
    """A goalie who dressed for more than one game always plays some non-5v5
    hockey, so the 5v5 denominator must be smaller. Equality means the
    cut-aware read silently fell back to boxscore TOI — the exact regression
    this change exists to prevent, and one that would show up on every row.

    Single-appearance goalies are excluded because equality is legitimate for
    them: an emergency backup's whole stint can fall inside 5v5 play. Three
    such rows exist (Berlin 2022 146s, Alexander 2022 70s, 8482668 2024 283s),
    each confirmed against goalie_toi_<season>.csv as timeline-derived rather
    than fallen back.
    """
    import sqlite3
    from pathlib import Path
    db = Path(__file__).resolve().parents[3] / "data" / "generated" / "browser" / "goalies.db"
    conn = sqlite3.connect(str(db))
    bad = conn.execute("""
        SELECT COUNT(*) FROM goalie_seasons a
        JOIN goalie_seasons b
          ON a.season = b.season AND a.goalie_id = b.goalie_id
        WHERE a.situation = '5v5' AND b.situation = 'all'
          AND b.gp > 1 AND a.toi_s >= b.toi_s
    """).fetchone()[0]
    conn.close()
    assert bad == 0, f"{bad} goalie-seasons have 5v5 TOI >= all-situations TOI"
