# Selmo — instructions for Claude

Read **first** `docs/selmo-dev.md` (the "Lessons learned" section) and `docs/selmo-bug-report.md`.

## Git workflow — Fabio's rule (session 13) · DO NOT DEVIATE

Git is the **only** safety net. Backups via `bk.bat` / `restore.bat` / `bk*` folders are **deprecated**: don't use them, don't create them, don't propose them.

**Only Fabio commits and bumps the version, via git. HARD RULE — DO NOT DEVIATE.**
Claude must **never** run `git commit`, `git add … && git commit`, `git tag`, or any version bump on its own — not even on positive feedback, not "to be helpful". The sandbox mount can serve corrupted file views (BUG-META-02), so a commit issued from the agent can poison the repo with NUL/truncated blobs. The final git step is Fabio's alone, run in his own Windows shell.

On **every positive feedback from Fabio** (e.g. "it works", "ok", "perfect", "we're there"):
1. Claude **prepares** the change in the working files (real files via the Read/Edit tools or clean writes) and then **hands Fabio a ready-to-paste commit command** — it does not run it.
2. The handoff must also **bump the version** by **+0.001** (thousandths): the `v0.x` badge in `chat.html` (search for `class="hbadge"`), the changed scripts' `?v=` in `chat.html`, **and** the `docs/selmo-dev.md` header. E.g. v0.7 → v0.701 → v0.702. **v1.0 is reserved** for the "real" release; don't reach it with incremental bumps.
   - **Claude does NOT edit the badge / `?v=` / dev.md header itself.** Editing `chat.html` for a version bump forces the whole Python-via-bash + BUG-META verification dance for a trivial string change. Instead Claude hands Fabio a **PowerShell substitution snippet** (placed *before* the git lines) that performs the bump in-place. This is the standard — it keeps bumps cheap so we do them more often. (Claude still edits `chat.html` directly, via Python, for real feature/markup changes — just not for the version strings.)

Don't let confirmed-good work sit unrecorded: the moment Fabio confirms, give him the exact commit command so nothing good is lost (costly lesson s13: the working vision version lived only in the working tree and was never committed → lost). But never prepare a commit for **unconfirmed** states: if it's an attempt, say so and wait for Fabio's test first.

### Commit-command format — DO NOT DEVIATE

- **PowerShell, not bash.** Fabio runs Windows PowerShell 5.1, which has **no `&&`**. Give each git command on its **own line** (preferred), or chain with `;` on one line. Never hand him a `git add … && git commit …` string.
- **No `cd`.** Fabio opens the terminal by right-clicking the Selmo folder, so the shell is **already in the repo root**. Do not prepend `cd <path>` — commit commands assume the working directory is the project root.
- **ASCII-only commit messages.** Use plain hyphens `-` and ASCII punctuation in the `-m` message (no em-dashes `—` or arrows `→`); the PS 5.1 console can mangle non-ASCII in the message.
- **Version bump = a PowerShell substitution snippet, not a Claude edit (DO NOT DEVIATE).** Hand it *before* the `git add`/`git commit` lines, tailored each time with the exact old→new strings. Use literal `.Replace()` (not `-replace`, which is regex) and write UTF-8 **without BOM** via .NET so accented chars round-trip cleanly. Template (adjust strings + which scripts changed):

  ```powershell
  $f='chat.html'; $t=[IO.File]::ReadAllText($f)
  $t=$t.Replace('hbadge">v0.917','hbadge">v0.918').Replace('selmo-media.js?v=0.916','selmo-media.js?v=0.918').Replace('selmo-boot.js?v=0.916','selmo-boot.js?v=0.918')
  [IO.File]::WriteAllText($f,$t,(New-Object Text.UTF8Encoding $false))
  $d='docs/selmo-dev.md'; $t=[IO.File]::ReadAllText($d)
  $t=$t.Replace('v0.917*','v0.918*')
  [IO.File]::WriteAllText($d,$t,(New-Object Text.UTF8Encoding $false))
  ```
  Only `.Replace()` the `?v=` of scripts that actually changed; leave the rest. The `docs/selmo-dev.md` changelog *entry* (the prose line) is Claude's to write in the file as usual — only the header version string moves via the snippet.

## chat.html — permanent rules

- **NEVER** use the Edit tool on `chat.html` (it truncates silently). Python via bash only — see BUG-META-01.
- `node --check` on the extracted script after every change; verify with the Read tool, not with `cat`/`wc` from bash.
- Restart `llama-server` after a change (it can serve from cache); anti-cache meta + Ctrl+F5.
- **Target browser: Firefox** (desktop + Firefox for Android). No Chrome-isms (`chrome://flags`, Chrome-only APIs); Firefox uses its **own NSS cert store**, not the OS one, and the phone mic needs a secure context — see BUG-MIC-01.
