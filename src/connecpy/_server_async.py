import base64
from abc import ABC, abstractmethod
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional, Tuple
from urllib.parse import parse_qs

from . import _compression, _server_shared
from ._codec import Codec, get_codec
from ._protocol import (
    CONNECT_UNARY_CONTENT_TYPE_PREFIX,
    ConnectWireError,
    HTTPException,
    codec_name_from_content_type,
)
from ._server_shared import ServiceContext
from .code import Code
from .exceptions import ConnecpyException
from .headers import Headers

if TYPE_CHECKING:
    # We don't use asgiref code so only import from it for type checking
    from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, HTTPScope, Scope
else:
    ASGIReceiveCallable = "asgiref.typing.ASGIReceiveCallable"
    ASGISendCallable = "asgiref.typing.ASGISendCallable"
    HTTPScope = "asgiref.typing.HTTPScope"
    Scope = "asgiref.typing.Scope"


class ConnecpyASGIApplication(ABC):
    """ASGI application for Connecpy."""

    @property
    @abstractmethod
    def path(self) -> str:
        raise NotImplementedError()

    def __init__(
        self,
        *,
        endpoints: Mapping[str, _server_shared.Endpoint],
        interceptors: Iterable[_server_shared.ServerInterceptor] = (),
        max_receive_message_length=1024 * 100 * 100,
    ):
        """Initialize the ASGI application."""
        super().__init__()
        self._endpoints = endpoints
        self._interceptors = interceptors
        self._max_receive_message_length = max_receive_message_length

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        """
        Handle incoming ASGI requests.

        Args:
            scope (dict): The ASGI scope.
            receive (callable): The ASGI receive function.
            send (callable): The ASGI send function.
        """
        assert scope["type"] == "http"

        ctx: Optional[ServiceContext] = None
        try:
            http_method = scope["method"]

            path = scope["path"]
            endpoint = self._endpoints.get(path)
            if not endpoint and scope["root_path"]:
                # The application was mounted at some root so try stripping the prefix.
                path = path.removeprefix(scope["root_path"])
                endpoint = self._endpoints.get(path)

            if not endpoint:
                raise HTTPException(HTTPStatus.NOT_FOUND, [])

            if http_method not in endpoint.allowed_methods:
                raise HTTPException(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    [("allow", ", ".join(endpoint.allowed_methods))],
                )

            headers = _process_headers(scope.get("headers", ()))
            accept_encoding = headers.get("accept-encoding", "")
            selected_encoding = _compression.select_encoding(accept_encoding)

            ctx = ServiceContext(headers)

            if http_method == "GET":
                request, codec = await self._handle_get_request(endpoint, scope, ctx)
            else:
                request, codec = await self._handle_post_request(
                    endpoint, scope, receive, ctx, headers
                )

            proc = endpoint.make_async_proc(self._interceptors)
            response_data = await proc(request, ctx)

            res_bytes = codec.encode(response_data)
            headers = {
                "content-type": [f"{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{codec.name()}"]
            }

            # Compress response if needed
            if selected_encoding != "identity":
                compressor = _compression.get_compression(selected_encoding)
                if compressor:
                    res_bytes = compressor.compress(res_bytes)
                    headers["content-encoding"] = [selected_encoding]
                    headers["vary"] = ["Accept-Encoding"]

            final_headers: list[tuple[bytes, bytes]] = []
            for key, values in headers.items():
                for value in values:
                    final_headers.append((key.lower().encode(), value.encode()))
            _add_context_headers(final_headers, ctx)

            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": final_headers,
                    "trailers": False,
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": res_bytes,
                    "more_body": False,
                }
            )

        except Exception as e:
            await self._handle_error(e, ctx, scope, receive, send)

    async def _handle_get_request(
        self,
        endpoint: _server_shared.Endpoint,
        scope: HTTPScope,
        ctx: _server_shared.ServiceContext,
    ) -> tuple[Any, Codec]:
        """Handle GET request with query parameters."""
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)

        # Validation
        if "message" not in params:
            raise ConnecpyException(
                Code.INVALID_ARGUMENT,
                "'message' parameter is required for GET requests",
            )

        # Get and decode message
        message = params["message"][0]
        is_base64 = "base64" in params and params["base64"][0] == "1"

        if is_base64:
            try:
                message = base64.urlsafe_b64decode(message + "===")
            except Exception:
                raise ConnecpyException(
                    Code.INVALID_ARGUMENT, "Invalid base64 encoding"
                )
        else:
            message = message.encode("utf-8")

        # Handle encoding
        codec_name = params.get("encoding", ("",))[0]
        codec = get_codec(codec_name)
        if not codec:
            raise ConnecpyException(
                Code.UNIMPLEMENTED, f"invalid message encoding: '{codec_name}'"
            )

        # Handle compression
        compression_name = params.get("compression", ["identity"])[0]
        compression = _compression.get_compression(compression_name)
        if not compression:
            raise ConnecpyException(
                Code.UNIMPLEMENTED,
                f"unknown compression: '{compression_name}': supported encodings are {', '.join(_compression.get_available_compressions())}",
            )

        # Decompress and decode message
        if message:  # Don't decompress empty messages
            message = compression.decompress(message)

        # Get the appropriate decoder for the endpoint
        return codec.decode(message, endpoint.input()), codec

    async def _handle_post_request(
        self,
        endpoint: _server_shared.Endpoint,
        scope: HTTPScope,
        receive,
        ctx: _server_shared.ServiceContext,
        headers: Headers,
    ) -> tuple[Any, Codec]:
        """Handle POST request with body."""

        codec_name = codec_name_from_content_type(headers.get("content-type", ""))
        codec = get_codec(codec_name)
        if not codec:
            raise HTTPException(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                [("Accept-Post", "application/json, application/proto")],
            )

        # Get request body and endpoint
        req_body = await self._read_body(receive)

        if len(req_body) > self._max_receive_message_length:
            raise ConnecpyException(
                Code.INVALID_ARGUMENT,
                f"Request body exceeds maximum size of {self._max_receive_message_length} bytes",
            )

        # Handle compression if specified
        compression_name = (
            dict(scope["headers"])
            .get(b"content-encoding", b"identity")
            .decode("ascii")
            .lower()
        )
        compression = _compression.get_compression(compression_name)
        if not compression:
            raise ConnecpyException(
                Code.UNIMPLEMENTED,
                f"unknown compression: '{compression_name}': supported encodings are {', '.join(_compression.get_available_compressions())}",
            )

        if req_body:  # Don't decompress empty body
            req_body = compression.decompress(req_body)

        return codec.decode(req_body, endpoint.input()), codec

    async def _read_body(self, receive: ASGIReceiveCallable) -> bytes:
        """Read the body of the request."""
        chunks = []
        while True:
            message = await receive()
            match message["type"]:
                case "http.request":
                    chunks.append(message.get("body", b""))
                    if not message.get("more_body", False):
                        break
                case "http.disconnect":
                    raise ConnecpyException(
                        Code.CANCELED,
                        "Client disconnected before request completion",
                    )
                case _:
                    raise ConnecpyException(
                        Code.UNKNOWN,
                        "Unexpected message type",
                    )
        return b"".join(chunks)

    async def _handle_error(
        self,
        exc,
        ctx: Optional[ServiceContext],
        scope: HTTPScope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
    ) -> None:
        """Handle errors that occur during request processing."""
        headers: list[tuple[bytes, bytes]]
        body: bytes
        status: int
        if isinstance(exc, HTTPException):
            status = exc.status.value
            headers = [(k.encode("utf-8"), v.encode("utf-8")) for k, v in exc.headers]
            body = b""
        else:
            wire_error = ConnectWireError.from_exception(exc)
            status = wire_error.to_http_status().code
            headers = [
                (b"content-type", b"application/json"),
            ]
            body = wire_error.to_json_bytes()

        if ctx:
            _add_context_headers(headers, ctx)

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
                "trailers": False,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            }
        )


def _process_headers(
    iterable: Iterable[Tuple[bytes, bytes]],
) -> Headers:
    result = Headers()
    for key, value in iterable:
        result.add(key.decode(), value.decode())
    return result


def _add_context_headers(
    headers: list[tuple[bytes, bytes]], ctx: ServiceContext
) -> None:
    headers.extend(
        (key.encode(), value.encode())
        for key, value in ctx.response_headers().allitems()
    )
    headers.extend(
        (f"trailer-{key}".encode(), value.encode())
        for key, value in ctx.response_trailers().allitems()
    )
