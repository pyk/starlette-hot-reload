"""ASGI Lifespan middleware for hot reload."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from starlette_hot_reload.watcher import FileWatcher

logger = logging.getLogger(__name__)


class HotReloadLifespanMiddleware:
    """ASGI middleware that manages file watcher lifecycle via lifespan protocol.

    This middleware intercepts lifespan protocol messages to start the file
    watcher on startup and stop it on shutdown. It passes through all other
    ASGI messages unchanged.

    Usage:
        from starlette.applications import Starlette
        from starlette_hot_reload.watcher import FileWatcher
        from starlette_hot_reload.lifespan import HotReloadLifespanMiddleware

        watcher = FileWatcher(watch_dirs=["templates"])
        middleware = HotReloadLifespanMiddleware(app, watcher)

    """

    def __init__(self, app: ASGIApp, watcher: FileWatcher) -> None:
        """Initialize the lifespan middleware.

        Args:
            app: The ASGI application to wrap.
            watcher: The file watcher to manage.

        """
        self.app = app
        self.watcher = watcher
        self._started = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle ASGI messages.

        Intercepts lifespan messages to manage the watcher, passes all
        other messages through to the wrapped app.

        """
        if scope["type"] != "lifespan":
            # Not a lifespan message, pass through
            await self.app(scope, receive, send)
            return

        async def wrapped_receive() -> Message:
            """Receive and intercept lifespan messages."""
            message = await receive()

            # Start the file watcher on lifespan.startup if not already started
            if message["type"] == "lifespan.startup" and not self._started:
                logger.debug("Starting file watcher (lifespan.startup)")
                await self.watcher.start()
                self._started = True
                logger.debug("File watcher started")

            # Stop the file watcher on lifespan.shutdown (before shutdown.complete)
            # This ensures SSE connections close before uvicorn waits for them
            if message["type"] == "lifespan.shutdown" and self._started:
                logger.debug("Stopping file watcher (lifespan.shutdown)")
                await self.watcher.stop()
                self._started = False
                logger.debug("File watcher stopped")

            return message

        async def wrapped_send(message: Message) -> None:
            """Send and intercept lifespan responses."""
            with suppress(asyncio.CancelledError):
                await send(message)

        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        except asyncio.CancelledError:
            # Server is shutting down, stop watcher if running
            if self._started:
                logger.debug("Stopping file watcher (cancelled)")
                with suppress(asyncio.CancelledError):
                    await self.watcher.stop()
                self._started = False
            raise
