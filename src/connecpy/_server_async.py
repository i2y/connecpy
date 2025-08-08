import base64
from abc import ABC, abstractmethod
from asyncio import CancelledError, sleep
from http import HTTPStatus
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Iterable,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
)
from urllib.parse import parse_qs

from . import _compression, _server_shared
from ._codec import Codec, get_codec
from ._envelope import EnvelopeReader, EnvelopeWriter
from ._protocol import (
    CONNECT_STREAMING_CONTENT_TYPE_PREFIX,
    CONNECT_STREAMING_HEADER_COMPRESSION,
    CONNECT_UNARY_CONTENT_TYPE_PREFIX,
    CONNECTS_STREAMING_HEADER_ACCEPT_COMPRESSION,
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


_REQ = TypeVar("_REQ")
_RES = TypeVar("_RES")


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
        read_max_bytes: int | None = None,
    ):
        """Initialize the ASGI application."""
        super().__init__()
        self._endpoints = endpoints
        self._interceptors = interceptors
        self._read_max_bytes = read_max_bytes

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
            ctx = ServiceContext(headers)

            if isinstance(endpoint, _server_shared.EndpointUnary):
                await self._handle_unary(
                    scope,
                    http_method,
                    headers,
                    endpoint,
                    receive,
                    send,
                    ctx,
                )
                return
        except Exception as e:
            await self._handle_error(e, ctx, scope, receive, send)

        # Streams have their own error handling so move out of the try block.
        await self._handle_stream(
            headers,
            endpoint,
            receive,
            send,
            ctx,
        )

    async def _handle_unary(
        self,
        scope: HTTPScope,
        http_method: str,
        headers: Headers,
        endpoint: _server_shared.EndpointUnary[_REQ, _RES],
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
        ctx: _server_shared.ServiceContext,
    ):
        accept_encoding = headers.get("accept-encoding", "")
        selected_encoding = _compression.select_encoding(accept_encoding)

        if http_method == "GET":
            request, codec = await self._handle_get_request(endpoint, scope, ctx)
        else:
            request, codec = await self._handle_post_request(
                endpoint, scope, receive, ctx, headers
            )

        proc = endpoint.make_async_proc(self._interceptors)
        response_data = await proc(request, ctx)

        res_bytes = codec.encode(response_data)
        response_headers: dict[str, str] = {
            "content-type": f"{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{codec.name()}"
        }

        # Compress response if needed
        if selected_encoding != "identity":
            compressor = _compression.get_compression(selected_encoding)
            if compressor:
                res_bytes = compressor.compress(res_bytes)
                response_headers["content-encoding"] = selected_encoding
                response_headers["vary"] = "Accept-Encoding"

        final_headers: list[tuple[bytes, bytes]] = []
        for key, value in response_headers.items():
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

    async def _handle_get_request(
        self,
        endpoint: _server_shared.Endpoint[_REQ, _RES],
        scope: HTTPScope,
        ctx: _server_shared.ServiceContext,
    ) -> tuple[_REQ, Codec]:
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

        codec_name = codec_name_from_content_type(
            headers.get("content-type", ""), False
        )
        codec = get_codec(codec_name)
        if not codec:
            raise HTTPException(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                [("Accept-Post", "application/json, application/proto")],
            )

        # Get request body and endpoint
        chunks: list[bytes] = []
        async for chunk in _read_body(receive):
            chunks.append(chunk)
        req_body = b"".join(chunks)

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

        if self._read_max_bytes is not None and len(req_body) > self._read_max_bytes:
            raise ConnecpyException(
                Code.RESOURCE_EXHAUSTED,
                f"message is larger than configured max {self._read_max_bytes}",
            )

        return codec.decode(req_body, endpoint.input()), codec

    async def _handle_stream(
        self,
        headers: Headers,
        endpoint: _server_shared.Endpoint[_REQ, _RES],
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
        ctx: _server_shared.ServiceContext,
    ):
        error: Exception | None = None
        sent_headers = False
        try:
            accept_compression = headers.get(
                CONNECTS_STREAMING_HEADER_ACCEPT_COMPRESSION, ""
            )
            response_compression_name = _compression.select_encoding(accept_compression)
            response_compression = _compression.get_compression(
                response_compression_name
            )

            codec_name = codec_name_from_content_type(
                headers.get("content-type", ""), True
            )
            codec = get_codec(codec_name)
            if not codec:
                raise HTTPException(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    [
                        (
                            "Accept-Post",
                            "application/connect+json, application/connect+proto",
                        )
                    ],
                )
            req_compression_name = headers.get(
                CONNECT_STREAMING_HEADER_COMPRESSION, "identity"
            )
            req_compression = (
                _compression.get_compression(req_compression_name)
                or _compression.IdentityCompression()
            )
            request_stream = _request_stream(
                receive,
                endpoint.input,
                codec,
                req_compression,
                self._read_max_bytes,
            )

            writer = EnvelopeWriter(codec, response_compression)

            if isinstance(endpoint, _server_shared.EndpointResponseStream):
                request = await _consume_single_request(request_stream)
            else:
                request = request_stream
            proc = endpoint.make_async_proc(self._interceptors)
            response = await proc(request, ctx)  # type:ignore # TODO
            if isinstance(endpoint, _server_shared.EndpointRequestStream):

                async def yield_single_response(response: _RES) -> AsyncIterator[_RES]:
                    yield response

                response_stream = yield_single_response(response)
            else:
                response_stream = response

            async for message in response_stream:  # type:ignore # TODO
                # Don't send headers until the first message to allow logic a chance to add
                # response headers.
                if not sent_headers:
                    await _send_stream_response_headers(
                        send, codec, response_compression_name, ctx
                    )
                    sent_headers = True

                body = writer.write(message)
                await send(
                    {
                        "type": "http.response.body",
                        "body": body,
                        "more_body": True,
                    }
                )
        except CancelledError as e:
            raise ConnecpyException(Code.CANCELED, "Request was cancelled") from e
        except Exception as e:
            error = e
        finally:
            if not sent_headers:
                # Exception before any response message is returned
                await _send_stream_response_headers(
                    send, codec, response_compression_name, ctx
                )
            await send(
                {
                    "type": "http.response.body",
                    "body": writer.end(
                        ctx.response_trailers(),
                        ConnectWireError.from_exception(error) if error else None,
                    ),
                    "more_body": False,
                }
            )

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


