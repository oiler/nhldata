# NHL API Documentation & Hockey Analytics Resources

## Summary
The NHL public API is not officially documented. There is no MCP server or official documentation portal. In place of those options, other users of the API have put together and shared the best information we have about accessing the API. Still, there are always changes and usually no official announcement to track those changes. The most recent information should be the most reliable, and the oldest information should be verified.

---

## Core Resources

### Unofficial API Documentation
The best, but still unofficial, documentation we have is this readme file:
* https://github.com/Zmalski/NHL-API-Reference/blob/main/README.md
  * Most comprehensive API endpoint reference
  * Actively maintained
  * Community-driven documentation

---

## Python Libraries & Tools

### Modern Python NHL API Wrappers (Recommended)
* **nhl-api-py** (2025/2026 Updated)
  * https://github.com/coreyjs/nhl-api-py
  * https://pypi.org/project/nhl-api-py/
  * **Status**: Actively maintained, updated for 2025-2026 season
  * **Features**: 
    - EDGE statistics support (skating distance, zone time, shot speed, etc.)
    - Comprehensive coverage of standings, schedules, rosters
    - Player career stats and game logs
    - Clean API design with intuitive methods
  * **Use Case**: Best choice for new projects requiring 2024-2025+ season data

### Active NHL Data Scraping Projects

* **scrapernhl**
  * https://github.com/maxtixador/scrapernhl
  * **Status**: Actively maintained
  * **Use Case**: Real-world reference implementation for NHL API access patterns

* **TopDownHockey_Scraper**
  * https://github.com/TopDownHockey/TopDownHockey_Scraper
  * **Status**: Actively maintained
  * **Features**: Elite Prospects scraping + NHL play-by-play data
  * **Includes**: Python Hockey Analytics Tutorial (Jupyter notebook)
  * **Use Case**: Learning resource and reference for comprehensive scraping solutions

### Legacy Python Libraries (Reference Only)

* **nhlscrapi**
  * https://pythonhosted.org/nhlscrapi/
  * https://github.com/robhowley/nhlscrapi
  * **Status**: Pre-release, not production-ready, older API
  * **Note**: Author recommends using the NHL's modern JSON API instead
  * **Use Case**: Historical reference only

* **Hockey-Scraper**
  * https://github.com/HarryShomer/Hockey-Scraper
  * **Status**: No longer maintained (archived)
  * **Note**: Contains foundational patterns for HTML fallback when API fails
  * **Use Case**: Reference for handling missing shifts data via HTML scraping

---

## Educational Resources & Tutorials

### Beginner-Friendly Python Tutorials

* **Python Hockey Analytics Tutorial** (Patrick Bacon / TopDownHockey)
  * Article: https://towardsdatascience.com/python-hockey-analytics-tutorial-b0883085938a
  * GitHub: https://github.com/TopDownHockey/TopDownHockey_Scraper/blob/main/Python%20Hockey%20Analytics%20Tutorial.ipynb
  * **Status**: Recently updated (January 2025)
  * **Scope**: Comprehensive beginner tutorial, no prior Python knowledge required
  * **Covers**: Basic Python, data analysis, NHL equivalency models
  * **Author**: @TopDownHockey (Patrick Bacon)

* **Learn to Code with Hockey**
  * https://codewithhockey.com/
  * **Format**: Paid book/course
  * **Coverage**: Python, Pandas, SQL, Machine Learning with NHL data
  * **Bonus**: Includes companion guide on productivity tools (terminal, Vim, Git, ChatGPT)
  * **Use Case**: Comprehensive structured learning path

* **Fantasy Data Pros - Learn Python with Hockey**
  * https://www.fantasydatapros.com/hockey/blog/beginner/1
  * **Status**: Updated for 2022+
  * **Scope**: Beginner series focusing on practical applications

### Intermediate/Advanced Tutorials

