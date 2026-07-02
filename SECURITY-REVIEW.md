# Selmo — Security review
*Autonomous review · July 2026 · covers the Python bridges, the front door, the launcher and the client*

Selmo is local-first by design ("your data stays on your computer"). But it is
served over the LAN on purpose (so the phone can reach it), so the real threat
model is **any other device on the same Wi-Fi / LAN** — a guest, a room-mate, a
compromised IoT gadget, or a public/school network the laptop roams onto. The
review is against that model: unauthenticated LAN peers, not a remote internet
attacker (nothing is exposed to the internet unless the user forwards a port).

Legend: **[FIXED]** applied in this pass · **[OPEN]** needs Fabio's decision.

---

## SEC-1 · `.git` directory was downloadable over the LAN — [FIXED]

**Severity: HIGH.** The front door (`selmo_https_proxy.py`) serves static files
from the project root. Its dotfile guard only checked the **final** path
component and a suffix blocklist, so `/.git/config`, `/.git/HEAD`, `/.git/index`
and the packed objects (leaf names `config`, `HEAD`, `index`, …, none starting
with `.`, none with a blocked suffix) were **served**. Any LAN peer could
`git clone` the working repo — including its **full history**. That history had
already been the subject of a secret/large-blob purge (dev log s24), so exposing
it is exactly the risk that work tried to close.

**Fix.** The static handler now rejects any request path containing a
dot-segment (`.git/…`, any dotfile/dir, and `..` traversal) *before* resolving,
so a non-dot leaf inside `.git/` is still caught. Also added `.md` to the block
list — `selmo-dev.md` / `selmo-bug-report.md` / `CLAUDE.md` carried the LAN IP
and internal architecture and the UI never needs any `.md`. Verified: `.git/*`
and internal `.md` → 403; `chat.html`, the `.js`, `selmo-config.json`, `selmo.crt`
still served.

## SEC-2 · Every backend bridge was bound to `0.0.0.0` — [FIXED]

**Severity: HIGH (defence-in-depth).** Eight services each opened an
**unauthenticated** listener on **all interfaces**: web (8081), gpu (8082),
whisper (8083), tts (8084), image (8086), the tray **control API** (8087), plus
the front door (8080/8443). The client, though, talks **only** to the front door
via relative `/proxy/808x` paths (confirmed in `selmo-boot.js`: `API/GMON/WEB/CTRL`
are all `origin + /proxy/…`). So binding the backends to every interface bought
nothing and handed LAN peers direct, unauthenticated access to: run web searches
and file fetches through the machine, transcribe audio, synthesise speech,
**generate images** (GPU/CPU abuse), read power telemetry, and — worst —
**load/unload models and shut the whole app down** via `POST /control/exit` on 8087.

**Fix.** All six Python bridges now bind **`127.0.0.1`** (llama-server already
did, on 8089). Only the front door stays on `0.0.0.0` for LAN/phone access. The
front door reaches every backend over loopback, and the phone reaches them
**through** the front door, so **zero functional change** — the attack surface
drops from eight open doors to one.

## SEC-4 · `/fetch` allowed `file://` → local file read over the LAN — [FIXED]

**Severity: MEDIUM.** `selmo_web.py`'s `/fetch?url=` (and the `full=1` branch of
`/search`) passed the URL straight to `urllib.request.urlopen`, whose default
opener also handles `file://` and `ftp://`. So
`/proxy/8081/fetch?url=file:///C:/Windows/win.ini` would read an **arbitrary
local file** and hand it back — an SSRF that became local-file disclosure. (After
SEC-2 this is only reachable via the front door, but the read itself was the bug.)

**Fix.** `fetch_text` now rejects any scheme that isn't `http`/`https` before
fetching. Verified: `file://`, `ftp://`, `FILE://` → empty; `http/https` → allowed.

---

## Still OPEN — Fabio's call (no safe silent fix)

## SEC-3 · The front door itself is unauthenticated on the LAN — [OPEN]

After SEC-1/2/4 there is **one** door left, but it is still open to anyone on the
LAN with no auth: a LAN peer can use the whole UI, generate images, run searches,
and reach the control API through `/proxy/8087` (load/unload/switch model, and
`/control/exit` to kill Selmo). For a home network with only family devices this
is usually acceptable — it is the price of phone access. It is **not** acceptable
on a shared/public network (a laptop that roams onto school or café Wi-Fi).

Options, cheapest first — pick per how the machine is used:
1. **Do nothing** on a trusted home LAN (accept the residual risk). Fine for the
   daughter's PC if it stays on your home Wi-Fi.
2. **Drop `8087` from the front door's `ALLOWED_PORTS`** so model-control is no
   longer reachable over the LAN at all (the desktop still works; the *phone*
   loses in-browser model switching — a fair trade for a kid's machine).
3. **Shared secret**: a token in a config file that the front door checks on every
   `/proxy/…` request and `chat.html` sends as a header. Real access control;
   ~30 lines; the only option that also stops a malicious phone.
4. **Bind the front door to `127.0.0.1` too** (desktop-only, no phone/LAN at all)
   for a machine that never needs remote access.

I did not apply any of these because each changes intended behaviour (phone access
or the UX). My recommendation for the daughter's PC: **option 2** (closes remote
model-control and app-shutdown, keeps everything else working).

## SEC-5 · Self-signed TLS on 8443 — [OPEN, known]

Tracked as BUG-MIC-01. The cert is self-signed, so the phone shows a one-time
warning. Not fixable without a locally-trusted CA (mkcert). Low risk on a LAN;
listed for completeness.

---

## Checked and found clean

- **Command injection**: the `srv`/`params` strings from the control API and the
  image bridge are `shlex.split` and passed as **argv** to `subprocess` with
  `shell=False` — no shell, so no injection. (They *can* inject arbitrary
  llama-server / sd-cli flags, but that is gated behind SEC-3 now that 8087 is
  loopback-only + the front-door decision above.)
- **Path traversal** in the image init-image write and the Whisper upload:
  Whisper saves to a `tempfile.NamedTemporaryFile` (name controlled by the OS,
  extension whitelisted); no user string reaches a filesystem path.
- **Model/path selection** on the control API: models are looked up by name
  against a directory scan, so the request can't point the launcher at an
  arbitrary path.

---

## Files changed in this pass

`selmo_https_proxy.py` (SEC-1), `selmo_web.py` (SEC-2 + SEC-4),
`selmo_whisper.py`, `selmo_tts.py`, `selmo_image.py`, `selmo_gpu_monitor.py`,
`selmo_tray.py` (SEC-2). All are `.py` (not `chat.html`), edited with the Edit
tool; each edited region was re-read with the Read tool to confirm it landed
(the bash mount served a stale/truncated view of three of them — BUG-META-02 —
so `py_compile` on the mount is not a reliable check for those; the Read tool is).
