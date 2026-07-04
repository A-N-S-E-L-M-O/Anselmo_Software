#!/usr/bin/env python3
"""
Selmo first-run engine setup (stdlib only -- runs on the bundled embeddable
Python). It downloads ONLY the llama.cpp backend matched to the machine:

  NVIDIA card -> CUDA build (+ cudart runtime libs)
  otherwise   -> Vulkan build (also runs on CPU)

Selmo is model-agnostic, so no model is forced on you. After the engine is
ready, first run OFFERS a default model (Mistral-7B-Instruct v0.3, ~3.5 GB -
Apache 2.0, European, no reasoning): say yes and it is fetched once, say no and
you drop your own .gguf into models\ and pick it in the browser. See MODELS.md.

Idempotent: skips if the backend is already present. Resumable via .part files.
Exit code 2 if the backend could not be set up (abort launch).
"""
import json, os, re, sys, time, ssl, urllib.request, urllib.error, zipfile, tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CFG  = json.loads((BASE / "installer" / "downloads.json").read_text("utf-8"))
UA   = {"User-Agent": "Selmo/1.0"}

# The embeddable Python has no CA bundle, so HTTPS verification fails. certifi
# is present (pulled in by requests/trafilatura); use it for a verified context.
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()

def human(n):
    for u in ("B","KB","MB","GB"):
        if n < 1024 or u == "GB": return f"{n:.1f}{u}"
        n /= 1024

def download(url, dest, min_bytes=0):
    dest = Path(dest)
    if dest.exists() and (min_bytes == 0 or dest.stat().st_size >= min_bytes):
        print(f"  [ok] {dest.name} already present"); return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    req  = urllib.request.Request(url, headers=dict(UA))
    if have: req.add_header("Range", f"bytes={have}-")
    print(f"  downloading {dest.name} ...")
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            total = int(r.headers.get("Content-Length", 0)) + have
            done  = have; t0 = time.time(); last = 0
            with open(part, "ab" if have else "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk: break
                    f.write(chunk); done += len(chunk)
                    if total and time.time() - last > 0.5:
                        sys.stdout.write(f"\r    {done*100//total:3d}%  {human(done)}/{human(total)}  "
                                         f"{human(done/max(time.time()-t0,0.1))}/s   ")
                        sys.stdout.flush(); last = time.time()
        print()
    except Exception as e:
        print(f"\n  [error] {e}\n          ({url})"); return False
    if min_bytes and part.stat().st_size < min_bytes:
        print(f"  [error] {dest.name} smaller than expected"); return False
    part.replace(dest)
    print(f"  [done] {dest.name}  ({human(dest.stat().st_size)})")
    return True

def has_nvidia():
    try:
        import subprocess
        out = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=8)
        return out.returncode == 0 and "GPU" in out.stdout
    except Exception:
        return False

def latest_assets(api):
    rel = json.loads(urllib.request.urlopen(
        urllib.request.Request(api, headers=dict(UA)), timeout=30, context=CTX).read().decode())
    return {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}

def pick(assets, pattern):
    for name, url in assets.items():
        if re.search(pattern, name, re.I):
            return name, url
    return None, None

def extract_zip(zip_path, bindir):
    bindir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for m in z.namelist():
            if m.lower().endswith((".exe", ".dll")):
                (bindir / Path(m).name).write_bytes(z.read(m))   # flatten

def setup_backend():
    bindir = BASE / "bin"
    if (bindir / "llama-server.exe").exists():
        print("  [ok] llama.cpp engine already present"); return True
    b = CFG["backend"]
    print("  resolving llama.cpp backend from GitHub ...")
    try:
        assets = latest_assets(b["api"])
    except Exception as e:
        print(f"  [error] cannot reach GitHub releases: {e}"); return False
    # Vulkan only: one backend that runs on AMD, Intel and NVIDIA (and CPU).
    print("  downloading Vulkan backend (runs on any GPU, and on CPU) ...")
    name, url = pick(assets, b["vulkan_zip"])
    if not url:
        print("  [error] vulkan asset not found in the latest release"); return False
    zp = Path(tempfile.gettempdir()) / name
    if not download(url, zp, 0): return False
    print(f"  extracting {name} -> bin\\")
    extract_zip(zp, bindir)
    return (bindir / "llama-server.exe").exists()

def has_model():
    mdir = BASE / "models"
    return mdir.exists() and any(mdir.glob("*.gguf"))

def offer_model():
    """First-run only: offer to download one small default model. Downloads
    just if the user says yes; a bare ENTER (default) accepts, 'n' declines,
    and a non-interactive run (EOF) declines so nothing huge is pulled silently."""
    m = CFG.get("model")
    if not m:
        return
    if has_model():
        print("\n  A model is already in  models\\  - nothing to download.")
        return
    mdir = BASE / "models"; mdir.mkdir(parents=True, exist_ok=True)
    print()
    print("-" * 56)
    print("  You need one model to chat. I can fetch a small default now:")
    print(f"    {m['name']}")
    print(f"    Mistral-7B-Instruct v0.3 - {m.get('size_h','~3.5 GB')}, Apache 2.0,")
    print("    European, no reasoning. A solid all-rounder; light enough for an")
    print("    entry-level 8GB PC. Good for trying the features.")
    print("  Say no and Selmo stays empty - drop your own .gguf into  models\\")
    print("  instead (see MODELS.md). You can always add or swap models later.")
    print("-" * 56)
    try:
        ans = input("  Download the default model now? [Y/n]  ").strip().lower()
    except EOFError:
        ans = "n"
    if ans in ("", "y", "yes"):
        if download(m["url"], mdir / m["name"], m.get("min_bytes", 0)):
            print(f"\n  [done] starter model ready:  models\\{m['name']}")
        else:
            print("\n  [skip] the download did not finish. You can drop a .gguf into")
            print("         models\\ yourself, or relaunch to try again. See MODELS.md.")
    else:
        print("\n  OK - no model downloaded. Drop a .gguf into  models\\  and pick")
        print("  it in the browser settings panel. See MODELS.md for suggestions.")

def main():
    print("=" * 56)
    print("  Selmo - engine setup (first run)")
    print("=" * 56)
    print()
    if not setup_backend():
        print("\n  Could not set up the engine. Check your connection and retry.")
        try: input("\n  Press ENTER to close...")
        except EOFError: pass
        sys.exit(2)
    print("\n  Engine ready.")
    offer_model()
    print("\n  Starting Selmo - the browser opens shortly.")
    time.sleep(1)

if __name__ == "__main__":
    main()
