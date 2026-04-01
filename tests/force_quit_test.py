"""Integration test for the force-quit shutdown path."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]


def test_force_quit_exits_with_connected_sse_client() -> None:
    """A live SSE client should not block process shutdown."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    server_code = """
from __future__ import annotations

import sys

import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route

from starlette_hot_reload import HotReload


async def homepage(request):
    return HTMLResponse("<html><body>Hello</body></html>")


app = Starlette(debug=True, routes=[Route("/", homepage)])
HotReload(watch_dirs=["."]).setup(app)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(sys.argv[1]),
        log_config=None,
    )
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    proc = subprocess.Popen(
        [sys.executable, "-c", server_code, str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        deadline = time.monotonic() + 10.0
        url = f"http://127.0.0.1:{port}/"
        with httpx.Client(timeout=1.0) as client:
            while True:
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    break
                except (
                    httpx.ConnectError,
                    httpx.ReadTimeout,
                    httpx.RemoteProtocolError,
                ):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("server did not start within 10 seconds")
                    time.sleep(0.1)

        sse_url = f"http://127.0.0.1:{port}/__starlette_hot_reload"
        with httpx.Client(timeout=5.0) as client:
            with client.stream("GET", sse_url) as response:
                assert response.status_code == 200

                proc.send_signal(signal.SIGINT)
                proc.wait(timeout=10)

        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
