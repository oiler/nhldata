import numpy as np
import pytest

from v2.goalies.irls import FitResult, fit_penalized_logistic, predict_proba


def _simulate(n=20000, beta=(0.4, -1.0, 0.25), seed=3):
    rng = np.random.default_rng(seed)
    X = np.column_stack([np.ones(n), rng.normal(0, 1, n), rng.normal(0, 1, n)])
    p = 1 / (1 + np.exp(-(X @ np.array(beta))))
    return X, (rng.uniform(size=n) < p).astype(float)


def test_recovers_known_coefficients_with_tiny_penalty():
    X, y = _simulate()
    fit = fit_penalized_logistic(X, y, penalty=np.full(3, 1e-6))
    assert fit.converged
    assert fit.coef == pytest.approx([0.4, -1.0, 0.25], abs=0.08)


def test_gradient_is_zero_at_optimum():
    X, y = _simulate(n=5000)
    pen = np.array([1e-6, 5.0, 50.0])
    fit = fit_penalized_logistic(X, y, penalty=pen)
    mu = predict_proba(X, fit.coef)
    grad = X.T @ (y - mu) - pen * fit.coef
    assert np.abs(grad).max() < 1e-4


def test_penalty_shrinks_toward_center():
    X, y = _simulate(n=5000)
    center = np.array([0.0, 0.5, 0.0])
    small = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 1.0, 1e-6]),
                                   prior_center=center)
    huge = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 1e9, 1e-6]),
                                  prior_center=center)
    assert huge.coef[1] == pytest.approx(0.5, abs=1e-3)          # pinned to center
    assert abs(small.coef[1] - 0.5) > abs(huge.coef[1] - 0.5)    # monotone pull


def test_separation_stays_finite():
    # a column perfectly predicting y would diverge unpenalized; penalty keeps it finite
    n = 1000
    X = np.column_stack([np.ones(n), np.repeat([0.0, 1.0], n // 2)])
    y = np.repeat([0.0, 1.0], n // 2)
    fit = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 2.0]))
    assert fit.converged and np.isfinite(fit.coef).all() and np.isfinite(fit.se).all()


def test_se_shrinks_with_penalty():
    X, y = _simulate(n=5000)
    loose = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 1e-6, 1e-6]))
    tight = fit_penalized_logistic(X, y, penalty=np.array([1e-6, 100.0, 1e-6]))
    assert tight.se[1] < loose.se[1]
