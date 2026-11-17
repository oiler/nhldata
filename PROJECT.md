# NHL Data

Why the product exists and what guides its tradeoffs.

- **Owner:** oiler
- **Started:** 2026-01-30

## Purpose

The NHL publishes a play-by-play log for every game, and each logged event carries a `situationCode` that says what strength it happened at. The log leaves out the moments when the situation itself changes, such as a penalty expiring and play going from 5v4 to 5v5. So the log can't say how much of a game was played at each strength, or who was on the ice for it.

This project builds the record the NHL doesn't publish: a log of every second of every game, with the situation code and the players on the ice. Seconds are the unit everything else is measured in. `docs/context/kickoff.md` is the original statement of the problem.

On top of that record, the project measures 5v5 play: how coaches deploy their players, who a player shares the ice with and plays against, and who produces in the hardest minutes.

## The three parts

- **The data pipeline.** Fetches raw game data from the NHL each day, builds the second-by-second timelines, and derives the metrics from them.
- **The browser app.** A Dash app at https://app.nhldata.org/ that serves the pipeline's output: games, teams, skaters, players, elites, and goalies.
- **The research.** Studies that use the same data to answer open questions, such as goalie evaluation and shooter handedness. A study's findings reach the browser only when they hold up.

## Who it's for

oiler, and readers of the browser app who want to compare players and teams on 5v5 play instead of box-score totals.

## Principles

- **Accuracy first.** Outputs must match official NHL statistics. A number that can't be validated against an official source doesn't ship.
- **5v5 only.** Power plays, penalty kills, and 4v4 are excluded from every metric. Special teams inflate individual production and make players hard to compare.
- **The second is the unit.** Every stat is derived from the per-second timeline, so every stat can be traced to the seconds it counts.
- **Missing source data is expected.** The NHL's API returns empty or late data often enough that every fetch needs a fallback, and a gap is handled as missing data, not as an error.
- **Say what the data can't show.** Research findings, including null results, are reported as they are. The browser states the limits of a number next to the number.
- **Small steps, verified.** Work goes one piece at a time: build, test, verify against official numbers, then move on.

## Design vision

`DESIGN.md` owns the browser's visual design.
