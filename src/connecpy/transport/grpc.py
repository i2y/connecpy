"""gRPC protocol transport implementation."""

from __future__ import annotations

import time
import types
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException

from .base import CallOptions, RetryPolicy
from .types import (
    GrpcChannelCredentials,
    GrpcChannelOptions,
    GrpcCompression,
    GrpcInterceptor,
)

if TYPE_CHECKING:
    from connecpy.method import MethodInfo

try:
    import grpc

    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    grpc = None  # type: ignore[assignment]


class GrpcTransport:
    """Transport implementation using the gRPC protocol.

    This transport uses grpcio to communicate with gRPC servers.
    Requires the 'grpcio' package to be installed.
    """

    def __init__(
        self,
        target: str,
        *,
        credentials: GrpcChannelCredentials | None = None,
        options: GrpcChannelOptions | None = None,
        compression: GrpcCompression | str | None = None,
        interceptors: list[GrpcInterceptor] | None = None,
    ) -> None:
        """Initialize the gRPC transport with all grpc channel parameters.

        Args:
            target: The server address (e.g., "localhost:50051")
            credentials: Channel credentials for secure connections (None for insecure)
            options: List of gRPC channel options as key-value tuples
            compression: Default compression algorithm
            interceptors: List of client interceptors
        """
        if not GRPC_AVAILABLE:
            msg = (
                "grpcio is required for GrpcTransport. "
                "Install it with: pip install connecpy[grpc]"
            )
            raise ImportError(msg)

        self._target = (
            target.replace("grpc://", "").replace("https://", "").replace("http://", "")
        )

        # Store parameters for later use
        self.credentials = credentials
        self.options = options or []
        self.compression = compression
        self.interceptors = interceptors or []

        # Add compression to options if specified
        channel_options = list(self.options)
        if compression is not None:
            channel_options.append(
                (
                    "grpc.default_compression_algorithm",
                    compression
                    if isinstance(compression, int)
                    else self._get_grpc_compression(str(compression)),
                )
            )

        # Create gRPC channel
        if credentials is not None:
            self._channel = grpc.secure_channel(  # type: ignore[attr-defined]
                self._target, credentials, options=channel_options
            )
        else:
            self._channel = grpc.insecure_channel(self._target, options=channel_options)  # type: ignore[attr-defined]

        # Apply interceptors if provided
        if self.interceptors:
            self._channel = grpc.intercept_channel(self._channel, *self.interceptors)  # type: ignore[attr-defined]

        # Cache for stubs
        self._stubs = {}

    def unary_unary(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Any:
        """Execute a unary-unary RPC with optional retry."""
        call_options = call_options or CallOptions()

        def execute() -> Any:
            stub = self._get_or_create_stub(method, "unary_unary")
            metadata = self._prepare_metadata(call_options)
            timeout = (
                call_options.timeout_ms / 1000.0 if call_options.timeout_ms else None
            )

            return stub(request, metadata=metadata, timeout=timeout)

        if call_options.retry_policy:
            return self._execute_with_retry(execute, call_options.retry_policy)
        return execute()

    def unary_stream(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Iterator[Any]:
        """Execute a unary-stream RPC."""
        call_options = call_options or CallOptions()
        stub = self._get_or_create_stub(method, "unary_stream")
        metadata = self._prepare_metadata(call_options)
        timeout = call_options.timeout_ms / 1000.0 if call_options.timeout_ms else None

        try:
            yield from stub(request, metadata=metadata, timeout=timeout)
        except grpc.RpcError as e:  # type: ignore[attr-defined]
            # Convert gRPC error to ConnecpyException for consistency
            code = self._grpc_status_to_code(e.code())
            msg = f"gRPC stream error: {e.details() or 'Unknown error'}"
            raise ConnecpyException(code, msg) from e

    def stream_unary(
        self,
        method: MethodInfo,
        stream: Iterator[Any],
        call_options: CallOptions | None = None,
    ) -> Any:
        """Execute a stream-unary RPC with optional retry."""
        call_options = call_options or CallOptions()

        def execute() -> Any:
            stub = self._get_or_create_stub(method, "stream_unary")
            metadata = self._prepare_metadata(call_options)
            timeout = (
                call_options.timeout_ms / 1000.0 if call_options.timeout_ms else None
            )

            return stub(stream, metadata=metadata, timeout=timeout)

        if call_options.retry_policy:
            return self._execute_with_retry(execute, call_options.retry_policy)
        return execute()

    def stream_stream(
        self,
        method: MethodInfo,
        stream: Iterator[Any],
        call_options: CallOptions | None = None,
    ) -> Iterator[Any]:
        """Execute a stream-stream RPC."""
        call_options = call_options or CallOptions()
        stub = self._get_or_create_stub(method, "stream_stream")
        metadata = self._prepare_metadata(call_options)
        timeout = call_options.timeout_ms / 1000.0 if call_options.timeout_ms else None

        try:
            yield from stub(stream, metadata=metadata, timeout=timeout)
        except grpc.RpcError as e:  # type: ignore[attr-defined]
            # Convert gRPC error to ConnecpyException for consistency
            code = self._grpc_status_to_code(e.code())
            msg = f"gRPC bidirectional stream error: {e.details() or 'Unknown error'}"
            raise ConnecpyException(code, msg) from e

    def close(self) -> None:
        """Close the gRPC channel."""
        self._channel.close()

    def __enter__(self) -> Self:
        """Enter the context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit the context manager and close resources."""
        self.close()

    def _get_or_create_stub(self, method: MethodInfo, rpc_type: str) -> Any:
        """Get or create a gRPC stub for the given method."""
        # Build the full method name
        full_method_name = f"/{method.service_name}/{method.name}"

        if full_method_name not in self._stubs:
            # Create the appropriate stub based on RPC type
            if rpc_type == "unary_unary":
                self._stubs[full_method_name] = self._channel.unary_unary(
                    full_method_name,
                    request_serializer=lambda x: x.SerializeToString(),  # type: ignore[attr-defined]
                    response_deserializer=lambda x: method.output().FromString(x),
                )
            elif rpc_type == "unary_stream":
                self._stubs[full_method_name] = self._channel.unary_stream(
                    full_method_name,
                    request_serializer=lambda x: x.SerializeToString(),  # type: ignore[attr-defined]
                    response_deserializer=lambda x: method.output().FromString(x),
                )
            elif rpc_type == "stream_unary":
                self._stubs[full_method_name] = self._channel.stream_unary(
                    full_method_name,
                    request_serializer=lambda x: x.SerializeToString(),  # type: ignore[attr-defined]
                    response_deserializer=lambda x: method.output().FromString(x),
                )
            elif rpc_type == "stream_stream":
                self._stubs[full_method_name] = self._channel.stream_stream(
                    full_method_name,
                    request_serializer=lambda x: x.SerializeToString(),  # type: ignore[attr-defined]
                    response_deserializer=lambda x: method.output().FromString(x),
                )

        return self._stubs[full_method_name]

    def _prepare_metadata(self, call_options: CallOptions) -> list[tuple[str, str]]:
        """Prepare gRPC metadata from options."""
        metadata = []
        for key, value in call_options.headers.items():
            metadata.append((key.lower(), value))
        return metadata

    def _merge_options(self, call_options: CallOptions | None) -> CallOptions:
        """Merge call options with transport defaults."""
        # Since we no longer have default TransportOptions,
        # just return the provided options or an empty one
        return call_options or CallOptions()

    def _execute_with_retry(self, func: Any, retry_policy: RetryPolicy) -> Any:
        """Execute a function with retry logic."""

        attempt = 0
        backoff_ms = retry_policy.initial_backoff_ms

        while attempt < retry_policy.max_attempts:
            try:
                return func()
            except grpc.RpcError as e:  # type: ignore[attr-defined]
                # Convert gRPC error to ConnecpyException for consistency
                code = self._grpc_status_to_code(e.code())

                # Check if the error is retryable
                if (
                    retry_policy.retryable_codes is None
                    or code not in retry_policy.retryable_codes
                ):
                    raise ConnecpyException(code, e.details() or "gRPC error") from e

                # Check if we've exhausted retries
                if attempt >= retry_policy.max_attempts - 1:
                    raise ConnecpyException(code, e.details() or "gRPC error") from e

                # Wait before retry with exponential backoff
                time.sleep(backoff_ms / 1000.0)
                backoff_ms = min(
                    int(backoff_ms * retry_policy.backoff_multiplier),
                    retry_policy.max_backoff_ms,
                )
                attempt += 1

        # Should never reach here
        msg = "Retry loop exited unexpectedly"
        raise RuntimeError(msg)

    def _grpc_status_to_code(self, grpc_status: grpc.StatusCode) -> Code:  # type: ignore[name-defined]
        """Convert gRPC status code to Connect Code."""

        # Note: Connect doesn't have an OK code, only error codes
        if not GRPC_AVAILABLE:
            return Code.UNKNOWN
        mapping = {
            grpc.StatusCode.CANCELLED: Code.CANCELED,  # type: ignore[attr-defined]
            grpc.StatusCode.UNKNOWN: Code.UNKNOWN,  # type: ignore[attr-defined]
            grpc.StatusCode.INVALID_ARGUMENT: Code.INVALID_ARGUMENT,  # type: ignore[attr-defined]
            grpc.StatusCode.DEADLINE_EXCEEDED: Code.DEADLINE_EXCEEDED,  # type: ignore[attr-defined]
            grpc.StatusCode.NOT_FOUND: Code.NOT_FOUND,  # type: ignore[attr-defined]
            grpc.StatusCode.ALREADY_EXISTS: Code.ALREADY_EXISTS,  # type: ignore[attr-defined]
            grpc.StatusCode.PERMISSION_DENIED: Code.PERMISSION_DENIED,  # type: ignore[attr-defined]
            grpc.StatusCode.RESOURCE_EXHAUSTED: Code.RESOURCE_EXHAUSTED,  # type: ignore[attr-defined]
            grpc.StatusCode.FAILED_PRECONDITION: Code.FAILED_PRECONDITION,  # type: ignore[attr-defined]
            grpc.StatusCode.ABORTED: Code.ABORTED,  # type: ignore[attr-defined]
            grpc.StatusCode.OUT_OF_RANGE: Code.OUT_OF_RANGE,  # type: ignore[attr-defined]
            grpc.StatusCode.UNIMPLEMENTED: Code.UNIMPLEMENTED,  # type: ignore[attr-defined]
            grpc.StatusCode.INTERNAL: Code.INTERNAL,  # type: ignore[attr-defined]
            grpc.StatusCode.UNAVAILABLE: Code.UNAVAILABLE,  # type: ignore[attr-defined]
            grpc.StatusCode.DATA_LOSS: Code.DATA_LOSS,  # type: ignore[attr-defined]
            grpc.StatusCode.UNAUTHENTICATED: Code.UNAUTHENTICATED,  # type: ignore[attr-defined]
        }
        return mapping.get(grpc_status, Code.UNKNOWN)

    def _get_grpc_compression(self, compression: str) -> int:
        """Convert compression name to gRPC compression algorithm."""
        if compression == "gzip":
            return 2  # grpc.Compression.Gzip
        if compression == "deflate":
            return 1  # grpc.Compression.Deflate
        return 0  # grpc.Compression.NoCompression
