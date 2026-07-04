#!/usr/bin/env python3
"""
Uninstall a Selmo add-on (voice / image): remove its downloaded models and its
EXCLUSIVE pip packages, freeing the disk space. The base is left untouched, and
shared packages (flask) are kept. Launched by Uninstall-Voice.cmd /
Uninstall-Image.cmd:

    python installer\\addon_uninstall.py  voice|image

(The hardware monitor is removed separately, via Uninstall-Hardware-Monitor.cmd,
because it also registers a machine-level scheduled task.)
"""
import sys
import shutil
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _dl import BASE, PY, pause_close


def rm(p):
    p = Path(p)
    if not p.exists():
        return
    try:
        p.unlink()
        print(f"  removed {p.name}")
    except Exception as e:
        print(f"  [skip] {p.name}: {e}")


def pip_uninstall(*pkgs):
    print(f"  pip uninstall {' '.join(pkgs)} ...")
    subprocess.run([str(PY), "-m", "pip", "uninstall", "-y", *pkgs])


VOICE_FILES = [BASE / "tts" / "kokoro-v1.0.onnx",
               BASE / "tts" / "voices-v1.0.bin"]
IMAGE_FILES = [BASE / "image" / "z_image_turbo-Q6_K.gguf",
               BASE / "image" / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
               BASE / "image" / "ae.safetensors"]


def main():
    which = (sys.argv[1] if len(sys.argv) > 1 else "").lower()

    if which == "voice":
        print("=" * 60)
        print("  Uninstall add-on:  VOICE")
        print("=" * 60)
        for f in VOICE_FILES:
            rm(f)
        pip_uninstall("faster-whisper", "kokoro-onnx", "soundfile")
        print("\n  Voice removed. Note: the Whisper model lives in your user HF cache")
        print("  (%USERPROFILE%\\.cache\\huggingface), not in the Selmo folder --")
        print("  delete it there too if you want that space back.")

    elif which == "image":
        print("=" * 60)
        print("  Uninstall add-on:  IMAGE GENERATION")
        print("=" * 60)
        for f in IMAGE_FILES:
            rm(f)
        sd = BASE / "bin" / "sd"
        if sd.exists():
            shutil.rmtree(sd, ignore_errors=True)
            print(f"  removed {sd.name}\\ (sd.cpp engine)")
        print("\n  Image models + the sd.cpp engine removed (~9 GB freed). The base")
        print("  and the llama.cpp DLLs in bin\\ are untouched.")

    else:
        print("Usage: addon_uninstall.py  voice|image")
        pause_close()
        sys.exit(1)

    print("\n  Restart Selmo; the matching buttons grey out again.")
    pause_close()


if __name__ == "__main__":
    main()
