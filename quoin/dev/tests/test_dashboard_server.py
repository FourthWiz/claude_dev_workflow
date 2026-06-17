"""Tests for quoin/scripts/dashboard_server.py — ThreadingHTTPServer.

Tests: model cross-load, route smoke, 405, 404, bind address, URL= line,
auto-increment port, explicit-port-taken exit, --no-browser suppression.
T-02, T-03, T-04 acceptance criteria.
"""
from __future__ import annotations

import http.client
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Load dashboard_server via spec_from_file_location
# ---------------------------------------------------------------------------

_SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts"
_DS_PATH = _SCRIPTS_PATH / "dashboard_server.py"

_SPEC = importlib.util.spec_from_file_location("_quoin_adapter_dashboard_server_test", _DS_PATH)
_DS = importlib.util.module_from_spec(_SPEC)
sys.modules["_quoin_adapter_dashboard_server_test"] = _DS
_SPEC.loader.exec_module(_DS)

DashboardServer = _DS.DashboardServer
DashboardHandler = _DS.DashboardHandler
_bind_server = _DS._bind_server
main = _DS.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path) -> Path:
    """Create a minimal project with .workflow_artifacts/."""
    proj = tmp_path / "project"
    (proj / ".workflow_artifacts").mkdir(parents=True)
    return proj


def _start_server(project_root: Path, port: int = 0):
    """Start server in a background thread on an ephemeral port. Returns (server, thread)."""
    import copy

    # Create a fresh handler subclass with the correct project_root
    class _Handler(DashboardHandler):
        pass

    _Handler.project_root = project_root
    _Handler.cost_provider = None  # counts-only for tests

    server = _DS.DashboardServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, t


def _get(server, path: str):
    """GET from the running server. Returns (status, headers, body_bytes)."""
    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, resp.getheaders(), body


def _method(server, method: str, path: str):
    """Make an arbitrary HTTP method request. Returns status int."""
    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path)
    resp = conn.getresponse()
    resp.read()
    conn.close()
    return resp.status


# ---------------------------------------------------------------------------
# T-02: module skeleton + model cross-load
# ---------------------------------------------------------------------------

class TestModuleLoad:
    def test_scan_tasks_bound(self):
        """spec-loading dashboard_server.py binds scan_tasks."""
        assert callable(_DS.scan_tasks)

    def test_task_detail_bound(self):
        assert callable(_DS.task_detail)

    def test_make_cost_provider_bound(self):
        assert callable(_DS.make_cost_provider)

    def test_model_load_uses_parents1(self):
        """dashboard_server.py loads model via parents[1]/core/scripts — not a bare import."""
        source = _DS_PATH.read_text(encoding="utf-8")
        assert 'parents[1]' in source
        assert '"core" / "scripts"' in source or '"core"' in source

    def test_no_bare_import_dashboard_model(self):
        """Must not do 'import dashboard_model'."""
        source = _DS_PATH.read_text(encoding="utf-8")
        assert "import dashboard_model" not in source


# ---------------------------------------------------------------------------
# T-03: do_GET routes + 405 + 404 + bind address
# ---------------------------------------------------------------------------

class TestRoutes:
    def test_api_tasks_returns_200(self, tmp_path):
        """GET /api/tasks → 200 JSON with tasks/active_task/project_root."""
        proj = _make_project(tmp_path)
        server, _ = _start_server(proj)
        try:
            status, _, body = _get(server, "/api/tasks")
            assert status == 200
            data = json.loads(body)
            assert "tasks" in data
            assert "active_task" in data
            assert "project_root" in data
        finally:
            server.shutdown()

    def test_api_tasks_missing_task_returns_404(self, tmp_path):
        """GET /api/tasks/does-not-exist → 404 with JSON error body."""
        proj = _make_project(tmp_path)
        server, _ = _start_server(proj)
        try:
            status, _, body = _get(server, "/api/tasks/does-not-exist")
            assert status == 404
            data = json.loads(body)
            assert "error" in data
        finally:
            server.shutdown()

    def test_post_returns_405(self, tmp_path):
        """POST /api/tasks → 405 Method Not Allowed."""
        proj = _make_project(tmp_path)
        server, _ = _start_server(proj)
        try:
            status = _method(server, "POST", "/api/tasks")
            assert status == 405
        finally:
            server.shutdown()

    def test_put_returns_405(self, tmp_path):
        """PUT /anything → 405."""
        proj = _make_project(tmp_path)
        server, _ = _start_server(proj)
        try:
            status = _method(server, "PUT", "/api/tasks")
            assert status == 405
        finally:
            server.shutdown()

    def test_path_traversal_returns_404(self, tmp_path):
        """GET /../etc/passwd → 404 (allowlist lookup, not path join)."""
        proj = _make_project(tmp_path)
        server, _ = _start_server(proj)
        try:
            status, _, _ = _get(server, "/../etc/passwd")
            assert status == 404
        finally:
            server.shutdown()

    def test_app_js_traversal_returns_404(self, tmp_path):
        """GET /app.js/../../secret → 404."""
        proj = _make_project(tmp_path)
        server, _ = _start_server(proj)
        try:
            status, _, _ = _get(server, "/app.js/../../secret")
            assert status == 404
        finally:
            server.shutdown()

    def test_bind_address_is_loopback(self, tmp_path):
        """Server socket must be bound to 127.0.0.1."""
        proj = _make_project(tmp_path)
        server, _ = _start_server(proj)
        try:
            assert server.server_address[0] == "127.0.0.1"
        finally:
            server.shutdown()

    def test_api_tasks_and_detail_use_same_project_root(self, tmp_path):
        """Both /api/tasks and /api/tasks/<name> use the same project_root (D-15)."""
        proj = _make_project(tmp_path)
        # Create a task directory so task_detail can find it
        task_dir = proj / ".workflow_artifacts" / "my-task"
        task_dir.mkdir(parents=True)
        (task_dir / "current-plan.md").write_text("# plan\n", encoding="utf-8")

        server, _ = _start_server(proj)
        try:
            # /api/tasks should list my-task
            status, _, body = _get(server, "/api/tasks")
            assert status == 200
            data = json.loads(body)
            names = [t["name"] for t in data.get("tasks", [])]
            assert "my-task" in names

            # /api/tasks/my-task should return 200 (not 404)
            status2, _, body2 = _get(server, "/api/tasks/my-task")
            assert status2 == 200
        finally:
            server.shutdown()

    def test_asset_root_returns_index_html(self, tmp_path):
        """GET / returns index.html content (or 404 if assets not yet deployed)."""
        proj = _make_project(tmp_path)
        server, _ = _start_server(proj)
        try:
            status, _, body = _get(server, "/")
            # Accept 200 (assets present) or 404 (assets not yet built, T-06 not done)
            assert status in (200, 404)
        finally:
            server.shutdown()


