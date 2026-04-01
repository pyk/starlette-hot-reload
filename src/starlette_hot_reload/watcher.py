"""File watcher for hot reload using anyio."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from types import TracebackType

    from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class FileWatcher:
    """Watch files for changes and notify connected clients.

    Uses anyio for async file watching as recommended by Starlette docs.
    """

    def __init__(
        self,
        watch_dirs: list[str] | None = None,
        extensions: list[str] | None = None,
    ) -> None:
        """Initialize the file watcher.

        Args:
            watch_dirs: Directories to watch. Defaults to current directory.
            extensions: File extensions to watch.
                Defaults to common web files.

        """
        self.watch_dirs = [
            Path(d) if isinstance(d, str) else d for d in (watch_dirs or ["."])
        ]
        self.extensions = extensions or [".py", ".html", ".js", ".css", ".json"]
        self.clients: set[WebSocket] = set()
        self._task_group = None
        self._stop_event: anyio.Event | None = anyio.Event()

    @asynccontextmanager
    async def __aenter__(self) -> AsyncIterator[FileWatcher]:
        """Async context manager entry."""
        await self.start()
        try:
            yield self
        finally:
            await self.stop()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""

    async def start(self) -> None:
        """Start watching files."""
        async with anyio.create_task_group() as tg:
            self._task_group = tg
            for watch_dir in self.watch_dirs:
                tg.start_soon(self._watch_directory, watch_dir)

    async def stop(self) -> None:
        """Stop watching files."""
        if self._stop_event:
            self._stop_event.set()

    async def add_client(self, websocket: WebSocket) -> None:
        """Add a WebSocket client to notify.

        Args:
            websocket: WebSocket connection to add.

        """
        self.clients.add(websocket)

    async def remove_client(self, websocket: WebSocket) -> None:
        """Remove a WebSocket client.

        Args:
            websocket: WebSocket connection to remove.

        """
        self.clients.discard(websocket)

    async def _watch_directory(self, watch_dir: Path) -> None:
        """Watch a directory for changes.

        Args:
            watch_dir: Directory to watch.

        """
        # Store file modification times
        file_mtimes: dict[Path, float] = {}

        while self._stop_event is not None and not self._stop_event.is_set():
            try:
                # Scan for changes
                changes = self._scan_changes(watch_dir, file_mtimes)

                if changes:
                    # Determine if we need full reload or just CSS refresh
                    css_only = all(change.suffix == ".css" for change in changes)
                    change_type = "css" if css_only else "reload"

                    # Notify all clients
                    await self._notify_all(change_type, changes)

                # Wait before next scan
                await anyio.sleep(1.0)

            except OSError as e:
                # Log error but continue watching
                logger.warning("Watch error: %s", e)
                await anyio.sleep(1.0)

    def _scan_changes(
        self,
        watch_dir: Path,
        file_mtimes: dict[Path, float],
    ) -> list[Path]:
        """Scan directory for file changes.

        Args:
            watch_dir: Directory to scan.
            file_mtimes: Dictionary of file modification times.

        Returns:
            List of changed file paths.

        """
        changes: list[Path] = []

        if not watch_dir.exists():
            return changes

        try:
            for ext in self.extensions:
                for file_path in watch_dir.rglob(f"*{ext}"):
                    try:
                        mtime = file_path.stat().st_mtime

                        if file_path in file_mtimes:
                            if mtime > file_mtimes[file_path]:
                                changes.append(file_path)
                                file_mtimes[file_path] = mtime
                        else:
                            file_mtimes[file_path] = mtime

                    except OSError:
                        continue

        except OSError as e:
            logger.warning("Scan error: %s", e)

        return changes

    async def _notify_all(self, change_type: str, changes: list[Path]) -> None:
        """Notify all connected clients of a change.

        Args:
            change_type: Type of change ('reload' or 'css').
            changes: List of changed file paths.

        """
        message = {
            "type": change_type,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "files": [str(f) for f in changes],
        }

        # Send to all clients
        disconnected: set[WebSocket] = set()
        for client in self.clients:
            try:
                await client.send_json(message)
            except OSError:
                # Mark for removal
                disconnected.add(client)

        # Remove disconnected clients
        for client in disconnected:
            self.clients.discard(client)
