from asyncio import CancelledError, wait_for
from typing import Iterable, Optional, TypeVar

import httpx
from google.protobuf.message import Message
from httpx import Headers, Timeout

from . import _client_shared
from ._client_shared import RequestHeaders
from ._codec import get_proto_binary_codec, get_proto_json_codec
from ._protocol import ConnectWireError
from .code import Code
from .exceptions import ConnecpyServerException

_RES = TypeVar("_RES", bound=Message)


class ConnecpyClient:
    """
    Represents an asynchronous client for Connecpy using httpx.

    Args:
        address (str): The address of the Connecpy server.
        timeout_ms (int): The timeout in ms for the overall request.
        session (httpx.AsyncClient): The httpx client session to use for making requests. If setting timeout_ms,
            the session should have timeout disabled or set higher than timeout_ms.
    """

    def __init__(
        self,
        address: str,
        proto_json: bool = False,
        accept_compression: Optional[Iterable[str]] = None,
        send_compression: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        session: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._address = address
        self._codec = get_proto_json_codec() if proto_json else get_proto_binary_codec()
        self._timeout_ms = timeout_ms
        self._accept_compression = accept_compression
        self._send_compression = send_compression
        if session:
            self._session = session
            self._close_client = False
        else:
            self._session = httpx.AsyncClient(
                timeout=_convert_connect_timeout(timeout_ms)
            )
            self._close_client = True
        self._closed = False

    async def close(self):
        """Close the HTTP client. After closing, the client cannot be used to make requests."""
        if not self._closed:
            self._closed = True
            if self._close_client:
                await self._session.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc_value, _traceback):
        await self.close()

    async def _make_request(
        self,
        *,
        url: str,
        request: Message,
        response_class: type[_RES],
        method="POST",
        headers: Optional[RequestHeaders] = None,
        timeout_ms: Optional[int] = None,
        session: Optional[httpx.AsyncClient] = None,
    ) -> _RES:
        """Make an HTTP request to the server."""
        # Prepare headers and request args using shared logic
        request_args = {}
        if timeout_ms is None:
            timeout_ms = self._timeout_ms
        else:
            timeout = _convert_connect_timeout(timeout_ms)
            request_args["timeout"] = timeout

        user_headers = Headers(headers) if headers else Headers()
        request_headers = _client_shared.prepare_headers(
            self._codec,
            user_headers,
            timeout_ms,
            self._accept_compression,
            self._send_compression,
        )
        timeout_s = timeout_ms / 1000.0 if timeout_ms is not None else None

        try:
            request_data = self._codec.encode(request)
            client = session or self._session

            request_data = _client_shared.maybe_compress_request(
                request_data, request_headers
            )

            if method == "GET":
                params = _client_shared.prepare_get_params(
                    self._codec, request_data, request_headers
                )
                request_headers.pop("content-type", None)
                resp = await wait_for(
                    client.get(
                        url=self._address + url,
                        headers=request_headers,
                        params=params,
                        **request_args,
                    ),
                    timeout_s,
                )
            else:
                resp = await wait_for(
                    client.post(
                        url=self._address + url,
                        headers=request_headers,
                        content=request_data,
                        **request_args,
                    ),
                    timeout_s,
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
        except (httpx.TimeoutException, TimeoutError):
            raise ConnecpyServerException(
                code=Code.DEADLINE_EXCEEDED,
                message="Request timed out",
            )
        except ConnecpyServerException:
            raise
        except CancelledError as e:
            raise ConnecpyServerException(
                code=Code.CANCELED,
                message="Request was cancelled",
            ) from e
        except Exception as e:
            raise ConnecpyServerException(
                code=Code.UNAVAILABLE,
                message=str(e),
            )


def _convert_connect_timeout(timeout_ms: Optional[int]) -> Timeout:
    if timeout_ms is None:
        # If no timeout provided, match connect-go's default behavior of a 30s connect timeout
        # and no read/write timeouts.
        return Timeout(None, connect=30.0)
    # We apply the timeout to the entire operation per connect's semantics so don't need
    # HTTP timeout
    return Timeout(None)