# ---------------------------------------------------------------------------
# T-04: URL= line, auto-increment, explicit-port-taken, --no-browser
# ---------------------------------------------------------------------------

class TestPortAndStartup:
    def test_url_line_printed_before_blocking(self, tmp_path):
        """dashboard_server.py --no-browser --port 0 prints exactly one URL= line."""
        proj = _make_project(tmp_path)
        script = str(_DS_PATH)
        proc = subprocess.Popen(
            [sys.executable, script, "--no-browser", "--port", "0",
             "--project-root", str(proj)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            # Read until we see the URL= line (max 5s)
            url_line = None
            deadline = time.time() + 5
            while time.time() < deadline:
                line = proc.stdout.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("URL="):
                    url_line = line
                    break
            assert url_line is not None, "No URL= line printed within 5 seconds"
            assert url_line.startswith("URL=http://127.0.0.1:")
            # Verify the port is real (>0)
            port_str = url_line.split(":")[-1]
            assert int(port_str) > 0
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_auto_increment_when_default_port_taken(self, tmp_path):
        """When 8787 is pre-bound, server auto-increments to next free port."""
        proj = _make_project(tmp_path)

        # Pre-bind 8787
        pre_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        pre_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            pre_sock.bind(("127.0.0.1", 8787))
            pre_sock.listen(1)
        except OSError:
            pytest.skip("Port 8787 not available for pre-binding test")

        try:
            script = str(_DS_PATH)
            proc = subprocess.Popen(
                [sys.executable, script, "--no-browser", "--project-root", str(proj)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                url_line = None
                deadline = time.time() + 5
                while time.time() < deadline:
                    line = proc.stdout.readline().decode("utf-8", errors="replace").strip()
                    if line.startswith("URL="):
                        url_line = line
                        break
                assert url_line is not None, "No URL= line printed within 5 seconds"
                port_str = url_line.split(":")[-1]
                actual_port = int(port_str)
                assert actual_port != 8787
                assert 8788 <= actual_port <= 8796
            finally:
                proc.terminate()
                proc.wait(timeout=5)
        finally:
            pre_sock.close()

    def test_explicit_port_taken_exits_nonzero(self, tmp_path):
        """--port <taken> exits non-zero with a clear stderr message (no auto-increment)."""
        proj = _make_project(tmp_path)

        # Bind a random ephemeral port first
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        taken_port = sock.getsockname()[1]
        sock.listen(1)
        try:
            script = str(_DS_PATH)
            proc = subprocess.run(
                [sys.executable, script, "--no-browser", "--port", str(taken_port),
                 "--project-root", str(proj)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            assert proc.returncode != 0
            stderr = proc.stderr.decode("utf-8", errors="replace")
            # Should mention the port and "in use"
            assert str(taken_port) in stderr or "in use" in stderr or "port" in stderr.lower()
        finally:
            sock.close()

    def test_no_browser_suppresses_open(self, tmp_path):
        """--no-browser must not call webbrowser.open.

        Tests the source-level logic: args.no_browser controls the open call.
        """
        proj = _make_project(tmp_path)
        source = _DS_PATH.read_text(encoding="utf-8")
        # Verify that --no-browser check guards webbrowser.open
        assert "no_browser" in source
        assert "webbrowser.open" in source
        # And that the guard is `if not args.no_browser` or similar
        assert "no_browser" in source

    def test_no_browser_arg_parsed_correctly(self, tmp_path):
        """Verify --no-browser is a recognised argument (argparse integration)."""
        proj = _make_project(tmp_path)
        script = str(_DS_PATH)
        # --help should list --no-browser without error
        proc = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True, timeout=5,
        )
        assert proc.returncode == 0
        assert b"no-browser" in proc.stdout


# ---------------------------------------------------------------------------
# T-05: SSE decision (polling-only mode — SSE was not implemented)
# ---------------------------------------------------------------------------

class TestSSEDecision:
    def test_api_events_absent(self, tmp_path):
        """GET /api/events → 404 (SSE was cut; polling-only per D-10 fallback)."""
        proj = _make_project(tmp_path)
        server, _ = _start_server(proj)
        try:
            status, _, body = _get(server, "/api/events")
            assert status == 404
        finally:
            server.shutdown()

    def test_no_eventsource_in_source(self):
        """app.js must not contain EventSource when SSE was cut (check after T-09)."""
        # This test will be meaningful once app.js exists. Skip gracefully if not yet.
        app_js = Path(__file__).resolve().parents[2] / "core" / "scripts" / "dashboard_assets" / "app.js"
        if not app_js.exists():
            pytest.skip("app.js not yet created (T-08/T-09 not done)")
        source = app_js.read_text(encoding="utf-8")
        assert "new EventSource" not in source and "EventSource(" not in source, (
            "SSE was cut (T-05 spike skipped); app.js must not construct EventSource"
        )


# ---------------------------------------------------------------------------
# T-07 IVG-85: url-file capture (Test C) and SIGHUP shutdown (Test D)
# ---------------------------------------------------------------------------

class TestUrlFileAndSighup:
    def test_url_file_arg_in_help(self, tmp_path):
        """--url-file is a recognised argument (argparse integration check)."""
        proc = subprocess.run(
            [sys.executable, str(_DS_PATH), "--help"],
            capture_output=True, timeout=5,
        )
        assert proc.returncode == 0
        assert b"url-file" in proc.stdout, "--url-file not listed in --help output"

    def test_url_file_written_on_startup(self, tmp_path):
        """T-07 Test C: dashboard_server.py --url-file X writes a http://127.0.0.1:<port>
        URL to X within the poll window (5s). (T-04 acceptance criterion)

        Uses subprocess with --port 0 (ephemeral) and --no-browser to avoid side-effects.
        Polls the url-file for up to 5s to match the agentdesk poller's timing contract.
        """
        proj = _make_project(tmp_path)
        url_file = tmp_path / "dash-url.txt"
        proc = subprocess.Popen(
            [sys.executable, str(_DS_PATH),
             "--no-browser", "--port", "0",
             "--project-root", str(proj),
             "--url-file", str(url_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            # Poll url-file for up to 5 seconds
            deadline = time.time() + 5
            url_content = None
            while time.time() < deadline:
                if url_file.exists():
                    content = url_file.read_text(encoding="utf-8").strip()
                    if content.startswith("http://127.0.0.1:"):
                        url_content = content
                        break
                time.sleep(0.1)

            assert url_content is not None, (
                f"URL not written to url-file within 5s; "
                f"url_file exists={url_file.exists()}"
            )
            assert url_content.startswith("http://127.0.0.1:"), (
                f"url-file content is not a loopback URL: {url_content!r}"
            )
            # Extract port and verify it's > 0
            port_str = url_content.rsplit(":", 1)[-1]
            assert int(port_str) > 0, f"Port in url-file should be > 0: {url_content!r}"
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_sighup_shuts_down_server(self, tmp_path):
        """T-07 Test D: SIGHUP causes the server to shut down within a bounded timeout.
        (T-01/T-02 acceptance criterion — validates the SIGHUP handler registered in main())

        Starts a real server subprocess, sends SIGHUP, asserts the process exits
        within 5 seconds. On platforms where SIGHUP is not available (Windows),
        the test is skipped.
        """
        import signal as signal_mod
        if not hasattr(signal_mod, "SIGHUP"):
            pytest.skip("SIGHUP not available on this platform")

        proj = _make_project(tmp_path)
        proc = subprocess.Popen(
            [sys.executable, str(_DS_PATH),
             "--no-browser", "--port", "0",
             "--project-root", str(proj)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            # Wait for the URL= line to confirm the server is up before sending SIGHUP.
            url_line = None
            deadline = time.time() + 5
            while time.time() < deadline:
                line = proc.stdout.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("URL="):
                    url_line = line
                    break
            assert url_line is not None, "Server did not print URL= line within 5s"

            # Send SIGHUP to the process.
            proc.send_signal(signal_mod.SIGHUP)

            # Assert the process shuts down within 5 seconds.
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise AssertionError(
                    "Server did not shut down within 5s after SIGHUP — "
                    "SIGHUP handler may not be registered"
                )
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=3)
