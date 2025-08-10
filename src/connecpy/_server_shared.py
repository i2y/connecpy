import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Iterator,
    TypeVar,
    Union,
)

from ._protocol import HTTPException
from .code import Code
from .exceptions import ConnecpyException
from .headers import Headers
from .method import IdempotencyLevel, MethodInfo

REQ = TypeVar("REQ")
RES = TypeVar("RES")
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

    _method: MethodInfo
    _request_headers: Headers
    _response_headers: Headers | None
    _response_trailers: Headers | None

    def __init__(self, method: MethodInfo, request_headers: Headers):
        """
        Initialize a Context object.
        """
        self._method = method
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

    def method(self) -> MethodInfo:
        """Information about the RPC method being invoked."""
        return self._method

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


@dataclass(kw_only=True, frozen=True, slots=True)
class Endpoint(Generic[REQ, RES]):
    """
    Represents an endpoint in a service.

    Attributes:
        service_name (str): The name of the service.
        name (str): The name of the endpoint.
        function (Callable[[T, context.ServiceContext], Awaitable[U]]): The function that implements the endpoint.
        input (type): The type of the input parameter.
        output (type): The type of the output parameter.
        allowed_methods (list[str]): The allowed HTTP methods for the endpoint.
        _async_proc (Callable[[T, context.ServiceContext], U] | None): The asynchronous function that implements the endpoint.
    """

    method: MethodInfo[REQ, RES]

    @staticmethod
    def unary(
        method: MethodInfo,
        function: Callable[
            [
                T,
                ServiceContext,
            ],
            Awaitable[U],
        ],
    ) -> "Endpoint[T, U]":
        return EndpointUnary(method=method, function=function)

    @staticmethod
    def client_stream(
        method: MethodInfo,
        function: Callable[
            [
                AsyncIterator[T],
                ServiceContext,
            ],
            Awaitable[U],
        ],
    ) -> "Endpoint[T, U]":
        return EndpointClientStream(method=method, function=function)

    @staticmethod
    def server_stream(
        method: MethodInfo,
        function: Callable[
            [
                T,
                ServiceContext,
            ],
            AsyncIterator[U],
        ],
    ) -> "Endpoint[T, U]":
        return EndpointServerStream(method=method, function=function)

    @staticmethod
    def bidi_stream(
        method: MethodInfo,
        function: Callable[
            [
                AsyncIterator[T],
                ServiceContext,
            ],
            AsyncIterator[U],
        ],
    ) -> "Endpoint[T, U]":
        return EndpointBidiStream(method=method, function=function)


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointUnary(Endpoint[REQ, RES]):
    function: Callable[
        [
            REQ,
            ServiceContext,
        ],
        Awaitable[RES],
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointClientStream(Endpoint[REQ, RES]):
    function: Callable[
        [
            AsyncIterator[REQ],
            ServiceContext,
        ],
        Awaitable[RES],
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointServerStream(Endpoint[REQ, RES]):
    function: Callable[
        [
            REQ,
            ServiceContext,
        ],
        AsyncIterator[RES],
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointBidiStream(Endpoint[REQ, RES]):
    function: Callable[
        [
            AsyncIterator[REQ],
            ServiceContext,
        ],
        AsyncIterator[RES],
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointSync(Generic[REQ, RES]):
    """
    Represents a sync endpoint in a service.

    Attributes:
        service_name (str): The name of the service.
        name (str): The name of the endpoint.
        function (Callable[[T, context.ServiceContext], U]): The function that implements the endpoint.
        input (type): The type of the input parameter.
        output (type): The type of the output parameter.
        allowed_methods (list[str]): The allowed HTTP methods for the endpoint.
        _async_proc (Callable[[T, context.ServiceContext], U] | None): The asynchronous function that implements the endpoint.
    """

    method: MethodInfo[REQ, RES]

    @staticmethod
    def unary(
        *,
        method: MethodInfo,
        function: Callable[
            [
                T,
                ServiceContext,
            ],
            U,
        ],
    ) -> "EndpointSync[T, U]":
        return EndpointUnarySync(method=method, function=function)

    @staticmethod
    def client_stream(
        *,
        method: MethodInfo,
        function: Callable[
            [
                Iterator[T],
                ServiceContext,
            ],
            U,
        ],
    ) -> "EndpointSync[T, U]":
        return EndpointClientStreamSync(method=method, function=function)

    @staticmethod
    def server_stream(
        *,
        method: MethodInfo,
        function: Callable[
            [
                T,
                ServiceContext,
            ],
            Iterator[U],
        ],
    ) -> "EndpointSync[T, U]":
        return EndpointServerStreamSync(method=method, function=function)

    @staticmethod
    def bidi_stream(
        method: MethodInfo,
        function: Callable[
            [
                Iterator[T],
                ServiceContext,
            ],
            Iterator[U],
        ],
    ) -> "EndpointSync[T, U]":
        return EndpointBidiStreamSync(method=method, function=function)


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointUnarySync(EndpointSync[REQ, RES]):
    function: Callable[
        [
            REQ,
            ServiceContext,
        ],
        RES,
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointClientStreamSync(EndpointSync[REQ, RES]):
    function: Callable[
        [
            Iterator[REQ],
            ServiceContext,
        ],
        RES,
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointServerStreamSync(EndpointSync[REQ, RES]):
    function: Callable[
        [
            REQ,
            ServiceContext,
        ],
        Iterator[RES],
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointBidiStreamSync(EndpointSync[REQ, RES]):
    function: Callable[
        [
            Iterator[REQ],
            ServiceContext,
        ],
        Iterator[RES],
    ]


def verify_http_method(http_method: str, method: MethodInfo) -> None:
    if method.idempotency_level == IdempotencyLevel.NO_SIDE_EFFECTS:
        if http_method not in ("GET", "POST"):
            raise HTTPException(
                HTTPStatus.METHOD_NOT_ALLOWED,
                [("allow", "GET, POST")],
            )
        return
    if http_method != "POST":
        raise HTTPException(
            HTTPStatus.METHOD_NOT_ALLOWED,
            [("allow", "POST")],
        )
