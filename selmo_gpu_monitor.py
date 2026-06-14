"""
Selmo system-power monitor.
 - GPU load / temp / VRAM and NVIDIA watts via NVML (pynvml).
 - Whole-system power estimate: CPU package + GPU power read from
   LibreHardwareMonitor's remote web server, plus a losses model.
Runs in the background and exposes the data on http://localhost:8082
"""
import sys
import json
import time
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Whole-system power estimate ────────────────────────────────────────────
# CPU package power and GPU power come from LibreHardwareMonitor's remote web
# server (in LHM: Options > Remote Web Server > Run; default port 8085) at
# /data.json. LHM reads Intel/AMD RAPL for the CPU and the card's own sensors
# for the GPU, so this is vendor-agnostic: it works for NVIDIA and AMD GPUs.
#
# Wall-power model (from the literature): every DC rail is fed through the PSU,
# so   wall ≈ (cpu_package + gpu + OTHER_DC) / PSU_EFF
#   OTHER_DC  baseline the rest of the desktop draws beyond CPU+GPU
#             (motherboard, RAM, drives, fans) — ~40-50 W typical.
#   PSU_EFF   80 PLUS efficiency at partial load (~0.88 for a Gold unit).
# Both are constants; calibrate against a wall meter later if wanted.
LHM_URL  = "http://127.0.0.1:8085/data.json"
PSU_EFF  = 0.88
OTHER_DC = 45.0

# Install pynvml if not present
try:
    import pynvml
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pynvml", "--quiet"])
    import pynvml

# Install psutil if not present (system RAM gauge)
try:
    import psutil
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "--quiet"])
    import psutil

# Global state
state = {"watts": 0, "vram_used": 0, "vram_total": 0, "gpu_pct": 0, "temp": 0,
         "ram_used": 0, "ram_total": 0, "ok": False,
         "cpu_watts": 0, "gpu_pwr": 0, "sys_watts": 0, "lhm_ok": False}


def read_ram():
    """System RAM, independent of the GPU loop so it works even without NVML."""
    try:
        vm = psutil.virtual_memory()
        state["ram_used"]  = round(vm.used / 1024**3, 2)
        state["ram_total"] = round(vm.total / 1024**3, 2)
    except Exception:
        pass

def read_gpu():
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        state["ok"] = True
        while True:
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW -> W
                mem   = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util  = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temp  = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                state["watts"]      = round(power, 1)
                state["vram_used"]  = round(mem.used / 1024**3, 2)
                state["vram_total"] = round(mem.total / 1024**3, 2)
                state["gpu_pct"]    = util.gpu
                state["temp"]       = temp
            except Exception as e:
                state["watts"] = 0
            time.sleep(1)
    except Exception as e:
        state["ok"] = False
        state["error"] = str(e)

# ── LibreHardwareMonitor: CPU package + GPU power (vendor-agnostic) ─────────
_GPU_HINTS = ("nvidia", "geforce", "radeon", "rtx", "gtx", " rx ", "arc ", "gpu")
_CPU_HINTS = ("intel", "ryzen", "core i", "xeon", "threadripper", "epyc", "processor")

def _val_w(v):
    """Parse a LHM value string like '45.3 W' -> 45.3, else None."""
    if not isinstance(v, str):
        return None
    s = v.strip()
    if s.endswith("W"):
        try:
            return float(s[:-1].replace(",", ".").strip())
        except ValueError:
            return None
    return None

def _powers(node):
    """All descendant power sensors of a node, as (text_lower, watts)."""
    out = []
    w = _val_w(node.get("Value"))
    if w is not None:
        out.append((node.get("Text", "").lower(), w))
    for c in node.get("Children", []) or []:
        out.extend(_powers(c))
    return out

def read_lhm_once():
    """Return (cpu_watts, gpu_watts) from LibreHardwareMonitor, else (0, 0)."""
    raw = urllib.request.urlopen(LHM_URL, timeout=1.0).read()
    data = json.loads(raw)
    devices = []
    for pc in data.get("Children", []) or []:           # root -> PC node(s)
        devices.extend(pc.get("Children", []) or [])     # PC -> hardware devices
    cpu = gpu = 0.0
    for dev in devices:
        name = dev.get("Text", "").lower()
        powers = _powers(dev)
        if not powers:
            continue
        # GPU is matched first: an "AMD Radeon" card name also contains "amd".
        if any(h in name for h in _GPU_HINTS):
            pk = [w for t, w in powers if ("package" in t or "board" in t
                  or "ppt" in t or "total graphics" in t or t == "gpu power")]
            gpu = max(pk) if pk else max(w for _, w in powers)
        elif any(h in name for h in _CPU_HINTS):
            pk = [w for t, w in powers if "package" in t]
            cpu = max(pk) if pk else max(w for _, w in powers)
    return cpu, gpu

def read_lhm_loop():
    """Poll LHM and keep the whole-system estimate fresh."""
    while True:
        try:
            cpu, gpu = read_lhm_once()
            state["cpu_watts"] = round(cpu, 1)
            state["gpu_pwr"]   = round(gpu, 1)
            state["lhm_ok"]    = True
        except Exception:
            state["lhm_ok"] = False
            state["cpu_watts"] = 0
            state["gpu_pwr"] = 0
        # Prefer LHM's GPU power (works for AMD); fall back to the NVML reading.
        gpu_for_sum = state["gpu_pwr"] if state["gpu_pwr"] > 0 else state["watts"]
        cpu_for_sum = state["cpu_watts"]
        if gpu_for_sum > 0 or cpu_for_sum > 0:
            state["sys_watts"] = round((cpu_for_sum + gpu_for_sum + OTHER_DC) / PSU_EFF, 1)
        else:
            state["sys_watts"] = 0
        time.sleep(2)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        read_ram()  # refresh RAM on each poll (cheap, GPU-independent)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(state).encode())
    def log_message(self, *args): pass  # silence the logs

if __name__ == "__main__":
    threading.Thread(target=read_gpu, daemon=True).start()
    threading.Thread(target=read_lhm_loop, daemon=True).start()
    print("Selmo system-power monitor on http://localhost:8082 "
          "(GPU via NVML; CPU+GPU via LibreHardwareMonitor :8085)")
    HTTPServer(("0.0.0.0", 8082), Handler).serve_forever()
