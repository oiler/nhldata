---
lens: frontend
doc: /Users/jrf1039/files/projects/nhl/docs/superpowers/plans/2026-09-29-season-toggle-plan.md
---

# frontend review

## Verdict

ready with changes

## Findings

### F-1 [blocker] Season radios turn purple on hover and keyboard focus, which conflicts with DESIGN.md

- Where: Task 11, Step 3, the `assets/style.css` block (`.season-options label { ... color: var(--text) }` and `.season-options input[type="radio"] { accent-color: var(--navy); margin: 0; }`)
- Evidence: The installed Dash is 4.0.0 (`python -c "import dash; print(dash.__version__)"` printed `4.0.0`). Its bundled `dcc` CSS (the `sourcesContent` of `optionslist.css` and `dcc.css` in `dash/dcc/dash_core_components.js.map`) defines `--Dash-Fill-Interactive-Strong: #7f4bc4` and sets `.dash-options-list-option:not(:has(input[disabled])):hover, ...:focus-within { color: var(--Dash-Fill-Interactive-Strong) }` (specificity 0,3,1) and `.dash-options-list-option-checkbox { outline-color: var(--Dash-Fill-Interactive-Strong) }`. I applied Task 1 and Task 11 exactly as written to a scratch copy of `v2/browser`, served it with `DATA_DIR` set, and read computed styles in headless Chrome through CDP. In the static state the label color was `rgb(23, 23, 23)` and the accent was `rgb(0, 32, 91)`, as the plan intends. With `:hover` forced, both option labels were `rgb(127, 75, 196)`. With `:focus-within` forced, which is the state keyboard users see, both were also `rgb(127, 75, 196)`. The radio `outline-color` was `rgb(127, 75, 196)` in every state. The plan's `.season-options label` rule (0,1,1) loses to Dash's hover and focus rule, and the plan never sets `outline-color`.
- Problem: DESIGN.md §3 says "Navy is the only chromatic text color", §2 says focus rings are Brand Navy, and §7 says "Don't introduce a second accent hue". The plan's CSS delivers purple text and a purple focus outline on the one control this change adds. Task 13 Step 4 checks only the resting state ("navy radios and dark option text"), so the verification would pass while the defect ships.
- Fix: In Task 11's CSS block, retoken Dash 4's variables on the filter bars rather than fighting its selectors. Add:
  ```css
  /* Dash 4 dcc controls read these tokens (default purple #7f4bc4). */
  .filter-bar {
    --Dash-Fill-Interactive-Strong: var(--navy);
    --Dash-Text-Strong: var(--text);
  }
  ```
  I injected exactly this rule into the scratch build. With `:hover` forced, the label color became `rgb(0, 32, 91)`, and the radio outline became `rgb(0, 32, 91)`. The rule also fixes the goalie situation dropdown, which today highlights its active option in `rgb(127, 75, 196)`. Add this to Task 13 Step 4: "Hover and Tab onto each season option. The text and focus outline are navy, never purple."

### F-2 [major] The season radio group has no accessible name, and Dash 4 renders it as an unnamed `listbox`

- Where: Task 11, Step 3, item 3 (`html.Label("Season", className="filter-bar-label")` beside `dcc.RadioItems(...)`)
- Evidence: The rendered DOM from the scratch build (outer HTML of `#season-bar`) is `<label class="filter-bar-label">Season</label><div id="filter-season" class="dash-options-list dash-radioitems season-options" role="listbox"><label class="dash-options-list-option selected dash-radioitems-inline" role="option" aria-selected="true"><span ...><input type="radio" name="filter-season" ...></span>...`. `#filter-season` has no `aria-label` or `aria-labelledby`. The "Season" `<label>` has no `for` attribute and wraps no control, so it labels nothing. `dcc.RadioItems` in Dash 4 exposes no ARIA props (`dash/dcc/RadioItems.py` prop list: options, value, inline, inputStyle, inputClassName, labelStyle, labelClassName, className, persistence, persisted_props, persistence_type, id). The `role="listbox"`/`role="option"` roles come from `src/utils/optionRendering.tsx` in the same source map.
- Problem: A screen reader announces an unnamed listbox of "2025-26" and "2026-27" with no mention of "Season". Each `role="option"` also contains a native radio input, and ARIA doesn't allow interactive content inside an option. That fails the base-layer rule that every form control has a programmatic label, and it's the only new control in this change. The goalie "Situations" `html.Label` the plan also edits has the same gap, because the Dash 4 dropdown button names itself from its own value spans (`aria-labelledby={`${accessibleId}-value-count ${accessibleId}-value`}` in `src/fragments/Dropdown.tsx`).
- Fix: Pick one of these and write it into Task 11:
  1. Preferred: switch to `dbc.RadioItems` (dash-bootstrap-components 2.0.4 is already loaded, and it supports `persistence`, `persistence_type`, `inline`, `options`, `value`, `input_class_name`, and `label_class_name`). It renders native `form-check` radios with no listbox roles. Wrap it in `html.Fieldset([html.Legend("Season", className="filter-bar-label"), dbc.RadioItems(id="filter-season", ...)], className="season-fieldset")` with CSS `.season-fieldset { display: flex; align-items: center; border: 0; margin: 0; padding: 0; min-width: 0; } .season-fieldset legend { float: left; width: auto; margin: 0 0.5rem 0 0; padding: 0; }`. Restyle `.form-check-input:checked` and `:focus` to navy (DESIGN.md §7: "override dbc component colors to the tokens"). The Task 11 test's `r.options` and `r.persistence` assertions still hold.
  2. Minimum: keep `dcc.RadioItems`, but replace the `html.Div` + `html.Label` with the same `html.Fieldset` + `html.Legend`, so the group gets a name. Record Dash 4's `listbox`/`option` roles as a known upstream defect.
  
  Either way, add this to Task 13 Step 4: "Tab to the season options. The screen reader (VoiceOver) announces 'Season' with the group, and the arrow keys move between 2025-26 and 2026-27."

