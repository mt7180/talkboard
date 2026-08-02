#!/usr/bin/env python3
"""Serve a talkboard HTML file, collect user annotations, emit TOON.

Workflow:
  1. Serves the given HTML file on localhost (auto-picks a free port).
  2. Opens the default browser (best effort).
  3. Waits for the page to POST its annotations to /annotations (JSON).
  4. Converts them to TOON, prints the TOON to stdout between marker lines,
     writes it to <html-stem>.annotations.toon next to the HTML file, exits.

Exit codes: 0 = annotations received or user ended the session via the
"Server beenden" button, 2 = timeout, 3 = bad input/payload.
"""

import argparse
import json
import re
import socket
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BEGIN_MARK = "-----BEGIN TOON-----"
END_MARK = "-----END TOON-----"

# --------------------------------------------------------------------------
# TOON encoding (tailored to the flat annotation schema)
# --------------------------------------------------------------------------

_NEEDS_QUOTE = re.compile(r'[,"\n\r]|^\s|\s$|^$|^#|^-')


def toon_scalar(value: str) -> str:
    """Quote a scalar the TOON way when it could be misread otherwise."""
    value = str(value)
    if _NEEDS_QUOTE.search(value) or value.strip() != value:
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "")
        )
        return f'"{escaped}"'
    return value


def annotations_to_toon(payload: dict) -> str:
    """Convert the submitted JSON payload to a TOON document."""
    doc = str(payload.get("doc", "canvas"))
    title = str(payload.get("title", ""))
    exported = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = payload.get("annotations", [])
    if not isinstance(rows, list):
        raise ValueError("'annotations' must be a list")

    lines = [
        f"doc: {toon_scalar(doc)}",
        f"title: {toon_scalar(title)}",
        f"exported: {exported}",
        f"annotations[{len(rows)}]{{id,target,label,comment}}:",
    ]
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError("annotation entries must be objects")
        cells = [
            toon_scalar(row.get("id", i)),
            toon_scalar(row.get("target", "")),
            toon_scalar(row.get("label", "")),
            toon_scalar(row.get("comment", "")),
        ]
        lines.append("  " + ",".join(cells))

    # Editable graph sections (freeform, cytoscape-based) are a separate, optional
    # set of tables — only emitted when at least one graph section exists, so a
    # canvas without one produces byte-identical output to before this feature.
    # Mirrors the JS encoder in assets/template.html; keep both in lockstep.
    graphs = payload.get("graphs", [])
    if not isinstance(graphs, list):
        raise ValueError("'graphs' must be a list")
    if graphs:
        for g in graphs:
            if not isinstance(g, dict):
                raise ValueError("graph entries must be objects")

        lines.append(f"graphs[{len(graphs)}]{{id,label}}:")
        for g in graphs:
            lines.append(
                "  " + ",".join(toon_scalar(x) for x in (g.get("id", ""), g.get("label", "")))
            )

        node_rows = [
            (g.get("id", ""), n.get("id", ""), n.get("label", ""))
            for g in graphs
            for n in (g.get("nodes") or [])
        ]
        lines.append(f"graph_nodes[{len(node_rows)}]{{graph,id,label}}:")
        for row in node_rows:
            lines.append("  " + ",".join(toon_scalar(x) for x in row))

        edge_rows = [
            (g.get("id", ""), e.get("from", ""), e.get("to", ""), e.get("label", ""))
            for g in graphs
            for e in (g.get("edges") or [])
        ]
        lines.append(f"graph_edges[{len(edge_rows)}]{{graph,from,to,label}}:")
        for row in edge_rows:
            lines.append("  " + ",".join(toon_scalar(x) for x in row))

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------


def make_handler(html_path: Path, done: threading.Event, result: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep stdout clean for the TOON
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, html_path.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/ping":
                self._send(200, b"ok", "text/plain")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path == "/shutdown":
                self._send(200, b'{"status":"bye"}', "application/json")
                result["shutdown"] = True
                done.set()
                return
            if self.path != "/annotations":
                self._send(404, b"not found", "text/plain")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                result["toon"] = annotations_to_toon(payload)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(400, str(exc).encode(), "text/plain; charset=utf-8")
                result["error"] = str(exc)
                done.set()
                return
            self._send(200, b'{"status":"received"}', "application/json")
            done.set()

    return Handler


def free_port(preferred: int) -> int:
    for port in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
        except OSError:
            continue
    raise OSError("no free port found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", help="Path to the talkboard HTML file")
    parser.add_argument("--port", type=int, default=4747)
    parser.add_argument("--timeout", type=int, default=1800, help="Seconds to wait")
    parser.add_argument("--no-open", action="store_true", help="Don't open a browser")
    args = parser.parse_args()

    html_path = Path(args.html).resolve()
    if not html_path.is_file():
        print(f"error: file not found: {html_path}", file=sys.stderr)
        return 3

    port = free_port(args.port)
    done = threading.Event()
    result: dict = {}
    server = ThreadingHTTPServer(
        ("127.0.0.1", port), make_handler(html_path, done, result)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/"
    print(f"talkboard: serving {html_path.name} at {url}", flush=True)
    print("talkboard: waiting for annotations …", flush=True)
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    got_it = done.wait(timeout=args.timeout)
    server.shutdown()

    if not got_it:
        print("talkboard: timeout, no annotations received", file=sys.stderr)
        return 2
    if result.get("shutdown") and "toon" not in result:
        print("talkboard: user ended the session; no annotations submitted", flush=True)
        return 0
    if "toon" not in result:
        print(f"talkboard: bad payload: {result.get('error')}", file=sys.stderr)
        return 3

    toon = result["toon"]
    out_file = html_path.with_suffix("").with_name(html_path.stem + ".annotations.toon")
    out_file.write_text(toon, encoding="utf-8")

    print(BEGIN_MARK)
    print(toon, end="")
    print(END_MARK)
    print(f"talkboard: written to {out_file}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
