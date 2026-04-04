"""Starlette lifespan integration for hot reload."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from starlette.middleware import Middleware

from starlette_hot_reload.events import HotReloadEvents
from starlette_hot_reload.middleware import HotReloadMiddleware
from starlette_hot_reload.watcher import FileWatcher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import StreamingResponse


@asynccontextmanager
async def hot_reload(
    *,
    app: Starlette,
    watch_dirs: list[str | Path] | None = None,
    events_path: str = "/__starlette_hot_reload",
    poll_interval: float = 0.25,
    inject_before_body: bool = True,
) -> AsyncIterator[None]:
    """Enable hot reload for a Starlette app inside lifespan.

    Usage:
        @asynccontextmanager
        async def lifespan(app: Starlette):
            async with hot_reload(app=app, watch_dirs=["templates", "static"]):
                yield

    Compose this with other lifespan-managed resources using
    ``contextlib.AsyncExitStack`` when needed.
    """
    if not getattr(app, "debug", False):
        yield
        return

    watcher = FileWatcher(
        [str(d) for d in (watch_dirs or ["."])],
        poll_interval=poll_interval,
    )

    original_routes = list(app.router.routes)
    original_middleware = list(app.user_middleware)
    original_stack = app.middleware_stack

    async def events_endpoint(request: Request) -> StreamingResponse:
        return await HotReloadEvents(watcher).handle(request)

    app.add_route(
        events_path,
        events_endpoint,
        methods=["GET"],
        name="hot_reload_events",
    )
    app.user_middleware.insert(
        0,
        Middleware(
            HotReloadMiddleware,
            events_path=events_path,
            inject_before_body=inject_before_body,
        ),
    )
    app.middleware_stack = app.build_middleware_stack()

    try:
        async with watcher.run():
            yield
    finally:
        app.router.routes[:] = original_routes
        app.user_middleware[:] = original_middleware
        app.middleware_stack = original_stack
