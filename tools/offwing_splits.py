"""5v5 off-wing vs strong-side shot conversion splits.

Even-strength replication of Parnass (2016, PP-only) using public play-by-play:
unblocked 5v5 (situationCode 1551) offensive-zone shots, shooter handedness
joined from player-landing files. Off-wing = shot taken from the side of the
ice opposite the shooter's handedness, after rotating coordinates so every
shooter attacks toward +x.

Scope decisions (see docs/ideas/2026-05-10-shooters.md research summary):
- Blocked shots excluded: no shotType, recorded at block location.
- Tips/deflections/wraparounds etc. excluded: not aimed shots, locations
  unreliable. Core types only: wrist, snap, slap, backhand.
- O-zone shots only, so sign(xCoord) gives attack direction without relying
  on homeTeamDefendingSide semantics.

Usage: python3 tools/offwing_splits.py
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pandas as pd

# Season is the 4-digit start year from NHL_SEASON (default 2025).
_SEASON = os.environ.get("NHL_SEASON", "2025")
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / _SEASON
OUT_DIR = DATA_DIR / "generated" / "offwing"

NET_X = 89.0
SHOT_EVENTS = {"goal", "shot-on-goal", "missed-shot"}
FIVE_V_FIVE = "1551"
CORE_SHOT_TYPES = ("wrist", "snap", "slap", "backhand")
DISTANCE_BANDS = ((15, "00-15ft"), (30, "15-30ft"), (45, "30-45ft"), (math.inf, "45ft+"))


# --- geometry / classification --------------------------------------------------

def normalize_coords(x: float, y: float) -> tuple[float, float]:
    """Rotate 180 degrees when the shooter attacks -x, so attack is always +x."""
    return (-x, -y) if x < 0 else (x, y)


def shot_side(y_norm: float) -> str | None:
    """Side of the ice from the attacking shooter's perspective; +y is their left."""
    if y_norm > 0:
        return "left"
    if y_norm < 0:
        return "right"
    return None


def classify_wing(shoots: str, y_norm: float) -> str | None:
    side = shot_side(y_norm)
    if side is None:
        return None
    return "strong" if (shoots == "L") == (side == "left") else "off"


def shot_distance(x_norm: float, y_norm: float) -> float:
    return math.hypot(NET_X - x_norm, y_norm)


def shot_angle(x_norm: float, y_norm: float) -> float:
    """Absolute angle off the net's center line, degrees; >90 means behind the goal line."""
    return math.degrees(math.atan2(abs(y_norm), NET_X - x_norm))


def distance_band(dist: float) -> str:
    for limit, label in DISTANCE_BANDS:
        if dist < limit:
            return label
    raise AssertionError("unreachable")


def parse_time(mmss: str) -> int:
    """'MM:SS' time-in-period to seconds."""
    m, s = mmss.split(":")
    return int(m) * 60 + int(s)


# --- statistics -------------------------------------------------------------------

