# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-04-08

### Added

- Expanded the project metadata published in `pyproject.toml`, including
  maintainers, project URLs, and classifier details.
- Refreshed the README with clearer installation, usage, limits, and example
  documentation.

### Changed

- Reduced watcher shutdown logging to a single debug log entry.

### Removed

- The CSS-only stylesheet refresh path. All watched file changes now trigger a
  full page reload.

## [0.2.1] - 2026-04-06

### Added

- Default watcher support for `.jinja` template files.

## [0.2.0] - 2026-04-04

### Added

- `examples/with_tailwind` showing hot reload composed with Tailwind CSS via
  Starlette lifespan.

### Changed

- Switched to an explicit lifespan-based `hot_reload(...)` API to match
  Starlette's application model.
- Updated examples and documentation to compose hot reload inside the app
  lifespan, including `AsyncExitStack` for multiple resources.

### Removed

- `HotReload.setup()` public API.

## [0.1.0] - 2026-04-04

### Added

- Initial release of `starlette-hot-reload`.
- `HotReload.setup()` integration that only activates when `debug=True`.
- Automatic HTML script injection through ASGI middleware.
- Server-Sent Events based live reload support without WebSocket dependencies.
- Smart reload behavior that refreshes CSS in place and reloads the page for
  other file changes.
- Automatic reconnect logic in the browser client with exponential backoff.
- Configurable watched directories, SSE endpoint path, and filesystem polling
  interval.
- Type-annotated package layout with a minimal dependency footprint beyond
  Starlette.

[Unreleased]: https://github.com/pyk/starlette-hot-reload/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/pyk/starlette-hot-reload/releases/tag/v0.3.0
[0.2.1]: https://github.com/pyk/starlette-hot-reload/releases/tag/v0.2.1
[0.2.0]: https://github.com/pyk/starlette-hot-reload/releases/tag/v0.2.0
[0.1.0]: https://github.com/pyk/starlette-hot-reload/releases/tag/v0.1.0
