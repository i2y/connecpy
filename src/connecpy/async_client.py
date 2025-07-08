from asyncio import wait_for
from typing import Optional, TypeVar

import httpx
from google.protobuf.message import Message
from httpx import Timeout

from . import shared_client
from . import compression
from . import context
from . import exceptions
from . import errors
from ._protocol import ConnectWireError


_RES = TypeVar("_RES", bound=Message)


class AsyncConnecpyClient:
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
        timeout_ms: Optional[int] = None,
        session: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._address = address
        self._timeout_ms = timeout_ms
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
        ctx: Optional[context.ClientContext],
        response_class: type[_RES],
        method="POST",
        timeout_ms: Optional[int] = None,
        session: Optional[httpx.AsyncClient] = None,
        **kwargs,
    ) -> _RES:
        """
        Makes a request to the Connecpy server.

        Args:
            url (str): The URL to send the request to.
            request: The request object to send.
            ctx (context.ClientContext): The client context.
            response_obj: The response object class to deserialize the response into.
            method (str): The HTTP method to use for the request. Defaults to "POST".
            session (httpx.AsyncClient, optional): The httpx client session to use for the request.
                If not provided, the session passed to the constructor will be used.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            The deserialized response object.

        Raises:
            exceptions.ConnecpyServerException: If an error occurs while making the request.
        """
        # Prepare headers and kwargs using shared logic
        if timeout_ms is None:
            timeout_ms = self._timeout_ms
        else:
            timeout = _convert_connect_timeout(timeout_ms)
            kwargs["timeout"] = timeout
        headers, kwargs = shared_client.prepare_headers(ctx, kwargs, timeout_ms)
        timeout_s = timeout_ms / 1000.0 if timeout_ms is not None else None

        try:
            client = session or self._session

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
                resp = await wait_for(
                    client.get(url=self._address + url, **kwargs),
                    timeout_s,
                )
            else:
                resp = await wait_for(
                    client.post(
                        url=self._address + url,
                        content=request_data,
                        **kwargs,
                    ),
                    timeout_s,
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
        except (httpx.TimeoutException, TimeoutError) as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.DeadlineExceeded,
                message="Request timed out",
            )
        except exceptions.ConnecpyException:
            raise
        except Exception as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unavailable,
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
