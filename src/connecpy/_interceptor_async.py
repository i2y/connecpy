from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Iterable,
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
class UnaryInterceptor(Protocol):
    async def intercept_unary(
        self,
        next: Callable[[REQ, RequestContext], Awaitable[RES]],
        request: REQ,
        ctx: RequestContext,
    ) -> RES:
        """Intercepts a unary RPC."""
        ...


@runtime_checkable
class ClientStreamInterceptor(Protocol):
    async def intercept_client_stream(
        self,
        next: Callable[[AsyncIterator[REQ], RequestContext], Awaitable[RES]],
        request: AsyncIterator[REQ],
        ctx: RequestContext,
    ) -> RES:
        """Intercepts a client-streaming RPC."""
        ...


@runtime_checkable
class ServerStreamInterceptor(Protocol):
    def intercept_server_stream(
        self,
        next: Callable[[REQ, RequestContext], AsyncIterator[RES]],
        request: REQ,
        ctx: RequestContext,
    ) -> AsyncIterator[RES]:
        """Intercepts a server-streaming RPC."""
        ...


@runtime_checkable
class BidiStreamInterceptor(Protocol):
    def intercept_bidi_stream(
        self,
        next: Callable[[AsyncIterator[REQ], RequestContext], AsyncIterator[RES]],
        request: AsyncIterator[REQ],
        ctx: RequestContext,
    ) -> AsyncIterator[RES]:
        """Intercepts a bidirectional-streaming RPC."""
        ...


@runtime_checkable
class MetadataInterceptor(Protocol[T]):
    """An interceptor that can be applied to any type of method, only having
    access to metadata such as headers and trailers.

    To access request and response bodies of a method, instead use an interceptor
    corresponding to the type of method such as UnaryInterceptor.
    """

    async def on_start(self, ctx: RequestContext) -> T:
        """Called when the RPC starts. The return value will be passed to on_end as-is.
        For example, if measuring RPC invocation time, on_start may return the current
        time.
        """
        ...

    async def on_end(self, token: T, ctx: RequestContext) -> None:
        """Called when the RPC ends."""
        return


Interceptor = (
    UnaryInterceptor
    | ClientStreamInterceptor
    | ServerStreamInterceptor
    | BidiStreamInterceptor
    | MetadataInterceptor
)


class MetadataInterceptorInvoker(Generic[T]):
    _delegate: MetadataInterceptor[T]

    def __init__(self, delegate: MetadataInterceptor[T]) -> None:
        self._delegate = delegate

    async def intercept_unary(
        self,
        next: Callable[[REQ, RequestContext], Awaitable[RES]],
        request: REQ,
        ctx: RequestContext,
    ) -> RES:
        token = await self._delegate.on_start(ctx)
        try:
            return await next(request, ctx)
        finally:
            await self._delegate.on_end(token, ctx)

    async def intercept_client_stream(
        self,
        next: Callable[[AsyncIterator[REQ], RequestContext], Awaitable[RES]],
        request: AsyncIterator[REQ],
        ctx: RequestContext,
    ) -> RES:
        token = await self._delegate.on_start(ctx)
        try:
            return await next(request, ctx)
        finally:
            await self._delegate.on_end(token, ctx)

    async def intercept_server_stream(
        self,
        next: Callable[[REQ, RequestContext], AsyncIterator[RES]],
        request: REQ,
        ctx: RequestContext,
    ) -> AsyncIterator[RES]:
        token = await self._delegate.on_start(ctx)
        try:
            async for response in next(request, ctx):
                yield response
        finally:
            await self._delegate.on_end(token, ctx)

    async def intercept_bidi_stream(
        self,
        next: Callable[[AsyncIterator[REQ], RequestContext], AsyncIterator[RES]],
        request: AsyncIterator[REQ],
        ctx: RequestContext,
    ) -> AsyncIterator[RES]:
        token = await self._delegate.on_start(ctx)
        try:
            async for response in next(request, ctx):
                yield response
        finally:
            await self._delegate.on_end(token, ctx)


def resolve_interceptors(
    interceptors: Iterable[Interceptor],
) -> Sequence[
    UnaryInterceptor
    | ClientStreamInterceptor
    | ServerStreamInterceptor
    | BidiStreamInterceptor
]:
    return [
        MetadataInterceptorInvoker(interceptor)
        if isinstance(interceptor, MetadataInterceptor)
        else interceptor
        for interceptor in interceptors
    ]
