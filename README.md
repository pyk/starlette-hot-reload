# Starlette Hot Reload

`starlette-hot-reload` is a lightweight hot reload utility for
[Starlette](https://starlette.dev/) that provides fast in-browser reloads for
templates and static files.

[Demo](https://x.com/sepyke/status/2039360612229374135)

It integrates directly with your Starlette app and provides:

- Automatic HTML injection via middleware.
- Server-Sent Events (SSE) based live reload (no WebSocket dependencies).
- Smart updates, CSS changes reload without a full page refresh.
- Automatic reconnection with exponential backoff.
- Fully typed, following Starlette patterns.
- Zero additional dependencies beyond Starlette.
- Explicit lifespan composition, matching Starlette's application model.

## Installation

```shell
uv add starlette-hot-reload
# or
pip install starlette-hot-reload
```

## Example

```python
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Route

from starlette_hot_reload import hot_reload

routes = [
    # your routes
]

@asynccontextmanager
async def lifespan(app: Starlette):
    async with hot_reload(app=app, watch_dirs=["templates", "static"]):
        yield

app = Starlette(
    debug=True,
    routes=routes,
    lifespan=lifespan,
)
```

Run the application using uvicorn:

```shell
$ uvicorn main:app
```

## How it works

`starlette-hot-reload` updates the browser without restarting the server.

It integrates into your app using middleware and a Server-Sent Events (SSE)
endpoint.

- HTML responses are automatically modified to include a small client script.
- The client connects to an SSE stream exposed by the app.
- File changes trigger reload events:
    - CSS changes update stylesheets in-place.
    - Other changes trigger a full page reload.
- The client automatically reconnects if the connection is lost.

It complements:

- ASGI server reload (`uvicorn --reload`)
- Frontend build tools (Vite, Webpack, etc.)

## Usage

Hot reload is only active when `debug=True`.

```python
app = Starlette(debug=True)
```

You can control which directories are watched:

```python
@asynccontextmanager
async def lifespan(app: Starlette):
    async with hot_reload(app=app, watch_dirs=["templates", "static", "assets"]):
        yield
```

You can customize the SSE endpoint path (default is `/__starlette_hot_reload`):

```python
async with hot_reload(
    app=app,
    watch_dirs=["templates", "static"],
    events_path="/custom-events-path",
):
    ...
```

You can also tune how often the watcher scans for changes. Lower values make
reloads feel faster, at the cost of a bit more filesystem polling:

```python
async with hot_reload(
    app=app,
    watch_dirs=["templates", "static"],
    poll_interval=0.25,
):
    ...
```

If you compose hot reload with other lifespan-managed resources, use
`contextlib.AsyncExitStack`:

```python
from contextlib import AsyncExitStack, asynccontextmanager

@asynccontextmanager
async def lifespan(app: Starlette):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(hot_reload(app=app, watch_dirs=["templates", "static"]))
        yield
```

### Debug Logging

To enable debug logging, configure Python's logging module:

```python
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    # ...
)
```

## License

MIT
