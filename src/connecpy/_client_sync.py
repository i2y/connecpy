import functools
from collections.abc import Iterable, Iterator, Mapping
from typing import (
    Any,
    Protocol,
    TypeVar,
)

import httpx
from httpx import USE_CLIENT_DEFAULT, Timeout

from . import _client_shared
from ._codec import Codec, get_proto_binary_codec, get_proto_json_codec
from ._compression import Compression
from ._envelope import EnvelopeReader, EnvelopeWriter
from ._interceptor_sync import (
    BidiStreamInterceptorSync,
    ClientStreamInterceptorSync,
    InterceptorSync,
    ServerStreamInterceptorSync,
    UnaryInterceptorSync,
    resolve_interceptors,
)
from ._protocol import CONNECT_STREAMING_HEADER_COMPRESSION, ConnectWireError
from .code import Code
from .exceptions import ConnecpyException
from .method import MethodInfo
from .request import Headers, RequestContext

REQ = TypeVar("REQ")
RES = TypeVar("RES")


class _ExecuteUnary(Protocol[REQ, RES]):
    def __call__(self, request: REQ, ctx: RequestContext[REQ, RES]) -> RES: ...


class _ExecuteClientStream(Protocol[REQ, RES]):
    def __call__(
        self, request: Iterator[REQ], ctx: RequestContext[REQ, RES]
    ) -> RES: ...


class _ExecuteServerStream(Protocol[REQ, RES]):
    def __call__(
        self, request: REQ, ctx: RequestContext[REQ, RES]
    ) -> Iterator[RES]: ...


class _ExecuteBidiStream(Protocol[REQ, RES]):
    def __call__(
        self, request: Iterator[REQ], ctx: RequestContext[REQ, RES]
    ) -> Iterator[RES]: ...


