# Selmo — instructions for Claude

Read **first** `selmo-dev.md` (the "Lessons learned" section) and `selmo-bug-report.md`.

## Git workflow — Fabio's rule (session 13) · DO NOT DEVIATE

Git is the **only** safety net. Backups via `bk.bat` / `restore.bat` / `bk*` folders are **deprecated**: don't use them, don't create them, don't propose them.

**Only Fabio commits and bumps the version, via git. HARD RULE — DO NOT DEVIATE.**
Claude must **never** run `git commit`, `git add … && git commit`, `git tag`, or any version bump on its own — not even on positive feedback, not "to be helpful". The sandbox mount can serve corrupted file views (BUG-META-02), so a commit issued from the agent can poison the repo with NUL/truncated blobs. The final git step is Fabio's alone, run in his own Windows shell.

On **every positive feedback from Fabio** (e.g. "it works", "ok", "perfect", "we're there"):
1. Claude **prepares** the change in the working files (real files via the Read/Edit tools or clean writes) and then **hands Fabio a ready-to-paste commit command** — it does not run it.
2. The commit command must also **bump the version** by **+0.001** (thousandths): the `v0.x` badge in `chat.html` (search for `class="hbadge"`, ~line 421) **and** the header of `selmo-dev.md`. E.g. v0.7 → v0.701 → v0.702. **v1.0 is reserved** for the "real" release; don't reach it with incremental bumps.

Don't let confirmed-good work sit unrecorded: the moment Fabio confirms, give him the exact commit command so nothing good is lost (costly lesson s13: the working vision version lived only in the working tree and was never committed → lost). But never prepare a commit for **unconfirmed** states: if it's an attempt, say so and wait for Fabio's test first.

## chat.html — permanent rules

- **NEVER** use the Edit tool on `chat.html` (it truncates silently). Python via bash only — see BUG-META-01.
- `node --check` on the extracted script after every change; verify with the Read tool, not with `cat`/`wc` from bash.
- Restart `llama-server` after a change (it can serve from cache); anti-cache meta + Ctrl+F5.
