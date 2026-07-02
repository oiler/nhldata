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


def test_below_range_inputs_preserve_ordering_and_spacing():
    rng = np.random.default_rng(7)
    reference = rng.uniform(10, 65, 20000)
    arena = rng.uniform(10, 65, 5000)
    qmap = fit_quantile_map(arena, reference)
    a_q, r_q = qmap[:, 0], qmap[:, 1]
    assert a_q[0] == pytest.approx(10, abs=1.0)  # q01 of a uniform(10, 65) fit is ~10

    adjusted = apply_quantile_map(np.array([1.0, 4.0]), qmap)
    # spacing between the two below-range inputs is preserved exactly
    assert adjusted[1] - adjusted[0] == pytest.approx(3.0)
    # both shift by the same endpoint delta rather than collapsing to a_q/r_q[0]
    expected_delta = r_q[0] - a_q[0]
    assert adjusted[0] == pytest.approx(1.0 + expected_delta, rel=0.05)
    assert adjusted[1] == pytest.approx(4.0 + expected_delta, rel=0.05)


def test_above_range_inputs_preserve_ordering():
    rng = np.random.default_rng(7)
    reference = rng.uniform(10, 65, 20000)
    arena = rng.uniform(10, 65, 5000)
    qmap = fit_quantile_map(arena, reference)
    a_q, r_q = qmap[:, 0], qmap[:, 1]

    adjusted = apply_quantile_map(np.array([a_q[-1] + 1.0, a_q[-1] + 5.0]), qmap)
    expected_delta = r_q[-1] - a_q[-1]
    assert adjusted[1] - adjusted[0] == pytest.approx(4.0)
    assert adjusted[0] == pytest.approx(a_q[-1] + 1.0 + expected_delta, rel=0.05)


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
