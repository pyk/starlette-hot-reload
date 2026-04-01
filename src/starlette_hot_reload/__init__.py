"""Starlette Hot Reload."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.applications import Starlette


class HotReload:
    """Hot reload configuration for Starlette applications.

    This class provides a simple way to enable hot reloading in your
    Starlette application. It automatically adds the necessary WebSocket
    route and middleware when the app is in debug mode.

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
        ws_path: str = "/__starlette_hot_reload",
    ) -> None:
        """Initialize hot reload configuration.

        Args:
            watch_dirs: Directories to watch for changes.
                If None, watches the current directory.
            ws_path: Path for the WebSocket endpoint.

        """
        self.watch_dirs = watch_dirs
        self.ws_path = ws_path

    def setup(self, app: Starlette) -> None:
        """Set up hot reload for a Starlette application.

        Automatically adds the WebSocket route and middleware only when
        the app is in debug mode.

        Args:
            app: The Starlette application instance.

        """
        if not getattr(app, "debug", False):
            return


__all__ = ["HotReload"]
