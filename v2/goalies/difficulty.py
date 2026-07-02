"""Layered difficulty models with per-goalie regularized terms (mini-Magnus).

Each layer is a penalized logistic regression on structure features plus a
goalie one-hot block. Goalie terms are shrunk toward prior centers with
penalty worth `goalie_prior_shots` league-average shots of evidence.
Raw terms are on the logit of the modeled outcome: positive `goal` term =
more goals allowed (bad); downstream reporting negates where positive=good.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from v2.goalies.features import STRUCTURE_COLS, build_features
from v2.goalies.irls import FitResult, fit_penalized_logistic, predict_proba

LAYERS = {
    "onnet": {"y": "on_net", "subset": "all"},
    "freeze": {"y": "froze", "subset": "saves"},
    "goal": {"y": "is_goal", "subset": "onnet"},
    "rebound": {"y": "rebound_generated", "subset": "saves"},
}


@dataclass
class LayerFit:
    goalie_terms: pd.DataFrame
    structure: pd.Series
    fit: FitResult
    base_rate: float


def layer_frame(df: pd.DataFrame, layer: str) -> pd.DataFrame:
    subset = LAYERS[layer]["subset"]
    if subset == "onnet":
        df = df[df["on_net"]]
    elif subset == "saves":
        df = df[df["on_net"] & ~df["is_goal"]]
    return df[df[LAYERS[layer]["y"]].notna()]


def fit_layer(df: pd.DataFrame, layer: str, *, goalie_prior_shots: float = 1000.0,
              structure_penalty: float = 1.0,
              prior_centers: dict[int, float] | None = None,
              include_goalies: bool = True) -> LayerFit:
    frame = layer_frame(df, layer)
    y = frame[LAYERS[layer]["y"]].to_numpy(dtype=float)
    X_struct = build_features(frame).to_numpy()
    base_rate = float(y.mean())

    n_struct = len(STRUCTURE_COLS)
    pen_struct = np.full(n_struct, structure_penalty)
    pen_struct[STRUCTURE_COLS.index("intercept")] = 1e-6

    if include_goalies:
        goalies = np.sort(frame["goalie_id"].unique())
        gidx = {g: i for i, g in enumerate(goalies)}
        G = np.zeros((len(frame), len(goalies)))
        G[np.arange(len(frame)), frame["goalie_id"].map(gidx).to_numpy()] = 1.0
        X = np.hstack([X_struct, G])
        lam_g = goalie_prior_shots * base_rate * (1.0 - base_rate)
        penalty = np.concatenate([pen_struct, np.full(len(goalies), lam_g)])
        centers = np.zeros(X.shape[1])
        if prior_centers:
            for g, c in prior_centers.items():
                if g in gidx:
                    centers[n_struct + gidx[g]] = c
    else:
        goalies = np.array([], dtype=int)
        X = X_struct
        penalty = pen_struct
        centers = np.zeros(X.shape[1])

    fit = fit_penalized_logistic(X, y, penalty, prior_center=centers)

    if include_goalies:
        counts = frame["goalie_id"].value_counts()
        terms = pd.DataFrame({
            "goalie_id": goalies,
            "term": fit.coef[n_struct:],
            "se": fit.se[n_struct:],
            "n_shots": [int(counts[g]) for g in goalies],
        })
    else:
        terms = pd.DataFrame(columns=["goalie_id", "term", "se", "n_shots"])

    structure = pd.Series(fit.coef[:n_struct], index=STRUCTURE_COLS)
    return LayerFit(goalie_terms=terms, structure=structure, fit=fit, base_rate=base_rate)


def predict_structure(df: pd.DataFrame, layer_fit: LayerFit) -> np.ndarray:
    """Probabilities from structure coefficients only — the goalie-blind view."""
    return predict_proba(build_features(df).to_numpy(), layer_fit.structure.to_numpy())