### F-3 [minor] Scoping the eyebrow rule silently restyles the goalie situation dropdown's options

- Where: Task 11, Step 3, "replace the `.filter-bar label { ... }` rule"
- Evidence: Dash 4's dropdown portals its option list into its own wrapper (`<Popover.Portal container={positioningContainerRef.current}>` in `src/fragments/Dropdown.tsx`), so the option `<label>` elements sit inside `#goalie-situation-bar.filter-bar`. I opened the dropdown in headless Chrome on `/goalies` in two copies. On today's code (`base`), the options computed `text-transform: uppercase; font-size: 12px; font-weight: 600; letter-spacing: 0.6px; color: rgb(102, 102, 102)`, so the eyebrow rule currently hits the options. On the plan's code, they computed `text-transform: none; font-size: 16px; font-weight: 400; color: rgba(0, 9, 38, 0.9)`, which is Dash's `--Dash-Text-Strong`, not `--text` `#171717`.
- Problem: The change fixes a real existing bug (menu options styled as eyebrow labels), but the plan doesn't say it happens, doesn't style the result to DESIGN.md (16px Dash default and an off-token color), and doesn't verify it. The implementer and reviewer will read the change as season-only.
- Fix: Add one sentence to Task 11: "Narrowing the rule also stops it from uppercasing the goalie situation dropdown's options, which render inside `.filter-bar`." Set their type to DESIGN.md body size with `.filter-bar .dash-dropdown-content .dash-options-list-option { font-size: 0.9rem; }`; F-1's token rule already gives them the `--text` color. Add a Task 13 check: "On /goalies, open the Situations dropdown. The options are sentence case, `#171717` text, and navy on hover."

### F-4 [minor] Early-season columns that come from `player_metrics` still render blank, not as em dashes

- Where: Task 10, Step 3, item 7 and the `team.py:118-119` / `teams.py:239-242` sentence. Also Global Constraints, "Missing numeric values render as `—` ... through `Format(...).nully("—")`"
- Evidence: `filters.compute_deployment_metrics()` returns an empty frame when `ppi_df` is empty (`filters.py`: `if comp_df.empty or ppi_df.empty: return pd.DataFrame()`), and both pages then set `ppi, ppi_plus, wppi, wppi_plus, avg_toi_share, deployment_rate, fwd_deployment_rate` to `None` (`pages/skaters.py:118-123`, `pages/team.py:212-219`). The plan adds `.nully("—")` only to PPI+, wPPI+, Age, SB/a60, and Max MPH. The other null columns keep formats without `nully`: skaters `tTOI%` (`FormatTemplate.percentage(1)`, `skaters.py:197`) and `DPS+` (`skaters.py:204`), plus team `PPI` (`team.py:117`) and `tTOI%` (`team.py:114`).
- Problem: For the first weeks of 2026-27, every row shows `—` under PPI+ and wPPI+ beside empty cells under tTOI%, DPS+, and (on the team page) PPI. That breaks the plan's own global constraint and looks broken rather than "not yet".
- Fix: In Task 10 item 7, also add `.nully("—")` to skaters `tTOI%` (`FormatTemplate.percentage(1).nully("—")`) and `DPS+`, and to team `PPI` and `tTOI%`. Extend the Task 13 Step 4 bullet to "PPI, PPI+, wPPI+, tTOI%, and DPS+ show em dashes while no skater has 5 games."

### F-5 [minor] Task 13 drops the desktop-width and interaction checks the spec requires

- Where: Task 13, Step 4
- Evidence: The spec's final checklist says "The season filter shows only on season-aware pages and matches DESIGN.md at desktop and phone widths." The plan's only visual check is "At a width under `640px`, the season options are `40px` rows with navy radios and dark option text."
- Problem: The plan has no desktop check and no hover, focus, or keyboard check. That gap is how F-1, F-2, and F-3 would pass verification.
- Fix: Replace the last Step 4 bullet with the following checks: "At desktop width and at 375px: the season options use navy radios and `#171717` text. They stay navy (not purple) on hover and on keyboard focus. Tab reaches the group, and the arrow keys switch seasons. Under `640px` each option is a 40px-tall target. On /team/EDM and /goalies, the Season and Situations bars stack without overflow."

