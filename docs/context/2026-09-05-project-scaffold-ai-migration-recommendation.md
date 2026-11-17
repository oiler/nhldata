---
status: draft
owner: oiler
last_reviewed: 2026-09-05
---

# Recommendation: moving the nhl project to the project-scaffold-ai format

> **Note, 2026-11-17:** This report targets the formal-v1 scaffold, which is now archived in the scaffold repository. The project moved to the lean scaffold on 2026-11-17, which doesn't move code or split the repository, so the staged plan below wasn't followed. The section "Coupling that blocks a move" is still accurate and is the starting checklist for the code restructure in `ROADMAP.md`. Paths to moved documents were updated on the same date.

Reference scaffold: `/Users/jrf1039/files/repo/project-scaffold-ai/project-name/`, reviewed at its 2026-09-05 revision, which adds `docs/design/` and renames the code-side design document to `ARCHITECTURE.md`. This report is read-only analysis. No files in either repository were changed or moved.

## Recommendation

Adopt the scaffold's document model now. Do not split the repository into `docs/` and `code/` yet.

The scaffold has two separable ideas. The first is a two-repository split with `code/` as the software record and `docs/` as the product record. The second is a set of governed document types: `OBJECTIVE.md`, `STATUS.md`, versioned dossiers, stable IDs, decision records, and change-control policy. The nhl project can absorb the second idea with zero functional risk, because it only adds files. The first idea breaks things today, because the running system assumes one repository root that contains code, data, docs, and resources together.

A three-stage path gets there without an outage:

1. **Stage 1, no risk.** Add the scaffold's governance documents inside the existing tree. Nothing moves.
2. **Stage 2, low risk.** Move source under `code/` inside the same repository, after fixing the path coupling listed in the "Coupling that blocks a move" section.
3. **Stage 3, optional.** Split `docs/` into a separate repository once stage 2 has run through at least one nightly cycle and one deploy.

## What the scaffold expects

| Scaffold location | Purpose |
| --- | --- |
| `docs/OBJECTIVE.md`, `STATUS.md`, `ROADMAP.md` | Durable purpose, current focus, ordered bets |
| `docs/versions/MAJOR.MINOR/` | One dossier per minor version: scope, specs, plans, reviews, acceptance, release records |
| `docs/decisions/DEC-NNN` | Product decisions, superseded rather than rewritten |
| `docs/research/` | Evidence notes with method, date, and limitations |
| `docs/policies/` | Versioning, traceability, change control |
| `docs/design/DESIGN-SYSTEM.md`, `ACCESSIBILITY.md`, `flows/`, `wireframes/`, `prototypes/` | Product experience and visual design, kept apart from software architecture |
| `code/src/`, `code/tests/`, `code/scripts/` | Implementation |
| `code/ARCHITECTURE.md` | Living software architecture, summarized from `code/docs/architecture/` |
| `code/docs/adr/ADR-NNN` | Technical decisions |
| `code/docs/operations/` | Deploy, rollback, runbooks |
| `code/release/*.yaml` | Manifest tying a tag to a docs baseline commit |
| `AGENTS.md` canonical, `CLAUDE.md` a pointer | Agent instructions in each repository |

## How the nhl tree maps onto it

The project already has most of the content. It lacks the structure and the IDs.

