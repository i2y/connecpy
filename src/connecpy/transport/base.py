"""Base classes and protocols for the Transport API."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from connecpy.code import Code

T = TypeVar("T")  # Generic type variable for responses

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from connecpy.interceptor import Interceptor, InterceptorSync
    from connecpy.method import MethodInfo


class TransportProtocol(Protocol):
    """Protocol for transport implementations.

    Transport implementations provide a protocol-agnostic interface for making
    RPC calls. Request and response types are protobuf Message instances.
    """

    def unary_unary(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Any:
        """Execute a unary-unary RPC.

        Args:
            method: Method information including service and method names
            request: The protobuf request message
            call_options: Optional call-specific options

        Returns:
            The protobuf response message
        """
        ...

    def unary_stream(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Iterator[Any]:
        """Execute a unary-stream RPC.

        Args:
            method: Method information including service and method names
            request: The protobuf request message
            call_options: Optional call-specific options

        Returns:
            Iterator of protobuf response messages
        """
        ...

    def stream_unary(
        self,
        method: MethodInfo,
        stream: Iterator[Any],
        call_options: CallOptions | None = None,
    ) -> Any:
        """Execute a stream-unary RPC.

        Args:
            method: Method information including service and method names
            stream: Iterator of protobuf request messages
            call_options: Optional call-specific options

        Returns:
            The protobuf response message
        """
        ...

    def stream_stream(
        self,
        method: MethodInfo,
        stream: Iterator[Any],
        call_options: CallOptions | None = None,
    ) -> Iterator[Any]:
        """Execute a stream-stream RPC.

        Args:
            method: Method information including service and method names
            stream: Iterator of protobuf request messages
            call_options: Optional call-specific options

        Returns:
            Iterator of protobuf response messages
        """
        ...

    def close(self) -> None:
        """Close the transport and release resources."""
        ...


class AsyncTransportProtocol(Protocol):
    """Protocol for async transport implementations.

    Async transport implementations provide a protocol-agnostic interface for making
    asynchronous RPC calls. Request and response types are protobuf Message instances.
    """

    async def unary_unary(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Any:
        """Execute a unary-unary RPC asynchronously.

        Args:
            method: Method information including service and method names
            request: The protobuf request message
            call_options: Optional call-specific options

        Returns:
            The protobuf response message
        """
        ...

    async def unary_stream(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> AsyncIterator[Any]:
        """Execute a unary-stream RPC asynchronously.

        Args:
            method: Method information including service and method names
            request: The protobuf request message
            call_options: Optional call-specific options

        Returns:
            Async iterator of protobuf response messages
        """
        ...

    async def stream_unary(
        self,
        method: MethodInfo,
        stream: AsyncIterator[Any],
        call_options: CallOptions | None = None,
    ) -> Any:
        """Execute a stream-unary RPC asynchronously.

        Args:
            method: Method information including service and method names
            stream: Async iterator of protobuf request messages
            call_options: Optional call-specific options

        Returns:
            The protobuf response message
        """
        ...

    async def stream_stream(
        self,
        method: MethodInfo,
        stream: AsyncIterator[Any],
        call_options: CallOptions | None = None,
    ) -> AsyncIterator[Any]:
        """Execute a stream-stream RPC asynchronously.

        Args:
            method: Method information including service and method names
            stream: Async iterator of protobuf request messages
            call_options: Optional call-specific options

        Returns:
            Async iterator of protobuf response messages
        """
        ...

    async def close(self) -> None:
        """Close the transport and release resources."""
        ...


@dataclass
class RetryPolicy:
    """Configuration for automatic retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including initial)
        initial_backoff_ms: Initial backoff in milliseconds
        max_backoff_ms: Maximum backoff in milliseconds
        backoff_multiplier: Multiplier for exponential backoff
        retryable_codes: List of error codes that trigger retry
    """

    max_attempts: int = 3
    initial_backoff_ms: int = 100
    max_backoff_ms: int = 5000
    backoff_multiplier: float = 2.0
    retryable_codes: list[Code] | None = None

    def __post_init__(self) -> None:
        """Set default retryable codes if not provided."""
        if self.retryable_codes is None:
            self.retryable_codes = [Code.UNAVAILABLE, Code.DEADLINE_EXCEEDED]


@dataclass
class TransportOptions:
    """Options for transport configuration.

    Attributes:
        timeout_ms: Default timeout in milliseconds
        retry_policy: Default retry policy
        interceptors: List of interceptors
        compression: Compression algorithm to use
        headers: Additional headers to include
    """

    timeout_ms: int | None = None
    retry_policy: RetryPolicy | None = None
    interceptors: list[Interceptor | InterceptorSync] = field(default_factory=list)
    compression: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class CallOptions:
    """Options for individual RPC calls.

    Attributes:
        timeout_ms: Timeout for this call (overrides transport default)
        retry_policy: Retry policy for this call (overrides transport default)
        headers: Additional headers for this call
    """

    timeout_ms: int | None = None
    retry_policy: RetryPolicy | None = None
    headers: dict[str, str] = field(default_factory=dict)
