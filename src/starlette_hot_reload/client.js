(function() {
    const eventsUrl = "__STARLETTE_HOT_RELOAD_EVENTS_URL__";
    let eventSource = null;
    let reconnectAttempts = 0;
    let shuttingDown = false;
    const maxReconnectAttempts = 10;
    const reconnectDelay = 1000;

    function connect() {
        eventSource = new EventSource(eventsUrl);

        eventSource.onopen = function() {
            console.log("[Hot Reload] Connected");
            reconnectAttempts = 0;
        };

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log("[Hot Reload]", data);

            if (data.type === "shutdown") {
                shuttingDown = true;
                eventSource.close();
                return;
            }

            if (data.type === "reload") {
                console.log("[Hot Reload] Reloading page...");
                window.location.reload();
            } else if (data.type === "css") {
                console.log("[Hot Reload] CSS changed");
                refreshCSS();
            }
        };

        eventSource.onerror = function(error) {
            console.error("[Hot Reload] SSE error:", error);
            if (shuttingDown) {
                return;
            }
            eventSource.close();
            attemptReconnect();
        };
    }

    function attemptReconnect() {
        if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            console.log(
                "[Hot Reload] Reconnecting... " +
                "(attempt " + reconnectAttempts + ")"
            );
            setTimeout(connect, reconnectDelay * reconnectAttempts);
        } else {
            console.log("[Hot Reload] Max reconnect attempts reached");
        }
    }

    function refreshCSS() {
        const links = document.querySelectorAll(
            'link[rel="stylesheet"]'
        );
        links.forEach(link => {
            const href = link.href;
            const url = new URL(href);
            url.searchParams.set("_hot_reload", Date.now().toString());
            link.href = url.toString();
        });
    }

    connect();
})();