| Current nhl path | Scaffold destination | Notes |
| --- | --- | --- |
| `Project Kickoff.md` | `docs/OBJECTIVE.md` | Rewrite into the template. The kickoff is a strong purpose statement already. |
| `README.md` (product half) | `docs/README.md`, `docs/OBJECTIVE.md` | The stat-model descriptions belong in the product record. |
| `README.md` (deploy half) | `code/README.md`, `code/docs/operations/` | |
| `docs/opportunities.md`, `docs/context/ideas/` | `docs/ROADMAP.md`, `docs/research/` | |
| `docs/plans/*-design.md` | `docs/versions/<v>/specs/SPEC-NNN` | 33 design docs. Assign IDs. |
| `docs/plans/*-plan.md` | `docs/versions/<v>/plans/PLAN-NNN` | 17 plans. |
| `docs/plans/*-report.md`, `*-preregistration.md` | `docs/research/` | Goalie research. |
| `docs/context/analysis/`, `docs/context/session-logs/` | `docs/research/`, `docs/versions/<v>/reviews/` | |
| `docs/data-limitations.md`, `docs/2024-season-support-status.md` | `docs/STATUS.md` and a `DEC-NNN` per accepted limitation | |
| `docs/elite-classification-model.md`, `docs/team-deployment-analysis.md` | `docs/versions/<v>/specs/` | These define externally observable behavior. |
| `docs/fly-deploy-runbook.md`, `resources/vps-setup-guide-fly.md` | `code/docs/operations/` | The runbook is gitignored today. Keep that decision. |
| `docs/commands.md` | `code/CONTRIBUTING.md` | |
| `resources/*.md` (rules, situationCode, API notes) | `docs/research/technical/` | Evidence, not spec. |
| `GLOSSARY.md` | `docs/GLOSSARY.md` | Direct move. |
| `DESIGN.md` | `docs/design/DESIGN-SYSTEM.md` | Clean fit. Already a 9-section design system. See the "Design system placement" section for the skill trigger. |
| `v2/browser/notes/`, `pages/notes.py` | `docs/design/flows/` or leave in code | Glossary-style notes the app renders. Decide whether they are product content or code. |
| No equivalent | `code/ARCHITECTURE.md` | New document. Source material: `runtime_paths.py` docstring, `Dockerfile` comments, `v2/*/README.md`, memory files. |
| `CHANGELOG.md` | `code/CHANGELOG.md` plus `docs/versions/<v>/releases/*.yaml` | Existing tags `v2.2.0`, `v2.3.0`, `v3.0.0` become release records. |
| `CLAUDE.md` | `code/AGENTS.md` with `CLAUDE.md` as a pointer | Content is almost entirely code-side. |
| `v2/` | `code/src/` | Seven packages. |
| `v1/nhlgame.py` | `code/src/` or `code/scripts/` | Still the production fetcher. Not legacy. |
| `tools/` | `code/scripts/` | |
| `v2/*/tests/`, `tools/test_offwing_splits.py` | `code/tests/` or leave in place | 47 test files. |
| `Dockerfile`, `fly.toml`, `.dockerignore`, `.github/` | `code/` root | |
| `pyproject.toml`, `uv.lock`, `v2/browser/requirements.txt` | `code/` root | Two dependency manifests today. |
| `sample-data/` | `code/tests/fixtures/` | |
| `data/` (20 GB, gitignored) | Outside both repositories | See the "Data tree" section. |
| `v2/browser/runtime_data/` | `code/dist/` | This is the scaffold's generated-output concept exactly. |
| `archive_2025_*.tar.gz`, `errors.json`, `.superpowers/` | Delete or leave at the old root | Untracked working files. |

Two things the scaffold asks for that the project has no equivalent of: acceptance records and release manifests. The closest existing evidence is the goalie preregistration and report pair, which is the acceptance pattern the scaffold wants applied to every version.

## Coupling that blocks a move

These are the concrete reasons stage 2 cannot happen by dragging folders. Each one is fixable, and each one is a place where a naive move would break a running system.

### Working-directory-relative data paths

Seven scripts resolve `data/` relative to the current working directory, not the file:

| File | Line |
| --- | --- |
| `v2/timelines/generate_timeline.py` | 27 |
| `v2/competition/compute_competition.py` | 23 |
| `v2/players/get_players.py` | 89, 111, 375 |
| `v2/browser/build_league_db.py` | 40 |
| `v2/browser/build_edm_db.py` | 27 |
| `v2/edge/compute_burst_rates.py` | 136 |
| `v2/edge/fetch_skater_detail.py` | 34 |

These work only because every documented command runs from the repository root. If `data/` is no longer a sibling of the invocation directory, every one of them fails silently or writes to the wrong place. The competition test at `v2/competition/tests/test_compute_competition.py:173` documents this dependency explicitly.

### File-relative repository roots

Eight modules compute the repository root by walking up from `__file__`:

