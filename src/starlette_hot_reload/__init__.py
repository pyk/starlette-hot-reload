"""Starlette Hot Reload."""

from typing import TYPE_CHECKING

from starlette_hot_reload.events import HotReloadEvents
from starlette_hot_reload.lifespan import HotReloadLifespanMiddleware
from starlette_hot_reload.middleware import HotReloadMiddleware
from starlette_hot_reload.watcher import FileWatcher

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import StreamingResponse


class HotReload:
    """Hot reload configuration for Starlette applications.

    This class provides a simple way to enable hot reloading in your
    Starlette application. It automatically adds the necessary SSE
    endpoint and middleware when the app is in debug mode.

    Usage:
        from starlette.applications import Starlette
        from starlette_hot_reload import HotReload

        app = Starlette(debug=True, routes=routes)

        hot_reload = HotReload(watch_dirs=["templates", "static"])
        hot_reload.setup(app)

    """

    def __init__(
        self,
        watch_dirs: list[str | Path] | None = None,
        events_path: str = "/__starlette_hot_reload",
        poll_interval: float = 0.25,
    ) -> None:
        """Initialize hot reload configuration.

        Args:
            watch_dirs: Directories to watch for changes.
                If None, watches the current directory.
            events_path: Path for the Server-Sent Events endpoint.
            poll_interval: Seconds between filesystem scans.

        """
        self.watch_dirs = watch_dirs
        self.events_path = events_path
        self.poll_interval = poll_interval

    def setup(self, app: Starlette) -> None:
        """Set up hot reload for a Starlette application.

        Automatically adds the SSE endpoint and middleware only when
        the app is in debug mode.

        This method adds middleware that manages the file watcher lifecycle
        automatically via the ASGI lifespan protocol.

        Args:
            app: The Starlette application instance.

        """
        if not getattr(app, "debug", False):
            return

        watcher = FileWatcher(
            [str(d) for d in (self.watch_dirs or ["."])],
            poll_interval=self.poll_interval,
        )

        async def events_endpoint(request: Request) -> StreamingResponse:
            return await HotReloadEvents(watcher).handle(request)

        # Add the SSE route
        app.add_route(
            self.events_path,
            events_endpoint,
            methods=["GET"],
            name="hot_reload_events",
        )

        # Add the middleware for HTML injection
        app.add_middleware(
            HotReloadMiddleware,
            events_path=self.events_path,
        )

        # Add lifespan middleware to manage the watcher lifecycle
        # This must be added last so it's the outermost middleware
        # and can intercept lifespan messages before they reach the router
        app.add_middleware(
            HotReloadLifespanMiddleware,
            watcher=watcher,
        )


__all__ = ["HotReload"]
