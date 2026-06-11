# Selmo — instructions for Claude

Read **first** `selmo-dev.md` (the "Lessons learned" section) and `selmo-bug-report.md`.

## Git workflow — Fabio's rule (session 13) · DO NOT DEVIATE

Git is the **only** safety net. Backups via `bk.bat` / `restore.bat` / `bk*` folders are **deprecated**: don't use them, don't create them, don't propose them.

On **every positive feedback from Fabio** (e.g. "it works", "ok", "perfect", "we're there"):
1. Commit the confirmed change **immediately**, with a clear message.
2. **Bump the version** by **+0.001** (thousandths): the `v0.x` badge in `chat.html` (search for `class="hbadge"`, ~line 421) **and** the header of `selmo-dev.md`. E.g. v0.7 → v0.701 → v0.702. **v1.0 is reserved** for the "real" release; don't reach it with incremental bumps.

Don't accumulate uncommitted changes. Every confirmed-good state must end up in a commit, so it's never lost (costly lesson s13: the working vision version lived only in the working tree and was never committed → lost).

Don't commit **unconfirmed** states: if it's an attempt, say so and wait for Fabio's test before the commit + bump.

## chat.html — permanent rules

- **NEVER** use the Edit tool on `chat.html` (it truncates silently). Python via bash only — see BUG-META-01.
- `node --check` on the extracted script after every change; verify with the Read tool, not with `cat`/`wc` from bash.
- Restart `llama-server` after a change (it can serve from cache); a