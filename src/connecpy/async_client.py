from typing import Optional
import httpx

from google.protobuf.message import Message
from . import shared_client
from . import compression
from . import context
from . import exceptions
from . import errors


class AsyncConnecpyClient:
    """
    Represents an asynchronous client for Connecpy using httpx.

    Args:
        address (str): The address of the Connecpy server.
        session (httpx.AsyncClient): The httpx client session to use for making requests.
    """

    def __init__(
        self, address: str, timeout=5, session: Optional[httpx.AsyncClient] = None
    ) -> None:
        self._address = address
        self._timeout = timeout
        if session:
            self._session = session
            self._close_client = False
        else:
            self._session = httpx.AsyncClient()
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
        response_class: type[Message],
        method="POST",
        session: Optional[httpx.AsyncClient] = None,
        **kwargs,
    ):
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
        headers, kwargs = shared_client.prepare_headers(ctx, kwargs, self._timeout)

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
                resp = await client.get(url=self._address + url, **kwargs)
            else:
                resp = await client.post(
                    url=self._address + url, content=request_data, **kwargs
                )

            resp.raise_for_status()

            if resp.status_code == 200:
                response = response_class()
                response.ParseFromString(resp.content)
                return response
            else:
                raise exceptions.ConnecpyServerException.from_json(await resp.json())
        except httpx.TimeoutException as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.DeadlineExceeded,
                message=str(e) or "request timeout",
            )
        except httpx.HTTPStatusError as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unavailable,
                message=str(e),
            )
        except Exception as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Internal,
                message=str(e),
            )
