# NHL Game Data Project Structure

## Directory Layout

```
nhlgamedata/                    # Project root
│
├── nhlgame.py                  # Main data collection script
├── pyproject.toml              # uv package configuration
├── README.md                   # Main project documentation
├── NHL_API_DOCUMENTATION.md    # API reference
│
├── nogames.json                # Log of 404 errors (games not found)
├── errors.json                 # Log of other API errors
│
├── 2025/                       # 2024-2025 season data
│   ├── shifts/
│   │   └── 2025020393.json
│   ├── plays/
│   │   └── 2025020393.json
│   ├── meta/
│   │   └── 2025020393.json
│   └── boxscores/
│       └── 2025020393.json
│
├── 2024/                       # 2023-2024 season data
│   ├── shifts/
│   ├── plays/
│   ├── meta/
│   └── boxscores/
│
├── 2023/                       # 2022-2023 season data
│   ├── shifts/
│   ├── plays/
│   ├── meta/
│   └── boxscores/
│
├── plays/                      # Play-by-play analysis tools
│   ├── flatten_plays.py        # CSV conversion script
│   ├── FLATTEN_PLAYS_README.md # Documentation
│   └── output/                 # Generated CSV files (auto-created)
│       ├── plays_2025020393.csv
│       ├── plays_2025020394.csv
│       └── ...
│
└── timelines/                  # SituationCode timeline generation
    ├── generate_timeline.py    # Timeline generation script
    ├── README.md               # Documentation
    ├── SITUATIONCODE_REFERENCE.md  # SituationCode format reference
    └── output/                 # Generated timeline files (auto-created)
        ├── 2025/
        │   ├── timeline_2025020591.json
        │   └── ...
        ├── 2024/
        │   └── ...
        └── 2023/
            └── ...
```

## Workflow

### 1. Data Collection (Project Root)
```bash
# Run from project root
python nhlgame.py 1 100
```
- Downloads game data for games 1-100
- Saves to `SEASON/[shifts|plays|meta|boxscores]/`
- Logs errors to `nogames.json` and `errors.json`

### 2. Play-by-Play Analysis (plays/ subdirectory)
```bash
# Run from plays/ subdirectory
cd plays
python flatten_plays.py 393 2025
```
- Reads from `../2025/plays/2025020393.json`
- Outputs to `output/plays_2025020393.csv`
- Auto-creates `output/` directory if needed

### 3. Timeline Generation (timelines/ subdirectory)
```bash
# Run from timelines/ subdirectory
cd timelines
python generate_timeline.py 591 2025
```
- Reads from `../2025/plays/2025020591.json`
- Outputs to `output/2025/timeline_2025020591.json`
- Auto-creates `output/SEASON/` directories if needed
- Generates clean situationCode timeline for time-on-ice calculations

## Path References

| Script Location | Input Data Location | Output Location |
|----------------|---------------------|-----------------|
| `nhlgame.py` (root) | NHL API | `SEASON/[endpoint]/` |
| `plays/flatten_plays.py` | `../SEASON/plays/` | `plays/output/` |
| `timelines/generate_timeline.py` | `../SEASON/plays/` | `timelines/output/SEASON/` |

## Design Rationale

- **Season folders at root**: Easy to see all available data years
- **plays/ and timelines/ subfolders**: Keeps analysis tools separate from raw data
- **output/ subfolders**: Keeps generated files organized and separate from source code
- **timelines/output/SEASON/**: Organizes timeline files by season for easier navigation
- **Relative paths**: Scripts work regardless of where project is located
