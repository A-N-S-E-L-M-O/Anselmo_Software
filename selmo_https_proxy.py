"""
selmo_https_proxy.py - Selmo front door  [HTTP 8080 + HTTPS 8443]

Single always-up entry point for the whole UI. It does two jobs:

  1. Serves chat.html and the other static files straight from disk, so the
     web UI stays reachable even while the LLM is unloaded (the v0.830 VRAM
     swap kills llama-server to free the GPU for image generation -- before
     this front door, that also took the page host down: 8080 stopped
     answering entirely until the next chat turn reloaded the model).
  2. Reverse-proxies the backends by port:
       /proxy/8081/...  ->  selmo_web
       /proxy/8082/...  ->  selmo_gpu_monitor
       /proxy/8083/...  ->  selmo_whisper
       /proxy/8084/...  ->  selmo_tts
       /proxy/8086/...  ->  selmo_image
       /proxy/8087/...  ->  tray control API (LLM load/unload)
       /proxy/8089/...  ->  llama-server (the LLM, now on a private port)
     anything else      ->  static file from the project folder

The client (chat.html) only ever talks to THIS origin, on one fixed port,
no matter which backend is loaded. When the LLM is swapped out, /proxy/8089
returns 502 and chat.html's ensureLLM() reloads it -- the page itself never
goes away.

It listens on BOTH:
  - HTTP  8080  (desktop / localhost -- already a secure context, mic works)
  - HTTPS 8443  (phone over LAN -- TLS gives getUserMedia its secure context)

The self-signed cert (selmo.crt / selmo.key) is generated on first run and
regenerated automatically when the LAN IP changes (the IP is baked into the
cert SAN; a stale IP used to need a manual delete -- see BUG-MIC-01).
"""

import ssl
import socket
import threading
import mimetypes
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE      = Path(__file__).resolve().parent
CERT_FILE = BASE / "selmo.crt"
KEY_FILE  = BASE / "selmo.key"
CERT_IP   = BASE / "selmo-cert-ip.txt"   # records the IP baked into the cert
HTTP_PORT  = 8080
HTTPS_PORT = 8443

# Backend ports we are willing to proxy. 8080 is us; never proxy to self.
# 8085 is the optional LibreHardwareMonitor web server; harmless to allow.
ALLOWED_PORTS = {8081, 8082, 8083, 8084, 8085, 8086, 8087, 8089}

# Never hand these out as static files (private key, source, configs, logs).
BLOCK_SUFFIX = {".key", ".py", ".pyc", ".pyo", ".log", ".bat",
                ".vbs", ".ps1", ".ini"}


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_cert(ip: str) -> bool:
    """Generate a self-signed cert valid for 10 years, SAN = local IP + loopback."""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime, ipaddress

        key  = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "selmo")])
        san  = x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.IPv4Address(ip)),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
            .add_extension(san, critical=False)
            .sign(key, hashes.SHA256())
        )
        CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        KEY_FILE.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
        CERT_IP.write_text(ip, encoding="utf-8")
        print(f"  [HTTPS] self-signed cert generated for {ip}")
        return True
    except ImportError:
        print("  [HTTPS] 'cryptography' not installed -> HTTPS disabled (mobile mic off).")
        print("  Run:  pip install cryptography --break-system-packages")
        return False


def _ensure_cert(ip: str) -> bool:
    """(Re)generate the cert if it is missing or baked for a different IP."""
    have = CERT_FILE.exists() and KEY_FILE.exists()
    baked = CERT_IP.read_text(encoding="utf-8").strip() if CERT_IP.exists() else ""
    if have and baked == ip:
        return True
    if have and baked != ip:
        print(f"  [HTTPS] LAN IP changed ({baked or '?'} -> {ip}); regenerating cert")
    return generate_cert(ip)


# Static file types we serve from disk.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("application/json", ".json")


