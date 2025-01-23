from dataclasses import field, dataclass


@dataclass
class CORSConfig:
    """
    Represents the configuration of the CORS policy.
    Attributes:
        allow_origin (str): The allowed origin. Defaults to "*".
        allow_methods (tuple[str, ...]): The allowed HTTP methods. Defaults to ("POST", "GET").
        allow_headers (tuple[str, ...]): The allowed HTTP headers. Defaults to (
            "Content-Type",
            "Connect-Protocol-Version",
            "Connect-Timeout-Ms",
            "X-User-Agent",
        ).
        access_control_max_age (int): The maximum age of the preflight request. Defaults to 86400.
    """

    allow_origin: str = field(default="*")
    allow_methods: tuple[str, ...] = field(default=("POST", "GET"))
    allow_headers: tuple[str, ...] = field(
        default=(
            "Content-Type",
            "Connect-Protocol-Version",
            "Connect-Timeout-Ms",
            "X-User-Agent",
        )
    )
    access_control_max_age: int = field(default=86400)


# ASGI Miidleware for ConnectRPC CORS
def middleware(app, config: CORSConfig):
    """
    Middleware for ConnectRPC CORS.
    Args:
        app (Callable): The ASGI application.
        config (CORSConfig): The CORS configuration.
    Returns:
        Callable: The ASGI application.
    """

    async def cors_middleware(scope, receive, send):
        if scope["type"] != "http":
            # Pass through for non-HTTP scopes (e.g. websocket)
            await app(scope, receive, send)
            return

        # Handle preflight requests
        if scope["method"] == "OPTIONS":
            headers = [
                (b"access-control-allow-origin", config.allow_origin.encode()),
                (
                    b"access-control-allow-methods",
                    b", ".join(m.encode() for m in config.allow_methods),
                ),
                (
                    b"access-control-allow-headers",
                    b", ".join(h.encode() for h in config.allow_headers),
                ),
                (
                    b"access-control-max-age",
                    str(config.access_control_max_age).encode(),
                ),
            ]

            await send(
                {
                    "type": "http.response.start",
                    "status": 204,
                    "headers": headers,
                }
            )

            await send(
                {
                    "type": "http.response.body",
                    "body": b"",
                }
            )

        # Handle normal requests with CORS headers
        if scope["method"] != "OPTIONS":

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    message["headers"].append(
                        (b"access-control-allow-origin", config.allow_origin.encode())
                    )

                await send(message)

            await app(scope, receive, send_wrapper)

    return cors_middleware


class CORSMiddleware:
    """
    Middleware for ConnectRPC CORS.
    Args:
        app (Callable): The ASGI application.
        config (CORSConfig): The CORS configuration.
    """

    def __init__(self, app, config: CORSConfig = CORSConfig()):
        self._app = app
        self._config = config

    async def __call__(self, scope, receive, send):
        return await middleware(self._app, self._config)(scope, receive, send)
