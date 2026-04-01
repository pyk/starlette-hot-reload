"""Server-Sent Events handler for hot reload connections."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from starlette.responses import StreamingResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request

    from starlette_hot_reload.watcher import FileWatcher


class HotReloadEvents:
    """Handles Server-Sent Events connections for hot reload."""

    def __init__(self, watcher: FileWatcher) -> None:
        """Initialize with a file watcher instance.

        Args:
            watcher: The file watcher that monitors for changes.

        """
        self.watcher = watcher

    async def handle(self, _request: Request) -> StreamingResponse:
        """Handle an SSE connection.

        Args:
            _request: The HTTP request (unused).

        Returns:
            StreamingResponse: SSE stream response.

        """
        # Create a queue for this client
        queue: asyncio.Queue[dict] = asyncio.Queue()
        await self.watcher.add_client(queue)

        async def event_generator() -> AsyncIterator[str]:
            """Generate SSE events."""
            try:
                while True:
                    # Wait for a message from the watcher
                    message = await queue.get()
                    # Format as SSE: data: {...}\n\n
                    yield f"data: {json.dumps(message)}\n\n"
            finally:
                # Clean up when client disconnects
                await self.watcher.remove_client(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
