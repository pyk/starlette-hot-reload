"""File watcher for hot reload using anyio."""

from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import anyio

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

logger = logging.getLogger(__name__)


class FileWatcher:
    """Watch files for changes and notify connected clients.

    Uses anyio for async file watching as recommended by Starlette docs.
    """

    def __init__(
        self,
        watch_dirs: list[str] | None = None,
        extensions: list[str] | None = None,
        poll_interval: float = 0.25,
    ) -> None:
        """Initialize the file watcher.

        Args:
            watch_dirs: Directories to watch. Defaults to current directory.
            extensions: File extensions to watch.
                Defaults to common web files.
            poll_interval: Seconds between filesystem scans.

        """
        self.watch_dirs = [
            Path(d) if isinstance(d, str) else d for d in (watch_dirs or ["."])
        ]
        self.extensions = extensions or [
            ".py",
            ".html",
            ".jinja",
            ".js",
            ".css",
            ".json",
        ]
        self.poll_interval = poll_interval
        self.clients: set[asyncio.Queue[dict]] = set()
        self._stop_event: anyio.Event | None = None
        self._watch_task: asyncio.Task | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._signal_handlers: dict[int, object] = {}
        self._shutdown_task: asyncio.Task | None = None

    def is_shutting_down(self) -> bool:
        """Check if the watcher is shutting down."""
        return self._shutdown_event.is_set()

    def wait_for_shutdown(self) -> asyncio.Event:
        """Get the shutdown event for waiting."""
        return self._shutdown_event

    @asynccontextmanager
    async def run(self) -> AsyncIterator[FileWatcher]:
        """Run the file watcher as an async context manager.

        Usage:
            async with watcher.run():
                # watcher is now running
                await asyncio.sleep_forever()

        """
        await self.start()
        try:
            yield self
        finally:
            await self.stop()

    async def start(self) -> None:
        """Start watching files.

        This creates a task that continuously watches for file changes.
        Use stop() to stop watching.

        """
        if self._watch_task is not None:
            logger.debug("File watcher already running")
            return

        logger.debug("Starting file watcher")
        self._loop = asyncio.get_running_loop()
        self._stop_event = anyio.Event()
        self._watch_task = asyncio.create_task(self._watch_all_directories())
        self._install_signal_handlers()
        logger.debug("File watcher started")

    async def stop(self) -> None:
        """Stop watching files."""
        logger.debug("stop() called, _watch_task is None: %s", self._watch_task is None)
        if self._watch_task is None:
            logger.debug("stop(): watch_task is None, returning early")
            return

        logger.debug("Stopping file watcher")

        # Signal that we're shutting down (this allows SSE connections to close)
        logger.debug("stop(): Setting shutdown event")
        self._shutdown_event.set()
        logger.debug("stop(): shutdown_event is set: %s", self._shutdown_event.is_set())

        if self._stop_event is not None:
            logger.debug("stop(): Setting stop event")
            self._stop_event.set()

        # Signal all clients to disconnect
        logger.debug("stop(): Signaling %d clients", len(self.clients))
        await self._signal_shutdown()
        logger.debug("stop(): Done signaling clients")

        self._watch_task.cancel()
        logger.debug("stop(): Cancelled watch task, awaiting...")
        with suppress(asyncio.CancelledError):
            await self._watch_task
        logger.debug("stop(): Watch task awaited")

        self._remove_signal_handlers()
        self._watch_task = None
        self._stop_event = None
        self._shutdown_event.clear()
        self._loop = None
        self._shutdown_task = None
        logger.debug("File watcher stopped")

    async def _signal_shutdown(self) -> None:
        """Signal all connected clients to disconnect."""
        shutdown_msg = {"type": "shutdown"}
        for queue in list(self.clients):
            with suppress(asyncio.QueueFull, RuntimeError):
                queue.put_nowait(shutdown_msg)

    def _install_signal_handlers(self) -> None:
        """Install signal handlers that trigger watcher shutdown."""
        if self._loop is None:
            return

        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                previous = signal.getsignal(signum)
                if previous is self._handle_signal:
                    continue
                signal.signal(signum, self._handle_signal)
                self._signal_handlers[signum] = previous
            except ValueError, OSError, RuntimeError:
                # Signals are not always available, e.g. in non-main threads.
                continue

    def _remove_signal_handlers(self) -> None:
        """Restore any signal handlers we replaced."""
        for signum, previous in list(self._signal_handlers.items()):
            try:
                if signal.getsignal(signum) is self._handle_signal:
                    signal.signal(signum, cast("signal.Handlers", previous))
            except ValueError, OSError, RuntimeError:
                continue
        self._signal_handlers.clear()

    def _handle_signal(self, signum: int, frame: object | None) -> None:
        """Bridge process shutdown signals into the async shutdown path."""
        logger.debug("Received shutdown signal: %s", signum)
        self._shutdown_event.set()
        if self._stop_event is not None:
            self._stop_event.set()

        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._request_shutdown)

        previous = self._signal_handlers.get(signum)
        if callable(previous) and previous is not signal.default_int_handler:
            handler = cast("Callable[[int, object | None], object]", previous)
            handler(signum, frame)

    def _request_shutdown(self) -> None:
        """Schedule a best-effort async shutdown."""
        if self._watch_task is None:
            return

        if self._shutdown_task is not None and not self._shutdown_task.done():
            return

        self._shutdown_task = asyncio.create_task(self.stop())

    async def _watch_all_directories(self) -> None:
        """Watch all directories for changes."""
        async with anyio.create_task_group() as tg:
            for watch_dir in self.watch_dirs:
                tg.start_soon(self._watch_directory, watch_dir)

    async def add_client(self, queue: asyncio.Queue[dict]) -> None:
        """Add an SSE client queue to notify.

        Args:
            queue: Asyncio queue to add.

        """
        self.clients.add(queue)

    async def remove_client(self, queue: asyncio.Queue[dict]) -> None:
        """Remove an SSE client queue.

        Args:
            queue: Asyncio queue to remove.

        """
        self.clients.discard(queue)

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
                    # Notify all clients
                    await self._notify_all("reload", changes)

                # Wait before next scan
                await anyio.sleep(self.poll_interval)

            except OSError as e:
                # Log error but continue watching
                logger.warning("Watch error: %s", e)
                await anyio.sleep(self.poll_interval)

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
            change_type: Type of change.
            changes: List of changed file paths.

        """
        message = {
            "type": change_type,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "files": [str(f) for f in changes],
        }

        # Send to all clients via their queues
        disconnected: set[asyncio.Queue[dict]] = set()
        for queue in self.clients:
            try:
                # Try to put message without blocking
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, mark as disconnected
                disconnected.add(queue)
            except RuntimeError, OSError:
                # Queue is closed or other error, mark as disconnected
                disconnected.add(queue)

        # Remove disconnected clients
        for queue in disconnected:
            self.clients.discard(queue)
