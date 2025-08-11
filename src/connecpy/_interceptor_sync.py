from typing import (
    Callable,
    Generic,
    Iterable,
    Iterator,
    Protocol,
    Sequence,
    TypeVar,
    runtime_checkable,
)

from .request import RequestContext

REQ = TypeVar("REQ")
RES = TypeVar("RES")
T = TypeVar("T")


@runtime_checkable
class UnaryInterceptorSync(Protocol):
    def intercept_unary_sync(
        self,
        next: Callable[[REQ, RequestContext], RES],
        request: REQ,
        ctx: RequestContext,
    ) -> RES:
        """Intercepts a unary RPC."""
        ...


@runtime_checkable
class ClientStreamInterceptorSync(Protocol):
    def intercept_client_stream_sync(
        self,
        next: Callable[[Iterator[REQ], RequestContext], RES],
        request: Iterator[REQ],
        ctx: RequestContext,
    ) -> RES:
        """Intercepts a client-streaming RPC."""
        ...


@runtime_checkable
class ServerStreamInterceptorSync(Protocol):
    def intercept_server_stream_sync(
        self,
        next: Callable[[REQ, RequestContext], Iterator[RES]],
        request: REQ,
        ctx: RequestContext,
    ) -> Iterator[RES]:
        """Intercepts a server-streaming RPC."""
        ...


@runtime_checkable
class BidiStreamInterceptorSync(Protocol):
    def intercept_bidi_stream_sync(
        self,
        next: Callable[[Iterator[REQ], RequestContext], Iterator[RES]],
        request: Iterator[REQ],
        ctx: RequestContext,
    ) -> Iterator[RES]:
        """Intercepts a bidirectional-streaming RPC."""
        ...


@runtime_checkable
class MetadataInterceptorSync(Protocol[T]):
    """An interceptor that can be applied to any type of method, only having
    access to metadata such as headers and trailers.

    To access request and response bodies of a method, instead use an interceptor
    corresponding to the type of method such as UnaryInterceptor.
    """

    def on_start_sync(self, ctx: RequestContext) -> T:
        """Called when the RPC starts. The return value will be passed to on_end as-is.
        For example, if measuring RPC invocation time, on_start may return the current
        time.
        """
        ...

    def on_end_sync(self, token: T, ctx: RequestContext) -> None:
        """Called when the RPC ends."""
        return


InterceptorSync = (
    UnaryInterceptorSync
    | ClientStreamInterceptorSync
    | ServerStreamInterceptorSync
    | BidiStreamInterceptorSync
    | MetadataInterceptorSync
)


class MetadataInterceptorInvokerSync(Generic[T]):
    _delegate: MetadataInterceptorSync[T]

    def __init__(self, delegate: MetadataInterceptorSync[T]) -> None:
        self._delegate = delegate

    def intercept_unary_sync(
        self,
        next: Callable[[REQ, RequestContext], RES],
        request: REQ,
        ctx: RequestContext,
    ) -> RES:
        token = self._delegate.on_start_sync(ctx)
        try:
            return next(request, ctx)
        finally:
            self._delegate.on_end_sync(token, ctx)

    def intercept_client_stream_sync(
        self,
        next: Callable[[Iterator[REQ], RequestContext], RES],
        request: Iterator[REQ],
        ctx: RequestContext,
    ) -> RES:
        token = self._delegate.on_start_sync(ctx)
        try:
            return next(request, ctx)
        finally:
            self._delegate.on_end_sync(token, ctx)

    def intercept_server_stream_sync(
        self,
        next: Callable[[REQ, RequestContext], Iterator[RES]],
        request: REQ,
        ctx: RequestContext,
    ) -> Iterator[RES]:
        token = self._delegate.on_start_sync(ctx)
        try:
            yield from next(request, ctx)
        finally:
            self._delegate.on_end_sync(token, ctx)

    def intercept_bidi_stream_sync(
        self,
        next: Callable[[Iterator[REQ], RequestContext], Iterator[RES]],
        request: Iterator[REQ],
        ctx: RequestContext,
    ) -> Iterator[RES]:
        token = self._delegate.on_start_sync(ctx)
        try:
            yield from next(request, ctx)
        finally:
            self._delegate.on_end_sync(token, ctx)


def resolve_interceptors(
    interceptors: Iterable[InterceptorSync],
) -> Sequence[
    UnaryInterceptorSync
    | ClientStreamInterceptorSync
    | ServerStreamInterceptorSync
    | BidiStreamInterceptorSync
]:
    return [
        MetadataInterceptorInvokerSync(interceptor)
        if isinstance(interceptor, MetadataInterceptorSync)
        else interceptor
        for interceptor in interceptors
    ]
