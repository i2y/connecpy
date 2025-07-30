import asyncio
import time
from dataclasses import dataclass
from functools import reduce
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Protocol,
    TypeVar,
    Union,
)

from .code import Code
from .exceptions import ConnecpyException
from .headers import Headers

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

    _response_headers: Headers | None
    _response_trailers: Headers | None

    def __init__(self, request_headers: Headers):
        """
        Initialize a Context object.
        """
        self._request_headers = request_headers
        self._response_headers = None
        self._response_trailers = None

        # We don't require connect-protocol-version header. connect-go provides an option
        # to require it but it's almost never used in practice.
        connect_protocol_version = self._request_headers.get(
            "connect-protocol-version", "1"
        )
        if connect_protocol_version != "1":
            raise ConnecpyException(
                Code.INVALID_ARGUMENT,
                f"connect-protocol-version must be '1': got '{connect_protocol_version}'",
            )
        self._connect_protocol_version = connect_protocol_version

        timeout_ms: Union[str, None] = request_headers.get("connect-timeout-ms", None)
        if timeout_ms is None:
            self._end_time = None
        else:
            self._end_time = time.monotonic() + float(timeout_ms) / 1000.0

    def request_headers(self) -> Headers:
        """
        Returns the request headers associated with the context.

        :return: A mapping of header keys to lists of header values.
        """
        return self._request_headers

    def response_headers(self) -> Headers:
        """
        Returns the response headers that will be sent before the response.
        """
        if self._response_headers is None:
            self._response_headers = Headers()
        return self._response_headers

    def clear_response_headers(self) -> None:
        """
        Clears the response headers that will be sent before the response.
        """
        self._response_headers = None

    def response_trailers(self) -> Headers:
        """
        Returns the response trailers that will be sent after the response.
        """
        if self._response_trailers is None:
            self._response_trailers = Headers()
        return self._response_trailers

    def timeout_ms(self) -> float | None:
        """
        Calculate the remaining time until the timeout.

        Returns:
            float | None: The remaining time in milliseconds, or None if no timeout is set.
        """
        if self._end_time is None:
            return None
        return (self._end_time - time.monotonic()) * 1000.0


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
