import base64
from contextvars import ContextVar, Token
from http import HTTPStatus
from typing import Iterable, Mapping, Optional, Sequence, TypeVar

from httpx import Headers as HttpxHeaders

from . import _compression
from ._codec import CODEC_NAME_JSON, CODEC_NAME_JSON_CHARSET_UTF8, Codec
from ._compression import Compression, get_available_compressions, get_compression
from ._protocol import (
    CONNECT_PROTOCOL_VERSION,
    CONNECT_STREAMING_CONTENT_TYPE_PREFIX,
    CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION,
    CONNECT_STREAMING_HEADER_COMPRESSION,
    CONNECT_UNARY_CONTENT_TYPE_PREFIX,
    CONNECT_UNARY_HEADER_ACCEPT_COMPRESSION,
    CONNECT_UNARY_HEADER_COMPRESSION,
    ConnectWireError,
    codec_name_from_content_type,
)
from ._version import __version__
from .code import Code
from .exceptions import ConnecpyException
from .method import MethodInfo
from .request import Headers, RequestContext

_DEFAULT_CONNECT_USER_AGENT = f"connecpy/{__version__}"

REQ = TypeVar("REQ")
RES = TypeVar("RES")


def resolve_send_compression(compression_name: str | None) -> Compression | None:
    if compression_name is None:
        return None
    compression = get_compression(compression_name)
    if compression is None:
        raise ValueError(
            f"Unsupported compression method: {compression_name}. "
            f"Available methods: {', '.join(get_available_compressions())}"
        )
    return compression


def create_request_context(
    *,
    method: MethodInfo[REQ, RES],
    http_method: str,
    user_headers: Headers | Mapping[str, str] | None,
    timeout_ms: int | None,
    codec: Codec,
    stream: bool,
    accept_compression: Iterable[str] | None,
    send_compression: Compression | None,
) -> RequestContext:
    match user_headers:
        case Headers():
            # Copy to prevent modification if user keeps reference
            # TODO: Optimize
            headers = Headers(tuple(user_headers.allitems()))
        case None:
            headers = Headers()
        case _:
            headers = Headers(user_headers)

    if "user-agent" not in headers:
        headers["user-agent"] = _DEFAULT_CONNECT_USER_AGENT
    headers["connect-protocol-version"] = CONNECT_PROTOCOL_VERSION

    compression_header = (
        CONNECT_STREAMING_HEADER_COMPRESSION
        if stream
        else CONNECT_UNARY_HEADER_COMPRESSION
    )
    accept_compression_header = (
        CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION
        if stream
        else CONNECT_UNARY_HEADER_ACCEPT_COMPRESSION
    )

    if accept_compression is not None:
        headers[accept_compression_header] = ", ".join(accept_compression)
    else:
        headers[accept_compression_header] = "gzip, br, zstd"
    if send_compression is not None:
        headers[compression_header] = send_compression.name()
    else:
        headers.pop(compression_header, None)
    headers["content-type"] = (
        f"{CONNECT_STREAMING_CONTENT_TYPE_PREFIX if stream else CONNECT_UNARY_CONTENT_TYPE_PREFIX}{codec.name()}"
    )
    if timeout_ms is not None:
        headers["connect-timeout-ms"] = str(timeout_ms)

    return RequestContext(
        method=method,
        http_method=http_method,
        request_headers=headers,
        timeout_ms=timeout_ms,
    )


def maybe_compress_request(request_data: bytes, headers: HttpxHeaders) -> bytes:
    if "content-encoding" not in headers:
        return request_data

    compression_name = headers["content-encoding"].lower()
    if compression_name == "identity":
        return request_data
    compression = _compression.get_compression(compression_name)
    if not compression:
        # TODO: Validate within client construction instead of request
        raise ValueError(f"Unsupported compression method: {compression_name}")
    try:
        return compression.compress(request_data)
    except Exception as e:
        raise Exception(
            f"Failed to compress request with {compression_name}: {str(e)}"
        ) from e


def prepare_get_params(codec: Codec, request_data, headers):
    params = {"connect": f"v{CONNECT_PROTOCOL_VERSION}"}
    if request_data:
        params["message"] = base64.urlsafe_b64encode(request_data).decode("ascii")
        params["base64"] = "1"
        params["encoding"] = codec.name()
    if "content-encoding" in headers:
        params["compression"] = headers.pop("content-encoding")
    return params


_current_response = ContextVar["ResponseMetadata"]("connecpy_current_response")


