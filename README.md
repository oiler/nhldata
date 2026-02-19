# NHL Data

## Summary

The NHL publishes event logs for each game, but those logs obscure the continuous state of play that exists in hockey. For example, when a penalty occurs, there's a logged event. But when a penalty expires, there is not. If you're tracking changes in the situationCode value (that measures play strength like 5v5, 5v4, etc), there's no complete log of changes. And since the shift API endpoint is not fully supported or reliable, this project attempts to merge both problems into a single solution.

## Solution 
Timelines merges shift data with play-by-play logs and creates a second-by-second canonical timeline, encoding rulebook logic and validating strength situations against external datasets. Additionally, all skaters and goalies on the ice are included in each second of the generated timeline.

## Examples
Timelines will create a csv and a json file for each NHL gameid. The project also identifies a sample of gameids that represent as much coverage as we can find in situationCode changes. See [resources/TEST_GAMES.md](resources/TEST_GAMES.md) for that information. 

The [sample-data/](sample-data/) folder contains data for gameid 0734 of the 2025-26 regular season. In that folder, examples of the timelines output is available in both formats:

- [sample-data/generated-timeline-2025020734.csv](sample-data/generated-timeline-2025020734.csv)
- [sample-data/generated-timeline-2025020734.json](sample-data/generated-timeline-2025020734.json)

## Usage

- The [docs/commands.md](docs/commands.md) file has a short guide to how to execute the different scripts in this repo. This will evolve and simplify as the project matures
- Some season values are hardcoded, so if you need <2025 data, check on those hardcoded values at the top of the script
- Run nhlgame.py to get the basic data from the NHL API
- Run nhlgame.py with the shifts parameter to get shift data from the NHL HTML reports
- Run v2/timelines/generate_timeline.py to create the new, generated timelines files for each game