### F-6 [minor] Switching to a not-ready season swaps page content with no announcement

- Where: Task 7, Step 3 (`season_not_ready` returns a bare `html.P`), and Task 9, Step 3
- Evidence: Each page writes its callback output into a plain `html.Div(id="<page>-content")` (for example `pages/games.py:31`, `pages/team.py:172`), with no `aria-live` or `role="status"`.
- Problem: A screen-reader user who picks 2026-27 hears nothing, even though the whole table was just replaced by "2026-27 data isn't available yet." The existing date-range messages share this gap, but this change adds a control whose main job is to swap that region.
- Fix: Optional scope. In Task 9, add `**{"aria-live": "polite"}` to each season-aware page's `html.Div(id="<page>-content")`. The live region has to exist before its content changes, so putting `role="status"` on the new `html.P` isn't enough.

### F-7 [nit] The not-ready state leaves live-looking date pickers and Home/Away toggles above the message

- Where: Task 7, Step 3 (`season_date_range` fallback) with Task 9, Step 3 (early `return not_ready`)
- Evidence: `register_season_callback` (`filters.py:84-98`) still resets the page's From/To pickers to the fallback range (`2026-09-01` to `2027-06-30`) when the season changes. The update callbacks then return the not-ready message before they read the dates.
- Problem: Users see enabled date pickers and All/Home/Away buttons that do nothing while the message is up. The spec accepts this implicitly, but the plan doesn't say it's intended.
- Fix: Add one line to Task 9 stating that the page filter bar stays visible and inert for a not-ready season, and that this is intended. Or hide it and record the decision.

### F-8 [nit] Two small copy points in the shell and the team goalie section

- Where: Task 11, Step 3, item 5 (Max MPH glossary text), and Task 9, Step 3 (`_goalie_environment_section` not-available branch)
- Evidence: The glossary footer shows on every page except home (`app.py:309-311`), including `/game/*` and `/goalie/*`, where the season filter is hidden. The new `html.H3("Goalie environment")` in the not-available branch drops the `(5v5)` suffix that the normal branch uses when `situation == "5v5"` (`pages/team.py:86`).
- Problem: "the selected season's regular-season ice time" refers to a control that isn't on those pages. With the 5v5 cut active, the heading changes between states.
- Fix: Change the Max MPH text to "...across one season's regular-season ice time." In the not-available branch, reuse the existing heading expression: `heading = "Goalie environment (5v5)" if situation == "5v5" else "Goalie environment"`.

## Checked and sound

- Session persistence works as the spec claims. In headless Chrome on the scratch build I clicked 2026-27 on `/skaters`, and `sessionStorage` gained `_dash_persistence.filter-season.value.true`. After a full navigation to `/teams`, the radio was still checked on `2026`, and the `store-season` value sent to page callbacks was `"2026"`.
- The phone-width layout holds. At a 375px viewport on `/team/EDM`, the Season bar (label plus both options) fits on one line above the Situations bar, and each option label computed `height: 40px` (width about 77-78px). That meets DESIGN.md §8's 40px touch-target rule. The page's horizontal overflow comes from the existing player table, not from the new bar.
- In the resting state, the plan's CSS gives option text `rgb(23, 23, 23)` (`--text`) and radio `accent-color` `rgb(0, 32, 91)` (`--navy`), and the eyebrow label stays `--text-3` uppercase. `#666666` on white is about 5.7:1, and `#171717` and navy on white are well above 4.5:1.
- The `.season-options label` and `.season-options input[type="radio"]` selectors match Dash 4's rendered `<label class="dash-options-list-option">` and `<input type="radio" class="dash-options-list-option-checkbox">`, and override Dash's `margin: 0 8px 0 0` on the input and `align-items: baseline` on the label.
- Native radios sharing `name="filter-season"` keep native Tab and arrow-key behavior. Dash's `readonly` attribute doesn't block selection (clicking worked in the persistence check).
- The `toggle_season_bar` page list matches the spec (games, teams, team, skaters, player, goalies). It hides the bar on home, game, goalie, elites, and notes, and it follows the existing `toggle_goalie_situation_bar` pattern.
- Heading structure: the new not-available goalie block uses `H3` under the team page's `H2`, matching the existing section heading level (`pages/team.py:87`). Not-ready messages are `P` elements inside each page's content region below its `H2`, so no page loses its heading.
- Em dashes through `Format(...).nully("—")` keep the columns numeric, so native sort and filter still work. This matches the project's existing missing-value convention (`utils.seconds_to_mmss` returns `"—"`).
- The change adds no motion: no transitions or animations on the new control.
- The not-available copy is plain and specific ("2026-27 data isn't available yet."), and the format is pinned in Global Constraints.
- Nothing in the working tree changed. All verification ran in a `mktemp -d` copy with `PYTHONDONTWRITEBYTECODE=1`, and `git status --short` is unchanged from the session start.
