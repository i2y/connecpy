import base64
import functools
import sys
from abc import ABC, abstractmethod
from dataclasses import replace
from http import HTTPStatus
from io import BytesIO
from typing import Iterable, Iterator, Mapping, Optional, Sequence, TypeVar
from urllib.parse import parse_qs

from . import _compression, _server_shared
from ._codec import Codec, get_codec
from ._envelope import EnvelopeReader, EnvelopeWriter
from ._interceptor_sync import (
    BidiStreamInterceptorSync,
    ClientStreamInterceptorSync,
    InterceptorSync,
    MetadataInterceptorInvokerSync,
    MetadataInterceptorSync,
    ServerStreamInterceptorSync,
    UnaryInterceptorSync,
)
from ._protocol import (
    CONNECT_STREAMING_CONTENT_TYPE_PREFIX,
    CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION,
    CONNECT_STREAMING_HEADER_COMPRESSION,
    CONNECT_UNARY_CONTENT_TYPE_PREFIX,
    ConnectWireError,
    HTTPException,
    codec_name_from_content_type,
)
from .code import Code
from .exceptions import ConnecpyException
from .request import Headers, RequestContext

if sys.version_info >= (3, 11):
    from wsgiref.types import StartResponse, WSGIEnvironment
else:
    StartResponse = "wsgiref.types.StartResponse"
    WSGIEnvironment = "wsgiref.types.WSGIEnvironment"


_REQ = TypeVar("_REQ")
_RES = TypeVar("_RES")

_BODY_CHUNK_SIZE = 4096


def _normalize_wsgi_headers(environ: WSGIEnvironment) -> dict:
    """Extract and normalize HTTP headers from WSGI environment."""
    headers = {}
    if "CONTENT_TYPE" in environ:
        headers["content-type"] = environ["CONTENT_TYPE"].lower()
    if "CONTENT_LENGTH" in environ:
        headers["content-length"] = environ["CONTENT_LENGTH"].lower()

    for key, value in environ.items():
        if key.startswith("HTTP_"):
            header = key[5:].replace("_", "-")
            headers[header] = value
    return headers


def _process_headers(headers: dict) -> Headers:
    """Convert headers dictionary to connecpy format."""
    result = Headers()
    for key, value in headers.items():
        if isinstance(value, (list, tuple)):
            for v in value:
                result.add(key, v)
        else:
            result.add(key, str(value))
    return result


def extract_metadata_from_query_params(query_string: str) -> dict:
    """Extract metadata from query parameters into a dictionary."""
    return parse_qs(query_string) if query_string else {}


def validate_request_headers(headers: dict) -> tuple[str, str]:
    """Validate and normalize request headers.

    Args:
        headers: Dictionary of request headers

    Returns:
        tuple[str, str]: Normalized content type and content encoding
    """
    # Get content type
    content_type = headers.get("content-type", "application/json").lower()
    if content_type not in ["application/json", "application/proto"]:
        raise ConnecpyException(
            Code.INVALID_ARGUMENT, f"Unsupported Content-Type: {content_type}"
        )

    # Get content encoding
    content_encoding = headers.get("content-encoding", "identity").lower()
    if content_encoding not in ["identity", "gzip", "br", "zstd"]:
        raise ConnecpyException(
            Code.UNIMPLEMENTED, f"Unsupported Content-Encoding: {content_encoding}"
        )

    return content_type, content_encoding


def prepare_response_headers(
    base_headers: dict[str, list[str]],
    selected_encoding: str,
    compressed_size: Optional[int] = None,
) -> tuple[dict[str, list[str]], bool]:
    """Prepare response headers and determine if compression should be used.

    Args:
        base_headers: Base response headers
        selected_encoding: Selected compression encoding
        compressed_size: Size of compressed content (if compression was attempted)

    Returns:
        tuple[dict, bool]: Final headers and whether to use compression
    """
    headers = base_headers.copy()
    use_compression = False

    if "content-type" not in headers:
        headers["content-type"] = ["application/proto"]

    if selected_encoding != "identity" and compressed_size is not None:
        headers["content-encoding"] = [selected_encoding]
        use_compression = True

    headers["vary"] = ["Accept-Encoding"]
    return headers, use_compression


