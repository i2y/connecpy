import asyncio
import time
from dataclasses import dataclass
from functools import reduce
from http import HTTPStatus
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    TypeVar,
    Union,
)

from ._protocol import HTTPException
from .code import Code
from .exceptions import ConnecpyServerException

T = TypeVar("T")
U = TypeVar("U")


class ServiceContext:
    """
    Represents the context of a Connecpy service.

    Attributes:
        _peer: The peer information of the service.
        _invocation_metadata: The invocation metadata of the service.
        _code: The response code of the service.
        _details: The response details of the service.
        _trailing_metadata: The trailing metadata of the service.
        _timeout_sec: The timeout duration in seconds.
        _start_time: The start time of the service.
    """

    _response_headers: Optional[list[tuple[str, str]]] = None
    _response_trailers: Optional[list[tuple[str, str]]] = None

    def __init__(self, peer: str, invocation_metadata: Mapping[str, List[str]]):
        """
        Initialize a Context object.

        Args:
            peer (str): The peer information.
            invocation_metadata (Mapping[str, List[str]]): The invocation metadata.

        Returns:
            None
        """
        self._peer = peer
        self._invocation_metadata = invocation_metadata
        self._code = 200
        self._details = ""
        self._trailing_metadata = {}

        # We don't require connect-protocol-version header. connect-go provides an option
        # to require it but it's almost never used in practice.
        connect_protocol_version = self._invocation_metadata.get(
            "connect-protocol-version", ["1"]
        )[0]
        if connect_protocol_version != "1":
            raise ConnecpyServerException(
                code=Code.INVALID_ARGUMENT,
                message=f"connect-protocol-version must be '1': got '{connect_protocol_version}'",
            )
        self._connect_protocol_version = connect_protocol_version

        ctype = self._invocation_metadata.get("content-type", ["application/proto"])[0]
        if ctype not in ("application/proto", "application/json"):
            raise HTTPException(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                [("Accept-Post", "application/json, application/proto")],
            )
        self._content_type = ctype

        timeout_ms: Union[str, None] = invocation_metadata.get(
            "connect-timeout-ms", [None]
        )[0]
        if timeout_ms is None:
            self._timeout_sec = None
        else:
            self._timeout_sec = float(timeout_ms) / 1000.0
            self._start_time = time.time()

    async def abort(self, code, message):
        """
        Abort the current request with the given code and message.

        :param code: The HTTP status code to return.
        :param message: The error message to include in the response.
        :raises: exceptions.ConnecpyServerException
        """
        raise ConnecpyServerException(code=code, message=message)

    def code(self) -> int:
        """
        Get the status code associated with the context.

        Returns:
            int: The status code associated with the context.
        """
        return self._code

    def details(self) -> str:
        """
        Returns the details of the context.

        :return: The details of the context.
        :rtype: str
        """
        return self._details

    def invocation_metadata(self) -> Mapping[str, List[str]]:
        """
        Returns the invocation metadata associated with the context.

        :return: A mapping of metadata keys to lists of metadata values.
        """
        return self._invocation_metadata

    def content_type(self) -> str:
        """
        Returns the content type associated with the context.

        :return: The content type associated with the context.
        :rtype: str
        """
        return self._content_type

    def peer(self):
        """
        Returns the peer associated with the context.
        """
        return self._peer

    def set_code(self, code: int) -> None:
        """
        Set the status code for the context.

        Args:
            code (int): The code to set.

        Returns:
            None
        """
        self._code = code

    def set_details(self, details: str) -> None:
        """
        Set the details of the context.

        Args:
            details (str): The details to be set.

        Returns:
            None
        """
        self._details = details

    def response_headers(self) -> Iterable[tuple[str, str]]:
        """
        Returns the response headers that will be sent before the response.
        """
        if self._response_headers is None:
            return ()
        return self._response_headers

    def add_response_header(self, key: str, value: str) -> None:
        """
        Add a response header to send before the response.

        Args:
            key (str): The header key.
            value (str): The header value.

        Returns:
            None
        """
        if self._response_headers is None:
            self._response_headers = []
        self._response_headers.append((key, value))

    def response_trailers(self) -> Iterable[tuple[str, str]]:
        """
        Returns the response trailers that will be sent after the response.
        """
        if self._response_trailers is None:
            return ()
        return self._response_trailers

    def add_response_trailer(self, key: str, value: str) -> None:
        """
        Add a response trailer to send after the response.

        Args:
            key (str): The header key.
            value (str): The header value.

        Returns:
            None
        """
        if self._response_trailers is None:
            self._response_trailers = []
        self._response_trailers.append((key, value))

    def time_remaining(self) -> Union[float, None]:
        """
        Calculate the remaining time until the timeout.

        Returns:
            float | None: The remaining time in seconds, or None if no timeout is set.
        """
        if self._timeout_sec is None:
            return None
        return self._timeout_sec - (time.time() - self._start_time)