* **Building a Full-Stack Sports Analytics Website** (Neil Pierre-Louis / PierreAnalytics)
  * Article: https://medium.com/@neilpierre24/a-guide-to-building-your-own-full-stack-sports-analytics-website-a9247cb3b99f
  * Website: https://www.pierreanalytics.com/
  * Twitter/X: @pierreanalytics
  * GitHub: https://github.com/neilpl24
  * **Published**: November 2024
  * **Focus**: Complete full-stack web development guide for sports analytics
  * **Technology Stack**: 
    - Backend: Express.js, SQLite
    - Frontend: Modern JavaScript frameworks
    - Data: NHL API integration with Jupyter notebooks
  * **Key Topics**:
    - NHL API data scraping and transformation
    - SQL database design for sports data
    - Building player cards and interactive visualizations
    - Expected goals models
    - Full data flow architecture
  * **Inspiration**: Based on Baseball Savant
  * **Author Background**: Software Engineer at Boston Red Sox, UNC Chapel Hill alum
  * **Additional Content**:
    - "The Offensive Revolution Part 1: Rebounds" article (Nov 2024)
    - Goaltending analytics (featured on Goalie Science podcast)
    - Hockey analysis on Twitter/X
  * **Use Case**: Comprehensive guide for building portfolio-worthy hockey analytics platforms

* **NHL API Tutorial by Vadzim Tashlikovich**
  * https://medium.com/@vtashlikovich/nhl-api-what-data-is-exposed-and-how-to-analyse-it-with-python-745fcd6838c2
  * **Published**: November 2024
  * **API Version**: Latest (2023+)
  * **Coverage**: Detailed walkthrough of new NHL API endpoints
  * **Sample Repo**: https://github.com/vtashlikovich/nhl-game-hotness

* **Hockey Analytics Video Tutorial Series** (Lars Skytte)
  * Main: https://hockey-statistics.com/2024/09/18/video-tutorial-full-hockey-analytics-project/
  * Getting Data: https://hockey-statistics.com/2025/05/14/hockey-analytics-getting-data-directly-from-the-nhl-api/
  * xG Models: https://hockey-statistics.com/2025/05/18/hockey-analytics-building-xg-models-in-python/
  * **Status**: Active series (2024-2025)
  * **Format**: Weekly YouTube videos with written guides
  * **Coverage**: Full pipeline from data extraction to xG model building
  * **Tools**: Python, Power Query, MySQL, Power BI, Scikit-learn
  * **Note**: Addresses 2024-2025 missing shifts data issue

* **Building Your First Data Pipeline** (DataPunk Hockey)
  * https://www.datapunkhockey.com/my-first-pipeline/
  * **Published**: February 2025
  * **Focus**: End-to-end data pipeline construction
  * **Output**: Win Probability report using NHL API

---

## Data Sources & Analytics Platforms

### Free Data Sources

* **MoneyPuck**
  * Main: https://www.moneypuck.com/
  * Data Downloads: https://www.moneypuck.com/data.htm
  * About/Methodology: https://www.moneypuck.com/about.htm
  * **Features**: 
    - Advanced metrics (xG, playoff odds, power rankings)
    - Historical data downloads (player, game, shot data from 2007+)
    - Excellent visualizations
    - Shot location data for xG model building
  * **Attribution**: Credit required when using their data
  * **Python Use**: Downloadable CSV files for analysis
  * **Kaggle**: https://www.kaggle.com/datasets/mexwell/nhl-database

* **Natural Stat Trick**
  * https://www.naturalstattrick.com/
    * Glossary: https://www.naturalstattrick.com/ (see site navigation)
  * Patreon: https://www.patreon.com/naturalstattrick/about
  * **Features**:
    - Live game reports with real-time updates
    - Advanced stats (Corsi, Fenwick, xG, scoring chances)
    - With/Without analysis
    - Player and team comparisons
    - CSV export functionality
  * **Status**: Mostly free (premium features on Patreon)
  * **Known For**: High-quality 5v4 power play predictions
  * **Scraping**: https://github.com/gschwaeb/scraping_naturalstattrick