async def _send_stream_response_headers(
    send: ASGISendCallable,
    codec: Codec,
    compression_name: str,
    ctx: ServiceContext,
):
    response_headers = [
        (
            b"content-type",
            f"{CONNECT_STREAMING_CONTENT_TYPE_PREFIX}{codec.name()}".encode(),
        ),
        (
            CONNECT_STREAMING_HEADER_COMPRESSION.encode(),
            compression_name.encode(),
        ),
    ]
    response_headers.extend(
        (key.encode(), value.encode())
        for key, value in ctx.response_headers().allitems()
    )
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": response_headers,
            "trailers": False,
        }
    )


async def _request_stream(
    receive: ASGIReceiveCallable,
    request_class: type[_REQ],
    codec: Codec,
    compression: _compression.Compression,
    read_max_bytes: int | None = None,
) -> AsyncIterator[_REQ]:
    reader = EnvelopeReader(request_class, codec, compression, read_max_bytes)
    try:
        async for chunk in _read_body(receive):
            for message in reader.feed(chunk):
                yield message
                # Check for cancellation each message. While this seems heavyweight,
                # conformance tests require it.
                await sleep(0)
    except CancelledError as e:
        raise ConnecpyException(Code.CANCELED, "Request was cancelled") from e


async def _read_body(receive: ASGIReceiveCallable) -> AsyncIterator[bytes]:
    """Read the body of the request."""
    while True:
        message = await receive()
        match message["type"]:
            case "http.request":
                body = message.get("body", b"")
                yield body
                if not message.get("more_body", False):
                    return
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


async def _consume_single_request(stream: AsyncIterator[_REQ]) -> _REQ:
    req = None
    async for message in stream:
        if req is not None:
            raise ConnecpyException(
                Code.UNIMPLEMENTED, "unary request has multiple messages"
            )
        req = message
    if req is None:
        raise ConnecpyException(Code.UNIMPLEMENTED, "unary request has zero messages")
    return req


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
