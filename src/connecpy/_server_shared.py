from dataclasses import dataclass
from http import HTTPStatus
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Iterator,
    TypeVar,
)

from ._protocol import (
    CONNECT_HEADER_PROTOCOL_VERSION,
    CONNECT_HEADER_TIMEOUT,
    CONNECT_PROTOCOL_VERSION,
    HTTPException,
)
from .code import Code
from .exceptions import ConnecpyException
from .method import IdempotencyLevel, MethodInfo
from .request import Headers, RequestContext

REQ = TypeVar("REQ")
RES = TypeVar("RES")
T = TypeVar("T")
U = TypeVar("U")


@dataclass(kw_only=True, frozen=True, slots=True)
class Endpoint(Generic[REQ, RES]):
    """
    Represents an endpoint in a service.

    Attributes:
        service_name (str): The name of the service.
        name (str): The name of the endpoint.
        function (Callable[[T, context.RequestContext[T, U]], Awaitable[U]]): The function that implements the endpoint.
        input (type): The type of the input parameter.
        output (type): The type of the output parameter.
        allowed_methods (list[str]): The allowed HTTP methods for the endpoint.
        _async_proc (Callable[[T, context.RequestContext[T, U]], U] | None): The asynchronous function that implements the endpoint.
    """

    method: MethodInfo[REQ, RES]

    @staticmethod
    def unary(
        method: MethodInfo[T, U],
        function: Callable[
            [
                T,
                RequestContext[T, U],
            ],
            Awaitable[U],
        ],
    ) -> "Endpoint[T, U]":
        return EndpointUnary(method=method, function=function)

    @staticmethod
    def client_stream(
        method: MethodInfo[T, U],
        function: Callable[
            [
                AsyncIterator[T],
                RequestContext[T, U],
            ],
            Awaitable[U],
        ],
    ) -> "Endpoint[T, U]":
        return EndpointClientStream(method=method, function=function)

    @staticmethod
    def server_stream(
        method: MethodInfo[T, U],
        function: Callable[
            [
                T,
                RequestContext[T, U],
            ],
            AsyncIterator[U],
        ],
    ) -> "Endpoint[T, U]":
        return EndpointServerStream(method=method, function=function)

    @staticmethod
    def bidi_stream(
        method: MethodInfo[T, U],
        function: Callable[
            [
                AsyncIterator[T],
                RequestContext[T, U],
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
            RequestContext[REQ, RES],
        ],
        Awaitable[RES],
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointClientStream(Endpoint[REQ, RES]):
    function: Callable[
        [
            AsyncIterator[REQ],
            RequestContext[REQ, RES],
        ],
        Awaitable[RES],
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointServerStream(Endpoint[REQ, RES]):
    function: Callable[
        [
            REQ,
            RequestContext[REQ, RES],
        ],
        AsyncIterator[RES],
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointBidiStream(Endpoint[REQ, RES]):
    function: Callable[
        [
            AsyncIterator[REQ],
            RequestContext[REQ, RES],
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
        function (Callable[[T, context.RequestContext[T, U]], U]): The function that implements the endpoint.
        input (type): The type of the input parameter.
        output (type): The type of the output parameter.
        allowed_methods (list[str]): The allowed HTTP methods for the endpoint.
        _async_proc (Callable[[T, context.RequestContext[T, U]], U] | None): The asynchronous function that implements the endpoint.
    """

    method: MethodInfo[REQ, RES]

    @staticmethod
    def unary(
        *,
        method: MethodInfo[T, U],
        function: Callable[
            [
                T,
                RequestContext[T, U],
            ],
            U,
        ],
    ) -> "EndpointSync[T, U]":
        return EndpointUnarySync(method=method, function=function)

    @staticmethod
    def client_stream(
        *,
        method: MethodInfo[T, U],
        function: Callable[
            [
                Iterator[T],
                RequestContext[T, U],
            ],
            U,
        ],
    ) -> "EndpointSync[T, U]":
        return EndpointClientStreamSync(method=method, function=function)

    @staticmethod
    def server_stream(
        *,
        method: MethodInfo[T, U],
        function: Callable[
            [
                T,
                RequestContext[T, U],
            ],
            Iterator[U],
        ],
    ) -> "EndpointSync[T, U]":
        return EndpointServerStreamSync(method=method, function=function)

    @staticmethod
    def bidi_stream(
        method: MethodInfo[T, U],
        function: Callable[
            [
                Iterator[T],
                RequestContext[T, U],
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
            RequestContext[REQ, RES],
        ],
        RES,
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointClientStreamSync(EndpointSync[REQ, RES]):
    function: Callable[
        [
            Iterator[REQ],
            RequestContext[REQ, RES],
        ],
        RES,
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointServerStreamSync(EndpointSync[REQ, RES]):
    function: Callable[
        [
            REQ,
            RequestContext[REQ, RES],
        ],
        Iterator[RES],
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointBidiStreamSync(EndpointSync[REQ, RES]):
    function: Callable[
        [
            Iterator[REQ],
            RequestContext[REQ, RES],
        ],
        Iterator[RES],
    ]


def create_request_context(
    method: MethodInfo[REQ, RES], http_method: str, headers: Headers
) -> RequestContext[REQ, RES]:
    if method.idempotency_level == IdempotencyLevel.NO_SIDE_EFFECTS:
        if http_method not in ("GET", "POST"):
            raise HTTPException(
                HTTPStatus.METHOD_NOT_ALLOWED,
                [("allow", "GET, POST")],
            )
    elif http_method != "POST":
        raise HTTPException(
            HTTPStatus.METHOD_NOT_ALLOWED,
            [("allow", "POST")],
        )

    # We don't require connect-protocol-version header. connect-go provides an option
    # to require it but it's almost never used in practice.
    connect_protocol_version = headers.get(
        CONNECT_HEADER_PROTOCOL_VERSION, CONNECT_PROTOCOL_VERSION
    )
    if connect_protocol_version != CONNECT_PROTOCOL_VERSION:
        raise ConnecpyException(
            Code.INVALID_ARGUMENT,
            f"connect-protocol-version must be '1': got '{connect_protocol_version}'",
        )

    timeout_header = headers.get(CONNECT_HEADER_TIMEOUT)
    if timeout_header:
        if len(timeout_header) > 10:
            raise ConnecpyException(
                Code.INVALID_ARGUMENT,
                f"Invalid timeout header: '{timeout_header} has >10 digits",
            )
        try:
            timeout_ms = int(timeout_header)
        except ValueError as e:
            raise ConnecpyException(
                Code.INVALID_ARGUMENT,
                f"Invalid timeout header: '{timeout_header}'",
            ) from e
    else:
        timeout_ms = None
    return RequestContext(
        method=method,
        http_method=http_method,
        request_headers=headers,
        timeout_ms=timeout_ms,
    )


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
