"""
Forwards vs Elite Defensemen — Hard Matchups
=============================================
Which forwards spend the most 5v5 time against elite opposing defensemen?

any_ed_pct  = fraction of 5v5 seconds where ≥1 elite opposing defenseman is on ice
frac_ed_pct = avg fraction of opposing defensemen who are elite each second

High numbers = opposing coaches are deploying their best D against this forward.
Low numbers  = forward is seeing soft defensive matchups.

The elite defenseman designation here is the deployment elite — the D who each team
sends over the boards to face the opponent's top line. So this metric captures which
forwards the whole league's coaches treat as the biggest threat.

Run: python analysis/fwd_vs_elite_def.py
"""

import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "../../data/2025/generated/browser/league.db")


def run():
    conn = sqlite3.connect(DB)

    print("FORWARDS vs ELITE DEFENSEMEN — 2025-26  (min 20 GP)\n")
    print(f"{'#':>3}  {'Player':<22} {'Team':>4}  {'GP':>3}  {'AnyEliteD%':>10}  {'FracEliteD%':>11}  {'EliteFwd?':>9}")
    print("-" * 75)

    rows = conn.execute("""
        SELECT
            p.firstName || ' ' || p.lastName AS player,
            c.team,
            COUNT(*) AS gp,
            ROUND(AVG(c.pct_any_elite_def) * 100, 1) AS any_ed_pct,
            ROUND(AVG(c.pct_vs_top_def) * 100, 1)    AS frac_ed_pct,
            MAX(CASE WHEN ef.playerId IS NOT NULL THEN 1 ELSE 0 END) AS is_elite_fwd
        FROM competition c
        JOIN players p ON c.playerId = p.playerId
        LEFT JOIN elite_forwards ef
            ON c.playerId = ef.playerId AND c.team = ef.team AND ef.is_carryover = 0
        WHERE c.position = 'F'
        GROUP BY c.playerId, c.team
        HAVING COUNT(*) >= 20
        ORDER BY any_ed_pct DESC
        LIMIT 40
    """).fetchall()

    for i, (player, team, gp, any_ed, frac_ed, is_elite) in enumerate(rows, 1):
        flag = "      yes" if is_elite else "         "
        print(f"{i:>3}. {player:<22} {team:>4}  {gp:>3}  {any_ed:>9.1f}%  {frac_ed:>10.1f}%  {flag}")

    print()
    print("AnyEliteD%  — % of 5v5 seconds where ≥1 opposing defenseman is elite (deployment)")
    print("FracEliteD% — avg fraction of opposing defensemen who are elite")
    print("EliteFwd?   — whether this forward is classified as elite themselves")
    print()

    # Show who ranks high despite not being elite (most telling signal)
    non_elite = [(p, t, gp, a, f) for p, t, gp, a, f, e in rows if not e]
    if non_elite:
        print("── Non-elite forwards drawing the toughest defensive assignments ──")
        print("   These are the players opposing coaches respect enough to matchup against")
        print()
        for player, team, gp, any_ed, frac_ed in non_elite[:10]:
            print(f"   {player:<22} {team}  {any_ed:.1f}%")

    # Also show the elite forwards at the bottom (sheltered from tough D)
    print()
    bottom = conn.execute("""
        SELECT
            p.firstName || ' ' || p.lastName AS player,
            c.team,
            COUNT(*) AS gp,
            ROUND(AVG(c.pct_any_elite_def) * 100, 1) AS any_ed_pct
        FROM competition c
        JOIN players p ON c.playerId = p.playerId
        JOIN elite_forwards ef
            ON c.playerId = ef.playerId AND c.team = ef.team AND ef.is_carryover = 0
        WHERE c.position = 'F'
        GROUP BY c.playerId, c.team
        HAVING COUNT(*) >= 20
        ORDER BY any_ed_pct ASC
        LIMIT 10
    """).fetchall()

    print("── Elite forwards with softest defensive matchups (sheltered) ──")
    for player, team, gp, any_ed in bottom:
        print(f"   {player:<22} {team}  {any_ed:.1f}%")

    conn.close()


if __name__ == "__main__":
    run()
