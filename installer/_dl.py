#!/usr/bin/env python3
"""
Shared helpers for Selmo's OPTIONAL add-on installers (Install-Voice /
Install-Image). Stdlib only, so it runs on the bundled embeddable Python.
Each add-on is independent and re-runnable; these are just the common bits.
"""
import os, re, ssl, sys, time, json, subprocess, urllib.request, zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent      # the Selmo folder
PY   = Path(sys.executable)                         # the bundled python.exe
UA   = {"User-Agent": "Selmo/1.0"}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# The embeddable Python has no CA bundle; certifi (pulled in by requests) gives
# a verified TLS context, else fall back to the default one.
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f}{u}"
        n /= 1024


def download(url, dest, min_bytes=0):
    """Resumable download with a progress line. Skips if already present and
    at least min_bytes. Returns True on success."""
    dest = Path(dest)
    if dest.exists() and (min_bytes == 0 or dest.stat().st_size >= min_bytes):
        print(f"  [ok] {dest.name} already present")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    # A .part that already meets the expected size is a completed download that
    # never got renamed (an earlier wrong size gate, or an interrupt before the
    # rename). Finalize it rather than resuming past EOF, which the server 416s.
    if have and min_bytes and have >= min_bytes:
        part.replace(dest)
        print(f"  [done] {dest.name}  ({human(have)}, already downloaded)")
        return True
    req  = urllib.request.Request(url, headers=dict(UA))
    if have:
        req.add_header("Range", f"bytes={have}-")
    print(f"  downloading {dest.name} ...")
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            total = int(r.headers.get("Content-Length", 0)) + have
            done  = have
            t0    = time.time()
            last  = 0.0
            with open(part, "ab" if have else "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total and time.time() - last > 0.5:
                        rate = human(done / max(time.time() - t0, 0.1))
                        sys.stdout.write(f"\r    {done*100//total:3d}%  "
                                         f"{human(done)}/{human(total)}  {rate}/s   ")
                        sys.stdout.flush()
                        last = time.time()
        print()
    except Exception as e:
        print(f"\n  [error] {e}\n          ({url})")
        return False
    if min_bytes and part.stat().st_size < min_bytes:
        print(f"  [error] {dest.name} smaller than expected")
        return False
    part.replace(dest)
    print(f"  [done] {dest.name}  ({human(dest.stat().st_size)})")
    return True


def latest_asset(api, pattern):
    """(name, url) of the first asset in the latest GitHub release whose name
    matches the regex. (None, None) if not found."""
    rel = json.loads(urllib.request.urlopen(
        urllib.request.Request(api, headers=dict(UA)), timeout=30, context=CTX
    ).read().decode())
    for a in rel.get("assets", []):
        if re.search(pattern, a["name"], re.I):
            return a["name"], a["browser_download_url"]
    return None, None


def extract_flat(zip_path, dest, exts=(".exe", ".dll")):
    """Extract just the matching files from a zip, flattening the paths."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for m in z.namelist():
            if m.lower().endswith(exts):
                (dest / Path(m).name).write_bytes(z.read(m))


def pip_install(*pkgs):
    """pip install into the bundled Python. Returns True on success."""
    print(f"  pip install {' '.join(pkgs)} ...")
    r = subprocess.run([str(PY), "-m", "pip", "install",
                        "--no-warn-script-location", *pkgs])
    return r.returncode == 0


def gpu_names():
    """List the machine's video adapters (any vendor), via WMI."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_VideoController).Name"],
            capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
        return [l.strip() for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def has_gpu():
    """(bool, names). True if a real GPU is present (NVIDIA / AMD / Intel) --
    i.e. anything other than the Microsoft Basic Display / remote adapters.
    Image generation needs one; on CPU alone it is impractically slow."""
    names = gpu_names()
    real  = [n for n in names
             if "microsoft basic" not in n.lower()
             and "remote display" not in n.lower()]
    return bool(real), names


def pause_close():
    try:
        input("\n  Press ENTER to close...")
    except EOFError:
        pass
