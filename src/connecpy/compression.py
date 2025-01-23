from collections.abc import Callable

from starlette.middleware.gzip import GZipMiddleware
from brotli_asgi import BrotliMiddleware
from zstd_asgi import ZstdMiddleware


def extract_header_value(headers: list[tuple[bytes, bytes]], name: bytes) -> bytes:
    name_lower = name.lower()
    for key, value in headers:
        if key.lower() == name_lower:
            return value
    return b""


def middleware(app, middleware_map):
    middleware_map["identity"] = app

    async def encoding_middleware(scope, receive, send):
        if scope["type"] != "http":
            # Pass through for non-HTTP scopes (e.g. websocket)
            await app(scope, receive, send)
            return

        # Pull Accept-Encoding from list-based headers via helper function
        raw_headers = scope.get("headers", [])
        accept_encoding = extract_header_value(raw_headers, b"accept-encoding")
        print(raw_headers)

        encodings = parse_accept_encoding(accept_encoding)

        if not encodings:
            await app(scope, receive, send)
            return

        for encoding in encodings:
            m = middleware_map.get(encoding)
            if m:
                await m(scope, receive, send)
                return

        # If the client uses an unsupported Content-Encoding,
        # servers should return an error with code "unimplemented" and a message listing the supported encodings.
        raise NotImplementedError(
            f"Unsupported Content-Encoding: {encodings}. Supported encodings: {list(middleware_map.keys())}"
        )

    return encoding_middleware


def parse_accept_encoding(accept_encoding) -> list[str]:
    encodings: list[str] = []
    for encoding in accept_encoding.split(b","):
        encoding = encoding.strip()
        if encoding:
            encodings.append(encoding.decode("ascii"))
    return encodings


class GenericEncodingMiddleware:
    """
    EncodingMiddleware handles encoding transformations for the application.
    Args:
        app: The main application instance.
        middleware_map (dict[str, Callable]): A dictionary mapping middleware identifiers to their corresponding callable implementations.
    Methods:
        __call__(scope, receive, send):
            Processes the incoming request by applying the appropriate middleware transformations.
    """

    def __init__(self, app, middleware_map: dict[str, Callable]):
        self.app = app
        self.middleware_map = middleware_map

    async def __call__(self, scope, receive, send):
        middleware_instance = middleware(self.app, self.middleware_map)
        await middleware_instance(scope, receive, send)


class CompressionMiddleware:
    """
    Middleware for handling content encoding (compression) in ConnectRPC applications.
    Args:
        app: The next application in the middleware chain.
        middleware_map (dict[str, Callable], optional): A mapping of encoding types to their respective middleware classes.
            Defaults to {
            }.
    Attributes:
        app: The next application in the middleware chain.
        middleware_map (dict[str, Callable]): A mapping of encoding types to their respective middleware classes.
    """

    def __init__(
        self,
        app,
        middleware_map: dict[str, Callable] | None = None,
    ):
        if middleware_map is None:
            middleware_map = {
                "gzip": GZipMiddleware(app, minimum_size=0),
                "br": BrotliMiddleware(app),
                "zstd": ZstdMiddleware(app),
            }
        self.app = app
        self.middleware_map = middleware_map

    async def __call__(self, scope, receive, send):
        middleware_instance = middleware(self.app, self.middleware_map)
        await middleware_instance(scope, receive, send)
