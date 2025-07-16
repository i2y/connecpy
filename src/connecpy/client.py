from typing import Optional, TypeVar

import httpx

from google.protobuf.message import Message
from httpx import Timeout

from . import context
from . import exceptions
from . import errors
from . import compression
from . import shared_client
from ._protocol import ConnectWireError


_RES = TypeVar("_RES", bound=Message)


class ConnecpyClient:
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
        timeout_ms: Optional[int] = None,
        session: Optional[httpx.Client] = None,
    ):
        self._address = address
        self._timeout_ms = timeout_ms
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
        ctx: Optional[context.ClientContext],
        response_class: type[_RES],
        method="POST",
        timeout_ms: Optional[int] = None,
        **kwargs,
    ) -> _RES:
        """Make an HTTP request to the server."""
        # Prepare headers and kwargs using shared logic
        if timeout_ms is None:
            timeout_ms = self._timeout_ms
        else:
            timeout = _convert_connect_timeout(timeout_ms)
            kwargs["timeout"] = timeout
        headers, kwargs = shared_client.prepare_headers(ctx, kwargs, timeout_ms)

        try:
            if "content-encoding" in headers:
                request_data, headers = shared_client.compress_request(
                    request, headers, compression
                )
            else:
                request_data = request.SerializeToString()

            if method == "GET":
                params = shared_client.prepare_get_params(request_data, headers)
                kwargs["params"] = params
                kwargs["headers"].pop("content-type", None)
                resp = self._session.get(url=self._address + url, **kwargs)
            else:
                resp = self._session.post(
                    url=self._address + url, content=request_data, **kwargs
                )

            if resp.status_code == 200:
                response = response_class()
                try:
                    response.ParseFromString(resp.content)
                except Exception as e:
                    raise exceptions.ConnecpyException(
                        f"Failed to parse response message: {str(e)}"
                    )
                return response
            else:
                raise ConnectWireError.from_response(resp).to_exception()
        except httpx.TimeoutException:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.DeadlineExceeded,
                message="Request timed out",
            )
        except exceptions.ConnecpyException:
            raise
        except Exception as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unavailable, message=str(e)
            )


# Convert a timeout with connect semantics to a httpx.Timeout. Connect timeouts
# should apply to an entire operation but this is difficult in synchronous Python code
# to do cross-platform. For now, we just apply the timeout to all httpx timeouts
# if provided, or default to no read/write timeouts but with a connect timeout if
# not provided to match connect-go behavior as closely as possible.
def _convert_connect_timeout(timeout_ms: Optional[int]) -> Timeout:
    if timeout_ms is None:
        return Timeout(None, connect=30.0)
    return Timeout(timeout_ms / 1000.0)
