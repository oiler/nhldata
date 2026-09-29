---
lens: design
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/specs/2026-09-29-season-toggle-design.md
---

# design review

## Verdict

not ready

## Findings

### F-1 [major] Age source is described wrongly, and the JSON-recovery path that supplies 21% of 2025 skaters is left out

- Where: Design > Age from player data, first bullet; Testing table row "`build_players_table()` on synthetic player JSONs writes a `birthDate` column"
- Evidence: `v2/browser/build_league_db.py:64-76`: `build_players_table()` reads `PLAYERS_CSV` (`data/<season>/generated/players/csv/players.csv`) with a fixed `keep` list; it reads no JSON. Player JSONs are read only by `_recover_missing_players()` (`build_league_db.py:79-115`), which appends rows for competition skaters missing from the CSV. Against the 2025 data (read-only): 940 distinct F/D skaters in `competition`; 742 are in `players.csv`; 198 enter the `players` table only through `_recover_missing_players()`. All 198 have a `birth_date` in the 2025 burst CSV today, so all 198 show an Age today. `players.csv` carries `birthDate` for 2024, 2025 and 2026 (column 10, 0 nulls in 2025 and 2026), and all 1024 `data/2025/players/*.json` carry `birthDate`.
- Problem: An implementer who adds `birthDate` to `build_players_table()` as written (the only function the spec names) gets the CSV rows. The recovered rows are appended with `to_sql(if_exists="append")` from dicts without a `birthDate` key, so SQLite stores NULL. 198 of 940 skaters (21%) regress from a real Age to an em dash. The success criterion "Age displays for every season whose players table carries `birthDate`" still passes, because the column exists. The planned test, "on synthetic player JSONs", targets the wrong input for `build_players_table()` and doesn't touch the recovery path.
- Fix: Replace the first bullet with: "`build_players_table()` adds `birthDate` to its `keep` list (`players.csv` already carries it as ISO `YYYY-MM-DD`). `_recover_missing_players()` adds `"birthDate": d.get("birthDate")` to each recovered row." Replace the test row with two rows: `build_players_table()` on a synthetic `players.csv` writes `birthDate`, and `_recover_missing_players()` on a synthetic player JSON writes that player's `birthDate`. Both fail before the change because the column is absent or NULL. Optionally add a post-rebuild check to the Testing section: for 2025, the count of F/D skaters with non-null `birthDate` equals the count with a burst `birth_date` today (940 of 940).

### F-2 [blocker] "Rollover is a change to one file" contradicts the Rollover section and misses the app.py glossary

