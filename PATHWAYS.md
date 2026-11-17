# Pathways

Files to add as the project grows. These are unproven suggestions: the canonical copy lives in the scaffold repository, and starting material for several of them is in that repository's `archive/formal-v1/`.

| Trigger | Add | Used by |
|---|---|---|
| UI work starts | `DESIGN.md` | `front-end-design` |
| A second builder joins | `CONTRIBUTING.md`, a PR template, and a CI workflow | Collaborators, GitHub |
| First internet-facing deployment, real users, or sensitive data | `SECURITY.md`, and a security review before each release | GitHub (`SECURITY.md`), `web-security` (the review) |
| A release with rollback stakes | Version tags | `git-tagging` |
| A decision gets relitigated | `DECISIONS.md`, append-only, with that rule stated at the top of the file. Number each entry with the `DEC` prefix, such as DEC1, and give it a date, the ruling, and why. Reverse a decision with a new entry that names the one it replaces. The only change allowed to an old entry is one appended line that points forward, such as `- **Replaced:** in part by DEC34, DEC42`. Name the file as controlling in `AGENTS.md`. | People and agents reading the project |
| Several documents describe the same behavior, such as `README.md`, `SECURITY.md`, and `ARCHITECTURE.md` | A "Keep the documents in sync" section in `AGENTS.md`. It holds a table of what each kind of change updates in the same commit, and a closing check: search the documents outside `docs/versions/`, `docs/context/`, and `docs/history.md` for every name the change added, renamed, or removed, and fix each match that disagrees with the code. | People and agents changing the project |
| An architectural choice needs its reasoning kept | `ARCHITECTURE.md` | `orko-review` |
| The code must be public and the documents private | A private parent git repository that holds the documents and ignores `code/`, with the code as a public repository in `code/`. Start sessions in the parent. A session loads the `CLAUDE.md` and the memories of the folder it starts in, not those of `code/`, so keep the project's rules in the parent's `AGENTS.md`, and name in the opening prompt anything in `code/` a session must read first. If the code already has history, start fresh history and scan for secrets first. | GitHub |