def two_prop_z(g1: int, n1: int, g2: int, n2: int) -> tuple[float, float]:
    """Two-proportion z-test. Returns (z, two-sided p)."""
    pooled = (g1 + g2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (g1 / n1 - g2 / n2) / se
    return z, math.erfc(abs(z) / math.sqrt(2))


def cmh_odds_ratio(strata) -> float:
    """Mantel-Haenszel pooled odds ratio.

    Each stratum is (off goals, off non-goals, strong goals, strong non-goals).
    """
    num = den = 0.0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n == 0:
            continue
        num += a * d / n
        den += b * c / n
    return num / den if den else float("nan")


def cmh_test(strata) -> tuple[float, float]:
    """Mantel-Haenszel chi-square (1 df, continuity-corrected). Returns (chi2, p)."""
    diff = var = 0.0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n < 2:
            continue
        diff += a - (a + b) * (a + c) / n
        var += (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
    if var == 0:
        return 0.0, 1.0
    chi2 = (abs(diff) - 0.5) ** 2 / var
    return chi2, math.erfc(math.sqrt(chi2 / 2))


# --- data loading -----------------------------------------------------------------

def load_handedness(players_dir: Path) -> dict[int, str]:
    out = {}
    for f in players_dir.glob("*.json"):
        sc = json.loads(f.read_text()).get("shootsCatches")
        if sc:
            out[int(f.stem)] = sc
    return out


def extract_shots(game: dict) -> list[dict]:
    """Unblocked 5v5 O-zone shot attempts by skaters, attack-normalized.

    Each shot also carries the nearest preceding same-period event that had
    coordinates and a timestamp (any type: faceoff, hit, shot, turnover...),
    with its coordinates rotated by the same flip as the shot — raw material
    for quick-release / cross-ice (one-timer-ish) proxies downstream.
    """
    positions = {rs["playerId"]: rs["positionCode"] for rs in game["rosterSpots"]}
    rows = []
    last_by_period: dict[int, tuple] = {}
    for play in game["plays"]:
        d = play.get("details", {})
        period = play["periodDescriptor"]["number"]
        t = parse_time(play["timeInPeriod"]) if "timeInPeriod" in play else None
        is_shot = (
            play["typeDescKey"] in SHOT_EVENTS
            and play.get("situationCode") == FIVE_V_FIVE
            and play["periodDescriptor"]["periodType"] in ("REG", "OT")
            and d.get("zoneCode") == "O"
            and d.get("xCoord") is not None
            and d.get("yCoord") is not None
        )
        if is_shot:
            x, y = d["xCoord"], d["yCoord"]
            shooter = d.get("shootingPlayerId") or d.get("scoringPlayerId")
            pos = positions.get(shooter)
            if pos is not None and pos != "G":
                xn, yn = normalize_coords(x, y)
                flip = -1 if x < 0 else 1
                prev = last_by_period.get(period)
                row = {
                    "game_id": game["id"],
                    "shooter_id": shooter,
                    "position": "D" if pos == "D" else "F",
                    "shot_type": d.get("shotType"),
                    "event": play["typeDescKey"],
                    "is_goal": play["typeDescKey"] == "goal",
                    "x_norm": xn,
                    "y_norm": yn,
                    "distance": shot_distance(xn, yn),
                    "angle": shot_angle(xn, yn),
                    "period": period,
                    "time_s": t,
                    "dt_prev": None,
                    "prev_type": None,
                    "prev_same_team": None,
                    "prev_x_norm": None,
                    "prev_y_norm": None,
                }
                if prev is not None and t is not None:
                    pt, ptype, powner, px, py = prev
                    row.update({
                        "dt_prev": t - pt,
                        "prev_type": ptype,
                        "prev_same_team": powner == d.get("eventOwnerTeamId"),
                        "prev_x_norm": flip * px,
                        "prev_y_norm": flip * py,
                    })
                rows.append(row)
        if t is not None and d.get("xCoord") is not None and d.get("yCoord") is not None:
            last_by_period[period] = (t, play["typeDescKey"], d.get("eventOwnerTeamId"), d["xCoord"], d["yCoord"])
    return rows


def build_shots_df(plays_dir: Path, players_dir: Path) -> tuple[pd.DataFrame, dict]:
    """All qualifying shots with handedness and wing labels, plus drop accounting."""
    rows = []
    for f in sorted(plays_dir.glob("*.json")):
        rows.extend(extract_shots(json.loads(f.read_text())))
    df = pd.DataFrame(rows)
    counts = {"qualifying_shots": len(df)}

    handedness = load_handedness(players_dir)
    df["shoots"] = df["shooter_id"].map(handedness)
    counts["dropped_no_handedness"] = int(df["shoots"].isna().sum())
    df = df.dropna(subset=["shoots"])

    counts["dropped_non_core_shot_type"] = int((~df["shot_type"].isin(CORE_SHOT_TYPES)).sum())
    df = df[df["shot_type"].isin(CORE_SHOT_TYPES)]

    df["wing"] = [classify_wing(s, y) for s, y in zip(df["shoots"], df["y_norm"])]
    counts["dropped_center_y0"] = int(df["wing"].isna().sum())
    df = df.dropna(subset=["wing"])

    df["dist_band"] = df["distance"].map(distance_band)
    counts["analyzed_shots"] = len(df)
    return df.reset_index(drop=True), counts


# --- reporting --------------------------------------------------------------------

def split_table(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    """Off-wing vs strong-side attempts, goals, Fenwick sh%, and z-test per group."""
    group_cols = group_cols or []
    out = []
    groups = df.groupby(group_cols) if group_cols else [((), df)]
    for key, g in groups:
        off = g[g["wing"] == "off"]
        strong = g[g["wing"] == "strong"]
        if len(off) == 0 or len(strong) == 0:
            continue
        og, sg = int(off["is_goal"].sum()), int(strong["is_goal"].sum())
        z, p = two_prop_z(og, len(off), sg, len(strong))
        row = dict(zip(group_cols, key if isinstance(key, tuple) else (key,)))
        row.update({
            "off_att": len(off),
            "off_goals": og,
            "off_sh%": 100 * og / len(off),
            "strong_att": len(strong),
            "strong_goals": sg,
            "strong_sh%": 100 * sg / len(strong),
            "diff_pp": 100 * (og / len(off) - sg / len(strong)),
            "z": z,
            "p": p,
            "off_dist": off["distance"].mean(),
            "strong_dist": strong["distance"].mean(),
            "off_angle": off["angle"].mean(),
            "strong_angle": strong["angle"].mean(),
        })
        out.append(row)
    return pd.DataFrame(out)


def strata_cells(df: pd.DataFrame, cols: list[str]):
    """2x2 cells per stratum for CMH: (off goals, off non-goals, strong goals, strong non-goals)."""
    cells = []
    for _, g in df.groupby(cols):
        off, strong = g[g["wing"] == "off"], g[g["wing"] == "strong"]
        og, sg = int(off["is_goal"].sum()), int(strong["is_goal"].sum())
        cells.append((og, len(off) - og, sg, len(strong) - sg))
    return cells


def fmt(table: pd.DataFrame) -> str:
    return table.to_string(index=False, float_format=lambda v: f"{v:.3f}")


def main() -> None:
    df, counts = build_shots_df(DATA_DIR / "plays", DATA_DIR / "players")

    print("=== 5v5 off-wing vs strong-side splits (Fenwick sh% on unblocked O-zone shots) ===\n")
    print(f"Games dir: {DATA_DIR / 'plays'}")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    # convention sanity check: defensemen overwhelmingly play their strong side,
    # so a majority-off-wing result here means the y-side convention is flipped
    d_shots = df[df["position"] == "D"]
    d_strong_share = (d_shots["wing"] == "strong").mean()
    print(f"\nSanity check - D strong-side shot share: {100 * d_strong_share:.1f}% "
          f"(expect well above 50%)")

    print("\n--- Overall ---")
    print(fmt(split_table(df)))

    print("\n--- By position ---")
    print(fmt(split_table(df, ["position"])))

    print("\n--- By shot type ---")
    print(fmt(split_table(df, ["shot_type"])))

    print("\n--- By distance band ---")
    print(fmt(split_table(df, ["dist_band"])))

    print("\n--- Doc scenario: wrist/snap, under 30 ft, forwards ---")
    scenario = df[df["shot_type"].isin(("wrist", "snap"))
                  & (df["distance"] < 30) & (df["position"] == "F")]
    print(fmt(split_table(scenario)))

    strata = strata_cells(df, ["position", "shot_type", "dist_band"])
    or_mh = cmh_odds_ratio(strata)
    chi2, p = cmh_test(strata)
    print(f"\n--- Stratified (position x shot type x distance band, {len(strata)} strata) ---")
    print(f"Mantel-Haenszel pooled odds ratio (off-wing vs strong): {or_mh:.3f}")
    print(f"CMH chi-square: {chi2:.2f}, p = {p:.4f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "shots.csv", index=False)
    pieces = [split_table(df).assign(split="overall")]
    for col in ("position", "shot_type", "dist_band"):
        pieces.append(split_table(df, [col]).assign(split=col))
    pd.concat(pieces, ignore_index=True).to_csv(OUT_DIR / "splits_summary.csv", index=False)
    print(f"\nWrote {OUT_DIR / 'shots.csv'} and {OUT_DIR / 'splits_summary.csv'}")


if __name__ == "__main__":
    main()
