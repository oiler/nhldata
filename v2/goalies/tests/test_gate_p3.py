import numpy as np
import pandas as pd
import pytest

from v2.goalies.gate_p3 import common_population_r, signal_share, year_pair_r


def test_signal_share_zero_when_noise_explains_all():
    terms = pd.DataFrame({"term_indep": [0.1, -0.1], "se_indep": [1.0, 1.0]})
    assert signal_share(terms) == 0.0


def test_signal_share_high_when_spread_exceeds_noise():
    rng = np.random.default_rng(5)
    terms = pd.DataFrame({"term_indep": rng.normal(0, 1.0, 200),
                          "se_indep": np.full(200, 0.1)})
    assert signal_share(terms) > 0.95


def test_year_pair_r_filters_and_correlates():
    a = pd.DataFrame({"goalie_id": [1, 2, 3, 4], "term_indep": [0.4, 0.2, -0.2, -0.4],
                      "n_shots": [2000, 2000, 2000, 500]})
    b = pd.DataFrame({"goalie_id": [1, 2, 3, 5], "term_indep": [0.3, 0.1, -0.3, 0.9],
                      "n_shots": [2000, 2000, 2000, 2000]})
    r, n = year_pair_r(a, b, "term_indep")
    assert n == 3                       # goalie 4 under min_shots, goalie 5 unmatched
    assert r == pytest.approx(1.0, abs=0.05)


def test_common_population_r_uses_gsax_shots_for_both_metrics():
    # goalies 1-5 qualify in both seasons; goalie 6 has enough gsax shots in
    # season a but drops below min_shots in season b; goalie 7 is missing
    # entirely from season b (unmatched). terms frames carry no shots column
    # at all, so a correct implementation can only filter via gsax "shots".
    ids = [1, 2, 3, 4, 5]
    terms_a = pd.DataFrame({
        "goalie_id": ids + [6, 7],
        "term_indep": [0.10, 0.20, 0.30, 0.40, 0.50, 0.15, 0.99],
    })
    terms_b = pd.DataFrame({
        "goalie_id": ids + [6],
        "term_indep": [0.12, 0.22, 0.29, 0.41, 0.52, 0.85],
    })
    gsax_a = pd.DataFrame({
        "goalie_id": ids + [6, 7],
        "shots": [1200, 1300, 1400, 1500, 1600, 1100, 1700],
        "gsax_per100": [1.0, 2.0, 3.0, 4.0, 5.0, 2.5, 9.9],
    })
    gsax_b = pd.DataFrame({
        "goalie_id": ids + [6],
        "shots": [1250, 1350, 1450, 1550, 1650, 400],  # goalie 6 under min_shots in b
        "gsax_per100": [1.5, 1.8, 3.5, 3.6, 5.6, 8.0],
    })

    r_goal, r_gsax, n = common_population_r(terms_a, terms_b, gsax_a, gsax_b)

    assert n == 5  # goalie 6 dropped (shots<1000 in b), goalie 7 dropped (unmatched in b)
    expected_goal_r = float(np.corrcoef(
        [0.10, 0.20, 0.30, 0.40, 0.50], [0.12, 0.22, 0.29, 0.41, 0.52])[0, 1])
    expected_gsax_r = float(np.corrcoef(
        [1.0, 2.0, 3.0, 4.0, 5.0], [1.5, 1.8, 3.5, 3.6, 5.6])[0, 1])
    assert r_goal == pytest.approx(expected_goal_r)
    assert r_gsax == pytest.approx(expected_gsax_r)
    assert r_goal != pytest.approx(r_gsax, abs=0.01)  # independently computed, not aliased
