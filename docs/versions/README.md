# Versions

One folder per release, named for its version, such as `docs/versions/0.1.0/`. A release's folder holds everything that went into it. Start the folder when the release's roadmap milestone starts, and write its `README.md` before any code, so the plan survives if the session that builds it ends.

## A release folder

```text
docs/versions/<version>/
├── README.md   The release record. Always present.
├── specs/      superpowers specs, when the project uses superpowers
├── plans/      superpowers plans, when the project uses superpowers
└── reviews/    reviews of the release: orko-review runs, or a review saved by hand
```

- **Without superpowers,** `README.md` holds the design.
- **With superpowers,** the spec and plan hold the design.
- Either way, when the folder holds more than `README.md`, its "This folder" section lists every file, so `README.md` is the index of the release.
- Keep `specs/` and `plans/` directly in the release folder, not in a `superpowers/` subfolder. orko-review then writes every review of the release, whether of the spec, the plan, or `README.md`, to the one `reviews/` folder.
- Commit the review runs, because later releases cite them.
- Real user data stays out of the folder. Keep it in the gitignored `tmp/`.
- To correct an earlier release's record, say so in the current release's `README.md`, and leave the earlier record as written.

## The release README

Copy this skeleton into `docs/versions/<version>/README.md`. When the owner says so, a patch release can leave out the design and the human test.

```markdown
# v<version>: <milestone name>

<Which roadmap milestone this is, and what it delivers.>

Rulings: <the DECISIONS.md entries that govern this release, when the project has DECISIONS.md>

## This folder

<Every file in this folder, one row each. Leave this section out when the folder holds only this README.>

| Path | What it is |
|---|---|

## What the release changes

| Path | What it is |
|---|---|

## Design

<Without superpowers: the design, written before any code. With superpowers: a link to the spec and the plan.>

## Human test

<Numbered steps the owner runs in a real session, with a check at each step. End with what to record in Results.>

## Results

### <Human test or Machine-led tests>, <YYYY-MM-DD>

- **Run by:**
- **Result:**
- **Found:**
- **Changed:**

## Close-out

- [ ] Every file in this folder listed under "This folder", and the human test recorded under "Results"
- [ ] The version added to `CHANGELOG.md`
- [ ] The milestone's row and log entry added to `docs/history.md`
- [ ] The milestone removed from `ROADMAP.md`, so the next milestone is first in its list
- [ ] The release branch merged into the branch releases build on, with `git merge --ff-only`
- [ ] The release commit tagged, when the project tags releases: the commit that adds the version to `CHANGELOG.md`
- [ ] The release branch deleted with `git branch -d`, which refuses a branch that isn't merged
- [ ] The next release's branch created from the branch releases build on
```

## Closing out a release

A release isn't done until it's closed out. The next minor or major release starts by closing out the previous one, unless the owner says its work carries over. A patch release skips the close-out and stays on its release's branch. Closing out doesn't open a pull request, which can wait.

Closing out moves the finished milestone from `ROADMAP.md` to `docs/history.md`, so the roadmap holds only planned work, and the release `README.md` holds the record of what the milestone delivered.

When each release has its own git worktree, the close-out adds three steps: create the next release's worktree from the branch releases build on, move gitignored files the next release needs, such as `tmp/`, into it, then remove the old worktree before deleting its branch.

Where a session starts decides what it can run:

| Session started in | Can run the close-out |
|---|---|
| A release's worktree | No. It can't run git against the main checkout or another worktree, and its `!` commands fail the same way |
| The main checkout, or a folder that contains the project | Yes |
| A terminal outside Claude | Yes |

Start the next release's session in its own worktree, the main checkout, or a parent folder, never in the previous release's worktree. A session started in a parent folder doesn't load the project's `AGENTS.md` or memories, so its opening prompt names them and the order to read them in.
