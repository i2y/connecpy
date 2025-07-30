from typing import Iterable, Mapping, Optional, TypeVar

import httpx
from google.protobuf.message import Message
from httpx import Timeout

from . import _client_shared
from ._codec import get_proto_binary_codec, get_proto_json_codec
from ._protocol import ConnectWireError
from .code import Code
from .exceptions import ConnecpyException
from .headers import Headers

_RES = TypeVar("_RES", bound=Message)


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

    def __init__(
        self,
        address: str,
        proto_json: bool = False,
        accept_compression: Optional[Iterable[str]] = None,
        send_compression: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        session: Optional[httpx.Client] = None,
    ):
        self._address = address
        self._codec = get_proto_json_codec() if proto_json else get_proto_binary_codec()
        self._timeout_ms = timeout_ms
        self._accept_compression = accept_compression
        self._send_compression = send_compression
        if session:
            self._session = session
            self._close_client = False
        else:
            self._session = httpx.Client(timeout=_convert_connect_timeout(timeout_ms))
            self._close_client = True
        self._closed = False

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

    def _make_request(
        self,
        *,
        url,
        request: Message,
        response_class: type[_RES],
        method="POST",
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: Optional[int] = None,
    ) -> _RES:
        """Make an HTTP request to the server."""
        # Prepare headers and request args using shared logic
        request_args = {}
        if timeout_ms is None:
            timeout_ms = self._timeout_ms
        else:
            timeout = _convert_connect_timeout(timeout_ms)
            request_args["timeout"] = timeout

        request_headers = _client_shared.prepare_headers(
            self._codec,
            headers,
            timeout_ms,
            self._accept_compression,
            self._send_compression,
        )

        try:
            request_data = self._codec.encode(request)
            request_data = _client_shared.maybe_compress_request(
                request_data, request_headers
            )

            if method == "GET":
                params = _client_shared.prepare_get_params(
                    self._codec, request_data, request_headers
                )
                request_headers.pop("content-type", None)
                resp = self._session.get(
                    url=self._address + url,
                    headers=request_headers,
                    params=params,
                    **request_args,
                )
            else:
                resp = self._session.post(
                    url=self._address + url,
                    content=request_data,
                    headers=request_headers,
                    **request_args,
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
                response = response_class()
                self._codec.decode(resp.content, response)
                return response
            else:
                raise ConnectWireError.from_response(resp).to_exception()
        except httpx.TimeoutException:
            raise ConnecpyException(Code.DEADLINE_EXCEEDED, "Request timed out")
        except ConnecpyException:
            raise
        except Exception as e:
            raise ConnecpyException(Code.UNAVAILABLE, str(e))


# Convert a timeout with connect semantics to a httpx.Timeout. Connect timeouts
# should apply to an entire operation but this is difficult in synchronous Python code
# to do cross-platform. For now, we just apply the timeout to all httpx timeouts
# if provided, or default to no read/write timeouts but with a connect timeout if
# not provided to match connect-go behavior as closely as possible.
def _convert_connect_timeout(timeout_ms: Optional[int]) -> Timeout:
    if timeout_ms is None:
        return Timeout(None, connect=30.0)
    return Timeout(timeout_ms / 1000.0)
