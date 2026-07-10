# A.N.S.E.L.M.O — release notes

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
