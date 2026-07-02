# Selmo — Quick start (install on any Windows PC)

Selmo runs **entirely on the PC**: no account, no cloud, nothing leaves the
machine. This guide uses the portable bundle, so there is **no installer to
sign and no administrator rights**. Unzip, drop in a model, click. It works on
any Windows PC, with or without an NVIDIA card.

---

## In 3 steps

**1. Unzip the `Selmo` folder wherever you like**
The Desktop or `C:\Selmo` are both fine. Avoid cloud-synced folders (OneDrive,
Dropbox): they are slow and not needed.

**2. Put a model in the `models\` subfolder**
A small model is **already included**, so you can skip this the first time. To
add more: download a `.gguf` file and copy it into `models\`. The recommended
models are listed in `installer\MODELS.md`.

**3. Double-click `Selmo.cmd`**
That is the only file to launch. Keep it handy (or make a Desktop shortcut:
right-click `Selmo.cmd` → Send to → Desktop).

Done. The browser opens with Selmo.

---

## What happens on the first launch

The **first** time, a black window opens and downloads the right engine for that
PC (the NVIDIA build if there is an NVIDIA card, otherwise the build that also
runs on CPU alone). It takes a minute or two and needs the internet **only this
once**. Then the browser opens by itself.

From the second launch on it starts straight away, even offline.

Down by the clock, bottom-right, the **Selmo icon** appears: that is where you
pick the model and shut everything down (right-click → Exit).

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

## Optional — 100% local web search with SearXNG

Selmo can search the web. By default it uses public engines (the query leaves the
PC). If you want **searches to stay local too**, you can run SearXNG in a
container on the PC. This is **optional**: without it, search still works.

You need **Podman Desktop** (free, https://podman.io). Then, once:

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
