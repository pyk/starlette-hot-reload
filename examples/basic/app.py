"""Example Starlette application with hot reload enabled."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from starlette.applications import Starlette
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from starlette_hot_reload import hot_reload

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request
    from starlette.responses import HTMLResponse

# Enable debug logging to stderr
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)

templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=templates_dir)


async def homepage(request: Request) -> HTMLResponse:
    """Handle homepage requests.

    Args:
        request: The incoming request object.

    Returns:
        HTMLResponse: Rendered index.html template.

    """
    return templates.TemplateResponse(request, "index.html", context={"title": "ACME"})


routes: list[BaseRoute] = [
    Mount(
        "/static",
        app=StaticFiles(directory=static_dir),
        name="static",
    ),
    Route("/", homepage),
]


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    """Run hot reload alongside the Starlette app lifespan."""
    async with hot_reload(app=app, watch_dirs=[templates_dir, static_dir]):
        yield


app = Starlette(
    debug=True,
    routes=routes,
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000, log_config=None)  # noqa: S104
