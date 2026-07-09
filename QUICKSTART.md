# A.N.S.E.L.M.O — Quick start (install on any Windows PC)

A.N.S.E.L.M.O — Selmo, to friends — runs **entirely on the PC**: no account,
no cloud, and nothing you write ever leaves the machine (the only exceptions:
the one-time engine download on first launch, and web searches if you turn
them on). This guide uses the portable bundle, so there is **no installer to
sign and no administrator rights**. Unzip, drop in a model, click. It works on
any Windows PC, with or without an NVIDIA card.

---

## In 3 steps

**1. Unzip the `Selmo` folder wherever you like**
The Desktop or `C:\Selmo` are both fine. Avoid cloud-synced folders (OneDrive,
Dropbox): they are slow and not needed.

**2. Get a model**
On the first launch Selmo offers to download a default (Mistral-7B-Instruct v0.3,
Apache 2.0 and European, fits an 8 GB PC) - say yes and you are ready to chat.
Prefer your own? Say no and drop a `.gguf` into `models\`; the recommended ones
are listed in `MODELS.md` (in the Selmo folder).

**3. Double-click `Selmo.cmd`**
That is the file to launch the **first** time. On that first run Selmo puts a
**Selmo icon on your Desktop** (and in the Start menu) - from then on just click
that little face to start it, and right-click it → **Pin to taskbar** to keep it
one click away. (Deleted the icon by mistake? Double-click
`Create-Selmo-Shortcut.cmd` in the Selmo folder to put it back.)

Done. The browser opens with Selmo.

---

## What happens on the first launch

The **first** time, a black window opens and downloads the right engine for that
PC (the NVIDIA build if there is an NVIDIA card, otherwise the build that also
runs on CPU alone). It takes a minute or two and needs the internet **only this
once**. Then the browser opens by itself.

From the second launch on it starts straight away, even offline.

Down by the clock, bottom-right, the **Selmo icon** appears: it is the engine
running in the background. You pick the model and chat in the browser; the icon
is just where you shut everything down (right-click → Exit).

---

## Optional add-ons — voice, images, hardware monitor

The base edition is deliberately light: **chat, web search and documents**. Three
optional add-ons live in the Selmo folder as separate files you can run — or
ignore — independently. Each is a single double-click; run it, then restart Selmo.

- **`Install-Voice.cmd`** — speak to Selmo (Whisper transcription) and have it read
  replies aloud (Kokoro). Downloads ~330 MB; the transcription model is fetched the
  first time you use the microphone.
- **`Install-Image.cmd`** — local image generation (Z-Image-Turbo via
  stable-diffusion.cpp). It **needs a graphics card** (NVIDIA, AMD or Intel) and
  stops by itself on a PC without one. Downloads ~9 GB.
- **`Install-CUDA.cmd`** — **NVIDIA only**: swaps Selmo's engine for the faster
  CUDA build. The base uses a universal Vulkan engine that runs on any GPU and on
  CPU; on an NVIDIA card CUDA is quicker. It stops by itself on a non-NVIDIA PC,
  downloads a few hundred MB, and is reversible with `Uninstall-CUDA.cmd`.
- **`Install-Hardware-Monitor.cmd`** — installs LibreHardwareMonitor so the energy
  monitor shows the **real CPU watts** instead of an estimate (asks for admin once,
  to read the CPU sensors).

Until an add-on is installed, its buttons in the bottom bar stay greyed out —
nothing in the interface pretends to work when the service behind it is missing.

**Removing an add-on** is just as easy: run its `Uninstall-…` twin in the same
folder. Voice and Image only delete their own files (freeing the disk space);
the hardware monitor's uninstaller also removes its background task. To remove
Selmo completely, run `Uninstall-Hardware-Monitor.cmd` first (if you ever
installed it), then delete the whole folder.

---

## The energy monitor — an on-screen estimate

On the right of the screen A.N.S.E.L.M.O shows an **estimate** of the power your
PC draws while it works: watts (CPU + GPU together), the watt-hours spent this
session and in total, the speed in tokens per second, and the running cost in
your own currency. Set your electricity price once in the `euro/kWh` field and
the cost estimate follows it.

This is a figure no other local AI puts on screen, and it is enough to compare a
light model against a heavy one on the same PC. But it is an **estimate, not a
certified measurement**: the GPU draw is read from the card, while the CPU and
the rest of the system are approximated from load (the CPU figure carries a `~`
when it is estimated rather than measured). If you want the exact number, a
plug-in wall power meter or a smart plug with energy metering measures what the
whole PC really pulls from the socket — and you can tune Selmo's estimate against
that reading. To have the CPU power measured rather than estimated, see the
optional LibreHardwareMonitor step near the end of this guide.

---

## If Windows blocks the launch

Windows may show **"Windows protected your PC"** (SmartScreen), because the file
is not signed. That is normal for a home-made program:

> click **More info** → **Run anyway**.

You only do this **once**. (This is exactly the signing hassle the bundle avoids:
there is no `.exe` to sign, just a script you start yourself.)

---

## If something does not start

- **"no .gguf file found in models\"** → the `models\` folder is empty: copy a
  `.gguf` file into it.
- **The black window closes immediately** → likely an antivirus block on the
  `python\` folder: add the `Selmo` folder to the antivirus exclusions.
- **The browser does not open** → open `http://127.0.0.1:8080/chat.html`
  manually.
