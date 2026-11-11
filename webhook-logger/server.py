"""Minimal Alertmanager webhook receiver.

Prints a readable line per alert so notifications are visible with
`docker compose logs -f webhook-logger`. Also keeps the last 100 payloads
at GET /alerts for quick inspection.
"""
import json
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

HISTORY = deque(maxlen=100)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        HISTORY.append({"path": self.path, "received": datetime.utcnow().isoformat(), **payload})
        for alert in payload.get("alerts", []):
            labels, ann = alert.get("labels", {}), alert.get("annotations", {})
            print(
                f"[{datetime.now():%H:%M:%S}] {alert.get('status', '?').upper():8} "
                f"{labels.get('severity', '-'):8} {labels.get('alertname', '?')} "
                f"instance={labels.get('instance', labels.get('job', '-'))} | {ann.get('summary', '')}",
                flush=True,
            )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_GET(self):
        body = json.dumps(list(HISTORY), indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):  # silence default access log
        pass


if __name__ == "__main__":
    print("webhook-logger listening on :5001", flush=True)
    HTTPServer(("0.0.0.0", 5001), Handler).serve_forever()
