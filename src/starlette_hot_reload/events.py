"""Server-Sent Events handler for hot reload connections."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from starlette.responses import StreamingResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request

    from starlette_hot_reload.watcher import FileWatcher

logger = logging.getLogger(__name__)


class HotReloadEvents:
    """Handles Server-Sent Events connections for hot reload."""

    def __init__(self, watcher: FileWatcher) -> None:
        """Initialize with a file watcher instance."""
        self.watcher = watcher

    async def handle(self, request: Request) -> StreamingResponse:
        """Handle an SSE connection."""
        queue: asyncio.Queue[dict] = asyncio.Queue()
        await self.watcher.add_client(queue)
        logger.debug("SSE client connected, total: %d", len(self.watcher.clients))

        async def event_generator() -> AsyncIterator[str]:
            """Generate SSE events."""
            try:
                while True:
                    # Check shutdown first
                    if self.watcher.is_shutting_down():
                        logger.debug("Shutdown detected, closing SSE")
                        break

                    # Check client disconnected
                    if await request.is_disconnected():
                        logger.debug("Client disconnected")
                        break

                    # Wait for message with short timeout
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=0.5)
                    except TimeoutError:
                        continue

                    if message.get("type") == "shutdown":
                        yield f"data: {json.dumps(message)}\n\n"
                        break

                    yield f"data: {json.dumps(message)}\n\n"

            except asyncio.CancelledError:
                logger.debug("SSE cancelled (server shutdown)")
                raise  # Re-raise to allow proper task cancellation
            except GeneratorExit:
                logger.debug("SSE generator exited")
                raise  # Re-raise to allow proper generator cleanup
            finally:
                await self.watcher.remove_client(queue)
                logger.debug(
                    "SSE client removed, remaining: %d", len(self.watcher.clients)
                )

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