def _read_body(environ: WSGIEnvironment) -> Iterator[bytes]:
    input_stream: BytesIO = environ["wsgi.input"]
    while True:
        chunk = input_stream.read(_BODY_CHUNK_SIZE)
        if not chunk:
            return
        yield chunk


class ConnecpyWSGIApplication(ABC):
    """WSGI application for Connecpy."""

    @property
    @abstractmethod
    def path(self) -> str:
        raise NotImplementedError()

    def __init__(
        self,
        *,
        endpoints: Mapping[str, _server_shared.EndpointSync],
        interceptors: Iterable[InterceptorSync] = (),
        read_max_bytes: int | None = None,
    ):
        """Initialize the WSGI application."""
        super().__init__()
        if interceptors:
            interceptors = [
                MetadataInterceptorInvokerSync(interceptor)
                if isinstance(interceptor, MetadataInterceptorSync)
                else interceptor
                for interceptor in interceptors
            ]
            endpoints = {
                path: _apply_interceptors(endpoint, interceptors)
                for path, endpoint in endpoints.items()
            }
        self._endpoints = endpoints
        self._read_max_bytes = read_max_bytes

    def __call__(
        self, environ: WSGIEnvironment, start_response: StartResponse
    ) -> Iterable[bytes]:
        """Handle incoming WSGI requests."""
        ctx: Optional[RequestContext] = None
        try:
            path = environ["PATH_INFO"]
            if not path:
                path = "/"
            endpoint = self._endpoints.get(path)
            if not endpoint and environ["SCRIPT_NAME"] == self.path:
                # The application was mounted at the service's path so we reconstruct
                # the full URL.
                endpoint = self._endpoints.get(self.path + path)

            if not endpoint:
                raise HTTPException(HTTPStatus.NOT_FOUND, [])

            http_method = environ["REQUEST_METHOD"]
            headers = _process_headers(_normalize_wsgi_headers(environ))

            ctx = _server_shared.create_request_context(
                endpoint.method, http_method, headers
            )

            match endpoint:
                case _server_shared.EndpointUnarySync():
                    return self._handle_unary(
                        environ, start_response, http_method, endpoint, ctx, headers
                    )
                case (
                    _server_shared.EndpointClientStreamSync()
                    | _server_shared.EndpointServerStreamSync()
                    | _server_shared.EndpointBidiStreamSync()
                ):
                    return self._handle_stream(
                        environ, start_response, headers, endpoint, ctx
                    )
                case _:
                    raise ConnecpyException(Code.INTERNAL, "Unknown endpoint type")

        except Exception as e:
            return self._handle_error(e, ctx, environ, start_response)

    def _handle_unary(
        self,
        environ: WSGIEnvironment,
        start_response: StartResponse,
        http_method: str,
        endpoint: _server_shared.EndpointUnarySync[_REQ, _RES],
        ctx: _server_shared.RequestContext[_REQ, _RES],
        headers: Headers,
    ):
        # Handle request based on method
        if http_method == "GET":
            request, codec = self._handle_get_request(environ, endpoint)
        else:
            request, codec = self._handle_post_request(environ, endpoint, headers)

        # Process request
        response = endpoint.function(request, ctx)

        # Encode response
        res_bytes = codec.encode(response)
        base_headers = {
            "content-type": [f"{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{codec.name()}"]
        }

        # Handle compression if accepted
        accept_encoding = headers.get("accept-encoding", "identity")
        selected_encoding = _compression.select_encoding(accept_encoding)
        compressed_bytes = None
        if selected_encoding != "identity":
            compression = _compression.get_compression(selected_encoding)
            if compression:
                compressed_bytes = compression.compress(res_bytes)
        response_headers, use_compression = prepare_response_headers(
            base_headers,
            selected_encoding,
            len(compressed_bytes) if compressed_bytes is not None else None,
        )

        # Convert headers to WSGI format
        wsgi_headers: list[tuple[str, str]] = []
        for key, values in response_headers.items():
            for value in values:
                wsgi_headers.append((key.lower(), value))
        _add_context_headers(wsgi_headers, ctx)

        start_response("200 OK", wsgi_headers)
        final_response = (
            compressed_bytes if use_compression and compressed_bytes else res_bytes
        )
        return [final_response]

    def _handle_post_request(
        self,
        environ: WSGIEnvironment,
        endpoint: _server_shared.EndpointSync[_REQ, _RES],
        request_headers: Headers,
    ) -> tuple[_REQ, Codec]:
        """Handle POST request with body."""

        codec_name = codec_name_from_content_type(
            request_headers.get("content-type", ""), False
        )
        codec = get_codec(codec_name)
        if not codec:
            raise HTTPException(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                [("Accept-Post", "application/json, application/proto")],
            )

        try:
            content_length = environ.get("CONTENT_LENGTH")
            if not content_length:
                content_length = 0
            else:
                content_length = int(content_length)
            if content_length > 0:
                req_body = environ["wsgi.input"].read(content_length)
            else:
                req_body_chunks: list[bytes] = []
                for chunk in _read_body(environ):
                    req_body_chunks.append(chunk)
                req_body = b"".join(req_body_chunks)

            # Handle compression if specified
            compression_name = environ.get("HTTP_CONTENT_ENCODING", "identity").lower()
            if compression_name != "identity":
                compression = _compression.get_compression(compression_name)
                if not compression:
                    raise ConnecpyException(
                        Code.UNIMPLEMENTED,
                        f"unknown compression: '{compression_name}': supported encodings are {', '.join(_compression.get_available_compressions())}",
                    )
                try:
                    req_body = compression.decompress(req_body)
                except Exception as e:
                    raise ConnecpyException(
                        Code.INVALID_ARGUMENT,
                        f"Failed to decompress request body: {str(e)}",
                    )

            if (
                self._read_max_bytes is not None
                and len(req_body) > self._read_max_bytes
            ):
                raise ConnecpyException(
                    Code.RESOURCE_EXHAUSTED,
                    f"message is larger than configured max {self._read_max_bytes}",
                )

            try:
                return codec.decode(req_body, endpoint.method.input()), codec
            except Exception as e:
                raise ConnecpyException(
                    Code.INVALID_ARGUMENT, f"Failed to decode request body: {str(e)}"
                )

        except Exception as e:
            if not isinstance(e, ConnecpyException):
                raise ConnecpyException(
                    Code.INTERNAL,
                    str(e),  # TODO
                )
            raise

    def _handle_get_request(
        self, environ, endpoint: _server_shared.EndpointUnarySync[_REQ, _RES]
    ) -> tuple[_REQ, Codec]:
        """Handle GET request with query parameters."""
        try:
            query_string = environ.get("QUERY_STRING", "")
            params = parse_qs(query_string)

            if "message" not in params:
                raise ConnecpyException(
                    Code.INVALID_ARGUMENT,
                    "'message' parameter is required for GET requests",
                )

            message = params["message"][0]

            if "base64" in params and params["base64"][0] == "1":
                try:
                    message = base64.urlsafe_b64decode(message + "===")
                except Exception as e:
                    raise ConnecpyException(
                        Code.INVALID_ARGUMENT, f"Invalid base64 encoding: {str(e)}"
                    )
            else:
                message = message.encode("utf-8")

            # Handle compression if specified
            if "compression" in params:
                compression_name = params["compression"][0]
                compression = _compression.get_compression(compression_name)
                if not compression:
                    raise ConnecpyException(
                        Code.UNIMPLEMENTED,
                        f"unknown compression: '{compression_name}': supported encodings are {', '.join(_compression.get_available_compressions())}",
                    )
                message = compression.decompress(message)

            codec_name = params.get("encoding", ("",))[0]
            codec = get_codec(codec_name)
            if not codec:
                raise ConnecpyException(
                    Code.UNIMPLEMENTED, f"invalid message encoding: '{codec_name}'"
                )
            # Handle GET request with proto decoder
            try:
                # TODO - Use content type from queryparam
                request = codec.decode(message, endpoint.method.input())
                return request, codec
            except Exception as e:
                raise ConnecpyException(
                    Code.INVALID_ARGUMENT, f"Failed to decode message: {str(e)}"
                )

        except Exception as e:
            if not isinstance(e, ConnecpyException):
                raise ConnecpyException(Code.INTERNAL, str(e))
            raise

    def _handle_stream(
        self,
        environ: WSGIEnvironment,
        start_response: StartResponse,
        headers: Headers,
        endpoint: _server_shared.EndpointClientStreamSync[_REQ, _RES]
        | _server_shared.EndpointServerStreamSync[_REQ, _RES]
        | _server_shared.EndpointBidiStreamSync[_REQ, _RES],
        ctx: _server_shared.RequestContext[_REQ, _RES],
    ) -> Iterable[bytes]:
        accept_compression = headers.get(
            CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION, ""
        )
        response_compression_name = _compression.select_encoding(accept_compression)
        response_compression = _compression.get_compression(response_compression_name)

        codec_name = codec_name_from_content_type(headers.get("content-type", ""), True)
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
            environ, endpoint.method.input, codec, req_compression, self._read_max_bytes
        )
        writer = EnvelopeWriter(codec, response_compression)
        try:
            match endpoint:
                case _server_shared.EndpointClientStreamSync():
                    response = endpoint.function(request_stream, ctx)
                    response_stream = iter([response])
                case _server_shared.EndpointServerStreamSync():
                    request = _consume_single_request(request_stream)
                    response_stream = endpoint.function(request, ctx)
                case _server_shared.EndpointBidiStreamSync():
                    response_stream = endpoint.function(request_stream, ctx)

            # Trigger service logic by consuming the first (possibly only) response message.
            first_response = next(response_stream, None)
            # Response headers set before the first message should be set to the context and
            # we can send them.
            _send_stream_response_headers(
                start_response, codec, response_compression_name, ctx
            )
            if first_response is None:
                # It's valid for a service method to return no messages, finish the response
                # without error.
                return [writer.end(ctx.response_trailers(), None)]

            # WSGI requires start_response to be called before returning the body iterator.
            # This means we cannot call yield in this function since the function would not
            # run at all until the iterator is consumed, meaning start_response wouldn't have
            # been called in time. So we return the response stream as a separate generator
            # function. This means some duplication of error handling.
            return _response_stream(first_response, response_stream, writer, ctx)
        except Exception as e:
            # Exception before any response message was returned. An error after the first
            # response message will be handled by _response_stream, so here we have a
            # full error-only response.
            _send_stream_response_headers(
                start_response, codec, response_compression_name, ctx
            )
            return [
                writer.end(
                    ctx.response_trailers(),
                    ConnectWireError.from_exception(e),
                )
            ]

    def _handle_error(
        self, exc, ctx: Optional[RequestContext], _environ, start_response
    ):
        """Handle and log errors with detailed information."""
        headers: list[tuple[str, str]]
        body: list[bytes]
        status: str
        if isinstance(exc, HTTPException):
            headers = exc.headers
            body = []
            status = f"{exc.status.value} {exc.status.phrase}"
        else:
            wire_error = ConnectWireError.from_exception(exc)
            http_status = wire_error.to_http_status()
            headers = [("Content-Type", "application/json")]
            body = [wire_error.to_json_bytes()]
            status = f"{http_status.code} {http_status.reason}"

        if ctx:
            _add_context_headers(headers, ctx)

        start_response(status, headers)
        return body