class ServerInterceptor(Protocol):
    """Interceptor for asynchronous Connecpy server."""

    async def intercept(
        self,
        method: Callable,
        request: Any,
        ctx: ServiceContext,
        method_name: str,
    ) -> Any: ...


@dataclass
class Endpoint(Generic[T, U]):
    """
    Represents an endpoint in a service.

    Attributes:
        service_name (str): The name of the service.
        name (str): The name of the endpoint.
        function (Callable[[T, context.ServiceContext], U]): The function that implements the endpoint.
        input (type): The type of the input parameter.
        output (type): The type of the output parameter.
        allowed_methods (list[str]): The allowed HTTP methods for the endpoint.
        _async_proc (Callable[[T, context.ServiceContext], U] | None): The asynchronous function that implements the endpoint.
    """

    service_name: str
    name: str
    function: Callable[
        [
            T,
            ServiceContext,
        ],
        U,
    ]
    input: type
    output: type
    allowed_methods: tuple[str, ...] = ("POST",)
    _async_proc: Union[
        Callable[
            [
                T,
                ServiceContext,
            ],
            U,
        ],
        None,
    ] = None
    _proc: Union[
        Callable[
            [
                T,
                ServiceContext,
            ],
            U,
        ],
        None,
    ] = None

    def make_async_proc(
        self,
        interceptors: Iterable[ServerInterceptor],
    ) -> Callable[[T, ServiceContext], U]:
        """
        Creates an asynchronous function that implements the endpoint.

        Args:
            interceptors (Iterable[interceptor.AsyncConnecpyServerInterceptor]): The interceptors to apply to the endpoint.

        Returns:
            Callable[[T, context.ServiceContext], U]: The asynchronous function that implements the endpoint.
        """
        if self._async_proc is not None:
            return self._async_proc

        method_name = self.name
        reversed_interceptors = reversed(tuple(interceptors))
        self._async_proc = reduce(
            lambda acc, interceptor: _apply_interceptor(interceptor, acc, method_name),
            reversed_interceptors,
            asynchronize(self.function),
        )  # type: ignore

        return self._async_proc  # type: ignore

    def make_proc(
        self,
    ) -> Callable[[T, ServiceContext], U]:
        """
        Creates an asynchronous function that implements the endpoint.

        Args:
            interceptors (Tuple[interceptor.AsyncConnecpyServerInterceptor, ...]): The interceptors to apply to the endpoint.

        Returns:
            Callable[[T, context.ServiceContext], U]: The asynchronous function that implements the endpoint.
        """
        if self._proc is not None:
            return self._proc

        self._proc = self.function

        return self._proc  # type: ignore


def thread_pool_runner(func):
    async def run(request, ctx: ServiceContext):
        return await asyncio.to_thread(func, request, ctx)

    return run


def asynchronize(func) -> Callable:
    """
    Decorator that converts a synchronous function into an asynchronous function.

    If the input function is already a coroutine function, it is returned as is.
    Otherwise, it is wrapped in a thread pool runner to execute it asynchronously.

    Args:
        func: The synchronous function to be converted.

    Returns:
        The converted asynchronous function.

    """
    if asyncio.iscoroutinefunction(func):
        return func
    else:
        return thread_pool_runner(func)


def _apply_interceptor(
    interceptor: ServerInterceptor, method: Callable, method_name: str
):
    async def run_interceptor(request: Any, ctx: ServiceContext) -> Any:
        return await interceptor.intercept(method, request, ctx, method_name)

    return run_interceptor