class ConnecpyClientSync:
    """
    Represents a synchronous client for Connecpy using httpx.

    Args:
        address (str): The address of the Connecpy server.
        timeout_ms (int): The timeout in ms for the overall request. Note, this is currently only implemented
            as a read timeout, which will be more forgiving than a timeout for the operation.
        session (httpx.Client): The httpx client session to use for making requests. If setting timeout_ms,
            the session should also at least have a read timeout set to the same value.
    """

    _execute_unary: _ExecuteUnary
    _execute_client_stream: _ExecuteClientStream
    _execute_server_stream: _ExecuteServerStream
    _execute_bidi_stream: _ExecuteBidiStream

    def __init__(
        self,
        address: str,
        *,
        proto_json: bool = False,
        accept_compression: Iterable[str] | None = None,
        send_compression: str | None = None,
        timeout_ms: int | None = None,
        read_max_bytes: int | None = None,
        interceptors: Iterable[InterceptorSync] = (),
        session: httpx.Client | None = None,
    ):
        self._address = address
        self._codec = get_proto_json_codec() if proto_json else get_proto_binary_codec()
        self._timeout_ms = timeout_ms
        self._read_max_bytes = read_max_bytes
        self._accept_compression = accept_compression
        self._send_compression = _client_shared.resolve_send_compression(
            send_compression
        )
        if session:
            self._session = session
            self._close_client = False
        else:
            self._session = httpx.Client(timeout=_convert_connect_timeout(timeout_ms))
            self._close_client = True
        self._closed = False

        interceptors = resolve_interceptors(interceptors)
        execute_unary = self._send_request_unary
        for interceptor in (
            i for i in reversed(interceptors) if isinstance(i, UnaryInterceptorSync)
        ):
            execute_unary = functools.partial(
                interceptor.intercept_unary_sync, execute_unary
            )
        self._execute_unary = execute_unary

        execute_client_stream = self._send_request_client_stream
        for interceptor in (
            i
            for i in reversed(interceptors)
            if isinstance(i, ClientStreamInterceptorSync)
        ):
            execute_client_stream = functools.partial(
                interceptor.intercept_client_stream_sync, execute_client_stream
            )
        self._execute_client_stream = execute_client_stream

        execute_server_stream: _ExecuteServerStream = self._send_request_server_stream
        for interceptor in (
            i
            for i in reversed(interceptors)
            if isinstance(i, ServerStreamInterceptorSync)
        ):
            execute_server_stream = functools.partial(
                interceptor.intercept_server_stream_sync, execute_server_stream
            )
        self._execute_server_stream = execute_server_stream

        execute_bidi_stream = self._send_request_bidi_stream
        for interceptor in (
            i
            for i in reversed(interceptors)
            if isinstance(i, BidiStreamInterceptorSync)
        ):
            execute_bidi_stream = functools.partial(
                interceptor.intercept_bidi_stream_sync, execute_bidi_stream
            )
        self._execute_bidi_stream = execute_bidi_stream

    def close(self):
        """Close the HTTP client. After closing, the client cannot be used to make requests."""
        if not self._closed:
            self._closed = True
            if self._close_client:
                self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()

    def execute_unary(
        self,
        *,
        request: REQ,
        method: MethodInfo[REQ, RES],
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
        use_get: bool = False,
    ) -> RES:
        ctx = _client_shared.create_request_context(
            method=method,
            http_method="GET" if use_get else "POST",
            user_headers=headers,
            timeout_ms=timeout_ms or self._timeout_ms,
            codec=self._codec,
            stream=False,
            accept_compression=self._accept_compression,
            send_compression=self._send_compression,
        )
        return self._execute_unary(request, ctx)

    def execute_client_stream(
        self,
        *,
        request: Iterator[REQ],
        method: MethodInfo[REQ, RES],
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> RES:
        ctx = _client_shared.create_request_context(
            method=method,
            http_method="POST",
            user_headers=headers,
            timeout_ms=timeout_ms or self._timeout_ms,
            codec=self._codec,
            stream=True,
            accept_compression=self._accept_compression,
            send_compression=self._send_compression,
        )
        return self._execute_client_stream(request, ctx)

    def execute_server_stream(
        self,
        *,
        request: REQ,
        method: MethodInfo[REQ, RES],
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> Iterator[RES]:
        ctx = _client_shared.create_request_context(
            method=method,
            http_method="POST",
            user_headers=headers,
            timeout_ms=timeout_ms or self._timeout_ms,
            codec=self._codec,
            stream=True,
            accept_compression=self._accept_compression,
            send_compression=self._send_compression,
        )
        return self._execute_server_stream(request, ctx)

    def execute_bidi_stream(
        self,
        *,
        request: Iterator[REQ],
        method: MethodInfo[REQ, RES],
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> Iterator[RES]:
        ctx = _client_shared.create_request_context(
            method=method,
            http_method="POST",
            user_headers=headers,
            timeout_ms=timeout_ms or self._timeout_ms,
            codec=self._codec,
            stream=True,
            accept_compression=self._accept_compression,
            send_compression=self._send_compression,
        )
        return self._execute_bidi_stream(request, ctx)

    def _send_request_unary(self, request: REQ, ctx: RequestContext[REQ, RES]) -> RES:
        request_headers = httpx.Headers(list(ctx.request_headers().allitems()))
        url = f"{self._address}/{ctx.method().service_name}/{ctx.method().name}"
        if (timeout_ms := ctx.timeout_ms()) is not None:
            timeout = _convert_connect_timeout(timeout_ms)
        else:
            timeout = USE_CLIENT_DEFAULT

        try:
            request_data = self._codec.encode(request)
            request_data = _client_shared.maybe_compress_request(
                request_data, request_headers
            )

            if ctx.http_method() == "GET":
                params = _client_shared.prepare_get_params(
                    self._codec, request_data, request_headers
                )
                request_headers.pop("content-type", None)
                resp = self._session.get(
                    url=url,
                    headers=request_headers,
                    params=params,
                    timeout=timeout,
                )
            else:
                resp = self._session.post(
                    url=url,
                    headers=request_headers,
                    content=request_data,
                    timeout=timeout,
                )

            _client_shared.validate_response_content_encoding(
                resp.headers.get("content-encoding", "")
            )
            _client_shared.validate_response_content_type(
                self._codec.name(),
                resp.status_code,
                resp.headers.get("content-type", ""),
            )
            _client_shared.handle_response_headers(resp.headers)

            if resp.status_code == 200:
                if (
                    self._read_max_bytes is not None
                    and len(resp.content) > self._read_max_bytes
                ):
                    raise ConnecpyException(
                        Code.RESOURCE_EXHAUSTED,
                        f"message is larger than configured max {self._read_max_bytes}",
                    )

                response = ctx.method().output()
                self._codec.decode(resp.content, response)
                return response
            raise ConnectWireError.from_response(resp).to_exception()
        except (httpx.TimeoutException, TimeoutError) as e:
            raise ConnecpyException(Code.DEADLINE_EXCEEDED, "Request timed out") from e
        except ConnecpyException:
            raise
        except Exception as e:
            raise ConnecpyException(Code.UNAVAILABLE, str(e)) from e

    def _send_request_client_stream(
        self,
        request: Iterator[REQ],
        ctx: RequestContext[REQ, RES],
    ) -> RES:
        return _consume_single_response(self._send_request_bidi_stream(request, ctx))

    def _send_request_server_stream(
        self,
        request: REQ,
        ctx: RequestContext[REQ, RES],
    ) -> Iterator[RES]:
        return self._send_request_bidi_stream(iter([request]), ctx)

    def _send_request_bidi_stream(
        self,
        request: Iterator[REQ],
        ctx: RequestContext[REQ, RES],
    ) -> Iterator[RES]:
        request_headers = httpx.Headers(list(ctx.request_headers().allitems()))
        url = f"{self._address}/{ctx.method().service_name}/{ctx.method().name}"
        if (timeout_ms := ctx.timeout_ms()) is not None:
            timeout = _convert_connect_timeout(timeout_ms)
        else:
            timeout = USE_CLIENT_DEFAULT

        try:
            request_data = _streaming_request_content(
                request, self._codec, self._send_compression
            )

            resp = self._session.post(
                url=url,
                headers=request_headers,
                content=request_data,
                timeout=timeout,
            )

            compression = _client_shared.validate_response_content_encoding(
                resp.headers.get(CONNECT_STREAMING_HEADER_COMPRESSION, "")
            )
            _client_shared.validate_stream_response_content_type(
                self._codec.name(),
                resp.headers.get("content-type", ""),
            )
            _client_shared.handle_response_headers(resp.headers)

            if resp.status_code == 200:
                reader = EnvelopeReader(
                    ctx.method().output, self._codec, compression, self._read_max_bytes
                )
                try:
                    for chunk in resp.iter_bytes():
                        yield from reader.feed(chunk)
                finally:
                    resp.close()
            else:
                raise ConnectWireError.from_response(resp).to_exception()
        except (httpx.TimeoutException, TimeoutError) as e:
            raise ConnecpyException(Code.DEADLINE_EXCEEDED, "Request timed out") from e
        except ConnecpyException:
            raise
        except Exception as e:
            raise ConnecpyException(Code.UNAVAILABLE, str(e)) from e


# Convert a timeout with connect semantics to a httpx.Timeout. Connect timeouts
# should apply to an entire operation but this is difficult in synchronous Python code
# to do cross-platform. For now, we just apply the timeout to all httpx timeouts
# if provided, or default to no read/write timeouts but with a connect timeout if
# not provided to match connect-go behavior as closely as possible.
def _convert_connect_timeout(timeout_ms: float | None) -> Timeout:
    if timeout_ms is None:
        return Timeout(None, connect=30.0)
    return Timeout(timeout_ms / 1000.0)


def _streaming_request_content(
    msgs: Iterator[Any],
    codec: Codec,
    compression: Compression | None,
) -> Iterator[bytes]:
    writer = EnvelopeWriter(codec, compression)
    for msg in msgs:
        yield writer.write(msg)


def _consume_single_response(stream: Iterator[RES]) -> RES:
    res = None
    for message in stream:
        if res is not None:
            raise ConnecpyException(
                Code.UNIMPLEMENTED, "unary response has multiple messages"
            )
        res = message
    if res is None:
        raise ConnecpyException(Code.UNIMPLEMENTED, "unary response has zero messages")
    return res
