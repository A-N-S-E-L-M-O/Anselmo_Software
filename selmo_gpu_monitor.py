"""
Selmo system-power monitor.
 - GPU load / temp / VRAM and NVIDIA watts via NVML (pynvml).
 - Whole-system power estimate: CPU package + GPU power read from
   LibreHardwareMonitor's remote web server, plus a losses model.
Runs in the background and exposes the data on http://localhost:8082
"""
import sys
import os
import json
import time
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

# Persistent lifetime energy total lives next to this script so it survives
# restarts and is shared by every UI instance (the box draws one set of watts
# no matter how many chat.html tabs are open).
WH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "selmo-wh.json")

# ── Whole-system power estimate ────────────────────────────────────────────
# CPU package power and GPU power come from LibreHardwareMonitor's remote web
# server (in LHM: Options > Remote Web Server > Run; default port 8085) at
# /data.json. LHM reads Intel/AMD RAPL for the CPU and the card's own sensors
# for the GPU, so this is vendor-agnostic: it works for NVIDIA and AMD GPUs.
#
# Wall-power model (from the literature): every DC rail is fed through the PSU,
# so   wall ≈ (cpu + gpu + OTHER_DC) / PSU_EFF
# OTHER_DC and PSU_EFF are defined below (laptop/desktop profile) since they
# apply whether the CPU figure is real (LHM) or estimated from load.
# LHM is OPTIONAL now: if its web server is up we use its real CPU/GPU watts,
# otherwise GPU comes from NVML and CPU is estimated from utilisation.
LHM_URL  = "http://127.0.0.1:8085/data.json"

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

# ── CPU power estimate (driver-free) ───────────────────────────────────────
# Real CPU package power needs a ring-0 driver (LHM/WinRing0) that Defender
# blocks and that isn't 5-minute-installable on an arbitrary laptop. So when
# LHM isn't feeding us real watts we ESTIMATE CPU power from utilisation:
# linear from idle to TDP. Battery presence picks laptop vs desktop defaults;
# all four numbers are tunable against a wall meter.
def _is_laptop():
    try:
        return psutil.sensors_battery() is not None
    except Exception:
        return False

if _is_laptop():
    CPU_IDLE_W, CPU_TDP_W = 4.0, 28.0     # typical mobile package idle..TDP
    OTHER_DC,   PSU_EFF   = 12.0, 0.90    # screen/board/charger losses
else:
    CPU_IDLE_W, CPU_TDP_W = 20.0, 125.0   # desktop package idle..TDP
    OTHER_DC,   PSU_EFF   = 45.0, 0.88    # board/RAM/drives/fans + 80+ Gold

def est_cpu_watts(load_pct):
    f = max(0.0, min(load_pct, 100.0)) / 100.0
    return CPU_IDLE_W + (CPU_TDP_W - CPU_IDLE_W) * f

# Global state
state = {"watts": 0, "vram_used": 0, "vram_total": 0, "gpu_pct": 0, "temp": 0,
         "ram_used": 0, "ram_total": 0, "ok": False, "cpu_pct": 0,
         "cpu_watts": 0, "gpu_pwr": 0, "sys_watts": 0, "lhm_ok": False,
         "cpu_temp": 0, "cpu_est": True, "wh_session": 0.0, "wh_total": 0.0}

# Full-precision energy accumulators (Wh). state[] holds rounded copies for JSON.
# wh_session resets on monitor (Selmo) launch; wh_total persists in WH_FILE.
# Both are also manually resettable via /reset_session and /reset_total.
_wh = {"session": 0.0, "total": 0.0}
_wh_lock = threading.Lock()


def load_wh_total():
    try:
        with open(WH_FILE, "r", encoding="utf-8") as f:
            _wh["total"] = float(json.load(f).get("wh_total", 0.0))
    except Exception:
        _wh["total"] = 0.0
    state["wh_total"] = round(_wh["total"], 4)


def save_wh_total():
    try:
        tmp = WH_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"wh_total": round(_wh["total"], 6)}, f)
        os.replace(tmp, WH_FILE)  # atomic, avoids a half-written file
    except Exception:
        pass


def integrate_energy():
    """Integrate sys_watts over real elapsed time -> Wh, once per second.
    Single source of truth for energy: every chat.html instance just displays
    these numbers, so multiple tabs/devices can never double-count."""
    last = time.monotonic()
    last_save = last
    while True:
        time.sleep(1)
        now = time.monotonic()
        dt = now - last          # real seconds, robust to scheduling jitter
        last = now
        w = state.get("sys_watts", 0) or 0
        if w > 0:
            wh = w * dt / 3600.0
            with _wh_lock:
                _wh["session"] += wh
                _wh["total"]   += wh
                state["wh_session"] = round(_wh["session"], 4)
                state["wh_total"]   = round(_wh["total"], 4)
        if now - last_save >= 10:  # persist the lifetime total every 10 s
            save_wh_total()
            last_save = now


