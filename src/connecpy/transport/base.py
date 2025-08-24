"""Base classes and protocols for the Transport API."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from connecpy.interceptor import Interceptor, InterceptorSync
    from connecpy.method import MethodInfo

from connecpy.code import Code


class TransportProtocol(Protocol):
    """Protocol for transport implementations."""

    def unary_unary(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Any:
        """Execute a unary-unary RPC."""
        ...

    def unary_stream(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Iterator[Any]:
        """Execute a unary-stream RPC."""
        ...

    def stream_unary(
        self,
        method: MethodInfo,
        stream: Iterator[Any],
        call_options: CallOptions | None = None,
    ) -> Any:
        """Execute a stream-unary RPC."""
        ...

    def stream_stream(
        self,
        method: MethodInfo,
        stream: Iterator[Any],
        call_options: CallOptions | None = None,
    ) -> Iterator[Any]:
        """Execute a stream-stream RPC."""
        ...

    def close(self) -> None:
        """Close the transport and release resources."""
        ...


class AsyncTransportProtocol(Protocol):
    """Protocol for async transport implementations."""

    async def unary_unary(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Any:
        """Execute a unary-unary RPC."""
        ...

    async def unary_stream(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> AsyncIterator[Any]:
        """Execute a unary-stream RPC."""
        ...

    async def stream_unary(
        self,
        method: MethodInfo,
        stream: AsyncIterator[Any],
        call_options: CallOptions | None = None,
    ) -> Any:
        """Execute a stream-unary RPC."""
        ...

    async def stream_stream(
        self,
        method: MethodInfo,
        stream: AsyncIterator[Any],
        call_options: CallOptions | None = None,
    ) -> AsyncIterator[Any]:
        """Execute a stream-stream RPC."""
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
