import base64
from contextvars import ContextVar, Token
from typing import Iterable, Optional

from httpx import Headers

from ._protocol import CONNECT_PROTOCOL_VERSION


# TODO: Embed package version correctly
_DEFAULT_CONNECT_USER_AGENT = "connecpy/0.0.0"


def prepare_headers(
    headers: Headers,
    timeout_ms: Optional[int],
    accept_compression: Optional[Iterable[str]],
    send_compression: Optional[str],
) -> Headers:
    if "user-agent" not in headers:
        headers["user-agent"] = _DEFAULT_CONNECT_USER_AGENT
    headers["connect-protocol-version"] = CONNECT_PROTOCOL_VERSION
    if accept_compression is not None:
        headers["accept-encoding"] = ", ".join(accept_compression)
    else:
        headers["accept-encoding"] = "gzip, br, zstd"
    if send_compression is not None:
        headers["content-encoding"] = send_compression
    else:
        headers.pop("content-encoding", None)
    headers["content-type"] = "application/proto"
    if timeout_ms is not None:
        headers["connect-timeout-ms"] = str(timeout_ms)
    return headers


def compress_request(request, headers, compression):
    request_data = request.SerializeToString()
    # If compression is requested
    if "content-encoding" in headers:
        compression_name = headers["content-encoding"].lower()
        compressor = compression.get_compressor(compression_name)
        if not compressor:
            raise Exception(f"Unsupported compression method: {compression_name}")
        try:
            compressed = compressor(request_data)
            if len(compressed) < len(request_data):
                # Optionally, log compression details
                request_data = compressed
            else:
                headers.pop("content-encoding", None)
        except Exception as e:
            raise Exception(
                f"Failed to compress request with {compression_name}: {str(e)}"
            )
    return request_data, headers


def prepare_get_params(request_data, headers):
    params = {}
    if request_data:
        params["message"] = base64.urlsafe_b64encode(request_data).decode("ascii")
        params["base64"] = "1"
        params["encoding"] = (
            "proto" if headers.get("content-type") == "application/proto" else "json"
        )
    if "content-encoding" in headers:
        params["compression"] = headers.pop("content-encoding")
    return params


_current_response = ContextVar["Response"]("connecpy_current_response")


def handle_response_headers(headers: Headers):
    response = _current_response.get(None)
    if not response:
        return

    response_headers: list[tuple[str, str]] = []
    response_trailers: list[tuple[str, str]] = []
    for key, value in headers.multi_items():
        if key.lower().startswith("trailer-"):
            key = key[len("trailer-") :]
            obj = response_trailers
        else:
            obj = response_headers
        obj.append((key, value))
    if response_headers:
        response._headers = Headers(response_headers)
    if response_trailers:
        response._trailers = Headers(response_trailers)


class Response:
    """
    Response data separate from the message payload.

    Commonly, RPC client invocations only need the message payload and do not need to
    directly read other data such as headers or trailers. In cases where they are needed,
    initialize this class in a context manager to access the response headers and trailers
    for the invocation made within the context.

    Example:
        with Response() as resp_data:
            resp = client.MakeHat(Size(inches=10))
            do_something_with_response_payload(resp)
            check_response_headers(resp_data.headers())
            check_response_trailers(resp_data.trailers())
    """

    _headers: Optional[Headers] = None
    _trailers: Optional[Headers] = None
    _token: Optional[Token["Response"]] = None

    def __enter__(self) -> "Response":
        self._token = _current_response.set(self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._token:
            try:
                _current_response.reset(self._token)
            except Exception:
                # Normal usage with context manager will always work but it is
                # theoretically possible for user to move to another thread
                # and this fails, it is fine to ignore it.
                pass
        self._token = None

    def headers(self) -> Headers:
        """Returns the response headers."""
        return self._headers or Headers()

    def trailers(self) -> Headers:
        """Returns the response trailers."""
        if self._trailers is None:
            return Headers()
        return self._trailers