* **Hockey Reference**
  * https://www.hockey-reference.com/
  * **Features**: 
    - Historical NHL data (comprehensive)
    - Season stats, playoff data
    - CSV export for most tables
  * **Python Integration**: BeautifulSoup scraping recommended for bulk downloads
  * **Use Case**: Historical analysis, season-over-season comparisons

* **NHL.com Official Stats**
  * https://www.nhl.com/stats
  * **Status**: Source of truth for official NHL statistics
  * **Note**: Not optimal for bulk downloads - use NHL API instead
  * **Coverage**: Real-time updates, daily refresh

### Advanced Analytics Platforms

* **Evolving Hockey**
  * https://evolving-hockey.com/
  * References: https://evolving-hockey.com/blog/
  * Glossary: Available on site
  * Patreon: https://www.patreon.com/evolvinghockey/posts
  * **Features**:
    - WAR (Wins Above Replacement) model
    - GAR (Goals Above Replacement) 
    - RAPM (Regularized Adjusted Plus-Minus)
    - xGAR (Expected Goals Above Replacement)
    - Contract projections
  * **Status**: Some features free, advanced metrics require $5/month Patreon
  * **Methodology**: Extensively documented on Hockey-Graphs
    - Part 1: https://hockey-graphs.com/2019/01/16/wins-above-replacement-history-philosophy-and-objectives-part-1/
    - Part 2: https://hockey-graphs.com/2019/01/21/wins-above-replacement-building-the-model-from-scratch-part-2/
    - Part 3: Available on Hockey-Graphs WAR category
  * **Alternative Analysis**: https://hockey-statistics.com/2020/07/13/interpretation-and-redefining-of-evolving-hockeys-gar-and-xgar-models/

* **HockeyViz** (Micah Blake McCurdy)
  * https://hockeyviz.com/
  * About: https://hockeyviz.com/about
  * Patreon: https://www.patreon.com/hockeyviz/about
  * **Features**:
    - Advanced visualizations (heat maps, shot charts)
    - Predictive models (playoff probabilities, draft lottery)
    - Expected goals model
    - Zone entry/exit analysis
    - Rush vs cycle shot analysis (2025 model update)
  * **Methodology**: Publicly documented and explained
  * **Status**: Subscription-based ($5-15/month)
  * **Philosophy**: Focus on visual intuition over raw numbers
  * **Author**: Math PhD, influential voice in hockey analytics community
  * **Twitter/X**: @IneffectiveMath (moving to Bluesky: @hockeyviz.com)
  * **Interview**: https://www.silversevensens.com/q-a-with-micah-mccurdy-of-hockeyviz/
  * **RITHAC Presentation**: https://hockey-graphs.com/wp-content/uploads/2017/10/rithac17.pdf

* **JFresh Hockey**
  * Patreon: https://www.patreon.com/jfreshhockey/posts
  * **Features**: 
    - Player and team cards (visual analytics)
    - Uses Patrick Bacon's WAR model
    - Tableau workbooks
  * **Status**: $5/month subscription
  * **Known For**: Widely-shared player cards on social media

---

## Hockey Analytics Blogs & Communities

### Active Blogs & Newsletters

