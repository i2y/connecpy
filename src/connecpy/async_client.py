import httpx

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

    def __init__(self, address: str, session: httpx.AsyncClient) -> None:
        self._address = address
        self.session = session

    async def _make_request(
        self,
        *,
        url: str,
        request,
        ctx: context.ClientContext,
        response_obj,
        session: httpx.AsyncClient | None = None,
        **kwargs,
    ):
        """
        Makes a request to the Connecpy server.

        Args:
            url (str): The URL to send the request to.
            request: The request object to send.
            ctx (context.ClientContext): The client context.
            response_obj: The response object class to deserialize the response into.
            session (httpx.AsyncClient, optional): The httpx client session to use for the request.
                If not provided, the session passed to the constructor will be used.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            The deserialized response object.

        Raises:
            exceptions.ConnecpyServerException: If an error occurs while making the request.
        """
        headers = ctx.get_headers()
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
        kwargs["headers"] = headers
        kwargs["headers"]["Content-Type"] = "application/proto"

        if session is None:
            session = self.session

        timeout = session.timeout
        if timeout.read is not None:
            kwargs["headers"]["connect-timeout-ms"] = str(timeout.read * 1000)
        elif timeout.connect is not None:
            kwargs["headers"]["connect-timeout-ms"] = str(timeout.connect * 1000)

        try:
            response = await session.post(
                url=url, content=request.SerializeToString(), **kwargs
            )
            response.raise_for_status()

            if response.status_code == 200:
                response_obj_inst = response_obj()
                response_obj_inst.ParseFromString(response.content)
                return response_obj_inst
            else:
                raise exceptions.ConnecpyServerException.from_json(response.json())
        except httpx.TimeoutException as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.DeadlineExceeded, message=str(e) or "request timeout"
            )
        except httpx.HTTPStatusError as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unavailable, message=str(e)
            )
        except Exception as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Internal, message=str(e)
            )
