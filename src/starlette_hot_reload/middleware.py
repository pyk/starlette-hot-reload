"""Hot reload middleware for automatic script injection."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send


_EVENTS_URL_PLACEHOLDER = "__STARLETTE_HOT_RELOAD_EVENTS_URL__"


@lru_cache(maxsize=1)
def _load_client_script() -> str:
    """Load the client-side script from the package resources."""
    return (
        files("starlette_hot_reload")
        .joinpath("client.js")
        .read_text(
            encoding="utf-8",
        )
    )


class HotReloadMiddleware:
    """ASGI middleware that injects the hot reload script into HTML responses.

    This is implemented as a plain ASGI wrapper instead of BaseHTTPMiddleware.
    That avoids the extra task-group machinery that can interfere with streaming
    responses and shutdown behavior.
    """

    def __init__(
        self,
        app: ASGIApp,
        events_path: str = "/__starlette_hot_reload",
        *,
        inject_before_body: bool = True,
    ) -> None:
        """Initialize the middleware."""
        self.app = app
        self.events_path = events_path
        self.inject_before_body = inject_before_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Dispatch HTTP requests through the injection path."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await self._handle_http(scope, receive, send)

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        response_start: Message | None = None
        body_chunks: list[bytes] = []
        is_html_response = False
        sent_start = False

        async def wrapped_send(message: Message) -> None:
            nonlocal response_start, body_chunks, is_html_response, sent_start

            if message["type"] == "http.response.start":
                response_start = message
                headers = self._headers_from_message(message)
                content_type = headers.get("content-type", "")
                is_html_response = "text/html" in content_type

                if not is_html_response:
                    sent_start = True
                    await send(message)
                return

            if message["type"] != "http.response.body":
                await send(message)
                return

            if not is_html_response:
                await send(message)
                return

            body_chunks.append(message.get("body", b""))
            if message.get("more_body", False):
                return

            if response_start is None:
                return
            content = b"".join(body_chunks)
            modified_body = self._maybe_inject_script(scope, content)

            start_message = self._rewrite_start_message(
                response_start,
                len(modified_body),
            )
            if not sent_start:
                await send(start_message)
            await send(
                {
                    "type": "http.response.body",
                    "body": modified_body,
                    "more_body": False,
                }
            )

        await self.app(scope, receive, wrapped_send)

    def _maybe_inject_script(self, scope: Scope, body: bytes) -> bytes:
        """Inject the client-side script into HTML bodies when possible."""
        try:
            content = body.decode("utf-8")
        except UnicodeDecodeError:
            return body

        events_url = self._build_events_url(scope)
        script = self._get_client_script(events_url)

        if self.inject_before_body and "</body>" in content:
            content = content.replace("</body>", f"{script}</body>")
        else:
            content = content + script

        return content.encode("utf-8")

    def _build_events_url(self, scope: Scope) -> str:
        """Build the absolute SSE URL for the current request."""
        scheme = scope.get("scheme", "http")
        headers = self._headers_from_scope(scope)
        host = headers.get("host")

        if host:
            return f"{scheme}://{host}{self.events_path}"

        server = scope.get("server")
        if isinstance(server, tuple):
            try:
                host_name, port = server
            except ValueError:
                pass
            else:
                if port is not None:
                    return f"{scheme}://{host_name}:{port}{self.events_path}"
                return f"{scheme}://{host_name}{self.events_path}"

        return f"{scheme}://localhost{self.events_path}"

    def _headers_from_message(self, message: Message) -> dict[str, str]:
        """Convert ASGI raw headers into a lowercase header mapping."""
        raw_headers = message.get("headers", [])
        return {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in raw_headers
        }

    def _headers_from_scope(self, scope: Scope) -> dict[str, str]:
        """Convert ASGI request headers into a lowercase header mapping."""
        raw_headers = scope.get("headers", [])
        return {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in raw_headers
        }

    def _rewrite_start_message(self, message: Message, body_length: int) -> Message:
        """Rewrite response headers after HTML injection."""
        headers = [
            (key, value)
            for key, value in message.get("headers", [])
            if key.lower() != b"content-length"
        ]
        headers.append((b"content-length", str(body_length).encode("latin-1")))

        return {
            **message,
            "headers": headers,
        }

    def _get_client_script(self, events_url: str) -> str:
        """Generate the client-side hot reload script."""
        script = _load_client_script().replace(
            _EVENTS_URL_PLACEHOLDER,
            events_url,
        )
        return f"<script>\n{script}\n</script>"