def validate_response_content_encoding(
    encoding: str | None,
) -> _compression.Compression:
    if not encoding:
        return _compression.IdentityCompression()
    res = _compression.get_compression(encoding.lower())
    if not res:
        raise ConnecpyException(
            Code.INTERNAL,
            f"unknown encoding '{encoding}'; accepted encodings are {', '.join(_compression.get_available_compressions())}",
        )
    return res


def validate_response_content_type(
    request_codec_name: str,
    status_code: int,
    response_content_type: str,
):
    if status_code != HTTPStatus.OK:
        # Error responses must be JSON-encoded
        if response_content_type in (
            f"{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{CODEC_NAME_JSON}",
            f"{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{CODEC_NAME_JSON_CHARSET_UTF8}",
        ):
            return
        raise ConnectWireError.from_http_status(status_code).to_exception()

    if not response_content_type.startswith(CONNECT_UNARY_CONTENT_TYPE_PREFIX):
        raise ConnecpyException(
            Code.UNKNOWN,
            f"invalid content-type: '{response_content_type}'; expecting '{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{request_codec_name}'",
        )

    response_codec_name = codec_name_from_content_type(
        response_content_type, stream=False
    )
    if response_codec_name == request_codec_name:
        return

    if (
        response_codec_name == CODEC_NAME_JSON
        and request_codec_name == CODEC_NAME_JSON_CHARSET_UTF8
    ) or (
        response_codec_name == CODEC_NAME_JSON_CHARSET_UTF8
        and request_codec_name == CODEC_NAME_JSON
    ):
        # Both are JSON
        return

    raise ConnecpyException(
        Code.INTERNAL,
        f"invalid content-type: '{response_content_type}'; expecting '{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{request_codec_name}'",
    )


def validate_stream_response_content_type(
    request_codec_name: str,
    response_content_type: str,
):
    if not response_content_type.startswith(CONNECT_STREAMING_CONTENT_TYPE_PREFIX):
        raise ConnecpyException(
            Code.UNKNOWN,
            f"invalid content-type: '{response_content_type}'; expecting '{CONNECT_STREAMING_CONTENT_TYPE_PREFIX}{request_codec_name}'",
        )

    response_codec_name = response_content_type[
        len(CONNECT_STREAMING_CONTENT_TYPE_PREFIX) :
    ]
    if response_codec_name != request_codec_name:
        raise ConnecpyException(
            Code.INTERNAL,
            f"invalid content-type: '{response_content_type}'; expecting '{CONNECT_STREAMING_CONTENT_TYPE_PREFIX}{request_codec_name}'",
        )


def handle_response_headers(headers: HttpxHeaders):
    response = _current_response.get(None)
    if not response:
        return

    response_headers: Headers = Headers()
    response_trailers: Headers = Headers()
    for key, value in headers.multi_items():
        if key.startswith("trailer-"):
            key = key[len("trailer-") :]
            obj = response_trailers
        else:
            obj = response_headers
        obj.add(key, value)
    if response_headers:
        response._headers = response_headers
    if response_trailers:
        response._trailers = response_trailers


def handle_response_trailers(trailers: Mapping[str, Sequence[str]]):
    response = _current_response.get(None)
    if not response:
        return
    response_trailers = response.trailers()
    for key, values in trailers.items():
        for value in values:
            response_trailers.add(key, value)
    if response_trailers:
        response._trailers = response_trailers


class ResponseMetadata:
    """
    Response metadata separate from the message payload.

    Commonly, RPC client invocations only need the message payload and do not need to
    directly read other data such as headers or trailers. In cases where they are needed,
    initialize this class in a context manager to access the response headers and trailers
    for the invocation made within the context.

    Example:

        with ResponseMetadata() as resp_data:
            resp = client.MakeHat(Size(inches=10))
            do_something_with_response_payload(resp)
            check_response_headers(resp_data.headers())
            check_response_trailers(resp_data.trailers())
    """

    _headers: Optional[Headers] = None
    _trailers: Optional[Headers] = None
    _token: Optional[Token["ResponseMetadata"]] = None

    def __enter__(self) -> "ResponseMetadata":
        self._token = _current_response.set(self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._token:
            try:
                _current_response.reset(self._token)
            except Exception:  # noqa: S110
                # Normal usage with context manager will always work but it is
                # theoretically possible for user to move to another thread
                # and this fails, it is fine to ignore it.
                pass
        self._token = None

    def headers(self) -> Headers:
        """Returns the response headers."""
        if self._headers is None:
            return Headers()
        return self._headers

    def trailers(self) -> Headers:
        """Returns the response trailers."""
        if self._trailers is None:
            return Headers()
        return self._trailers
