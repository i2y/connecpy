# import asyncio
# import json

# import aiohttp

# from . import context
# from . import exceptions
# from . import errors


# class AsyncConPyClient:
#     """
#     Represents an asynchronous client for ConPy.

#     Args:
#         address (str): The address of the ConPy server.
#         session (aiohttp.ClientSession): The aiohttp client session to use for making requests.
#     """

#     def __init__(self, address: str, session: aiohttp.ClientSession) -> None:
#         self._address = address
#         self._session = session

#     async def _make_request(
#         self,
#         *,
#         url: str,
#         request,
#         ctx: context.ClientContext,
#         response_obj,
#         session: aiohttp.ClientSession | None = None,
#         **kwargs
#     ):
#         """
#         Makes a request to the ConPy server.

#         Args:
#             url (str): The URL to send the request to.
#             request: The request object to send.
#             ctx (context.ClientContext): The client context.
#             response_obj: The response object class to deserialize the response into.
#             session (aiohttp.ClientSession, optional): The aiohttp client session to use for the request.
#                 If not provided, the session passed to the constructor will be used.
#             **kwargs: Additional keyword arguments to pass to the request.

#         Returns:
#             The deserialized response object.

#         Raises:
#             exceptions.ConPyServerException: If an error occurs while making the request.
#         """
#         headers = ctx.get_headers()
#         if "headers" in kwargs:
#             headers.update(kwargs["headers"])
#         kwargs["headers"] = headers
#         kwargs["headers"]["Content-Type"] = "application/proto"

#         if session is None:
#             session = self._session

#         timeout = session.timeout
#         if timeout.total is not None:
#             kwargs["headers"]["connect-timeout-ms"] = str(timeout.total * 1000)
#         elif timeout.sock_read is not None:
#             kwargs["headers"]["connect-timeout-ms"] = str(timeout.sock_read * 1000)

#         try:
#             async with await session.post(
#                 url=url, data=request.SerializeToString(), **kwargs
#             ) as resp:
#                 if resp.status == 200:
#                     response = response_obj()
#                     response.ParseFromString(await resp.read())
#                     return response
#                 try:
#                     raise exceptions.ConPyServerException.from_json(await resp.json())
#                 except (aiohttp.ContentTypeError, json.JSONDecodeError):
#                     raise exceptions.conpy_error_from_intermediary(
#                         resp.status, resp.reason, resp.headers, await resp.text()
#                     ) from None
#         except asyncio.TimeoutError as e:
#             raise exceptions.ConPyServerException(
#                 code=errors.Errors.DeadlineExceeded,
#                 message=str(e) or "request timeout",
#             )
#         except aiohttp.ServerConnectionError as e:
#             raise exceptions.ConPyServerException(
#                 code=errors.Errors.Unavailable,
#                 message=str(e),
#             )

import httpx

from . import context
from . import exceptions
from . import errors


class AsyncConPyClient:
    """
    Represents an asynchronous client for ConPy using httpx.

    Args:
        address (str): The address of the ConPy server.
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
        **kwargs
    ):
        """
        Makes a request to the ConPy server.

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
            exceptions.ConPyServerException: If an error occurs while making the request.
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
                raise exceptions.ConPyServerException.from_json(response.json())
        except httpx.TimeoutException as e:
            raise exceptions.ConPyServerException(
                code=errors.Errors.DeadlineExceeded, message=str(e) or "request timeout"
            )
        except httpx.HTTPStatusError as e:
            raise exceptions.ConPyServerException(
                code=errors.Errors.Unavailable, message=str(e)
            )
        except Exception as e:
            raise exceptions.ConPyServerException(
                code=errors.Errors.Internal, message=str(e)
            )
