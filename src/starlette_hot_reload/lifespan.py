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
    """ASGI middleware for hot reload lifespan and HTTP management."""

    def __init__(self, app: ASGIApp, watcher: FileWatcher) -> None:
        """Initialize middleware."""
        self.app = app
        self.watcher = watcher
        self._started = False
        self._shutting_down = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle ASGI messages."""
        if scope["type"] == "http":
            await self._handle_http(scope, receive, send)
            return

        if scope["type"] != "lifespan":
            await self.app(scope, receive, send)
            return

        await self._handle_lifespan(scope, receive, send)

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle HTTP scope with shutdown detection."""

        async def wrapped_send(message: Message) -> None:
            """Send with shutdown detection."""
            if self._shutting_down:
                logger.debug("HTTP send while shutting down, aborting")
                raise asyncio.CancelledError
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        except asyncio.CancelledError:
            logger.debug("HTTP request cancelled during shutdown")
            raise

    async def _handle_lifespan(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Handle lifespan scope."""
        logger.debug("Lifespan started")

        async def wrapped_receive() -> Message:
            """Receive lifespan messages."""
            message = await receive()

            if message["type"] == "lifespan.startup" and not self._started:
                logger.debug("Starting file watcher")
                await self.watcher.start()
                self._started = True

            if message["type"] == "lifespan.shutdown" and self._started:
                logger.debug("Stopping file watcher (lifespan.shutdown)")
                self._shutting_down = True
                await self.watcher.stop()
                self._started = False

            return message

        try:
            await self.app(scope, wrapped_receive, send)
        except asyncio.CancelledError:
            logger.debug("Lifespan cancelled, forcing shutdown")
            self._shutting_down = True
            if self._started:
                with suppress(asyncio.CancelledError):
                    await self.watcher.stop()
                self._started = False
            raise
        finally:
            logger.debug("Lifespan ended")
