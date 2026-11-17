# Versions

One folder per release, named for its version, such as `docs/versions/0.1.0/`. A release's folder holds everything that went into it. Start the folder when the release's roadmap milestone starts, and write its `README.md` before any code, so the plan survives if the session that builds it ends.

## A release folder

```text
docs/versions/<version>/
├── README.md   The release record. Always present.
├── specs/      a separate spec, when the release has one
├── plans/      a separate implementation plan, when the release has one
└── reviews/    reviews of the release: orko-review runs, or a review saved by hand
```

- By default, `README.md` holds the design.
- When a release is large enough for a separate spec and plan, they hold the design, and `README.md` links to them.
- Either way, when the folder holds more than `README.md`, its "This folder" section lists every file, so `README.md` is the index of the release.
- Keep `specs/` and `plans/` directly in the release folder. orko-review then writes every review of the release, whether of the spec, the plan, or `README.md`, to the one `reviews/` folder.
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

<The design, written before any code, or links to the release's spec and plan.>

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
- [ ] The release commit tagged by oiler: the commit that adds the version to `CHANGELOG.md`
```

## Closing out a release

A release isn't done until it's closed out. The next minor or major release starts by closing out the previous one, unless the owner says its work carries over. A patch release skips the close-out.

Closing out moves the finished milestone from `ROADMAP.md` to `docs/history.md`, so the roadmap holds only planned work, and the release `README.md` holds the record of what the milestone delivered.

The project uses trunk-based development (`AGENTS.md` section "Project rules"), so a release has no branch or worktree of its own. Its work is committed to `master` as it's built.