- Where: Goal > Success means, last bullet; "Rollover next season" section
- Evidence: The Goal says "Next season's rollover is a change to one file, `v2/browser/seasons.py`." The Rollover section's step 2 edits `tools/sync-runtime-data.sh` and the `Dockerfile`, so that's three files. `v2/browser/app.py:162-163` also hard-codes season-specific text in the Max MPH glossary entry: "A single peak value across all 2025-26 regular-season ice time. League average ≈ 22.2; McDavid leads at 24.6."
- Problem: The success criterion can't be met by the design as written, and the two sections disagree. Rated blocker because the brief's rubric puts internal contradictions there; the fix is a small decision between (a) and (b). Once 2026-27 is selectable, the Max MPH glossary text is wrong for 2026-27, and neither this design nor the rollover list covers it.
- Fix: Pick one of these:
  - (a) Make the criterion true. `sync-runtime-data.sh` loops over the seasons from `python3 -c 'import sys; sys.path.insert(0,"v2/browser"); from seasons import SEASONS; print(*SEASONS)'`. The Dockerfile `RUN` guard calls a small Python check that imports `SEASONS` from `/app/seasons.py` (it's copied in at `Dockerfile:35`) and tests each season's `league.db` and `player_bursts.csv`.
  - (b) Reword the criterion to "Next season's rollover is the three edits listed under Rollover next season" and keep the explicit lists. That also satisfies `BACKLOG.md:16`'s point that the guards name files explicitly.

  In either case, make the Max MPH glossary season-neutral: drop "2025-26", and drop or date the league-average and leader figures. Add that edit to the App shell section.

### F-3 [major] The Edge-burst em dash mechanism named ("same rendering as missing TOI") doesn't fit numeric columns

- Where: Design > Edge bursts per season, fourth bullet; Design > Age from player data, last bullet; Goal success criterion 4
- Evidence: Commit `53c2290` gets the TOI em dash from `seconds_to_mmss()` returning the string `"—"` (`v2/browser/utils.py`), which feeds a text column (`toi_display`, `skaters.py:196`). SB/a60, Max MPH and Age are `"type": "numeric"` columns with `Format(...)` (`skaters.py:188, 201-202`). The current behavior isn't a failure: a scratch run of `grouped.join(empty_bursts_frame)` with pandas 3.0.0 returns NaN columns, and the DataTable shows them as blank cells. `dash.dash_table.Format.Format` has a `nully` method (checked: `hasattr(Format(), 'nully')` printed `True`). Not browser-verified: I didn't confirm in a browser that NaN serializes to null and renders through `.nully`.
- Problem: Copying the TOI approach, which writes `"—"` strings into the frame, puts strings in numeric columns. Native sort and filter then mix types, and the fixed-precision `Format` no longer applies. "Instead of failing" also misstates the current behavior: the columns show blank, and for 2026 the real defect is that 2025 burst values get joined onto 2026 rows (`skaters.py:35, 160`).
- Fix: Replace the bullet with: "Rows without burst data keep NaN, and the SB/a60, Max MPH and Age column formats add `.nully("—")` (for example `Format(precision=2, scheme=Scheme.fixed).nully("—")`, and `Format().nully("—")` for Age), so the columns stay numeric for sort and filter." Reword success criterion 4 to "shows an em dash in SB/a60 and Max MPH instead of another season's values or a blank cell."

### F-4 [minor] Lazy burst loading removes the boot-time failure that the burst_data.py and Dockerfile comments describe as the safety net

- Where: Design > Edge bursts per season, third bullet
- Evidence: `v2/browser/burst_data.py:4-9` says the production raise "turns a silent 'blank columns' regression into a boot failure that Fly's deploy health check catches before the bad image takes traffic". `Dockerfile:37-41` says a dataless image's "skaters page raises at import". The Dockerfile guard tests only `-s` (non-empty), so a header-only CSV passes it; `load_bursts()` raises on that file (`burst_data.py:34-36`). The spec itself says the error "now fires on the first request for the season instead of at import."
- Problem: If an image skips `sync-runtime-data.sh` (the case the Dockerfile guard exists for), a header-only or truncated CSV now passes the build and the health check, and returns a 500 on `/skaters` to real users. That's the regression the docstring was written to prevent. Both comments also go stale.
- Fix: Add a bullet: "In runtime mode (`is_runtime_mode()`), `skaters.py` calls `_bursts_for(s)` for each `s` in `SEASONS` at import, so a bad CSV still fails boot. Local dev stays lazy." Also update the `burst_data.py` module docstring and the `Dockerfile:37-41` comment to match.

### F-5 [minor] No deploy guard catches a stale league.db without the birthDate column

- Where: Design > Age from player data, third bullet ("The skaters page doesn't guard against a missing column")
- Evidence: The deployed `league.db` files are image-baked copies (`tools/sync-runtime-data.sh:19-20`). `verify_runtime_data.py` checks burst coverage only. The current `data/2025/generated/browser/league.db` `players` columns are `playerId, currentTeamAbbrev, firstName, lastName, position, heightInInches, weightInPounds, shootsCatches` (no `birthDate`). `_COMP_SQL` selecting `p.birthDate` against that DB raises `sqlite3.OperationalError: no such column`, and pandas re-raises it as `DatabaseError`.
- Problem: "A database without it is a build that hasn't been rerun" is true locally but mitigates nothing in production. If the code ships before the 2025 rebuild and resync (for example, the rebuild step is skipped or run from the wrong cwd), `/skaters` returns a 500 in production for every season. No boot or build check catches it.
- Fix: Add to the Deploy guard section: "`sync-runtime-data.sh` asserts that `players` has a `birthDate` column in each synced season's `league.db` (`PRAGMA table_info(players)`), and exits non-zero otherwise." A one-function addition to `verify_runtime_data.py` with a red-then-green test fits the existing pattern (`tests/test_verify_runtime_data.py`).

### F-6 [minor] Switching store-season to session storage has no effect, because the RadioItems resets it on every load

- Where: Design > App shell, third bullet
- Evidence: `app.py:302-304`: `sync_season` has `Input("filter-season", "value")` with no `prevent_initial_call`, and the RadioItems is created with `value=DEFAULT_SEASON` (`app.py:92`) and no `persistence`. I didn't run this in a browser. By Dash's initial-call semantics, a full reload restores the session store's saved value, then `sync_season` fires with `"2025"` and overwrites it. SPA navigation (`dcc.Location(refresh=False)`) keeps the store in memory either way.
- Problem: The change is described as restoring the pre-hiding behavior, but it persists nothing across reloads. On a reload where the saved value is `"2026"`, page callbacks can fire twice, once with `"2026"` from storage and again with `"2025"` after the overwrite.
- Fix: Decide whether the season should survive a reload. If yes: keep `store-season` at `memory`, add `persistence=True, persistence_type="session"` to the `filter-season` RadioItems, and rewrite the `app.py:58-60` comment to say so. If no: drop this bullet and just update the comment. Add one manual check to the Testing section: select 2026-27, reload, and confirm which season shows.

### F-7 [minor] The now-visible season filter appears on pages that ignore it

- Where: Design > App shell, second bullet; Design > Pages ("`elites.py` keeps reading its season from the URL", "`game.py` needs no change")
- Evidence: The filter bar is global (`app.py:86-99`), with no pathname toggle. `/` (home), `/game/<id>` (season from the ID, `game.py:121`), `/goalie/<id>` (all seasons, `goalie.py:14-16, 91`) and `/elites` (URL `season`, `elites.py:122-123`) don't read `store-season`. The goalie situation bar already sets the precedent of showing by pathname (`app.py:314-318`).
- Problem: On those pages, changing the season does nothing visible. A user who picks 2026-27 on a game page can reasonably assume they're looking at 2026-27 data.
- Fix: Add a bullet: "A `toggle_season_bar` callback on `url.pathname` shows the season filter bar only on `/games`, `/teams`, `/team/*`, `/skaters`, `/player/*` and `/goalies`, following `toggle_goalie_situation_bar`." Give the season bar an `id` so it can be targeted.

### F-8 [blocker] Elites is listed as following the selected season, but the design keeps it URL-driven

- Where: Goal > Success means, second bullet vs. Design > Pages and shared modules, third bullet
- Evidence: The success criterion says "Games, teams, team, skaters, player, goalies, and elites pages all follow the selected season." The design says "`elites.py` keeps reading its season from the URL, defaulting to `DEFAULT_SEASON`." `elites.py:122` is `layout(season=None)` with no `store-season` input, and it's excluded from the nav (`app.py:76`).
- Problem: This is an internal contradiction, rated blocker per the brief's rubric; the fix is a one-line edit. Acceptance testing against the criterion ("switch seasons on each page") fails on `/elites`.
- Fix: Remove "elites" from the success-criterion list and add "`/elites` stays URL-driven (`?season=`) and hidden from the nav." Alternatively, add `store-season` as an input to an elites content callback. The first option matches the rest of the design.

### F-9 [minor] Unlisted risk: every deploy now waits on a manual Edge refresh that meets 80% coverage

- Where: Design > Deploy guard, final paragraph
- Evidence: The spec says "A stale 2026 burst CSV fails that check as the season adds skaters, which signals that an Edge refresh is due." `BACKLOG.md:54-59` describes the Edge refresh as manual, about 800 requests, and planned monthly. `verify_runtime_data.py:19` sets `DEFAULT_MIN_OVERLAP = 0.80` against all F/D skaters in `competition`. No `data/2026/generated/edge/` exists yet.
- Problem: After this change, any deploy (including an unrelated security or bug fix) is blocked until someone runs a fresh 2026 Edge fetch. Early in the season, when call-ups keep adding skaters, coverage can fall under 80% within days. I haven't verified whether Edge publishes bursts for players with only one or two games. If it lags, even a same-day refresh could fail the check. The spec presents this coupling as a signal, not as a cost, and gives no escape hatch.
- Fix: Add to the Deploy guard section either a documented override (the script's existing third CLI argument, `min_overlap`, passed for 2026 only via an env var such as `MIN_BURST_OVERLAP_2026`), or a stated decision that blocking unrelated deploys on an Edge refresh is acceptable. Also note the open question of Edge coverage for low-GP skaters early in the season.

### F-10 [minor] Test seams aren't named for the Age and player-metadata tests, and the lru_cache test needs cache isolation

- Where: Testing table, rows 3, 5 and 6
- Evidence: Age today is computed inline in `update_skaters()` (`skaters.py:160-165`). `_age_on()` already exists and already passes the boundary cases with an explicit cutoff, so a test of `_age_on` alone can't go red. The metadata lookup is inline in `player.py` `layout()` (`player.py:105-107`). `_bursts_for` is to be a module-level `functools.lru_cache`, and tests monkeypatch `DATA_DIR` per test (`tests/test_burst_data.py`).
- Problem: "Each test goes red before the change" needs a function that exists after the change and behaves differently before it. The spec doesn't name that function for rows 3 and 5. Row 6 can pass or fail depending on test order, because the cache survives across tests.
- Fix: Name the seams:
  - Row 3 targets `_age_for(birth_date, season)`, defined as `_age_on(birth_date, age_cutoff(season))`, or goes through `age_cutoff`. It's red before the change because `age_cutoff` doesn't exist and `_AGE_CUTOFFS.get("2026")` is `None`.
  - Row 5 targets an extracted `_player_meta(pid) -> pd.Series | None` in `player.py`, tested against two synthetic `league.db` files under a monkeypatched `DATA_DIR`.
  - Row 6 calls `_bursts_for.cache_clear()` in a fixture.

### F-11 [blocker] The season filter will ship with Bootstrap-default styling, which conflicts with DESIGN.md

- Where: Design > App shell, second bullet ("The filter bar loses `display:none`")
- Evidence: `app.py:94-96` sets inline `labelStyle` `color: "#212529"` (Bootstrap's body color) and gives the radio input no accent color. `assets/style.css:94-101` applies `.filter-bar label` uppercase eyebrow styling to every label in the bar, including the option labels. The inline style overrides size, weight and color, but not `text-transform` or `letter-spacing`. DESIGN.md §2 sets Primary Text to `#171717` (`--text`). §4 Inputs says "Radio/checkbox accent: navy". §7 says "Don't ship purple/blue Bootstrap defaults." §8 says radio controls get 40px rows on mobile.
- Problem: This conflicts with the evergreen DESIGN.md, so it's rated blocker per the brief's rubric, although the fix is small. Un-hiding the control ships an element that was never styled to the design system: off-token text color, the browser-default radio accent, eyebrow tracking on the option text, and no mobile touch-target sizing.
- Fix: Add a bullet: "Replace the inline `labelStyle`/`inputStyle` with a `season-options` class. In `style.css`, set option labels to `color: var(--text)`, `text-transform: none`, `letter-spacing: 0`; set `accent-color: var(--navy)` on the inputs; and give 40px rows under the 640px breakpoint. Scope the eyebrow `.filter-bar label` rule to the group label (`.filter-bar > div > label`)."

### F-12 [nit] Two hard-coded 2025 references the spec's list misses or misdescribes

- Where: Problem, second bullet; Design > Date-range fallback
- Evidence: `filters.py:16` is `yr = int(season) if season else 2025`. It's a hard-coded `2025` not in the Problem list, and the fallback text's `yr = int(season)` silently drops the `else`. The Problem bullet cites `app.py:84` for `display:none`, but line 84 is a comment; the style is at `app.py:99`.
- Problem: The "No page falls back to a hard-coded `"2025"`" criterion leaves one integer fallback in place, and one line citation is wrong.
- Fix: Add `filters.py:16` to the Problem list, and write the fallback as `yr = int(season or DEFAULT_SEASON)`. Change `app.py:84` to `app.py:99`.

### F-13 [nit] The team-page goalie section is already omitted, not empty

- Where: Design > Goalie sections, second bullet ("instead of an empty section")
- Evidence: `team.py:80-83` returns `None` when `env` is empty, and `team.py:344-345` appends the section only when it isn't `None`.
- Problem: This is a factual misstatement of the current behavior. It's harmless, but it could send an implementer looking for an empty container.
- Fix: Change "instead of an empty section" to "instead of omitting the section".

### F-14 [nit] The player metadata lookup silently drops the 2024 fallback

- Where: Design > Pages and shared modules, second bullet
- Evidence: `player.py:105-107` falls back to 2024. The new lookup iterates `SEASONS` (`["2025", "2026"]`), and 2024 stays out of it (Non-goals). `/elites?season=2024` still renders `/player/<id>` links (`elites.py:40, 85`), and `runtime_data/2024/league.db` still ships.
- Problem: A 2024-only player reached from `/elites?season=2024` now shows "Player <id>" instead of a name. It's small, but the spec doesn't make the removal a stated decision.
- Fix: Add one sentence: "The 2024 fallback is dropped; 2024-only players show `Player <id>`." Alternatively, keep `"2024"` as a trailing lookup season outside `SEASONS`.

## Checked and sound

- The circular-import rationale for a standalone `seasons.py` holds. `app.py` triggers page discovery (`use_pages=True`), pages import only flat sibling modules (`db`, `filters`, `burst_data`), and none imports `app`. A dependency-free `seasons.py` on the same flat path is the simplest fix.
- The hard-coded `"2025"` sites listed in the Problem section match the code: `games.py:37`, `teams.py:65`, `team.py:181`, `skaters.py:22, 35, 81`, `player.py:105, 138`, `goalies.py:42`, `elites.py:123`, `filters.py:9, 97`, `db.py:31, 46`, `burst_data.py:24`. The exceptions are the `app.py:84` citation and `filters.py:16` (F-12).
- The `season_date_range()` bug is real: `filters.py:16-17` returns `(yr-1)-10-01` through `yr-06-30`, so `"2026"` maps to the 2025-26 window. The proposed `yr`/`yr+1` fallback is correct for start-year keys.
- Seasons are start-year keyed across stores: `goalies.db` `goalie_seasons` and `team_environment` both hold seasons 2021 through 2025, and `data/2026/` is the 2026-27 tree. The `/goalies` empty-state text already exists at `goalies.py:45-46`.
- `age_cutoff` boundary arithmetic: with a cutoff of 2026-09-15, someone born 2000-09-15 is 26 and someone born 2000-09-16 is 25, as the test row states.
- Age values agree across sources. For the 742 2025 skaters in both `players.csv` and the burst CSV, `birthDate` equals `birth_date` in all 742 rows (0 mismatches), so moving Age to the players table doesn't change any displayed value where both exist.
- `data/2026/generated/players/csv/players.csv` exists with 778 rows and `birthDate` populated, so 2026-27 Age will work once `league.db` is built. `data/2026/generated/browser/` doesn't exist yet, which confirms the "until the first daily run" framing.
- The orchestrator defaults to `NHL_SEASON=2026` (`v2/orchestrator/config.py:11`) and includes a `build_league_db` step, which supports "the daily orchestrator run keeps the 2026 database current."
- `db.query()` / `edm.db` has no callers outside `db.py` and `tests/test_smoke.py`, which supports the `edm.db` non-goal.
- `player.py`'s `_load_bursts()` is already per-season and tolerates a missing file (`player.py:87-94`), as the spec says.
- The sync-script failure test works as described: with `set -euo pipefail`, a `cp` of a missing 2026 burst CSV exits non-zero before the non-empty loop runs.
- Extending both deploy guards to 2026 keeps `BACKLOG.md:16`'s requirement that "a dataless or partial image can't ship."
- CLAUDE.md constraints are respected: the tests use synthetic data, the spec runs `python -m pytest v2/ -v` before finishing, metric logic isn't duplicated (`metrics.py` is untouched), and nothing in the spec commits to git.
- `lru_cache` on `_bursts_for` returns a shared frame, but the only use is `grouped.join(...)`, which doesn't mutate its argument, so sharing is safe.