def read_ram():
    """System RAM + CPU load, independent of the GPU loop so it works even without NVML."""
    try:
        vm = psutil.virtual_memory()
        state["ram_used"]  = round(vm.used / 1024**3, 2)
        state["ram_total"] = round(vm.total / 1024**3, 2)
    except Exception:
        pass
    try:
        # interval=None -> non-blocking, measured since the previous call
        # (the dashboard polls ~every 1.5 s, so each read covers that window).
        state["cpu_pct"] = round(psutil.cpu_percent(interval=None))
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

def _val_c(v):
    """Parse a LHM temperature string like '55.0 °C' -> 55.0, else None."""
    if not isinstance(v, str):
        return None
    s = v.strip()
    if s.endswith("°C") or s.endswith("C"):
        try:
            return float(s.rstrip("C").rstrip("°").replace(",", ".").strip())
        except ValueError:
            return None
    return None

def _temps(node):
    """All descendant temperature sensors of a node, as (text_lower, celsius)."""
    out = []
    c = _val_c(node.get("Value"))
    if c is not None:
        out.append((node.get("Text", "").lower(), c))
    for ch in node.get("Children", []) or []:
        out.extend(_temps(ch))
    return out

def read_lhm_once():
    """Return (cpu_watts, gpu_watts, cpu_temp) from LibreHardwareMonitor."""
    raw = urllib.request.urlopen(LHM_URL, timeout=1.0).read()
    data = json.loads(raw)
    devices = []
    for pc in data.get("Children", []) or []:           # root -> PC node(s)
        devices.extend(pc.get("Children", []) or [])     # PC -> hardware devices
    cpu = gpu = cpu_temp = 0.0
    for dev in devices:
        name = dev.get("Text", "").lower()
        powers = _powers(dev)
        # GPU is matched first: an "AMD Radeon" card name also contains "amd".
        if any(h in name for h in _GPU_HINTS):
            if powers:
                pk = [w for t, w in powers if ("package" in t or "board" in t
                      or "ppt" in t or "total graphics" in t or t == "gpu power")]
                gpu = max(pk) if pk else max(w for _, w in powers)
        elif any(h in name for h in _CPU_HINTS):
            if powers:
                pk = [w for t, w in powers if "package" in t]
                cpu = max(pk) if pk else max(w for _, w in powers)
            temps = _temps(dev)
            if temps:
                # Prefer CPU package; else hottest real core temp. Exclude
                # "Distance to TjMax" (also reported in °C) so it can't win.
                core = [c for t, c in temps
                        if "distance" not in t and "tjmax" not in t]
                pt = [c for t, c in temps if "package" in t]
                cpu_temp = (max(pt) if pt else
                            max(core) if core else max(c for _, c in temps))
    return cpu, gpu, cpu_temp

def read_lhm_loop():
    """Poll LHM and keep the whole-system estimate fresh."""
    while True:
        try:
            cpu, gpu, cpu_temp = read_lhm_once()
            state["cpu_watts"] = round(cpu, 1)
            state["gpu_pwr"]   = round(gpu, 1)
            state["cpu_temp"]  = round(cpu_temp)
            state["lhm_ok"]    = True
        except Exception:
            state["lhm_ok"] = False
            state["cpu_watts"] = 0
            state["gpu_pwr"] = 0
            state["cpu_temp"] = 0
        # GPU: prefer LHM's power (works for AMD); fall back to NVML's reading.
        gpu_for_sum = state["gpu_pwr"] if state["gpu_pwr"] > 0 else state["watts"]
        # CPU: use LHM's real watts if present, else estimate from load so the
        # gauge always has a CPU figure (no driver / no admin needed).
        if state["cpu_watts"] > 0 and state["lhm_ok"]:
            cpu_for_sum = state["cpu_watts"]
            state["cpu_est"] = False
        else:
            cpu_for_sum = est_cpu_watts(state.get("cpu_pct", 0))
            state["cpu_watts"] = round(cpu_for_sum, 1)   # expose the estimate
            state["cpu_est"] = True
        state["sys_watts"] = round((cpu_for_sum + gpu_for_sum + OTHER_DC) / PSU_EFF, 1)
        time.sleep(2)

class Handler(BaseHTTPRequestHandler):
    def _json(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/reset_total":
            with _wh_lock:
                _wh["total"] = 0.0
                state["wh_total"] = 0.0
            save_wh_total()
            return self._json({"ok": True, "wh_total": 0.0})
        if path == "/reset_session":
            with _wh_lock:
                _wh["session"] = 0.0
                state["wh_session"] = 0.0
            return self._json({"ok": True, "wh_session": 0.0})
        read_ram()  # refresh RAM on each poll (cheap, GPU-independent)
        self._json(state)
    def log_message(self, *args): pass  # silence the logs

if __name__ == "__main__":
    load_wh_total()
    threading.Thread(target=read_gpu, daemon=True).start()
    threading.Thread(target=read_lhm_loop, daemon=True).start()
    threading.Thread(target=integrate_energy, daemon=True).start()
    print("Selmo system-power monitor on http://localhost:8082 "
          "(GPU via NVML; CPU+GPU via LibreHardwareMonitor :8085)")
    # Loopback only: reached via the front door /proxy/8082, not directly. (security review)
    HTTPServer(("127.0.0.1", 8082), Handler).serve_forever()
