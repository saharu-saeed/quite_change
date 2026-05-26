"""Tiny local persistence receiver for the rejection log.

Usage:
    python scripts/rejection_server.py        # listens on 127.0.0.1:5057
    python scripts/rejection_server.py 5099   # custom port

The generated UI (outputs/ui/sweep_*.html) probes GET /health on page load.
If this server is up, the page POSTs each kill to /log and the server
appends to outputs/desk_review/rejection_log.csv with flush + os.fsync —
so a browser close or Ctrl+C cannot lose anything the UI marked "synced."

If this server is NOT running, the UI shows a LOUD red sticky banner
("PERSISTENCE OFFLINE") and falls back to localStorage. Unsynced kills
can still be exported manually via the UI's Export CSV button, but the
banner makes it visually impossible to miss that those kills aren't
durable yet.

Scope discipline (deliberate, not a config tweak):
  - Same machine only. Bound to 127.0.0.1, not 0.0.0.0.
  - No auth. Single user.
  - No HTTPS. No multi-user. If the desk ever needs those, it's a
    different project — don't soften this script to get there.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "outputs" / "desk_review" / "rejection_log.csv"
HOST = "127.0.0.1"  # localhost only — deliberate, see module docstring
DEFAULT_PORT = 5057

# Column order matches the existing REJECTION_LOG_TEMPLATE.csv shape and
# the data attributes captured by the UI's kill button.
COLUMNS = [
    "timestamp", "sweep_date", "ticker", "company", "sector", "profile",
    "rank", "tier", "composite_at_kill", "stock_3m", "div_pp", "attn",
    "retail", "mcap_jpy", "liq_jpy_daily", "flags_at_kill",
    "reason_code", "note",
]


def _csv_quote(v) -> str:
    if v is None:
        return ""
    s = str(v)
    if any(ch in s for ch in (',', '"', '\n', '\r')):
        return '"' + s.replace('"', '""') + '"'
    return s


def _ensure_csv() -> None:
    """Create the CSV with header if it doesn't exist. Idempotent."""
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            f.write(",".join(COLUMNS) + "\n")
            f.flush()
            os.fsync(f.fileno())


def append_durable(row: dict) -> None:
    """Append one row to the CSV. flush + fsync before returning, so we
    only acknowledge a kill to the UI AFTER the bytes are on disk."""
    _ensure_csv()
    line = ",".join(_csv_quote(row.get(c)) for c in COLUMNS) + "\n"
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


class _Handler(BaseHTTPRequestHandler):
    server_version = "QuietChangeRejectionLog/1.0"

    def _send(self, code: int, body: bytes = b"", content_type: str = "text/plain"):
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802 — required signature
        self._send(204)

    def do_GET(self):  # noqa: N802 — required signature
        if self.path == "/health":
            payload = json.dumps({
                "status": "ok",
                "csv_path": str(CSV_PATH),
                "host": f"{HOST}:{self.server.server_port}",
                "schema_columns": COLUMNS,
            }).encode("utf-8")
            self._send(200, payload, "application/json")
            return
        self._send(404, b"not found")

    def do_POST(self):  # noqa: N802 — required signature
        if self.path != "/log":
            self._send(404, b"not found")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            row = json.loads(body)
        except Exception as e:
            self._send(400, f"bad request: {e}".encode("utf-8"))
            return
        try:
            append_durable(row)
        except Exception as e:
            self._send(500, f"write failed: {e}".encode("utf-8"))
            return
        # Only ack AFTER fsync. The UI marks the row synced on this 200.
        self._send(200, b'{"status":"ok"}', "application/json")

    def log_message(self, fmt, *args):
        # Quieter than the default — one line per request with timestamp.
        sys.stderr.write(
            f"[{datetime.now().isoformat(timespec='seconds')}] {fmt % args}\n"
        )


def main(argv: list[str] | None = None) -> int:
    port = DEFAULT_PORT
    if argv and len(argv) > 1:
        try:
            port = int(argv[1])
        except ValueError:
            print(f"Bad port: {argv[1]!r}; using default {DEFAULT_PORT}")
    _ensure_csv()
    print(f"Rejection log receiver: http://{HOST}:{port}")
    print(f"  CSV path:  {CSV_PATH}")
    print(f"  Endpoints: GET /health | POST /log")
    print(f"  Stop with Ctrl+C.")
    try:
        HTTPServer((HOST, port), _Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