- `v2/browser/runtime_paths.py:41` uses `parents[2]`.
- `v2/browser/build_goalies_db.py:16` uses `parents[2]`.
- `v2/orchestrator/config.py:7` uses `parent.parent.parent`.
- `v2/goalies/{build_shots,portability,era_probe,cut,switch_registry,build_terms,freeze_value,game_difficulty}.py` use `parent.parent.parent`.
- `v2/browser/tests/test_smoke.py:43` and `test_build_goalies_db.py:135` use `parents[3]`.

Adding a `code/` level changes the depth by one and every one of these points at the wrong directory. The memory file `feedback_module_level_path_parents.md` records that this exact class of bug cost a deploy cycle already.

### `v2.` as an import package name

The goalies package and two build scripts import as `from v2.goalies.cut import ...`, with `sys.path.insert` of the repository root to make it work. Renaming `v2/` to `src/` or moving it under `code/` breaks 14 import sites. The fix is to give the code a real package name and install it editable, which is also what the scaffold's `src/` layout implies.

### Orchestrator absolute paths

The nightly orchestrator hardcodes the current location:

- `v2/orchestrator/run.sh:5` runs `cd /Users/jrf1039/files/projects/nhl`.
- `v2/orchestrator/run.sh:12` uses a pyenv interpreter path.
- `v2/orchestrator/com.nhl.orchestrator.plist` lines 23, 26, 40, and 42 hardcode the repository path and log paths.
- `v2/orchestrator/config.py:37-44` builds script paths from `PROJECT_ROOT`, including `v1/nhlgame.py` and `tools/`.

Moving the repository without reinstalling the launchd plist stops the nightly pipeline with no error visible in the repository.

### Docker build context

`Dockerfile` copies `v2/browser/` to `/app/` and checks for five runtime files. `.dockerignore` excludes `v1/`, `tools/`, `docs/`, `resources/`, `data/`, and `sample-data/` by name. `tools/sync-runtime-data.sh` derives the repository root from its own location and copies from `data/` into `v2/browser/runtime_data/`. The GitHub Actions workflows reference `v2/browser/requirements.txt` and run `pytest v2/`. All of these need path updates for stage 2. None need to change for stage 1.

### Claude Code auto-memory

The persistent memory directory is keyed to the absolute project path: `~/.claude/projects/-Users-jrf1039-files-projects-nhl/memory/`. Moving or renaming the directory orphans ten memory files and the index. Copy the memory directory to the new key before the first session in the new location. This applies to any stage that renames the top-level directory, and it is the one item on this list that a code-only review would never catch.

## Design system placement

The scaffold revision reviewed for this report resolves the earlier collision between a visual `DESIGN.md` and a technical design document. Visual design now lives at `docs/design/DESIGN-SYSTEM.md` in the product record, and the code repository carries `ARCHITECTURE.md` for system structure. The nhl `DESIGN.md` is already in the scaffold's 9-section design-system shape, so it moves to `docs/design/DESIGN-SYSTEM.md` with a frontmatter block and a governance section added.

One tooling dependency remains. The `front-end-design` skill auto-triggers only on a file named `DESIGN.md` in the project root. Its `SKILL.md` states this at line 14 and repeats it at line 25. After the move, that trigger goes quiet. Two options:

- Keep a one-line `DESIGN.md` at the code root that points to `docs/design/DESIGN-SYSTEM.md`. The skill still fires and reads the pointer. Cheapest, and it mirrors how the scaffold treats `CLAUDE.md` as a pointer to `AGENTS.md`.
- Update the skill to also look for `docs/design/DESIGN-SYSTEM.md`. Better long term if every scaffold project uses this layout. That change is in the skill repository, not this one.

Recommended: do the first now and the second when a second scaffold project exists. Record the choice as `ADR-001`.

`ARCHITECTURE.md` has no existing source file. The content exists in fragments: the two-mode data policy in `runtime_paths.py`, the runtime-file guard in `Dockerfile`, the package READMEs under `v2/`, and the deploy and backfill memory files. Writing it is stage 1 work and needs no code change.

## Data tree

`data/` is 20 GB, gitignored, and lives in the repository root. The scaffold has no home for it, and it does not belong in either repository. The `DATA_DIR` environment variable already exists for the deployed app. Generalizing it to the pipeline scripts, so that every `Path("data")` becomes `Path(os.environ.get("NHL_DATA_DIR", ...))`, decouples the code from the data location and is a prerequisite for stage 2 whether or not the data moves.

