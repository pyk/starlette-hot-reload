<h3 align="center">starlette-hot-reload</h3>

<p align="center">
    Hot reload for Starlette templates and static files
</p>

<p align="center">
<a href="https://pypi.org/project/starlette-hot-reload/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/starlette-hot-reload?style=flat&labelColor=%23000000&color=%23000000"></a> <a href="https://pypi.org/project/starlette-hot-reload/"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/starlette-hot-reload?style=flat&labelColor=000000&color=000000"></a> <a href="https://pypi.org/project/starlette-hot-reload/"><img alt="PyPI - License" src="https://img.shields.io/pypi/l/starlette-hot-reload?labelColor=000&color=000"></a>
</p>

### Overview

`starlette-hot-reload` reloads the browser when your Starlette templates or
static assets change. It injects a small client script into HTML responses and
uses Server-Sent Events (SSE) to notify the browser about changes.

[Demo](https://x.com/sepyke/status/2039360612229374135)

### Quick Start

Install the package:

```shell
uv add starlette-hot-reload
# or
pip install starlette-hot-reload
```

Enable it in your app lifespan:

```python
from contextlib import asynccontextmanager
from starlette.applications import Starlette
from starlette_hot_reload import hot_reload

@asynccontextmanager
async def lifespan(app: Starlette):
    async with hot_reload(app=app, watch_dirs=["templates", "static"]):
        yield

app = Starlette(
    debug=True,
    lifespan=lifespan,
)
```

Run your app:

```shell
uvicorn main:app
```

### What You Get

- Reloads the browser when watched files change.
- Injects the client script into HTML responses automatically.
- Uses SSE, no websocket.
- Composes with Starlette lifespan context managers.
- Adds no extra runtime dependency beyond Starlette.

### Basic Usage

Hot reload only runs when `debug=True`.

```python
app = Starlette(debug=True)
```

Watch specific directories:

```python
@asynccontextmanager
async def lifespan(app: Starlette):
    async with hot_reload(
        app=app,
        watch_dirs=["templates", "static", "assets"],
    ):
        yield
```

Use a custom SSE endpoint:

```python
async with hot_reload(
    app=app,
    watch_dirs=["templates", "static"],
    events_path="/custom-events-path",
):
    ...
```

Tune filesystem polling:

```python
async with hot_reload(
    app=app,
    watch_dirs=["templates", "static"],
    poll_interval=0.25,
):
    ...
```

Compose it with other lifespan resources using `AsyncExitStack`:

```python
from contextlib import AsyncExitStack, asynccontextmanager

@asynccontextmanager
async def lifespan(app: Starlette):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            hot_reload(app=app, watch_dirs=["templates", "static"])
        )
        yield
```

### How It Works

When you request an HTML page, the middleware injects a small client script into
the response body. That script opens an SSE connection to the app.

The file watcher polls the directories you configured. When a file changes:

- Watched changes trigger a full page reload.

This package complements server reload tools such as `uvicorn --reload`. It does
not restart your Python process.

### Limits

- Hot reload is disabled when `debug=False`.
- The watcher uses polling, not native OS file notifications.
- Python code changes reload the browser page, but they do not reload server
  state or restart the app process.
- Script injection targets HTML responses. Non-HTML responses are left alone.

### Examples

The repository includes example apps under `examples/`.

#### `examples/basic`

This example shows the smallest Starlette setup with:

- Jinja templates
- Static files
- `hot_reload()` in the app lifespan

Run it from the repository root:

```shell
uv run python -m examples.basic.app
```

Open `http://127.0.0.1:3000` and edit files in `examples/basic/templates` or
`examples/basic/static`.

#### `examples/with_tailwind`

This example shows how to compose `starlette-hot-reload` with
`starlette-tailwindcss`.

It watches the whole example directory so changes to templates, CSS, and built
assets all trigger a browser reload.

Run it from the repository root:

```shell
uv run python -m examples.with_tailwind.app
```

Open `http://127.0.0.1:3000` and edit files in `examples/with_tailwind/`.

### Debug Logging

If you want watcher and SSE logs during development, enable Python logging:

```python
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
```

### More Starlette Packages

If you are building server-rendered Starlette apps, these packages fit well with
`starlette-hot-reload`:

- [starlette-tailwindcss](https://github.com/pyk/starlette-tailwindcss):
  Tailwind CSS integration for Starlette apps
- [starlette-html-stories](https://github.com/pyk/starlette-html-stories):
  Storybook-like development tools for `starlette-html` components
- [starlette-html](https://github.com/pyk/starlette-html): Python-first HTML DSL
  for server-rendered UI in Starlette

### License

MIT
