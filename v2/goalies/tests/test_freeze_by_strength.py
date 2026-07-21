import numpy as np
import pandas as pd

from v2.goalies.freeze_by_strength import freeze_strength_design


def test_design_matrix_interactions():
    saves = pd.DataFrame({
        "froze": [1.0, 1.0, 1.0, 0.0],
        "strength": ["EV", "SH", "PP", "SH"],
    })
    X = freeze_strength_design(saves)
    # columns: froze, froze*SH, froze*PP
    assert X.shape == (4, 3)
    np.testing.assert_array_equal(X[0], [1.0, 0.0, 0.0])   # EV freeze: main only
    np.testing.assert_array_equal(X[1], [1.0, 1.0, 0.0])   # PK freeze
    np.testing.assert_array_equal(X[2], [1.0, 0.0, 1.0])   # PP freeze
    np.testing.assert_array_equal(X[3], [0.0, 0.0, 0.0])   # non-freeze: all zero
