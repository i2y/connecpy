"""Type definitions for the Transport API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    import grpc
    import grpc.aio


# Type variables for request/response messages
RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")

# gRPC types (only used when grpcio is installed)
try:
    import grpc
    import grpc.aio

    GrpcChannelCredentials = grpc.ChannelCredentials
    GrpcCompression = grpc.Compression
    GrpcChannel = grpc.Channel | grpc.aio.Channel
    GrpcClientInterceptor = grpc.aio.ClientInterceptor
    GrpcInterceptor = grpc.UnaryUnaryClientInterceptor | grpc.aio.ClientInterceptor
    GrpcChannelOptions = list[tuple[str, Any]]
except ImportError:
    # Fallback types when grpcio is not installed
    GrpcChannelCredentials = Any  # type: ignore[misc]
    GrpcCompression = Any  # type: ignore[misc]
    GrpcChannel = Any  # type: ignore[misc]
    GrpcClientInterceptor = Any  # type: ignore[misc]
    GrpcInterceptor = Any  # type: ignore[misc]
    GrpcChannelOptions = list[tuple[str, Any]]  # type: ignore[misc]


class GrpcStubProtocol(Protocol):
    """Protocol for gRPC stubs."""

    def __call__(self, channel: GrpcChannel) -> GrpcStubProtocol:
        """Create a stub instance with the channel."""
        ...


class ConnectClientProtocol(Protocol):
    """Protocol for Connect clients."""

    def execute_unary(
        self,
        request: RequestT,
        method: Any,
        *,
        headers: Any = None,
        timeout_ms: int | None = None,
        use_get: bool = False,
    ) -> ResponseT:
        """Execute a unary RPC."""
        ...

    def execute_server_stream(
        self,
        request: RequestT,
        method: Any,
        *,
        headers: Any = None,
        timeout_ms: int | None = None,
    ) -> Iterator[ResponseT]:
        """Execute a server streaming RPC."""
        ...

    def execute_client_stream(
        self,
        request: Iterator[RequestT],
        method: Any,
        *,
        headers: Any = None,
        timeout_ms: int | None = None,
    ) -> ResponseT:
        """Execute a client streaming RPC."""
        ...

    def execute_bidirectional_stream(
        self,
        request: Iterator[RequestT],
        method: Any,
        *,
        headers: Any = None,
        timeout_ms: int | None = None,
    ) -> Iterator[ResponseT]:
        """Execute a bidirectional streaming RPC."""
        ...

    def close(self) -> None:
        """Close the client."""
        ...


class AsyncConnectClientProtocol(Protocol):
    """Protocol for async Connect clients."""

    async def execute_unary(
        self,
        request: RequestT,
        method: Any,
        *,
        headers: Any = None,
        timeout_ms: int | None = None,
        use_get: bool = False,
    ) -> ResponseT:
        """Execute a unary RPC."""
        ...

    async def execute_server_stream(
        self,
        request: RequestT,
        method: Any,
        *,
        headers: Any = None,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[ResponseT]:
        """Execute a server streaming RPC."""
        ...

    async def execute_client_stream(
        self,
        request: AsyncIterator[RequestT],
        method: Any,
        *,
        headers: Any = None,
        timeout_ms: int | None = None,
    ) -> ResponseT:
        """Execute a client streaming RPC."""
        ...

    async def execute_bidirectional_stream(
        self,
        request: AsyncIterator[RequestT],
        method: Any,
        *,
        headers: Any = None,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[ResponseT]:
        """Execute a bidirectional streaming RPC."""
        ...

    async def close(self) -> None:
        """Close the client."""
        ...
