# NHL Game Data Analytics Project

## Project Overview
This project builds accurate NHL game analytics by processing public API data and validating against official sources like ESPN box scores. The focus is on data accuracy, robust error handling, and creating production-ready analytics tools.

## Core Principles
- **Validation First**: All outputs must match official NHL statistics exactly
- **Discuss Before Implementing**: Always talk through solutions and edge cases before writing code
- **Handle API Reliability Issues**: NHL's API frequently returns empty data - implement fallbacks
- **Python Over R**: Use Python-based tools and libraries for all implementations

## Current Components

### 1. Situation Timeline Generator
Processes play-by-play data to track game situations using situationCode format:
- Format: `[Away Goalie][Away Skaters][Home Skaters][Home Goalie]`
- Example: `1551` = away goalie, 5v5, home goalie
- Example: `1441` = away goalie, 4v4, home goalie

**Critical Rule - Coincidental Penalties (Rule 19.1)**:
- When exactly one minor penalty per team occurs simultaneously with no other penalties in effect, teams play 4v4
- Penalties are canceled by total count, not by type
- See `/mnt/project/Rules_Coincidental_Penalties.md` for full details and Table 13 examples

### 2. On-Ice Shifts Processor
Creates second-by-second player timelines for time-on-ice calculations.

**Critical Timing Rules**:
- Overlapping shifts: Departing players get priority at the same timestamp
- Use "startTime + 1" approach for incoming players
- Process period-by-period (0-1200 seconds per period) to eliminate boundary overlaps
- Goaltender detection: Analyze period starters + total ice time patterns (no position data in raw API)

**Known API Issue - Empty Shifts Data**:
- NHL shifts API frequently returns empty responses for 2024-2025+ season games
- This is NOT an error condition - it's missing data that requires fallback
- **Solution**: Implement HTML scraping from NHL Time-on-Ice reports
- **References**: Hockey-Scraper (archived but has patterns), scrapernhl, TopDownHockey_Scraper
- See `/mnt/project/NHL_API_Documentation.md` section "API Access Patterns" for details

## Technical Stack

### Primary Libraries
- **nhl-api-py**: Modern NHL API wrapper (2025-2026 updated)
- **pandas**: Data processing and analysis
- **requests/BeautifulSoup**: HTML fallback scraping when API fails

### Output Formats
- JSON: Structured data for programmatic access
- CSV: Analysis-ready tabular data
- Comprehensive documentation with each output

## Data Validation Standards
All outputs must be validated against official sources:
- ESPN box scores for game summaries
- NHL.com official stats for time-on-ice
- Cross-reference with established scrapers (Hockey-Scraper patterns)

## Key Resources

### Project Files
- `/mnt/project/Rules_Coincidental_Penalties.md`: NHL Rule 19 + Table 13 examples
- `/mnt/project/NHL_API_Documentation.md`: API endpoints, libraries, tutorials

### External References
- NHL API Reference: https://github.com/Zmalski/NHL-API-Reference
- nhl-api-py: https://github.com/coreyjs/nhl-api-py
- Hockey-Scraper: https://github.com/HarryShomer/Hockey-Scraper (archived, reference for HTML fallback)
- TopDownHockey tutorials: https://github.com/TopDownHockey/TopDownHockey_Scraper

## Development Workflow
1. **Understand First**: Discuss the problem, edge cases, and solution approach
2. **Validate Assumptions**: Check against official NHL rules and data
3. **Implement**: Write clean, well-documented code
4. **Test**: Verify outputs match official statistics exactly
5. **Handle Failures**: Implement robust error handling and fallback mechanisms

## Known Edge Cases to Handle
- Coincidental penalties creating 4v4 situations (Rule 19.1)
- Empty shifts API responses requiring HTML fallback
- Period boundary timing overlaps (solve with period-by-period processing)
- Goaltender detection without explicit position data
- Multiple simultaneous penalties requiring cancellation logic
- Captain's choice scenarios in penalty assessment

## Communication Style
- oiler prefers methodical discussion before implementation
- Wait for explicit instruction to write code
- Explain reasoning and trade-offs
- Reference specific rules and official sources
- Never capitalize "oiler" in responses