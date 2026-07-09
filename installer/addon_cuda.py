#!/usr/bin/env python3
"""
Selmo add-on:  CUDA BACKEND  (NVIDIA-only engine swap)

Independent installer, launched by Install-CUDA.cmd. The base Selmo downloads the
Vulkan llama.cpp build on first run (it runs on any GPU and on CPU). On an NVIDIA
card CUDA is faster, so this add-on swaps the engine in bin\\ for the official
CUDA build plus its cudart runtime libs, from the latest llama.cpp release.

Safety-first swap (learned the hard way):
  - It STAGES the new engine in a temp folder and verifies llama-server.exe is
    really there BEFORE it removes anything from bin\\. A wrong/failed download
    can no longer brick Selmo - the working engine stays until the new one is
    proven good.
  - It picks the MAIN cuda build explicitly and skips the 'cudart' asset (whose
    name also contains 'bin-win-cuda'), the mismatch that broke the first cut.
  - It swaps only the llama.cpp files at the bin\\ ROOT (*.exe / *.dll); the
    isolated bin\\sd\\ (image) and bin\\LibreHardwareMonitor\\ are untouched.
  - Reversible: `addon_cuda.py revert` (Uninstall-CUDA.cmd) restores Vulkan.
  - Close Selmo first: while it runs, the engine DLLs are locked by Windows.

Re-runnable and idempotent. Restart Selmo afterwards (Exit from the tray, relaunch).
"""
import json, shutil, sys, tempfile, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _dl import BASE, download, extract_flat, gpu_names, pause_close, CTX, UA

API = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
BIN = BASE / "bin"


def is_nvidia():
    return any("nvidia" in n.lower() for n in gpu_names())


def _assets():
    rel = json.loads(urllib.request.urlopen(
        urllib.request.Request(API, headers=dict(UA)), timeout=30, context=CTX).read().decode())
    return {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}


def _pick(assets, kind):
    """kind: 'cuda' (the main CUDA build, NOT cudart), 'cudart', or 'vulkan'."""
    for name, url in assets.items():
        n = name.lower()
        if not n.endswith("-x64.zip"):
            continue
        if kind == "cuda" and "bin-win-cuda" in n and "cudart" not in n:
            return name, url
        if kind == "cudart" and "cudart" in n:
            return name, url
        if kind == "vulkan" and "bin-win-vulkan" in n:
            return name, url
    return None, None


def _stage(kind):
    """Download + extract the requested engine into a fresh temp dir. Returns the
    staging bin Path ONLY if it contains llama-server.exe (so we verify before we
    ever touch bin\\); otherwise None and nothing in bin\\ is changed."""
    try:
        assets = _assets()
    except Exception as e:
        print(f"  [error] cannot reach GitHub releases: {e}")
        return None
    name, url = _pick(assets, kind)
    if not url:
        print(f"  [error] no {kind} build found in the latest llama.cpp release.")
        return None
    tmp = Path(tempfile.mkdtemp(prefix="selmo-eng-"))
    stage = tmp / "bin"
    zp = tmp / name
    if not download(url, zp):
        return None
    extract_flat(zp, stage)
    if kind == "cuda":
        rn, ru = _pick(assets, "cudart")
        if ru:
            rzp = tmp / rn
            if download(ru, rzp):
                extract_flat(rzp, stage)      # cudart DLLs next to the exe
            else:
                print("  [warn] cudart libs did not download.")
        else:
            print("  [warn] no cudart libs in the release; CUDA may not start.")
    if not (stage / "llama-server.exe").exists():
        print("  [error] the downloaded build has no llama-server.exe - aborting.")
        print("          Your current engine in bin\\ is left untouched.")
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    return stage


def _clean_backend():
    """Remove the llama.cpp files at the bin\\ ROOT only (*.exe / *.dll)."""
    if not BIN.exists():
        return
    for p in BIN.iterdir():
        if p.is_file() and p.suffix.lower() in (".exe", ".dll"):
            try:
                p.unlink()
            except Exception as e:
                print(f"  [warn] could not remove {p.name} (is Selmo still running?): {e}")


def swap(kind):
    """Stage the new engine and, only if it is valid, replace the bin\\ root."""
    label = "CUDA" if kind == "cuda" else "Vulkan"
    print(f"  Resolving the {label} llama.cpp build from GitHub ...")
    stage = _stage(kind)
    if stage is None:
        return False
    print(f"  swapping the engine in bin\\  ->  {label} ...")
    BIN.mkdir(parents=True, exist_ok=True)
    _clean_backend()
    for f in stage.iterdir():
        if f.is_file():
            try:
                shutil.copy2(f, BIN / f.name)
            except Exception as e:
                print(f"  [warn] could not write {f.name} (is Selmo still running?): {e}")
    shutil.rmtree(stage.parent, ignore_errors=True)
    return (BIN / "llama-server.exe").exists()


def main():
    revert = len(sys.argv) > 1 and sys.argv[1].lower() in ("revert", "uninstall", "--revert")
    print("=" * 60)
    print("  Selmo add-on:  CUDA BACKEND" +
          ("   (revert to Vulkan)" if revert else "   (NVIDIA engine swap)"))
    print("=" * 60)

    # The swap rewrites the live engine files; Windows locks them while Selmo
    # runs. Make the user close it first so the swap can't half-fail.
    print("\n  IMPORTANT: close Selmo first - right-click the tray icon -> Exit.")
    print("  (While Selmo runs, the engine files are locked and the swap fails.)")
    try:
        input("  Press ENTER when Selmo is closed, or close this window to cancel... ")
    except EOFError:
        pass

    if revert:
        ok = swap("vulkan")
        if ok:
            print("\n  [done] Base Vulkan engine restored.")
        else:
            print("\n  [error] Could not restore Vulkan. Your models are safe; reconnect")
            print("          to the internet and re-run Uninstall-CUDA.cmd.")
        print("  Restart Selmo (Exit from the tray, then relaunch).")
        pause_close()
        sys.exit(0 if ok else 1)

    if not is_nvidia():
        print("\n  No NVIDIA GPU detected. The base Vulkan build is already right here")
        print("  (it runs on AMD, Intel and CPU too), so the CUDA add-on won't install.")
        seen = gpu_names()
        if seen:
            print("  Adapters seen: " + ", ".join(seen))
        pause_close()
        sys.exit(1)

    print("  NVIDIA GPU: " + ", ".join(n for n in gpu_names() if "nvidia" in n.lower()))
    ok = swap("cuda")
    print()
    if ok:
        print("  [done] CUDA backend installed - Selmo will use the GPU via CUDA.")
    else:
        print("  [error] CUDA install did not complete; the previous engine was left")
        print("          in place. Re-run this, or use Uninstall-CUDA.cmd for Vulkan.")
    print("\n  Restart Selmo (Exit from the tray, then relaunch) to use it.")
    pause_close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
