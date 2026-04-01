"""Standalone test server used by the force-quit integration test."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route

from starlette_hot_reload import HotReload

if TYPE_CHECKING:
    from starlette.requests import Request


async def homepage(_request: Request) -> HTMLResponse:
    """Serve a simple HTML page that triggers hot reload injection."""
    return HTMLResponse("<html><body>Hello</body></html>")


def create_app() -> Starlette:
    """Build the demo app used by the force-quit test."""
    app = Starlette(debug=True, routes=[Route("/", homepage)])
    HotReload(watch_dirs=["."]).setup(app)
    return app


def main() -> None:
    """Run the standalone server."""
    app = create_app()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(sys.argv[1]),
        log_config=None,
    )


if __name__ == "__main__":
    main()
