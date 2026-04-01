"""Hot reload middleware for automatic script injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp


class HotReloadMiddleware(BaseHTTPMiddleware):
    """Middleware that injects hot reload script into HTML responses.

    Automatically detects HTML responses and injects the client-side
    hot reload script before the closing </body> tag.

    Usage:
        from starlette.applications import Starlette
        from starlette_hot_reload import HotReloadMiddleware

        app = Starlette()
        app.add_middleware(
            HotReloadMiddleware,
            events_path="/__starlette_hot_reload",
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        events_path: str = "/__starlette_hot_reload",
        *,
        inject_before_body: bool = True,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application.
            events_path: Path to the Server-Sent Events endpoint for hot reload.
            inject_before_body: Whether to inject before </body>
                or at end of response.

        """
        super().__init__(app)
        self.events_path = events_path
        self.inject_before_body = inject_before_body

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and inject script if response is HTML."""
        response = await call_next(request)

        # Only inject in debug mode
        if not getattr(request.app, "debug", False):
            return response

        # Only process HTML responses
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return response

        # Build the SSE URL
        events_url = f"{request.url.scheme}://{request.url.netloc}{self.events_path}"

        # Generate the client script
        script = self._get_client_script(events_url)

        # Modify the response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        content = body.decode("utf-8")

        # Inject the script
        if self.inject_before_body and "</body>" in content:
            content = content.replace("</body>", f"{script}</body>")
        else:
            content = content + script

        # Return new response with modified content
        new_headers = dict(response.headers)
        new_headers.pop("content-length", None)
        return HTMLResponse(
            content=content,
            status_code=response.status_code,
            headers=new_headers,
        )

    def _get_client_script(self, events_url: str) -> str:
        """Generate the client-side hot reload script."""
        return f"""<script>
(function() {{
    const eventsUrl = "{events_url}";
    let eventSource = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    const reconnectDelay = 1000;

    function connect() {{
        eventSource = new EventSource(eventsUrl);

        eventSource.onopen = function() {{
            console.log("[Hot Reload] Connected");
            reconnectAttempts = 0;
        }};

        eventSource.onmessage = function(event) {{
            const data = JSON.parse(event.data);
            console.log("[Hot Reload]", data);

            if (data.type === "reload") {{
                console.log("[Hot Reload] Reloading page...");
                window.location.reload();
            }} else if (data.type === "css") {{
                console.log("[Hot Reload] CSS changed");
                refreshCSS();
            }}
        }};

        eventSource.onerror = function(error) {{
            console.error("[Hot Reload] SSE error:", error);
            eventSource.close();
            attemptReconnect();
        }};
    }}

    function attemptReconnect() {{
        if (reconnectAttempts < maxReconnectAttempts) {{
            reconnectAttempts++;
            console.log(
                "[Hot Reload] Reconnecting... " +
                "(attempt " + reconnectAttempts + ")"
            );
            setTimeout(connect, reconnectDelay * reconnectAttempts);
        }} else {{
            console.log("[Hot Reload] Max reconnect attempts reached");
        }}
    }}

    function refreshCSS() {{
        const links = document.querySelectorAll(
            'link[rel="stylesheet"]'
        );
        links.forEach(link => {{
            const href = link.href;
            const url = new URL(href);
            url.searchParams.set("_hot_reload", Date.now().toString());
            link.href = url.toString();
        }});
    }}

    connect();
}})();
</script>"""
