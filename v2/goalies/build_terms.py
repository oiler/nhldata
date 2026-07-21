"""Fit all difficulty layers per season; write chained + independent goalie terms.

Chained: each season's goalie priors center on the previous season's chained
terms (McCurdy-style information carry-over) — used for the eventual talent
estimates. Independent: zero-centered per-season fits — REQUIRED for the gate's
repeatability correlations, which chained priors would mechanically inflate.

Usage: python3 v2/goalies/build_terms.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from v2.goalies.difficulty import LAYERS, fit_layer  # noqa: E402
from v2.goalies.cut import gen_dir, load_shots, parse_situation  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "data" / "generated" / "goalies"
SEASONS = ("2021", "2022", "2023", "2024", "2025")


def chain_seasons(season_dfs: dict[str, pd.DataFrame], layer: str,
                  goalie_prior_shots: float = 1000.0) -> dict[str, pd.DataFrame]:
    out = {}
    prior = None
    for season in sorted(season_dfs):
        df = season_dfs[season]
        chained = fit_layer(df, layer, goalie_prior_shots=goalie_prior_shots,
                            prior_centers=prior)
        indep = fit_layer(df, layer, goalie_prior_shots=goalie_prior_shots)
        merged = chained.goalie_terms.merge(
            indep.goalie_terms[["goalie_id", "term", "se"]].rename(
                columns={"term": "term_indep", "se": "se_indep"}),
            on="goalie_id")
        out[season] = merged
        prior = dict(zip(merged["goalie_id"], merged["term"]))
    return out


def main() -> None:
    situation = parse_situation()
    out = gen_dir(situation)
    out.mkdir(parents=True, exist_ok=True)
    season_dfs = {s: load_shots(s, situation) for s in SEASONS}
    per_season_terms = {s: [] for s in SEASONS}
    structure_rows = {s: [] for s in SEASONS}

    for layer in LAYERS:
        chained = chain_seasons(season_dfs, layer)
        for season, terms in chained.items():
            per_season_terms[season].append(terms.assign(layer=layer))
        for season, df in season_dfs.items():
            fit = fit_layer(df, layer, include_goalies=False)
            structure_rows[season].extend(
                {"layer": layer, "feature": f, "coef": c}
                for f, c in fit.structure.items())

    for season in SEASONS:
        pd.concat(per_season_terms[season], ignore_index=True)[
            ["goalie_id", "layer", "term", "se", "n_shots", "term_indep", "se_indep"]
        ].to_csv(out / f"goalie_terms_{season}.csv", index=False)
        pd.DataFrame(structure_rows[season]).to_csv(
            out / f"structure_coefs_{season}.csv", index=False)
        print(f"{season}: terms + structure written")


if __name__ == "__main__":
    main()
