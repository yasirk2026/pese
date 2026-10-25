"""Desktop-only ASGI boundary; static assets never contain the launch secret."""
import hmac


class DesktopBoundary:
    def __init__(self, app, token: str, origin: str, is_stopping=None):
        self.app, self.token, self.origin = app, token, origin
        self.is_stopping = is_stopping or (lambda: False)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin1")
        origin = headers.get(b"origin", b"").decode("latin1")
        allowed_host = self.origin.split("://", 1)[1]
        private = scope["path"].startswith(("/api/", "/desktop/")) or scope["path"] == "/health"
        supplied = headers.get(b"x-pese-token", b"").decode("latin1")
        status = 0
        if host != allowed_host or (origin and origin != self.origin):
            status = 403
        elif private and not hmac.compare_digest(supplied, self.token):
            status = 401
        elif scope["path"].startswith("/api/") and self.is_stopping():
            status = 503
        if status:
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": b'{"detail":"Private PESE desktop endpoint"}'})
            return

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cross-origin-resource-policy", b"same-origin"),
                    (b"content-security-policy", (
                        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                        "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                        "font-src 'self' data:; connect-src 'self'; frame-src 'none'; "
                        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
                    ).encode()),
                ]
                if private:
                    message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        await self.app(scope, receive, secured_send)
