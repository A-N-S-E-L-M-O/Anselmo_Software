# A.N.S.E.L.M.O — release notes

## v1.007 — 2026-07-22

This build sharpens two things you'll feel in use: long web research with the agent, and how many languages Selmo can speak.

**Deep research now finishes instead of stalling.** Before, a broad "search the web from several angles" task could fill the model's memory and stop with nothing on screen. Now the agent uses the whole context window, and as it nears the limit it stops gathering and writes the answer from what it found, so you still get a result. It also gained a way to open a page in full rather than only the short search snippet: it searches to find sources, then reads the promising ones the same way it reads a local file. This needs web search switched on.

**Voice speaks more languages.** Read-aloud now covers Japanese, Chinese, Korean, Hindi, French, Spanish and Brazilian Portuguese alongside Italian and English, choosing the voice from the language of the text automatically. German falls back to the default voice.

### Upgrading

Unzip over your existing folder; your `models\` and settings are untouched. Hard-refresh the browser once with **Ctrl+F5** so the updated client loads.

## v1.001 (beta) — 2026-07-17

A small patch on top of 1.0. It fixes Agent mode in the packaged build and makes
the Stop button behave while the agent is reasoning.

**Agent mode, now working in the distributed build.** With the Agent toggle on,
the model gets direct access to a folder you choose. It can list and read the
files inside, search across them for what you need, and — only if you tick the
write permission — create or change files, working through several steps to finish
a task instead of replying in one shot. Web search, when you switch it on, becomes
a tool the agent can call, so it reaches past your machine only when you let it.
You pick the folder, that folder is the boundary, and writing stays off until you
grant it. Agent mode asks a lot of the model: it lights up only on one that can
call tools reliably (the reference is Qwen3.6-35B-A3B — see `docs\MODELS.md`) and
stays greyed with an explanation on one that can't.

Why 1.0 needed this: the bundle deliberately never ships your personal agent
settings, because they hold an absolute folder path and a write flag that must
start empty on someone else's PC. The catch was that the list of tools the agent
could use lived in that same file, so a fresh unzip left the model with nothing to
call and the folder picker with no real effect. The tool catalog now lives in the
code itself. A freshly unzipped Selmo has a working agent straight away, and the
settings file keeps only the folder you pick and whether writing is allowed.

**Stop works while the agent reasons.** Pressing Stop during an agent run used to
cancel only the call in flight. Between steps, or while a tool was running, the
loop would quietly begin the next step anyway — easy to hit with reasoning on,
where each step runs long. Stop now ends the whole loop cleanly, and you can start
a new turn right after.

A small thing you'll notice: the Selmo avatar spins like a washing-machine drum
while it thinks. In agent mode that spin could keep going after you pressed Stop,
because the turn never truly ended. It now settles the moment the agent stops.

### Install

Same as 1.0. Unzip anywhere (avoid OneDrive/Dropbox folders), drop a `.gguf` into
`models\`, and double-click `Selmo.cmd`. Full guide in `QUICKSTART.md`; models,
including the embedders for folder search, in `docs\MODELS.md`.

### Upgrading from 1.0

Unzip over your existing folder or into a fresh one — your `models\` and settings
are untouched. Hard-refresh the browser once with **Ctrl+F5** so the updated
client loads. If you had already chosen an agent folder it stays put; the agent
simply has its tools back.

Windows, tested on Firefox.

## v1.0 — 2026-07-13

The first stable release. A.N.S.E.L.M.O — Selmo, to friends — is a local-first AI
that runs entirely on your own Windows PC: no account, no cloud, no telemetry, and
nothing you write leaves the machine (the only exceptions are the one-time engine
download on first launch and any web searches you switch on). This 1.0 closes the
beta series and adds the two capabilities that were missing to call the package
complete.

**Agent mode.** Turn on the Agent toggle and the model can work inside a folder
you choose — listing, reading and, if you allow it, writing files — reasoning
across several steps to finish a task instead of answering in one shot. You pick
the folder, that folder is the boundary, and writing stays off until you grant it.
Web search, when it is on, becomes a tool the agent can call, so it reaches outside
the machine only when you let it. Agent mode asks a lot of the model: it lights up
only on a model able to call tools reliably, and stays greyed with an explanation
on one that can't. The reference model for it is Qwen3.6-35B-A3B — see
`docs\MODELS.md`.

**Folder search (RAG).** Point Selmo at a folder of your own files and it builds a
local semantic index, so you can ask questions across the whole set and the agent
can search it too. It all stays on the machine: a tiny embedding model does the
work on the CPU, and the index is written next to Selmo, never uploaded. Prose and
source code each get their own tuned embedder — details in `docs\MODELS.md`.

**Everything the betas already did**, now settled:

- Local chat on llama.cpp, on a GPU or the CPU alone, zero-install and click-to-run.
- Web search with a local SearXNG option and a public fallback.
- The whole-document pipeline that covers every passage of a long file, provably, rather than retrieving a few snippets.
- Voice: speak to Selmo (Whisper), hands-free conversation (VAD), replies read aloud (Kokoro).
- Image input, vision and OCR; local image generation via stable-diffusion.cpp.
- The on-screen energy monitor — watts, watt-hours, tokens per Wh — that no other local AI puts in front of you.
- Phone access to your PC's model over the LAN, secured and openable by QR code.
- A trilingual interface (Italian, English, French), and no telemetry of any kind.

The license is **source-available** (Apache 2.0 with the Commons Clause): use it,
study it, change it, share it — you just may not sell it. See `LICENSE`, `NOTICE`
and `TERMS.md`.

### Install

Download the 1.0 bundle, unzip it anywhere (avoid OneDrive/Dropbox folders), drop
a `.gguf` into `models\`, and double-click `Selmo.cmd`. Full guide in
`QUICKSTART.md`; recommended models, including the embedders for folder search, in
`docs\MODELS.md`.

### Upgrading from a beta

Unzip over your existing folder or into a fresh one — your `models\` and settings
are untouched. Hard-refresh the browser once with **Ctrl+F5** so the 1.0 client
loads. Agent mode and folder search each need their model in `models\`: an
agent-capable chat model for the agent, and a small embedding model for search.

Windows, tested on Firefox. Voice, image generation, CUDA and the hardware monitor
stay optional add-ons; the base now covers chat, web search, documents, folder
search and the agent.

## v0.929 (beta) — 2026-07-10

**Scan to open Selmo on your phone.** The phone-access popup (the 📱 button in the
header, desktop only) now shows a QR code of your Selmo address. Point your
phone's camera at it and the browser opens straight on the phone — no typing the
`https://…:8443` address by hand. The typed address stays underneath as a
fallback. The QR is drawn on your own machine, fully offline: no external
service, nothing about the address leaves the PC.

