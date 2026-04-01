"""Example Starlette application with hot reload enabled."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from starlette.applications import Starlette
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from starlette_hot_reload import HotReload

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import HTMLResponse

templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=templates_dir)
hot_reload = HotReload(watch_dirs=[templates_dir, static_dir])


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


app = Starlette(
    debug=True,
    routes=routes,
)
hot_reload.setup(app)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)  # noqa: S104
