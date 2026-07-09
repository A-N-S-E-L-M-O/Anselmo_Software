#!/usr/bin/env python3
"""
Selmo add-on:  IMAGE GENERATION  (stable-diffusion.cpp + Z-Image-Turbo)

Independent installer, launched by Install-Image.cmd. It needs a GPU of any
vendor (NVIDIA / AMD / Intel) and EXITS on a GPU-less machine, because diffusion
on the CPU alone is impractically slow -- so a base/demo PC never wastes ~9 GB
of downloads on something it can't run.

What it installs:
  - the sd.cpp engine (Vulkan build -> runs on any GPU) into  bin\\sd\\
  - the Apache-2.0 weights into  image\\ :
      z_image_turbo-Q6_K.gguf            diffusion model (leejet/Z-Image-Turbo-GGUF)
      Qwen3-4B-Instruct-2507-Q4_K_M.gguf text encoder (--llm)
      ae.safetensors                     VAE (ungated Comfy-Org/z_image_turbo mirror)

The engine is installed unconditionally; the ~9 GB default weights are OFFERED
and skippable (decline to use your own image model instead), the same pattern as
the first-run LLM model. Re-runnable and idempotent. Restart Selmo afterwards.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _dl import BASE, download, latest_asset, extract_flat, pip_install, has_gpu, pause_close

# sd.cpp engine: latest official release, Windows Vulkan build (any GPU).
SD_API = "https://api.github.com/repos/leejet/stable-diffusion.cpp/releases/latest"
SD_WIN = r"sd-.*-bin-win-vulkan-x64\.zip$"

# Weights placed in image\ ; names match selmo_image.py's expected defaults.
WEIGHTS = [
    ("z_image_turbo-Q6_K.gguf",
     "https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q6_K.gguf",
     5_263_239_104),
    ("Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
     "https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF/resolve/main/"
     "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
     2_497_280_736),
    ("ae.safetensors",
     "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
     335_304_388),
]


def main():
    print("=" * 60)
    print("  Selmo add-on:  IMAGE GENERATION   (Z-Image-Turbo)")
    print("=" * 60)

    ok, names = has_gpu()
    if not ok:
        print("\n  No GPU detected. Image generation needs a graphics card")
        print("  (NVIDIA, AMD or Intel); on the CPU alone it is far too slow,")
        print("  so this add-on will not install.")
        if names:
            print("  Adapters seen: " + ", ".join(names))
        pause_close()
        sys.exit(1)
    print("  GPU: " + ", ".join(names))

    print("\n  Installing Python package (flask)...")
    if not pip_install("flask"):
        print("\n  [error] pip install failed.")
        pause_close()
        sys.exit(1)

    # 1. the sd.cpp engine (Vulkan -> any GPU)
    print("\n  Resolving stable-diffusion.cpp (Vulkan) from GitHub...")
    try:
        name, url = latest_asset(SD_API, SD_WIN)
    except Exception as e:
        print(f"  [error] cannot reach GitHub releases: {e}")
        pause_close()
        sys.exit(1)
    if not url:
        print("  [error] could not find the Windows Vulkan build in the latest release.")
        pause_close()
        sys.exit(1)
    zp = Path(tempfile.gettempdir()) / name
    if not download(url, zp):
        pause_close()
        sys.exit(1)
    # Isolate sd.cpp in bin\sd\ : its bundled ggml-*.dll clash with (and are
    # locked by) llama.cpp's DLLs in bin\, which caused a PermissionError.
    print(f"  extracting {name} -> bin\\sd\\  (isolated from the llama.cpp DLLs)")
    extract_flat(zp, BASE / "bin" / "sd")

    # 2. the weights - OFFERED and skippable, exactly like the first-run LLM
    #    model. The engine above is installed unconditionally; the ~9 GB default
    #    weights are optional, so a user who wants their own image model can
    #    decline and drop it into image\ instead. A bare ENTER accepts; 'n'
    #    declines; a non-interactive run (EOF) declines so nothing huge is pulled
    #    silently.
    img = BASE / "image"
    print()
    print("-" * 60)
    print("  The image ENGINE is installed. Download the default image model now?")
    print("    Z-Image-Turbo Q6_K + Qwen3-4B encoder + FLUX VAE - ~9 GB, Apache 2.0.")
    print("  Say no to skip and drop your own model into  image\\  instead")
    print("  (see docs\\MODELS.md / selmo-image-models.ini). You can re-run this")
    print("  installer any time to fetch the default later.")
    print("-" * 60)
    try:
        ans = input("  Download the default image model now? [Y/n]  ").strip().lower()
    except EOFError:
        ans = "n"
    if ans not in ("", "y", "yes"):
        print("\n  [skip] No image model downloaded. Drop your own into  image\\  and")
        print("         pick it in the browser settings, then restart Selmo.")
        pause_close()
        return

    print("\n  Downloading the image model into  image\\  (~9 GB total)...")
    good = all(download(u, img / n, mb) for n, u, mb in WEIGHTS)

    print()
    if good:
        print("  [done] Image generation installed.")
    else:
        print("  [partial] Some files did not download. Just re-run this installer.")

    print("\n  Restart Selmo to enable the image button.")
    pause_close()


if __name__ == "__main__":
    main()