class FrontDoor(BaseHTTPRequestHandler):
    # HTTP/1.0 (the default) on purpose: proxied responses are streamed with
    # no Content-Length, so the body is close-delimited -- the client sees EOF
    # when we close the socket. Under HTTP/1.1 keep-alive a streamed reply with
    # no length/chunked framing would hang the browser's fetch reader.

    def log_message(self, fmt, *args):
        pass  # silence per-request logs

    # -- routing ---------------------------------------------------------------
    def _backend_url(self):
        """Return the backend URL for a /proxy/<port>/... path, else None."""
        if not self.path.startswith("/proxy/"):
            return None
        full = self.path[len("/proxy/"):]      # e.g. 8089/v1/chat?x=1
        path, _, query = full.partition("?")
        seg, _, tail = path.partition("/")
        try:
            port = int(seg)
        except ValueError:
            return None
        if port not in ALLOWED_PORTS:
            return None
        suffix = "/" + tail if tail else "/"
        if query:
            suffix += "?" + query
        return f"http://127.0.0.1:{port}{suffix}"

    # -- static ----------------------------------------------------------------
    def _serve_static(self):
        raw = self.path.split("?", 1)[0]
        rel = raw.lstrip("/")
        if rel == "":
            rel = "chat.html"
        target = (BASE / rel).resolve()
        # Path-traversal guard: must stay inside BASE.
        if BASE not in target.parents and target != BASE:
            self._text(403, "forbidden")
            return
        if target.suffix.lower() in BLOCK_SUFFIX or target.name.startswith("."):
            self._text(403, "forbidden")
            return
        if not target.is_file():
            self._text(404, "not found")
            return
        try:
            data = target.read_bytes()
        except Exception as e:
            self._text(500, str(e))
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # Never cache the app shell / config, so a reload always gets fresh UI.
        if target.suffix.lower() in (".html", ".json"):
            self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    # -- proxy -----------------------------------------------------------------
    def _proxy(self, url):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body   = self.rfile.read(length) if length > 0 else None
        fwd = {k: v for k, v in self.headers.items()
               if k.lower() not in ("host", "connection", "transfer-encoding")}
        req = urllib.request.Request(url, data=body, headers=fwd, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=610) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding", "connection", "content-length"):
                        continue
                    self.send_header(k, v)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                while True:
                    chunk = resp.read(512)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() in ("transfer-encoding", "connection", "content-length"):
                    continue
                self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            # Backend down (e.g. LLM unloaded by the image swap) -> 502.
            self._text(502, str(e))

    def _text(self, code, msg):
        body = msg.encode("utf-8", "replace")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # -- verbs -----------------------------------------------------------------
    def _dispatch(self):
        url = self._backend_url()
        if url is not None:
            self._proxy(url)
        else:
            self._serve_static()

    def do_GET(self):    self._dispatch()
    def do_POST(self):   self._dispatch()
    def do_HEAD(self):   self._dispatch()
    def do_DELETE(self): self._dispatch()
    def do_PUT(self):    self._dispatch()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD, DELETE, PUT")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()


def _serve_http(ip: str):
    srv = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), FrontDoor)
    print(f"  [HTTP]  front door  ->  http://127.0.0.1:{HTTP_PORT}/chat.html", flush=True)
    srv.serve_forever()


def _serve_https(ip: str):
    if not _ensure_cert(ip):
        print("  [HTTPS] disabled (no cert).", flush=True)
        return
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(CERT_FILE), str(KEY_FILE))
    srv = ThreadingHTTPServer(("0.0.0.0", HTTPS_PORT), FrontDoor)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print(f"  [HTTPS] front door  ->  https://{ip}:{HTTPS_PORT}/chat.html", flush=True)
    srv.serve_forever()


def run():
    ip = _local_ip()
    # HTTPS in a background thread; HTTP holds the main thread. Either can run
    # without the other (HTTP always works; HTTPS needs the cryptography pkg).
    threading.Thread(target=_serve_https, args=(ip,), daemon=True).start()
    _serve_http(ip)


if __name__ == "__main__":
    run()
