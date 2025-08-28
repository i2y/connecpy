"""Type definitions for the Transport API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import TypeAlias

    import grpc
    import grpc.aio

    GrpcChannelCredentials: TypeAlias = grpc.ChannelCredentials
    GrpcCompression: TypeAlias = grpc.Compression
    GrpcChannel: TypeAlias = grpc.Channel | grpc.aio.Channel
    GrpcClientInterceptor: TypeAlias = grpc.aio.ClientInterceptor
    GrpcInterceptor: TypeAlias = (
        grpc.UnaryUnaryClientInterceptor | grpc.aio.ClientInterceptor
    )
    GrpcChannelOptions: TypeAlias = list[tuple[str, Any]]
else:
    # Runtime fallback when grpcio is not installed
    GrpcChannelCredentials: TypeAlias = Any  # type: ignore[misc]
    GrpcCompression: TypeAlias = Any  # type: ignore[misc]
    GrpcChannel: TypeAlias = Any  # type: ignore[misc]
    GrpcClientInterceptor: TypeAlias = Any  # type: ignore[misc]
    GrpcInterceptor: TypeAlias = Any  # type: ignore[misc]
    GrpcChannelOptions: TypeAlias = list[tuple[str, Any]]  # type: ignore[misc]
