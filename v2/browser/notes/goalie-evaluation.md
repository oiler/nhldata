# What we learned trying to evaluate goalies

*July 21, 2026*

I went into this project believing goaltenders are hockey's running backs: judged on outcomes their environment mostly controls. Five seasons of play-by-play data later, the data agrees. The most useful things we found were not the things we set out to find.

## The hypothesis

NFL analytics spent a decade learning that running back production is mostly blocking, scheme, and game state, and that "yards over expected" barely repeats from year to year. The goalie version of that claim: save results are mostly shot quality faced, team defense, schedule, and scorekeeper quirks. If that holds, the popular goalie metrics are measuring the environment and crediting it to the goalie. We set out to test it, and to see whether anything survives once the environment is stripped away.

## What we tried

Everything runs on public NHL play-by-play, seasons 2021-22 through 2025-26, about 560,000 shots. We adjusted shot locations for arena scorer bias (arenas disagree by whole feet, enough to move a career). We fit a layered shot model — on net, frozen, goal, rebound — with per-goalie terms shrunk hard toward league average, because a goalie tells you far less per shot than a shooter does. We scored every goalie start against a difficulty index (expected goals faced per 60, ranked against all starts league-wide) and weighted outcomes by win-probability leverage.

The test that matters is portability. Talent should travel; environment stays behind. So we took every goalie who changed teams with enough work on both sides (67 cases) and asked whether any pre-trade measurement predicts post-trade results better than the standard baseline, goals saved above expected (GSAx).

## What we learned

**Nothing predicted post-trade results — including GSAx itself.** Every candidate we tested landed within noise of zero, and pre-trade GSAx weakly anti-predicted post-trade GSAx. This is not "our model lost to the standard one." Nothing worked, which is exactly what the environment hypothesis predicts. GSAx repeats year to year at roughly r = 0.1 in our data, matching published work.

One skill is real: freezing the puck. Freeze rate repeats year over year (r ≈ 0.6–0.7), travels with goalies who switch teams, and is absent between teammates, so it is not a scorekeeper or team artifact. We priced it: each freeze suppresses about 0.02 expected goals over the next 30 seconds of play, mostly by killing rebound chances. Across a starter's season, the gap between a high-freeze and a low-freeze goalie is worth about two goals. Real, and small.

The environment story held everywhere we poked it. Goalie starts differ enormously in difficulty; a hard night carries about twice the expected goals per 60 of an easy one, and season averages hide that spread. Tandem partners who share a team, a defense, and a schedule barely correlate (r ≈ 0.14). The team's total effect on save results bounds out at a fraction of a percent of save percentage, consistent with public work from a decade ago.

Public data has era cliffs. The 2023 tracking-system transition shifted event timestamps by one to two seconds and changed how rebounds are coded; one of our model's coefficients flipped sign at exactly that boundary. Anyone fitting multi-season NHL play-by-play should go looking for these seams before trusting a trend.

## Where that leaves us

The site now presents goalies the way the evidence says it should: results next to the difficulty of what they faced, the one skill that repeats priced in goals, and each team's workload graded like an offensive line. There is no goalie ranking, because the honest finding is that we cannot rank goalies from this data.

We went looking for a better way to rank goalies and came back with good evidence that ranking is the wrong ask. Measure the workload, price what repeats, and hold the rest loosely. That is the bet this site makes.
