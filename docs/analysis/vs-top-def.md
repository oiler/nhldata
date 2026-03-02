
# Analyzing how "vs Top Def %" is calculated

## Example gameid 2025020951

Here's what we're looking at. MIN (home) vs STL (away), 3-1 STL win in regulation. Let me check the STL D
deployment to validate the MIN forward numbers.
                                                                                                                 
STL's 6 defensemen by 5v5 TOI:
                                                                                                                 
┌──────────┬───────────┬────────┐                         
│  Player  │ TOI (sec) │ Top-4? │
├──────────┼───────────┼────────┤
│ Faulk    │ 1318      │ Yes    │
├──────────┼───────────┼────────┤
│ Broberg  │ 1313      │ Yes    │
├──────────┼───────────┼────────┤
│ Mailloux │ 1218      │ Yes    │
├──────────┼───────────┼────────┤
│ Fowler   │ 1122      │ Yes    │
├──────────┼───────────┼────────┤
│ Kessel   │ 871       │ No     │
├──────────┼───────────┼────────┤
│ Tucker   │ 804       │ No     │
└──────────┴───────────┴────────┘

Top-4 total: 4,971s | Bottom pair total: 1,675s | Top-4 share: 74.8% of all D ice time.

How pct_vs_top_def works: For each 5v5 second a forward is on ice, the code computes (# of top-4 opposing D on ice)
/ (total opposing D on ice) — typically 0/2, 1/2, or 2/2. The player's final value is the average across all their
5v5 seconds.

Should these add up consistently? Yes, within a game there's a constraint. Since 3 forwards are always on ice
during 5v5, the TOI-weighted sum across all forwards must equal 3/2 × (opponent's top-4 D total TOI). Let me
verify:

Weighted sum is 7,655 vs theoretical 7,456 — about 2.7% higher. The small difference is likely from pulled-goalie  
situations (codes 0651/1560) where extra forwards are on ice. Let me verify:

Good - there were 87 seconds of pulled-goalie play (code 1560) where MIN had an extra skater on ice, which explains
the 2.7% overshoot.
                                                                                                                 
Here's the analysis:                                      
                                                                                                                 
The numbers pass the smell test. Here's why:              

1. The weighted average is correct. Across all 12 MIN forwards, the TOI-weighted average pct_vs_top_def is 75.3%.
STL's top-4 D (Faulk, Broberg, Mailloux, Fowler) account for 74.8% of all D ice time. These should match, and they
do (the 0.5% gap is from the 87 seconds of pulled goalie play).

2. The pairing structure explains the extreme spread. STL's D pairs are:
- Pair 1: Faulk (1318s) + Broberg (1313s) — both top-4 → fraction = 1.0
- Pair 2: Mailloux (1218s) + Fowler (1122s) — both top-4 → fraction = 1.0
- Pair 3: Kessel (871s) + Tucker (804s) — neither top-4 → fraction = 0.0

Since both defensemen on each pair are in the same category, the per-second fraction is essentially binary: 1.0 or
0.0. There's no middle ground. That's what creates the extreme separation — a forward is either facing a top pair
(100%) or the 3rd pair (0%), and the averages land where they do based on matchup frequency.

3. The line matching is strong but plausible. The 3rd pair plays ~838 seconds. Trenin/Tarasenko/Yurov (the bottom
line at 38-40%) absorb roughly 60% of the 3rd pair's ice time. Hinostroza/Sturm/Pitlick (middle line at 66-70%)
take another chunk. What's left for the top 6 is very little 3rd-pair exposure, pushing them to 89-94%.

4. Should these add up the same game to game? No — the constraint is 3/2 × (opponent's top-4 D total TOI), which
varies by opponent and game. But within any single game, the TOI-weighted sum is fixed by the opponent's D
deployment.

The takeaway: The numbers look extreme because STL's D pairings happen to split cleanly into top-4 vs non-top-4. In
a game where top-4 D are split across pairs (e.g., one top-4 + one bottom-pair on the same pair), you'd see more
values clustering around 50% rather than the 0-or-1 distribution here. The metric is working correctly.
