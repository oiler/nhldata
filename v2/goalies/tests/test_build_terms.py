import numpy as np
import pandas as pd

from v2.goalies.build_terms import chain_seasons
from v2.goalies.tests.test_difficulty import _synthetic_shots


def test_chain_seasons_two_seasons_carry_priors():
    s1 = _synthetic_shots(1500, seed=1)
    s2 = _synthetic_shots(1500, seed=2)
    out = chain_seasons({"2021": s1, "2022": s2}, "goal")
    assert set(out) == {"2021", "2022"}
    t2 = out["2022"].set_index("goalie_id")
    assert {"term", "se", "n_shots", "term_indep", "se_indep"} <= set(t2.columns)
    # chained 2022 estimate for the bad goalie sits closer to his 2021 term
    # than the independent one does to zero-centered shrinkage alone
    t1 = out["2021"].set_index("goalie_id")
    assert abs(t2.loc[901, "term"] - t1.loc[901, "term"]) < abs(t2.loc[901, "term_indep"] - 0.0)
    # independent variant must not depend on season order (no chaining leakage)
    solo = chain_seasons({"2022": s2}, "goal")["2022"].set_index("goalie_id")
    assert np.isclose(solo.loc[901, "term_indep"], t2.loc[901, "term_indep"])
