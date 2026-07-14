import numpy as np
import pandas as pd
import pytest

from v2.goalies.game_ledger import ledger_rows


def test_ledger_math():
    shots = pd.DataFrame({
        "season": [2023] * 4, "game_id": [1] * 4, "goalie_id": [900] * 4,
        "is_goal": [True, False, False, False],
    })
    xg = np.array([0.5, 0.5, 0.1, 0.1])
    lev = np.array([0.2, 0.2, 0.1, 0.1])
    r = ledger_rows(shots, xg, lev).iloc[0]
    assert r["ga"] == 1 and r["xga"] == pytest.approx(1.2)
    assert r["gsax_game"] == pytest.approx(0.2)
    var = 2 * 0.5 * 0.5 + 2 * 0.1 * 0.9
    assert r["perf_z"] == pytest.approx(0.2 / np.sqrt(var))
    # lev_value: 0.2*(0.5-1) + 0.2*(0.5-0) + 0.1*(0.1-0)*2
    assert r["lev_value"] == pytest.approx(-0.1 + 0.1 + 0.02)


def test_ledger_zero_variance_guard():
    shots = pd.DataFrame({"season": [2023], "game_id": [1], "goalie_id": [900],
                          "is_goal": [False]})
    r = ledger_rows(shots, np.array([0.0]), np.array([0.0])).iloc[0]
    assert np.isnan(r["perf_z"])