def _add_context_headers(headers: list[tuple[str, str]], ctx: RequestContext) -> None:
    headers.extend((key, value) for key, value in ctx.response_headers().allitems())
    headers.extend(
        (f"trailer-{key}", value) for key, value in ctx.response_trailers().allitems()
    )


def _send_stream_response_headers(
    start_response: StartResponse,
    codec: Codec,
    compression_name: str,
    ctx: RequestContext,
):
    response_headers = [
        (
            "content-type",
            f"{CONNECT_STREAMING_CONTENT_TYPE_PREFIX}{codec.name()}",
        ),
        (
            CONNECT_STREAMING_HEADER_COMPRESSION,
            compression_name,
        ),
    ]
    response_headers.extend(
        (key, value) for key, value in ctx.response_headers().allitems()
    )
    start_response("200 OK", response_headers)


def _request_stream(
    environ: WSGIEnvironment,
    request_class: type[_REQ],
    codec: Codec,
    compression: _compression.Compression,
    read_max_bytes: int | None = None,
) -> Iterator[_REQ]:
    reader = EnvelopeReader(request_class, codec, compression, read_max_bytes)
    for chunk in _read_body(environ):
        for message in reader.feed(chunk):
            yield message


def _response_stream(
    first_response: _RES,
    response_stream: Iterator[_RES],
    writer: EnvelopeWriter,
    ctx: RequestContext,
) -> Iterable[bytes]:
    error: Exception | None = None
    try:
        body = writer.write(first_response)
        yield body
        for message in response_stream:
            body = writer.write(message)
            yield body
    except Exception as e:
        error = e
    finally:
        yield writer.end(
            ctx.response_trailers(),
            ConnectWireError.from_exception(error) if error else None,
        )


