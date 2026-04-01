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
        from acme.ui.hot_reload import HotReloadMiddleware

        app = Starlette()
        app.add_middleware(
            HotReloadMiddleware,
            ws_path="/__hot_reload_ws",
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        ws_path: str = "/__hot_reload_ws",
        *,
        inject_before_body: bool = True,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application.
            ws_path: Path to the WebSocket endpoint for hot reload.
            inject_before_body: Whether to inject before </body>
                or at end of response.

        """
        super().__init__(app)
        self.ws_path = ws_path
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

        # Build the WebSocket URL
        ws_scheme = "wss" if request.url.scheme == "https" else "ws"
        ws_url = f"{ws_scheme}://{request.url.netloc}{self.ws_path}"

        # Generate the client script
        script = self._get_client_script(ws_url)

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
        return HTMLResponse(
            content=content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )

    def _get_client_script(self, ws_url: str) -> str:
        """Generate the client-side hot reload script."""
        return f"""<script>
(function() {{
    const wsUrl = "{ws_url}";
    let ws = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    const reconnectDelay = 1000;

    function connect() {{
        ws = new WebSocket(wsUrl);

        ws.onopen = function() {{
            console.log("[Hot Reload] Connected");
            reconnectAttempts = 0;
        }};

        ws.onmessage = function(event) {{
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

        ws.onclose = function() {{
            console.log("[Hot Reload] Disconnected");
            attemptReconnect();
        }};

        ws.onerror = function(error) {{
            console.error("[Hot Reload] WebSocket error:", error);
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