## Where the project already matches the scaffold

- Dated design and plan pairs in `docs/plans/` are the spec and plan artifacts. They lack IDs and status fields.
- The goalie preregistration plus report is a complete acceptance record in the scaffold's sense.
- `CHANGELOG.md` with git tags `v2.2.0`, `v2.3.0`, and `v3.0.0` is the release history. It needs the docs-baseline commit reference to become a manifest.
- `runtime_paths.py` is the two-mode data policy the scaffold's `dist/` README asks for.
- The Dockerfile build guard and the `requires_data` pytest marker are release-evidence discipline.
- `CLAUDE.md` plus the memory files carry the "agent boundaries" content that `AGENTS.md` formalizes.

## Where the scaffold would be a poor fit

- **Design split from code.** The visual design system moves to the docs repository in stage 3, but the CSS that implements it stays in `v2/browser/assets/`. Every token change then touches two repositories. Tolerable in stages 1 and 2, where both are one tree.
- **Two repositories for one person.** The scaffold justifies the split by different contributors, access controls, and release cycles. This project has one contributor and one release cycle. The split costs cross-repository linking on every change and returns little until a second person joins.
- **Minor-version dossiers versus a research cadence.** The goalie evaluation ran as P0 through P6 phases over two months and produced one deployable change. The scaffold's `versions/` model fits shipped features well and research arcs poorly. Use `docs/research/` for research and reserve dossiers for versions that ship.
- **Waiver overhead.** The scaffold's `standard` profile requires spec, plan, review, acceptance, and release for every change. Most nhl changes are `quick-fix`. Declare `quick-fix` as the default profile for this project and require the full set only for a new stat model or a schema change.

## Stage 1 checklist

All additive. No functional risk.

1. Write `docs/OBJECTIVE.md` from `Project Kickoff.md` and the `README.md` stat-model section.
2. Write `docs/STATUS.md` from the current memory index and `docs/opportunities.md`.
3. Move `DESIGN.md` to `docs/design/DESIGN-SYSTEM.md` and leave a pointer `DESIGN.md` at the root so the `front-end-design` skill still triggers. This is the one stage 1 item that moves a file.
4. Write `ARCHITECTURE.md` from the fragments named in the "Design system placement" section.
5. Create `docs/decisions/` and backfill the decisions that already constrain the code: 5v5 excludes 4v4, deploys are local-only, runtime data is image-baked, `master` is the default branch.
6. Create `docs/policies/` by copying the scaffold's three policy files and setting `quick-fix` as the default profile.
7. Add `AGENTS.md` at the root with the current `CLAUDE.md` content, and reduce `CLAUDE.md` to the pointer. Verify the next session still loads the instructions.
8. Assign `SPEC-NNN` and `PLAN-NNN` IDs to the 50 existing docs in `docs/plans/` by adding frontmatter, without renaming files, so the memory files and session logs that link to them stay valid.
9. Create `docs/versions/3.0/` as the active dossier and index the existing `v3.0.0` tag.

## Stage 2 prerequisites

Do these before moving any source file.

1. Replace every `Path("data")` and `f"data/{season}"` with a single `data_root()` helper that reads `NHL_DATA_DIR` and falls back to the repository root. `runtime_paths.py` is the model.
2. Replace every `parents[N]` root lookup with the same helper or with an installed package.
3. Give `v2/` a package name in `pyproject.toml`, install it editable, and drop the `sys.path.insert` lines and `v2.` import prefix.
4. Merge `v2/browser/requirements.txt` into `pyproject.toml` or document why two manifests exist.
5. Parameterize `run.sh` and the plist on the repository path, and write the reinstall step into `code/docs/operations/`.
6. Copy the Claude Code memory directory to the new path key.
7. Run `python -m pytest v2/ -v`, one full orchestrator cycle, `./tools/sync-runtime-data.sh`, and a Docker build, and compare the built image's five runtime files against the current image before deploying.

## Bottom line

The project can move to this format without breaking the pipeline, the nightly orchestrator, or the deployed app, but only in stages and only after the path coupling is removed. The document model is worth adopting immediately. The repository split is not worth its cost until a second contributor or a separate docs release cycle exists.