def _consume_single_request(stream: Iterator[_REQ]) -> _REQ:
    req = None
    for message in stream:
        if req is not None:
            raise ConnecpyException(
                Code.UNIMPLEMENTED, "unary request has multiple messages"
            )
        req = message
    if req is None:
        raise ConnecpyException(Code.UNIMPLEMENTED, "unary request has zero messages")
    return req


def _apply_interceptors(
    endpoint: _server_shared.EndpointSync[_REQ, _RES],
    interceptors: Sequence[InterceptorSync],
) -> _server_shared.EndpointSync:
    match endpoint:
        case _server_shared.EndpointUnarySync():
            func = endpoint.function
            for interceptor in reversed(interceptors):
                if not isinstance(interceptor, UnaryInterceptorSync):
                    continue
                func = functools.partial(interceptor.intercept_unary_sync, func)
            return replace(endpoint, function=func)
        case _server_shared.EndpointClientStreamSync():
            func = endpoint.function
            for interceptor in reversed(interceptors):
                if not isinstance(interceptor, ClientStreamInterceptorSync):
                    continue
                func = functools.partial(interceptor.intercept_client_stream_sync, func)
            return replace(endpoint, function=func)
        case _server_shared.EndpointServerStreamSync():
            func = endpoint.function
            for interceptor in reversed(interceptors):
                if not isinstance(interceptor, ServerStreamInterceptorSync):
                    continue
                func = functools.partial(interceptor.intercept_server_stream_sync, func)
            return replace(endpoint, function=func)
        case _server_shared.EndpointBidiStreamSync():
            func = endpoint.function
            for interceptor in reversed(interceptors):
                if not isinstance(interceptor, BidiStreamInterceptorSync):
                    continue
                func = functools.partial(interceptor.intercept_bidi_stream_sync, func)
            return replace(endpoint, function=func)
        case _:
            raise ValueError("Unknown endpoint type")
