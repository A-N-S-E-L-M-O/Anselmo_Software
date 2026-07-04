#!/usr/bin/env python3
"""
Selmo add-on:  VOICE  (speech-to-text + text-to-speech)

Independent installer, launched by Install-Voice.cmd. It adds, on top of the
base edition:
  - Whisper transcription (faster-whisper)  -> the microphone / hands-free buttons
  - Kokoro neural TTS (kokoro-onnx)          -> the "speak" button
    (without it, "speak" still works via the browser's built-in Web Speech voice)

Re-runnable and idempotent. Restart Selmo afterwards; the voice buttons then
enable themselves (the UI greys out any capability whose service is not up).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _dl import BASE, download, pip_install, pause_close

KOKORO_BASE = ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
               "model-files-v1.0/")
KOKORO_FILES = [
    ("kokoro-v1.0.onnx", 300_000_000),   # ~325 MB voice model
    ("voices-v1.0.bin",   20_000_000),   # voice embeddings (incl. Italian)
]


def main():
    print("=" * 60)
    print("  Selmo add-on:  VOICE   (Whisper STT + Kokoro TTS)")
    print("=" * 60)

    print("\n  Installing Python packages")
    print("  (flask, faster-whisper, kokoro-onnx, soundfile, langdetect)...")
    if not pip_install("flask", "faster-whisper", "kokoro-onnx", "soundfile", "langdetect"):
        print("\n  [error] pip install failed. Check your connection and retry.")
        pause_close()
        sys.exit(1)

    print("\n  Downloading the Kokoro voice model into  tts\\  (~330 MB)...")
    tts = BASE / "tts"
    ok = all(download(KOKORO_BASE + name, tts / name, min_bytes)
             for name, min_bytes in KOKORO_FILES)

    print()
    if ok:
        print("  [done] Voice add-on installed.")
        print("  The Whisper model (~150-500 MB) downloads by itself the first")
        print("  time you use the microphone -- no extra step here.")
    else:
        print("  [partial] Some files did not download. Just re-run this installer.")

    print("\n  Restart Selmo (Exit from the tray, then launch again) to enable it.")
    pause_close()


if __name__ == "__main__":
    main()
