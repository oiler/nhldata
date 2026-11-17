"""
Forwards vs Elite Forwards — Matchup Lines
===========================================
Which forwards spend the most 5v5 time against elite opposing forwards?

any_ef_pct  = fraction of games with at least one elite opposing forward on ice
frac_ef_pct = avg fraction of opposing forwards who are elite each second

High numbers = coach is matching this player's line against elite opposing lines.
Low numbers  = player is being sheltered from top opponents.

Run: python analysis/fwd_vs_elite_fwd.py
"""

import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "../../data/2025/generated/browser/league.db")


def run():
    conn = sqlite3.connect(DB)

    print("FORWARDS vs ELITE FORWARDS — 2025-26  (min 20 GP)\n")
    print(f"{'#':>3}  {'Player':<22} {'Team':>4}  {'GP':>3}  {'AnyEliteF%':>10}  {'FracEliteF%':>11}  {'Elite?':>6}")
    print("-" * 72)

    rows = conn.execute("""
        SELECT
            p.firstName || ' ' || p.lastName AS player,
            c.team,
            COUNT(*) AS gp,
            ROUND(AVG(c.pct_any_elite_fwd) * 100, 1) AS any_ef_pct,
            ROUND(AVG(c.pct_vs_top_fwd) * 100, 1)    AS frac_ef_pct,
            MAX(CASE WHEN ef.playerId IS NOT NULL THEN 1 ELSE 0 END) AS is_elite_fwd
        FROM competition c
        JOIN players p ON c.playerId = p.playerId
        LEFT JOIN elite_forwards ef
            ON c.playerId = ef.playerId AND c.team = ef.team AND ef.is_carryover = 0
        WHERE c.position = 'F'
        GROUP BY c.playerId, c.team
        HAVING COUNT(*) >= 20
        ORDER BY any_ef_pct DESC
        LIMIT 40
    """).fetchall()

    for i, (player, team, gp, any_ef, frac_ef, is_elite) in enumerate(rows, 1):
        flag = "  yes" if is_elite else "     "
        print(f"{i:>3}. {player:<22} {team:>4}  {gp:>3}  {any_ef:>9.1f}%  {frac_ef:>10.1f}%  {flag}")

    print()
    print("AnyEliteF%  — % of 5v5 seconds where ≥1 opposing forward is elite")
    print("FracEliteF% — avg fraction of opposing forwards who are elite")
    print("Elite?      — whether this forward is classified as elite themselves")
    print()

    # Highlight interesting non-elite players high on the list
    non_elite = [(p, t, gp, a, f) for p, t, gp, a, f, e in rows if not e]
    if non_elite:
        print("── Non-elite forwards with hardest forward competition ──")
        for player, team, gp, any_ef, frac_ef in non_elite[:10]:
            print(f"   {player:<22} {team}  {any_ef:.1f}%")

    conn.close()


if __name__ == "__main__":
    run()
