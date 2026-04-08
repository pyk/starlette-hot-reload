"""Tests for the file watcher."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from starlette_hot_reload.watcher import FileWatcher


def test_default_extensions_include_jinja(tmp_path: Path) -> None:
    """Default file watching should include Jinja templates."""
    watcher = FileWatcher(watch_dirs=[str(tmp_path)])
    if ".jinja" not in watcher.extensions:
        msg = "expected .jinja in default extensions"
        raise AssertionError(msg)

    template = tmp_path / "templates" / "index.jinja"
    template.parent.mkdir()
    template.write_text("hello", encoding="utf-8")

    file_mtimes: dict[Path, float] = {}
    if watcher._scan_changes(tmp_path, file_mtimes) != []:  # noqa: SLF001
        msg = "expected initial scan to record no changes"
        raise AssertionError(msg)

    old_mtime = file_mtimes[template]
    os.utime(template, (old_mtime + 1, old_mtime + 1))
    if watcher._scan_changes(tmp_path, file_mtimes) != [template]:  # noqa: SLF001
        msg = "expected changed .jinja file to be detected"
        raise AssertionError(msg)


@pytest.mark.asyncio
async def test_css_changes_trigger_full_reload() -> None:
    """CSS changes should use the same reload event as other files."""
    watcher = FileWatcher()
    queue: asyncio.Queue[dict] = asyncio.Queue()

    await watcher.add_client(queue)
    await watcher._notify_all("reload", [Path("styles.css")])  # noqa: SLF001

    message = await queue.get()
    assert message["type"] == "reload"
    assert message["files"] == ["styles.css"]
