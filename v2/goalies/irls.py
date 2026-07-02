"""Penalized logistic regression via Newton-IRLS, numpy only.

Generalized ridge: per-coefficient L2 penalties and prior centers, which
sklearn's uniform-penalty LogisticRegression cannot express (spec decision).
Objective: -loglik + 0.5 * sum(penalty_j * (beta_j - center_j)^2).
"""

from dataclasses import dataclass

import numpy as np

ETA_CLIP = 30.0


@dataclass
class FitResult:
    coef: np.ndarray
    se: np.ndarray
    converged: bool
    n_iter: int
    objective: float


def predict_proba(X: np.ndarray, coef: np.ndarray) -> np.ndarray:
    eta = np.clip(X @ coef, -ETA_CLIP, ETA_CLIP)
    return 1.0 / (1.0 + np.exp(-eta))


def _objective(X, y, beta, penalty, center) -> float:
    eta = np.clip(X @ beta, -ETA_CLIP, ETA_CLIP)
    loglik = float(y @ eta - np.logaddexp(0.0, eta).sum())
    return -loglik + 0.5 * float(penalty @ (beta - center) ** 2)


def fit_penalized_logistic(X, y, penalty, prior_center=None,
                           max_iter: int = 50, tol: float = 1e-8) -> FitResult:
    """penalty must be > 0 component-wise: diag(penalty) is the PD floor of H,
    and exact zeros combined with separation could make H singular."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    penalty = np.asarray(penalty, dtype=float)
    center = np.zeros(X.shape[1]) if prior_center is None else np.asarray(prior_center, dtype=float)

    beta = center.copy()
    obj = _objective(X, y, beta, penalty, center)
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        mu = predict_proba(X, beta)
        w = mu * (1.0 - mu)
        grad = X.T @ (y - mu) - penalty * (beta - center)
        H = X.T @ (X * w[:, None]) + np.diag(penalty)
        step = np.linalg.solve(H, grad)

        scale = 1.0
        accepted = False
        for _ in range(10):  # step-halving keeps the objective monotone
            candidate = beta + scale * step
            cand_obj = _objective(X, y, candidate, penalty, center)
            if cand_obj <= obj + 1e-12:
                accepted = True
                break
            scale *= 0.5
        if not accepted:  # no non-worsening step found; stop without moving
            break
        beta = candidate
        if np.abs(scale * step).max() < tol or abs(obj - cand_obj) < tol:
            obj = cand_obj
            converged = True
            break
        obj = cand_obj

    # spec: se from the Hessian at the optimum, so recompute at the final beta
    mu = predict_proba(X, beta)
    w = mu * (1.0 - mu)
    H = X.T @ (X * w[:, None]) + np.diag(penalty)
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    return FitResult(coef=beta, se=se, converged=converged, n_iter=it, objective=obj)
