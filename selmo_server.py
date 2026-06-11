"""
selmo_server.py — Selmo backend launcher
Avvia tutti i servizi Python in background (nessuna finestra)
e llama-server in foreground in questa finestra.
Chiudendo questa finestra (o Ctrl+C), tutto si spegne.

Uso (chiamato da Selmo.bat):
  python selmo_server.py --model <path> --ngl <N> --ctx <N> [--mmproj <path>] [--voice <nome>]
"""

import subprocess
import sys
import os
import atexit
import time
import threading
import argparse
from pathlib import Path

BASE   = Path(__file__).parent
PYTHON = Path(sys.executable)

# Log persistente di llama-server: stdout+stderr finiscono qui oltre che a video.
# Serve per diagnosticare i 400 multimodali (es. immagine dal telefono) leggendo
# l'errore reale del server. Vedi BUG-IMG-02.
LLAMA_LOG = BASE / "selmo-llama.log"


def _tee(proc, logpath):
    """Legge l'output di llama-server e lo scrive sia a video sia su file."""
    try:
        with open(logpath, "w", encoding="utf-8", errors="replace") as lf:
            for raw in iter(proc.stdout.readline, b""):
                s = raw.decode("utf-8", errors="replace")
                sys.stdout.write(s)
                sys.stdout.flush()
                lf.write(s)
                lf.flush()
    except Exception:
        pass

# pythonw.exe = Python senza finestra console (meglio se disponibile)
PYTHONW = PYTHON.parent / "pythonw.exe"
if not PYTHONW.exists():
    PYTHONW = PYTHON

# Flag Windows: crea il processo senza finestra console
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Lista processi figli da terminare all'uscita
_procs: list[subprocess.Popen] = []


# -- Cleanup -------------------------------------------------------------------

def _cleanup():
    """Termina tutti i processi figli avviati da questo launcher."""
    if not _procs:
        return
    print("\n[Selmo] Arresto servizi...", flush=True)
    for p in _procs:
        try:
            p.terminate()
        except Exception:
            pass
    time.sleep(0.8)
    for p in _procs:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass
    print("[Selmo] Tutto fermato.", flush=True)


atexit.register(_cleanup)


# -- Gestione chiusura finestra (tasto X) su Windows --------------------------

if sys.platform == "win32":
    import ctypes

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
    def _ctrl_handler(event):
        # CTRL_C=0, CTRL_BREAK=1, CTRL_CLOSE=2, CTRL_LOGOFF=5, CTRL_SHUTDOWN=6
        _cleanup()
        os._exit(0)
        return True

    ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl_handler, True)


# -- Avvio servizi -------------------------------------------------------------

def _start(label: str, args: list) -> subprocess.Popen:
    """Avvia un servizio Python senza finestra e senza output visibile."""
    cmd = [str(PYTHONW)] + args
    print(f"  -> {label}", flush=True)
    p = subprocess.Popen(
        cmd,
        creationflags=NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _procs.append(p)
    return p


# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Selmo Backend Launcher")
    parser.add_argument("--model",  required=True,  help="Path al file .gguf")
    parser.add_argument("--ngl",    type=int, default=45,       help="Layer GPU")
    parser.add_argument("--ctx",    type=int, default=8192,     help="Context size")
    parser.add_argument("--mmproj", default=None,               help="Path mmproj (visione)")
    parser.add_argument("--voice",  default="im_nicola",        help="Voce TTS")
    args = parser.parse_args()

    model_name = Path(args.model).name

    print()
    print("  +------------------------------------------+")
    print("  |  Selmo  --  IA locale, GDPR by design   |")
    print("  |  I tuoi dati restano sul tuo computer.  |")
    print("  +------------------------------------------+")
    print()
    print(f"  Modello  : {model_name}")
    print(f"  -ngl     : {args.ngl}   ctx: {args.ctx}")
    if args.mmproj:
        print(f"  Visione  : attiva  ({Path(args.mmproj).name})")
    else:
        print("  Visione  : solo testo")
    print()
    print("  Avvio servizi Python (nessuna finestra separata)...")

    _start("GPU Monitor   [porta 8082]", [str(BASE / "selmo_gpu_monitor.py")])
    _start("Web Bridge    [porta 8081]", [str(BASE / "selmo_web.py")])
    _start("Whisper STT   [porta 8083]", [str(BASE / "selmo_whisper.py")])
    _start("TTS Kokoro    [porta 8084]", [str(BASE / "selmo_tts.py"), "--voice", args.voice])

    # Piccola pausa per dare tempo ai servizi di partire
    time.sleep(2)

    # Apri il browser
    try:
        os.startfile("http://127.0.0.1:8080/chat.html")
    except Exception:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "http://127.0.0.1:8080/chat.html"],
            creationflags=NO_WINDOW,
        )

    # -- Costruisci comando llama-server --------------------------------------
    llama = str(BASE / "bin" / "llama-server.exe")
    cmd = [
        llama,
        "--model",              args.model,
        "--host",               "0.0.0.0",
        "--port",               "8080",
        "--ctx-size",           str(args.ctx),
        "-ngl",                 str(args.ngl),
        "--parallel",           "1",
        "--no-warmup",
        # BUG-IMG-02: --timeout 0 azzera il read-timeout di cpp-httplib. Su
        # localhost il body arriva tutto subito e va bene, ma da rete (telefono)
        # un body grande (immagine ~200KB, audio Whisper) arriva in tanti pacchetti
        # con micro-gap: col timeout a 0 la read fallisce al primo pacchetto non
        # ancora pronto e httplib risponde 400 a corpo vuoto (no content-type,
        # len 0) PRIMA dell'handler. Valore generoso: non taglia le generazioni
        # lunghe (il client aborta a 300s) ma lascia leggere i body lenti.
        "--timeout",            "600",
        "--metrics",
        "--path",               str(BASE),
        "--temp",               "0.75",
        "--top-p",              "0.9",
        "--reasoning-format",   "deepseek",
    ]
    if args.mmproj:
        cmd += [
            "--mmproj",             args.mmproj,
            "--batch-size",         "2048",
            "--ubatch-size",        "2048",
        ]
        # --image-min/max-tokens e' un budget di token specifico di Gemma 3/4.
        # Su un encoder Pixtral (Magistral / Mistral-Small) llama.cpp non lo
        # supporta e rifiuta la richiesta immagine con HTTP 400 PRIMA di lanciare
        # lo slot (nessuna inferenza nel log) -> sintomo di BUG-IMG-02. Applichiamo
        # quei flag solo a Gemma; gli altri modelli vision usano la loro risoluzione
        # nativa.
        if "gemma" in model_name.lower():
            cmd += ["--image-min-tokens", "1120", "--image-max-tokens", "1120"]

    print()
    print("  Avvio llama-server...")
    print("  -----------------------------------------------------")
    print("  Ctrl+C  o  chiudi questa finestra  per fermare tutto.")
    print()

    # llama-server in foreground: output a video (via tee) + su selmo-llama.log
    print(f"  Log llama-server: {LLAMA_LOG.name}")
    print()
    llama_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    _procs.append(llama_proc)
    threading.Thread(target=_tee, args=(llama_proc, LLAMA_LOG), daemon=True).start()

    try:
        llama_proc.wait()
    except KeyboardInterrupt:
        pass
    # _cleanup() viene chiamato da atexit


if __name__ == "__main__":
    main()
