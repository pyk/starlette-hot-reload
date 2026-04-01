from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=templates_dir)


async def homepage(request: Request) -> HTMLResponse:
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
