# Review brief: operations

## Paths

- Lens: operations
- Document under review: /Users/jrf1039/files/projects/nhl/docs/superpowers/plans/2026-09-29-season-toggle-plan.md
- Spec: /Users/jrf1039/files/projects/nhl/docs/superpowers/specs/2026-09-29-season-toggle-design.md
- Evergreen docs: /Users/jrf1039/files/projects/nhl/CLAUDE.md, /Users/jrf1039/files/projects/nhl/DESIGN.md
- Reviews directory (off limits except your report): /Users/jrf1039/files/projects/nhl/docs/superpowers/reviews
- Write your report to: /Users/jrf1039/files/projects/nhl/docs/superpowers/reviews/2026-09-29-season-toggle-plan/2026-09-29-155748/operations.md

## Lens: operations

Check what the document proposes for:

- Deploy steps, configuration, and environment differences.
- CI: what runs, what gates a merge.
- Rollback: how to undo a bad release, and what can't be undone.
- Observability: how anyone would notice it broke.

## How to review

You have a fresh context on purpose. Nobody has told you what to think of this document, and nothing you need is missing: read the files listed under Paths, and read the codebase and any source the document cites. Treat the evergreen docs as constraints the document must respect. A conflict with one is always a finding.

- Report every finding you can support, at every severity. Don't filter to the important ones and don't soften them; the orchestrator filters.
- Verify before you claim. Each finding carries evidence someone else can re-check in under a minute: a file and line, a quote, a command and what it printed, or a URL and what it says. A suspicion you couldn't confirm is still a finding if you say what you checked and what stayed open.
- Say what the fix is. "Unclear" isn't a fix; the replacement text or the decision that's missing is.
- Record what you checked and found sound. It tells the orchestrator what your review covered.
- Don't edit the document under review or any file other than your report. If you need scratch space to verify something (a test run, an assembled build), create a fresh temporary directory of your own with `mktemp -d` and work only there; never modify an existing file. Running the project's code in place counts as modifying it (Python writes `__pycache__` next to the source, for one), so copy what you need into your directory first.
- Don't open anything under the reviews directory listed in Paths except your brief and your report path: not other reviewers' reports, not earlier runs, not `run.json`. Your review is worth something only if it's independent of theirs. Exclude that directory from any search you run (for example `grep -r --exclude-dir=<its name>`), or search only paths outside it.

Severity:

- `blocker` — the document can't be acted on as written: a wrong fact something depends on, a contradiction, a conflict with an evergreen doc, a missing piece that stops the next step.
- `major` — acting on it as written produces a defect or significant rework.
- `minor` — a real gap or error with a small blast radius.
- `nit` — wording, formatting, consistency.

## Report

Write the report to the path under Paths, in exactly this format. Number findings `F-1`, `F-2`, … with no gaps. If you have no findings, the Findings section holds the single line `None.` The Checked and sound section is never empty.

```markdown
---
lens: <your lens name, from Paths>
doc: <the document path, from Paths>
---

# <lens> review

## Verdict

<one of: ready | ready with changes | not ready>

## Findings

### F-1 [<blocker|major|minor|nit>] <one-line title>

- Where: <section heading or line>
- Evidence: <what you checked and what it showed>
- Problem: <what is wrong>
- Fix: <the concrete change to the document>

## Checked and sound

- <something you verified and found correct>
```

Writing the report is your last step. After you write it, read it back once to confirm it is on disk, then reply with one line: the report path.
