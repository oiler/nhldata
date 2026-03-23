# How We Classify Elite NHL Players

Most hockey analytics treat all opponents the same. A forward's time-on-ice against Connor McDavid counts the same as his time against a fourth-liner. That flattens something important about how coaches actually deploy their players and what that deployment tells us about a skater's role.

We built an elite classification model to fix that. It identifies the best forwards and defensemen across the league, then measures how much time every skater spends facing those players. The result is a competition quality metric that separates players who absorb tough matchups from players who are sheltered from them.

## Why This Matters

Two defensemen can average 22 minutes a night and look similar in a box score. But if one spends most of his 5v5 time against Nikita Kucherov and Nathan MacKinnon while the other draws bottom-six matchups, those 22 minutes are not the same.

**The elite classification gives us a way to quantify that difference.** Once we know who the best players are, we can calculate the fraction of any skater's ice time spent against them. A defenseman with a high percentage against elite forwards is absorbing hard matchups. A defenseman with a low percentage is not. Neither number is inherently good or bad, but they tell very different stories about how a coach uses that player.

## The Forward Model

A forward earns elite status by clearing three thresholds:

- **P/60 >= 2.0** — at least 2.0 points per 60 minutes of 5v5 ice time
- **tTOI% >= 28** — team time-on-ice share of at least 28%
- **iTOI% < 83** — individual 5v5 share below 83%

All three matter. Here is why.

**P/60 is the production filter.** It asks a simple question: does this forward produce at 5v5? We use 2.0 as the threshold because it separates genuine offensive contributors from players who score at replacement-level rates. In the 2025-26 season, 49 forwards across 25 teams clear this bar. Seven teams have zero. Colorado has five. That distribution feels right. Not every team has elite offensive talent, and the model reflects that.

**tTOI% is the usage filter.** It measures how much of his team's total ice time a player gets. A 28% share means the player receives above-average deployment from his coaching staff. This keeps out players who score at a decent rate but only in limited minutes. If a coach does not trust a forward with real ice time, the model does not treat him as elite regardless of his per-minute production.

**iTOI% is the specialist filter.** It measures what fraction of a player's total ice time comes at 5v5 versus other situations like the power play, penalty kill, or 4-on-4. A player with an iTOI% near 100% plays almost exclusively at 5v5. He does not see the power play, which means the coaching staff views him as a role player, not a top talent. We cap this at 83% to exclude players who produce at 5v5 but are limited to that single situation. True elite forwards play in all contexts.

### What the Thresholds Produce

The 2025-26 season has 49 elite forwards from 25 teams. The top of the list is not surprising: Kucherov (3.90 P/60), MacKinnon (3.58), Brayden Point (3.09). Tampa Bay leads the league with four elite forwards. Colorado has five.

Ten teams have exactly one elite forward. Seven teams have none. That is not a flaw in the model. It is the model doing its job. Not every team has a forward who produces at 2.0 P/60 with real minutes and multi-situational deployment.

## The Defense Model

Defensemen are harder to classify because the position has two distinct elite archetypes that do not always overlap.

Some defensemen are elite because of their talent. They produce points, drive offense, and get power play time. Cale Makar and Quinn Hughes are obvious examples. Other defensemen are elite because of their assignment. They face the toughest opposing forwards every night, and their coaches trust them to absorb those matchups at heavy minutes. These two groups sometimes overlap. Often they do not.

We use two separate designations to capture this:

### Production Elite

This is the talent-driven designation. The criteria are close to the forward model but adjusted for defensive norms:

- **P/60 >= 1.25** — defensemen score at lower rates than forwards, so the threshold is lower, but 1.25 is high enough to separate real offensive contributors from defensemen who happen to be on the ice for a few goals
- **tTOI% >= 33** — defensemen carry heavier workloads than forwards, so the usage bar is higher
- **iTOI% < 83** — same specialist filter as forwards

Within each team, we rank production-eligible defensemen by P/60 and keep only the top one. A team gets at most one production elite defenseman. Eighteen teams have one in 2025-26. Fourteen do not. That distribution tracks with reality. Not every team has a defenseman who produces at high rates with multi-situational usage.

### Deployment Elite

This is the coaching-driven designation. It asks: which defenseman on this team faces the toughest forward competition?

The criteria are simpler:

- **tTOI% >= 33** — must carry a significant workload
- **Highest vs Elite Forward %** — among qualifying defensemen on each team, the one who faces elite forwards at the highest rate

Every team gets exactly one deployment elite defenseman. This is by design. Every coaching staff has a top defensive pairing they send over the boards against the opponent's best forwards. We want to know who that player is.

**The deployment designation is fundamentally different from the production designation.** Production elite is about what a player can do. Deployment elite is about what his coach asks him to do. A defenseman does not choose to face Kucherov and MacKinnon every night. His coach puts him there because the coach trusts him in that role.

### Full Elite

A defenseman who earns both designations is a full elite. But the model also accounts for defensive pairings. If a production elite defenseman's vs elite forward percentage is within 1.5 percentage points of his team's deployment elite, the model treats them as a pair and promotes the production D to full elite. The logic is simple: if two defensemen face elite forwards at nearly identical rates, they are on the ice together. The production D is absorbing the same matchups as the deployment D.

Take Edmonton as an example. Evan Bouchard is the production elite (P/60 of 1.66) and Mattias Ekholm is the deployment elite (highest vs elite forward rate on the team). Bouchard faces elite forwards at 15.03% and Ekholm at 15.07%. That gap is 0.04 percentage points. They play together. Bouchard deserves credit for facing the same competition Ekholm does, so the model marks him as full elite.

Compare that to Montreal, where Lane Hutson is the production elite and Mike Matheson is the deployment elite. Hutson faces elite forwards at 13.83% while Matheson is at 23.87%. That gap is over 10 percentage points. They are clearly on different pairings with different assignments, so Hutson stays production-only.

Fourteen defensemen hold full elite status in 2025-26. That list includes Charlie McAvoy, Zach Werenski, Cale Makar, Evan Bouchard, Quinn Hughes, Adam Fox, Erik Karlsson, John Carlson, Rasmus Dahlin, Rasmus Andersson, and Miro Heiskanen. Several of these players earned full elite through the pairing rule rather than by being their team's deployment elite directly. The gap threshold surfaces defensemen who do both jobs without requiring them to be the single highest vs-elite-forward player on their roster.

## How We Use This

The classification feeds directly into two competition metrics: **pct_vs_top_fwd** and **pct_vs_top_def**.

For every second of 5v5 play in every game, we look at who is on the ice. For each skater, we calculate the fraction of opposing forwards (or defensemen) who are elite. Then we average that fraction across all of a player's ice time in a given game.

A forward who consistently faces elite defensemen has a high pct_vs_top_def. A defenseman who consistently faces elite forwards has a high pct_vs_top_fwd. These percentages give us a second-by-second accounting of competition quality that goes well beyond what a box score can tell you.

## Trade Handling

Players who are traded mid-season carry their elite designation to their new team. If a forward qualifies as elite on one team and then gets traded, he appears as a carry-over on the new team's elite list. This matters because opposing players who face that forward before and after the trade should have their competition quality measured consistently. The forward did not stop being elite because he changed jerseys.

## Closing Thought

The point of this model is not to rank players or declare who is the best. It is to measure what kinds of opponents a player faces. That measurement gives context to every other stat we track. A goal scored against Cale Makar is different from a goal scored against a third-pairing defenseman, and a forward who produces while facing elite competition is doing something different from a forward who produces against depth players.

**The elite classification makes those differences visible.** Everything else we build sits on top of it.