* **PierreAnalytics** (Neil Pierre-Louis)
  * Website: https://www.pierreanalytics.com/
  * Twitter/X: @pierreanalytics
  * Medium: https://medium.com/@neilpierre24
  * GitHub: https://github.com/neilpl24
  * LinkedIn: https://www.linkedin.com/in/neil-pierre-louis/
  * **Focus**: Full-stack hockey analytics platform and educational content
  * **Features**:
    - Player cards with advanced statistics
    - Interactive goal plots with video links
    - Expected goals models
    - Goaltending analytics
  * **Notable Work**:
    - Comprehensive full-stack development guide (Nov 2024)
    - "The Offensive Revolution" series analyzing offensive trends
    - Rebound analytics using NHL shot data
    - OT Bot - overtime prediction Discord bot
  * **Background**: Software Engineer, Baseball Systems at Boston Red Sox
  * **Philosophy**: Inspired by Baseball Savant, focuses on making advanced analytics accessible
  * **Tech Stack**: Express.js, SQLite, NHL API integration
  * **Status**: Active (2021-present)
  * **Podcast Appearances**: 
    - Goalie Science Podcast (Nov 2024)
    - Sport Analytics Podcast (Episode #3)

* **DataPunk Hockey**
  * https://www.datapunkhockey.com/
  * **Focus**: Practical tutorials, data pipeline guides
  * **Topics**: Free data sources, Python/R tutorials, Power BI
  * **Recent**: 4 Free Data Sources guide (Feb 2025)

* **Hockey-Statistics.com** (Lars Skytte)
  * https://hockey-statistics.com/
  * **Focus**: Comprehensive video tutorials + written guides
  * **Topics**: API access, xG models, MySQL, Power BI
  * **Language**: English with Danish roots
  * **Status**: Very active (2024-2025)

* **Hockey Graphs**
  * https://hockey-graphs.com/
  * **Historical**: Archive of influential analytics articles
  * **Topics**: WAR models, RAPM, methodology deep-dives
  * **Status**: Archive mode, foundational content

* **Data Driven Hockey**
  * https://www.data-driven-hockey.com/
  * Resources: https://www.data-driven-hockey.com/hockey-modelling-resources/
  * **Features**: Curated list of data sources and modeling resources
  * **Use Case**: Quick reference for finding data and tools

* **LB-Hockey**
  * https://lb-hockey.com/
  * **Focus**: Advanced modeling (SPAR, playing styles)
  * **Recent**: Capturing playing styles article (Dec 2025)
  * **Status**: Active, subscription-based tools ($6.99/month)

### Community Forums & Resources

* **HFBoards - Advanced Stats Thread**
  * https://forums.hfboards.com/threads/best-advanced-stats-resources.2817255/
  * **Updated**: 2021 but contains excellent historical context
  * **Value**: Community recommendations and discussion

* **GitHub Topics**
  * NHL API: https://github.com/topics/nhl-api
  * NHL Data: https://github.com/topics/nhl-data
  * **Use Case**: Finding active projects and code examples

---

## Key Insights & Best Practices

### API Access Patterns

1. **Primary Data Source**: NHL JSON API (https://api-web.nhle.com/v1/)
   - Modern API introduced in 2023
   - Most reliable for recent seasons (2023-2024+)
   - Comprehensive endpoints documented in Zmalski's repo

2. **HTML Fallback Strategy** (Critical for Shift Data)
   - NHL shifts API frequently returns empty data (2024-2025 season onward)
   - Implement HTML scraping from Time-on-Ice reports as fallback
   - Reference: Hockey-Scraper, scrapernhl patterns
   - Source: HTML reports on NHL.com

3. **Rate Limiting Considerations**
   - Be respectful with API calls
   - Implement caching for frequently accessed data
   - Batch requests when possible

### Model Building Resources

* **Expected Goals (xG) Models**:
  - MoneyPuck: Tends to underpredict 5v4 goals
  - Natural Stat Trick: Best at predicting 5v4 totals
  - Evolving Hockey: Typically highest predictions
  - HockeyViz: Latest model includes rush vs cycle differentiation (May 2025)
  - Comparison: https://hockeyanalysis.com/2024/04/08/quick-comparison-of-four-public-expected-goal-models/

* **WAR/GAR Models**:
  - Evolving Hockey: RAPM-based, most comprehensive public model
  - Conversion: ~5.6 GAR = 1 WAR (Evolving Hockey)
  - Considerations: Models behind paywalls, less accessible than xG
  - Critical Analysis: https://hockey-statistics.com/2020/07/13/interpretation-and-redefining-of-evolving-hockeys-gar-and-xgar-models/

### Python Ecosystem Recommendations

* **For New Projects (2025+)**: Use `nhl-api-py` package
* **For Learning**: Follow TopDownHockey, Lars Skytte, or PierreAnalytics tutorials
* **For Full-Stack Development**: Study PierreAnalytics' comprehensive guide on building sports analytics websites
* **For Advanced Analytics**: Combine NHL API with MoneyPuck/Natural Stat Trick downloads
* **For Visualizations**: Study HockeyViz methodology and outputs
* **For Historical Data**: Hockey Reference + web scraping
* **For Database Design**: Reference PierreAnalytics' SQLite patterns and SQL best practices

---

## Additional Context & Resources

### Methodology & Philosophy

* **HockeyStats.com Methodology**
  * https://hockeystats.com/methodology
  * **Topics**: Data collection approaches, validation techniques

* **League Equivalencies Research**
  * Gabriel Desjardins: http://hockeyanalytics.com/Research_files/League_Equivalencies.pdf
  * **Use Case**: Converting stats from different leagues (AHL, European leagues)

### Tools & Technologies

* **Primary Languages**: Python, R
* **Popular Libraries**: 
  - Python: pandas, requests, BeautifulSoup, scikit-learn, matplotlib
  - R: tidyverse, hockey data packages
* **Databases**: MySQL for data warehousing
* **Visualization**: Power BI, Tableau, matplotlib, plotly
* **Data Pipeline**: Power Query, Python scripts, scheduled jobs

### Twitter/Social Media Accounts (Analytics Community)

* @pierreanalytics (Neil Pierre-Louis - PierreAnalytics)
* @IneffectiveMath (Micah McCurdy - HockeyViz)
* @TopDownHockey (Patrick Bacon)
* @EvolvingHockey (Josh & Luke Younggren)
* @JFreshHockey (JFresh)
* @MoneyPuckdotcom (MoneyPuck)
* @HockeyStatsCZ
* @ShutdownLine (Corey Sznajder)
* @HockeyGraphs

---

## Archived & Historical References

These resources are no longer maintained but contain foundational information:

* **Hockey-Scraper** (HarryShomer)
  * https://github.com/HarryShomer/Hockey-Scraper
  * **Value**: HTML fallback patterns, shift data handling

* **Corsica Hockey**
  * **Status**: Defunct
  * **Legacy**: Pioneered public advanced stats

* **WAR on Ice**
  * **Status**: Defunct (2015-2016)
  * **Legacy**: First major public WAR model for hockey

* **Extra Skater**
  * **Status**: Defunct
  * **Legacy**: Early advanced stats platform

---

## Recent Updates & Current Issues

### Known API Issues (2024-2025 Season)

1. **Missing Shifts Data**
   - NHL shifts API returning empty responses for many 2024-2025 games
   - **Workaround**: Implement HTML scraping fallback from Time-on-Ice reports
   - **References**: 
     - Lars Skytte's video series addresses this
     - Hockey-Scraper patterns for HTML extraction

2. **API Version Changes**
   - New API introduced in 2023 (api-web.nhle.com/v1/)
   - Old API endpoints may be deprecated
   - Always verify with latest documentation

### Active Development Areas

* Player tracking data (EDGE statistics)
* Puck and player location tracking
* Zone entry/exit micro-stats
* Passing networks
* Real-time analytics during games

---

## Quick Start Recommendations

### For Beginners
1. Start with TopDownHockey's Python Hockey Analytics Tutorial
2. Use `nhl-api-py` for easy API access
3. Download sample data from MoneyPuck
4. Follow DataPunk Hockey's data pipeline guide

### For Intermediate Users
1. Study Lars Skytte's video series for complete workflows
2. Implement dual-source approach (API + HTML) for shifts data
3. Build expected goals model using MoneyPuck shot data
4. Explore Natural Stat Trick for advanced metrics

### For Advanced Users
1. Review Evolving Hockey's WAR methodology papers
2. Study HockeyViz's predictive modeling approaches
3. Implement RAPM models following published research
4. Contribute to open-source projects (scrapernhl, TopDownHockey_Scraper)

---

## License & Attribution

When using data from these sources, please provide appropriate attribution:
- MoneyPuck: Credit required for data usage
- Natural Stat Trick: Credit recommended
- Hockey Reference: Follow their terms of service
- Always cite academic papers and methodology documents

---

*Last Updated: January 2026*
*Maintained by the NHL Analytics Community*