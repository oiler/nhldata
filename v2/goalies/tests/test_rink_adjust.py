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
