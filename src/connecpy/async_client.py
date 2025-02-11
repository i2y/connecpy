from typing import Union
import httpx
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
        self, address: str, timeout=5, session: Union[httpx.AsyncClient, None] = None
    ) -> None:
        self._address = address
        self._timeout = timeout
        self._session = session

    async def _make_request(
        self,
        *,
        url: str,
        request,
        ctx: context.ClientContext,
        response_obj,
        method="POST",
        session: Union[httpx.AsyncClient, None] = None,
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
            if session or self._session:
                client = session or self._session
                close_client = False
            else:
                client = httpx.AsyncClient()
                close_client = True

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
                    resp = await client.get(url=self._address + url, **kwargs)
                else:
                    resp = await client.post(
                        url=self._address + url, content=request_data, **kwargs
                    )

                resp.raise_for_status()

                if resp.status_code == 200:
                    response = response_obj()
                    response.ParseFromString(resp.content)
                    return response
                else:
                    raise exceptions.ConnecpyServerException.from_json(
                        await resp.json()
                    )
            finally:
                if close_client:
                    await client.aclose()
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
