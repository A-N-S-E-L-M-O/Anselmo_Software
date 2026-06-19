"""
selmo_https_proxy.py — Selmo HTTPS reverse proxy  [port 8443]
Generates a self-signed TLS cert on first run (selmo.crt / selmo.key).
Routes:
  /proxy/8081/...  →  http://127.0.0.1:8081/...   (selmo_web)
  /proxy/8082/...  →  http://127.0.0.1:8082/...   (selmo_gpu_monitor)
  /proxy/8083/...  →  http://127.0.0.1:8083/...   (selmo_whisper)
  /proxy/8084/...  →  http://127.0.0.1:8084/...   (selmo_tts)
  /proxy/8086/...  →  http://127.0.0.1:8086/...   (selmo_image)
  /proxy/8087/...  →  http://127.0.0.1:8087/...   (tray control API)
  everything else  →  http://127.0.0.1:8080/...   (llama-server)

Purpose: enable getUserMedia (microphone) on mobile browsers over LAN
without a real CA certificate. The user accepts the browser warning once.
"""

import ssl
import socket
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

BASE      = Path(__file__).parent
CERT_FILE = BASE / "selmo.crt"
KEY_FILE  = BASE / "selmo.key"
PORT      = 8443

ROUTES = {
    "/proxy/8081": 8081,
    "/proxy/8082": 8082,
    "/proxy/8083": 8083,
    "/proxy/8084": 8084,
    "/proxy/8086": 8086,
    "/proxy/8087": 8087,
}


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
    """Generate self-signed cert valid for 10 years, with SAN for local IP."""
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
        print(f"  [HTTPS] self-signed cert generated for {ip}")
        return True
    except ImportError:
        print("  [HTTPS] ERROR: 'cryptography' package not installed.")
        print("  Run:  pip install cryptography")
        print("  HTTPS proxy disabled — mic will not work on mobile.")
        return False


class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence per-request logs

    def _backend_url(self) -> str:
        path = self.path
        for prefix, port in ROUTES.items():
            if path == prefix or path.startswith(prefix + "/"):
                rest = path[len(prefix):]
                if not rest.startswith("/"):
                    rest = "/" + rest
                return f"http://127.0.0.1:{port}{rest}"
        return f"http://127.0.0.1:8080{path}"

    def _proxy(self):
        url    = self._backend_url()
        length = int(self.headers.get("Content-Length", 0) or 0)
        body   = self.rfile.read(length) if length > 0 else None

        # Forward headers, strip hop-by-hop
        fwd = {k: v for k, v in self.headers.items()
               if k.lower() not in ("host", "connection", "transfer-encoding")}

        req = urllib.request.Request(url, data=body, headers=fwd, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=610) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding", "connection"):
                        continue
                    self.send_header(k, v)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                # Stream in small chunks to support SSE / llama-server token stream
                while True:
                    chunk = resp.read(512)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() in ("transfer-encoding", "connection"):
                    continue
                self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(str(e).encode())

    def do_GET(self):      self._proxy()
    def do_POST(self):     self._proxy()
    def do_HEAD(self):     self._proxy()
    def do_DELETE(self):   self._proxy()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()


def run():
    ip = _local_ip()

    # Regenerate cert if IP changed (stored in first line of cert subject)
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        if not generate_cert(ip):
            return

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(CERT_FILE), str(KEY_FILE))

    srv = HTTPServer(("0.0.0.0", PORT), ProxyHandler)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print(f"  [HTTPS] proxy ready  →  https://{ip}:{PORT}/chat.html")
    srv.serve_forever()


if __name__ == "__main__":
    run()
