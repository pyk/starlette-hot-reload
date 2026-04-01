"""WebSocket handler for hot reload connections."""

from __future__ import annotations

import json
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from starlette_hot_reload.watcher import FileWatcher


class HotReloadWebSocket:
    """Handles WebSocket connections for hot reload."""

    def __init__(self, watcher: FileWatcher) -> None:
        """Initialize with a file watcher instance.

        Args:
            watcher: The file watcher that monitors for changes.

        """
        self.watcher = watcher

    async def handle(self, websocket: WebSocket) -> None:
        """Handle a WebSocket connection.

        Args:
            websocket: The WebSocket connection to handle.

        """
        await websocket.accept()

        # Register this connection with the watcher
        await self.watcher.add_client(websocket)

        with suppress(OSError):
            # Keep connection alive and handle pings
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)

                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

        # Unregister this connection
        await self.watcher.remove_client(websocket)

    async def notify_reload(
        self, websocket: WebSocket, *, change_type: str = "reload"
    ) -> None:
        """Send a reload notification to a client.

        Args:
            websocket: The WebSocket client to notify.
            change_type: Type of change ('reload' or 'css').

        """
        with suppress(OSError):
            await websocket.send_json(
                {
                    "type": change_type,
                    "timestamp": json.dumps(None),
                }
            )
