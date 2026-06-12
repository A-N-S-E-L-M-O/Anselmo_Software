"""
Selmo GPU Monitor -- reads real watts from the GPU via NVML
Runs in the background and exposes the data on http://localhost:8082
"""
import sys
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Install pynvml if not present
try:
    import pynvml
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pynvml", "--quiet"])
    import pynvml

# Global state
state = {"watts": 0, "vram_used": 0, "vram_total": 0, "gpu_pct": 0, "temp": 0, "ok": False}

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

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(state).encode())
    def log_message(self, *args): pass  # silence the logs

if __name__ == "__main__":
    t = threading.Thread(target=read_gpu, daemon=True)
    t.start()
    print("Selmo GPU Monitor started on http://localhost:8082")
    HTTPServer(("0.0.0.0", 8082), Handler).serve_forever()
