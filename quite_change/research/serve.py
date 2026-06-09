# -*- coding: utf-8 -*-
"""Interactive web UI for the R+ classification project.

Run this script and open http://localhost:5000 in a browser. Type one or more
4-digit stock codes, click "Research", and see results render as cards in the
same visual style as the main dashboard. Useful for testing 1-3 companies
quickly without typing CLI commands.

Usage:
    pip install anthropic flask
    export ANTHROPIC_API_KEY=sk-ant-...
    python -m research.serve

    # Or specify port:
    python -m research.serve --port 8000

The backend reuses research/run_one_company.py's `research_company()` function,
so the prompt and model are exactly the same as the CLI tools."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

# Force UTF-8 stdout/stderr (Windows compatibility).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError as e:
    print(
        f"Error importing flask: {e!r}\n\n"
        f"This Python is at: {sys.executable}\n"
        f"sys.path[0..3]: {sys.path[:3]}\n\n"
        "Likely causes:\n"
        "  1. flask not installed in the Python interpreter shown above.\n"
        "     Fix: ensure your venv is active, then run:\n"
        f"       \"{sys.executable}\" -m pip install flask anthropic\n"
        "  2. A local file named 'flask.py' or folder 'flask/' shadowing the real package.\n"
        "  3. Your venv is activated but `python` resolves to a different interpreter.\n"
        "     Check: python -c \"import sys; print(sys.executable)\"",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from anthropic import Anthropic
except ImportError as e:
    print(
        f"Error importing anthropic: {e!r}\n"
        f"Run: \"{sys.executable}\" -m pip install anthropic flask",
        file=sys.stderr,
    )
    sys.exit(1)

# Support both `python -m research.serve` and `python research/serve.py`.
if __package__:
    from .run_one_company import research_company
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from run_one_company import research_company  # type: ignore


HERE = Path(__file__).parent
STATIC_DIR = HERE / "static"
STAGING_DIR = HERE / "staging"  # successful results land here; canonical data/ is NEVER auto-touched

MAX_TICKERS_PER_REQUEST = 10  # cost guardrail: ~$0.30 per ticker at real-time rates

# In-memory job store. {job_id: {tickers, started_at, results, errors, status}}
# Lives only for the lifetime of the process — restart and jobs are gone.
_jobs: dict = {}
_jobs_lock = threading.Lock()


app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")


@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/research", methods=["POST"])
def submit_research():
    """Submit a list of tickers for research. Returns a job_id to poll."""
    data = request.get_json(silent=True) or {}
    tickers = data.get("tickers", [])

    if not isinstance(tickers, list) or not tickers:
        return jsonify({"error": "Request body must include a non-empty 'tickers' list."}), 400

    if len(tickers) > MAX_TICKERS_PER_REQUEST:
        return jsonify({
            "error": f"Too many tickers in one request (max {MAX_TICKERS_PER_REQUEST}). "
                     "Split into smaller batches to stay within cost guardrails."
        }), 400

    # Normalize each entry to {code, name}
    normalized: list[dict] = []
    for t in tickers:
        if isinstance(t, str):
            # Bare string — parse "code name" or just "code"
            parts = t.strip().split(maxsplit=1)
            code = parts[0]
            name = parts[1] if len(parts) > 1 else code
        elif isinstance(t, dict):
            code = str(t.get("code", "")).strip()
            name = str(t.get("name", code)).strip() or code
        else:
            return jsonify({"error": f"Bad ticker entry: {t!r}"}), 400

        if not code or not code.isdigit() or len(code) != 4:
            return jsonify({"error": f"Stock code must be 4 digits, got {code!r}"}), 400

        normalized.append({"code": code, "name": name})

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "Server is missing ANTHROPIC_API_KEY environment variable."}), 500

    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "tickers": normalized,
            "started_at": time.time(),
            "results": {},   # {code: result_dict}
            "errors": {},    # {code: error_message}
            "in_progress": set(t["code"] for t in normalized),
            "status": "running",
        }

    threading.Thread(target=_run_job, args=(job_id, api_key), daemon=True).start()

    return jsonify({"job_id": job_id, "tickers": normalized})


def _write_to_staging(code: str, entry_name: str, result: dict) -> Path | None:
    """Persist a successful research result to research/staging/{code}.json.

    Returns the path written, or None on failure (failures are non-fatal —
    the in-memory result is still returned to the browser either way).

    NOTE: this directory is isolated from data/. Canonical sector files are
    never auto-touched. Use research/promote_staging.py to merge a staging
    entry into a data/ file after manual review.
    """
    try:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "_meta": {
                "saved_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "saved_by": "research/serve.py",
                "input_name": entry_name,
                "ticker": code,
                "note": "Test result from interactive UI. NOT yet promoted to canonical data/. "
                        "Use research/promote_staging.py to merge into the appropriate sector file.",
            },
            **(result if isinstance(result, dict) else {"raw": result}),
        }
        out = STAGING_DIR / f"{code}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out
    except Exception as e:  # noqa: BLE001
        print(f"WARN: failed to write staging for {code}: {e}", file=sys.stderr)
        return None


def _run_job(job_id: str, api_key: str) -> None:
    """Worker thread: research each ticker sequentially (low concurrency to be polite)."""
    client = Anthropic(api_key=api_key)
    with _jobs_lock:
        job = _jobs[job_id]

    for entry in job["tickers"]:
        code = entry["code"]
        try:
            result = research_company(client, code, entry["name"], lang="en")
            # Model wraps result in {"<code>": {...}} — unwrap one level.
            inner = result.get(code, result) if isinstance(result, dict) else result
            if isinstance(inner, dict):
                inner.setdefault("name", entry["name"])
            # Persist to staging directory (canonical data/ files are NEVER auto-touched)
            staging_path = _write_to_staging(code, entry["name"], inner)
            if isinstance(inner, dict) and staging_path is not None:
                inner["_staging_path"] = str(staging_path.relative_to(HERE.parent))
            with _jobs_lock:
                job["results"][code] = inner
                job["in_progress"].discard(code)
        except Exception as e:  # noqa: BLE001
            with _jobs_lock:
                job["errors"][code] = str(e)
                job["in_progress"].discard(code)

    with _jobs_lock:
        job["status"] = "done"
        job["finished_at"] = time.time()


@app.route("/api/status/<job_id>")
def job_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        # Build response snapshot under the lock so it's atomic
        snapshot = {
            "job_id": job_id,
            "status": job["status"],
            "total": len(job["tickers"]),
            "done_count": len(job["results"]) + len(job["errors"]),
            "results": dict(job["results"]),
            "errors": dict(job["errors"]),
            "in_progress": sorted(job["in_progress"]),
            "elapsed_seconds": int(time.time() - job["started_at"]),
        }
    return jsonify(snapshot)


@app.route("/api/staging")
def list_staging():
    """List all results currently saved in research/staging/.

    Used by the UI to repopulate cards after a browser refresh or to let
    the senior see runs from previous sessions.
    """
    items = []
    if STAGING_DIR.exists():
        for p in sorted(STAGING_DIR.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                meta = data.get("_meta", {}) if isinstance(data, dict) else {}
                items.append({
                    "code": p.stem,
                    "saved_at": meta.get("saved_at", ""),
                    "input_name": meta.get("input_name", p.stem),
                    "tab": data.get("tab", ""),
                    "bucket": data.get("bucket", ""),
                    "biz_classification": data.get("biz_classification", ""),
                })
            except Exception:  # noqa: BLE001
                items.append({"code": p.stem, "saved_at": "", "error": "unreadable"})
    return jsonify({"staging_dir": str(STAGING_DIR), "items": items})


@app.route("/api/staging/<code>")
def get_staging(code: str):
    """Return the full saved JSON for one staging entry."""
    p = STAGING_DIR / f"{code}.json"
    if not p.exists():
        return jsonify({"error": "Not found"}), 404
    try:
        return jsonify(json.loads(p.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Failed to read: {e}"}), 500


@app.route("/api/health")
def health():
    return jsonify({
        "ok": True,
        "model": "claude-sonnet-4-6",
        "max_tickers_per_request": MAX_TICKERS_PER_REQUEST,
        "api_key_present": bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the interactive web UI for R+ classification research.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        print("         The UI will load but research requests will fail.", file=sys.stderr)
        print(file=sys.stderr)

    print(f"Starting research web UI on http://{args.host}:{args.port}", file=sys.stderr)
    print(f"Max tickers per request: {MAX_TICKERS_PER_REQUEST}", file=sys.stderr)
    print(f"Open the URL above in a browser to use the UI.", file=sys.stderr)
    print(f"Press Ctrl+C to stop.", file=sys.stderr)
    print(file=sys.stderr)

    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
