import numpy as np
import pandas as pd
import pytest

from v2.goalies.gate_p3 import signal_share, year_pair_r


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