**Documentation corrected.** A few details in the quick start had fallen behind
the software:

- The engine is **not** auto-picked per machine. The base download is a
  universal **Vulkan** build that runs on any GPU, and on the CPU alone when
  there is no graphics card.
- The faster **CUDA** engine is an optional add-on (`Install-CUDA.cmd`, NVIDIA
  only), reversible with `Uninstall-CUDA.cmd`. The website quick start was
  missing it entirely — it is now listed.
- The quick start now reflects that the **Desktop / Start-menu icon is created
  automatically on first launch** (then pin it to the taskbar; re-create it any
  time with `Create-Selmo-Shortcut.cmd`). The old manual "Send to → Desktop"
  step is gone.
- Model docs made clearer: **no model ships bundled** — Qwen included. You
  download the model you want. The tuned launch presets in `selmo-models.ini`
  ship; the weights do not.

### Install

Download `Selmo-beta-0.929.zip`, unzip it anywhere (avoid OneDrive/Dropbox
folders), drop a `.gguf` into `models\`, and double-click `Selmo.cmd`. Full guide
in `QUICKSTART.md`; recommended models in `docs\MODELS.md`.

### Upgrading from 0.928

Unzip over your existing folder (or into a fresh one) — your `models\` and
settings are untouched. In the browser, hard-refresh with **Ctrl+F5** once so the
updated client loads.

Windows, tested on Firefox. Voice, image generation, CUDA and the hardware
monitor stay optional add-ons; the base is chat, web search and documents.