- **From a phone** (same Wi-Fi) → open `https://PC-IP:8443/chat.html` and accept
  the certificate warning (once). The PC's IP is shown in the tray icon.

---

## What you do NOT need

No Python to install (it is already inside the folder), no installer, no
administrator, no account. Voice and image generation are optional extras: the
chat works without them.

---

## A note for educators and parents

Image generation is an optional extra: it stays off unless an image model is
placed in the `image\` folder. Be aware that text-to-image models — all of
them, not just the ones Selmo supports — can easily be pushed toward
inappropriate images, and a model running locally has **no cloud-side filter**.
In a classroom, or on a PC used by minors, the safest setup is the default
one: **leave the `image\` folder empty** and supervise the use of the chat.
Locally-run chat models only carry the safety training of whoever released
them — an adult nearby is the real filter.

---

## Optional — measure the CPU power instead of estimating it

The energy monitor needs no install: it runs the moment Selmo starts. On an
NVIDIA machine the GPU watts are read from the card; the CPU figure is an
**estimate** from load, marked with a `~`.

To have the CPU power **measured** instead, install LibreHardwareMonitor once.
Open the `Selmo` project folder, right-click an empty spot inside it, choose
**Open in Terminal**, then paste the command below and press Enter:

```powershell
powershell -ExecutionPolicy Bypass -File setup-lhm.ps1
```

It asks for administrator rights once (reading CPU package power needs them),
downloads LibreHardwareMonitor into `bin\`, sets it to start quietly at logon,
and Selmo then shows the real CPU watts — the `~` disappears. To check, open
`http://127.0.0.1:8085/data.json`: you should see CPU and GPU watts.

Some locked-down PCs block the sensor driver (Windows Defender flags this class
of driver). If that happens nothing breaks — Selmo keeps using the estimate. And
whatever the software reports, only a plug-in wall power meter or a smart plug
with energy metering measures exactly what the PC pulls from the socket.

---

## Optional — 100% local web search with SearXNG

Selmo can search the web. By default it uses public engines (the query leaves the
PC). If you want **searches to stay local too**, you can run SearXNG in a
container on the PC. This is **optional**: without it, search still works.

You need **Podman Desktop** (free, https://podman.io). Then, once: open the
`Selmo` project folder, right-click an empty spot inside it, choose **Open in
Terminal**, then paste the command below and press Enter:

```powershell
podman run -d --name searxng -p 8888:8080 `
  -e "BASE_URL=http://localhost:8888/" `
  searxng/searxng
```

Selmo detects SearXNG on `localhost:8888` by itself and routes searches to it:
from then on the sources bar shows "SearXNG local" and the query no longer leaves
the PC. To stop it: `podman stop searxng`. To restart it: `podman start searxng`.

*(This is the only piece that uses a container, and it is entirely optional —
that is why it sits at the bottom.)*
