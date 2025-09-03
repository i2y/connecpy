"""Connect protocol transport implementation."""

from __future__ import annotations

import time
import types
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any

import httpx
from typing_extensions import Self

from connecpy._client_sync import ConnecpyClientSync
from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.interceptor import InterceptorSync

from .base import CallOptions, RetryPolicy

if TYPE_CHECKING:
    from connecpy.method import MethodInfo


class ConnectTransport:
    """Transport implementation using the Connect protocol.

    This transport wraps the existing ConnecpyClientSync to provide
    a protocol-agnostic interface. It accepts all the same parameters
    as ConnecpyClientSync for full compatibility.
    """

    def __init__(
        self,
        address: str,
        *,
        proto_json: bool = False,
        accept_compression: Iterable[str] | None = None,
        send_compression: str | None = None,
        timeout_ms: int | None = None,
        read_max_bytes: int | None = None,
        interceptors: Iterable[InterceptorSync] = (),
        session: httpx.Client | None = None,
    ) -> None:
        """Initialize the Connect transport with all ConnecpyClientSync parameters.

        Args:
            address: The address of the server to connect to, including scheme
                (e.g., "http://localhost:3000" or "https://api.example.com")
            proto_json: Whether to use JSON for the protocol
            accept_compression: A list of compression algorithms to accept from the server
            send_compression: The compression algorithm to use for sending requests
            timeout_ms: The timeout for requests in milliseconds
            read_max_bytes: The maximum number of bytes to read from the response
            interceptors: A list of interceptors to apply to requests
            session: An httpx Client to use for requests (useful for custom TLS config)
        """
        self._address = address
        self._client_kwargs = {
            "proto_json": proto_json,
            "accept_compression": accept_compression,
            "send_compression": send_compression,
            "timeout_ms": timeout_ms,
            "read_max_bytes": read_max_bytes,
            "interceptors": interceptors,
            "session": session,
        }

        # Create the underlying client
        self._client = ConnecpyClientSync(address, **self._client_kwargs)

        # Store for later use in create_client
        self.address = address
        self.proto_json = proto_json
        self.accept_compression = accept_compression
        self.send_compression = send_compression
        self.timeout_ms = timeout_ms
        self.read_max_bytes = read_max_bytes
        self.interceptors = interceptors
        self.session = session

    def unary_unary(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Any:
        """Execute a unary-unary RPC with optional retry."""
        call_options = call_options or CallOptions()

        def execute() -> Any:
            return self._call_unary(method, request, call_options)

        if call_options.retry_policy:
            return self._execute_with_retry(execute, call_options.retry_policy)
        return execute()

    def unary_stream(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Iterator[Any]:
        """Execute a unary-stream RPC."""
        call_options = call_options or CallOptions()
        return self._call_server_stream(method, request, call_options)

    def stream_unary(
        self,
        method: MethodInfo,
        stream: Iterator[Any],
        call_options: CallOptions | None = None,
    ) -> Any:
        """Execute a stream-unary RPC with optional retry."""
        call_options = call_options or CallOptions()

        def execute() -> Any:
            return self._call_client_stream(method, stream, call_options)

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
        return self._call_bidi_stream(method, stream, call_options)

    def close(self) -> None:
        """Close the underlying client."""
        self._client.close()

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

    def _merge_options(self, call_options: CallOptions | None) -> CallOptions:
        """Merge call options with transport defaults."""
        if not call_options:
            return CallOptions(
                timeout_ms=self.timeout_ms, retry_policy=None, headers={}
            )

        return CallOptions(
            timeout_ms=call_options.timeout_ms or self.timeout_ms,
            retry_policy=call_options.retry_policy,
            headers=call_options.headers.copy(),
        )

    def _execute_with_retry(self, func: Any, retry_policy: RetryPolicy) -> Any:
        """Execute a function with retry logic."""
        attempt = 0
        backoff_ms = retry_policy.initial_backoff_ms

        while attempt < retry_policy.max_attempts:
            try:
                return func()
            except ConnecpyException as e:
                # Check if the error is retryable
                if (
                    retry_policy.retryable_codes is None
                    or e.code not in retry_policy.retryable_codes
                ):
                    raise

                # Check if we've exhausted retries
                if attempt >= retry_policy.max_attempts - 1:
                    raise

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

    def _validate_and_get_timeout(self, options: CallOptions) -> int | None:
        """Validate timeout value and return the effective timeout.

        Args:
            options: Call options containing timeout settings

        Returns:
            The effective timeout in milliseconds, or None for infinite timeout

        Raises:
            ValueError: If timeout is invalid (negative or too large)
        """
        timeout_ms = (
            options.timeout_ms if options.timeout_ms is not None else self.timeout_ms
        )
        if timeout_ms is not None:
            if timeout_ms <= 0:
                msg = f"Timeout must be positive, got {timeout_ms}ms"
                raise ValueError(msg)
            if timeout_ms > 8640000000:  # 100 days max (protocol supports 100+ days)
                msg = f"Timeout too large ({timeout_ms}ms), max is 100 days (8640000000ms)"
                raise ValueError(msg)
        return timeout_ms

    def _handle_timeout_error(self, e: httpx.TimeoutException) -> None:
        """Convert HTTP timeout exception to ConnecpyException.

        Args:
            e: The HTTP timeout exception

        Raises:
            ConnecpyException: Always raises with DEADLINE_EXCEEDED code
        """
        raise ConnecpyException(Code.DEADLINE_EXCEEDED, f"Request timeout: {e}") from e

    def _call_unary(
        self, method: MethodInfo, request: Any, options: CallOptions
    ) -> Any:
        """Internal method to call unary RPC through the client."""
        timeout_ms = self._validate_and_get_timeout(options)
        try:
            return self._client.execute_unary(
                request=request,
                method=method,
                headers=options.headers,
                timeout_ms=timeout_ms,
            )
        except httpx.TimeoutException as e:
            self._handle_timeout_error(e)
            raise  # Unreachable, but satisfies type checker

    def _call_server_stream(
        self, method: MethodInfo, request: Any, options: CallOptions
    ) -> Iterator[Any]:
        """Internal method to call server streaming RPC."""
        timeout_ms = self._validate_and_get_timeout(options)
        try:
            return self._client.execute_server_stream(
                request=request,
                method=method,
                headers=options.headers,
                timeout_ms=timeout_ms,
            )
        except httpx.TimeoutException as e:
            self._handle_timeout_error(e)
            raise  # Unreachable, but satisfies type checker

    def _call_client_stream(
        self, method: MethodInfo, stream: Iterator[Any], options: CallOptions
    ) -> Any:
        """Internal method to call client streaming RPC."""
        timeout_ms = self._validate_and_get_timeout(options)
        try:
            return self._client.execute_client_stream(
                request=stream,
                method=method,
                headers=options.headers,
                timeout_ms=timeout_ms,
            )
        except httpx.TimeoutException as e:
            self._handle_timeout_error(e)
            raise  # Unreachable, but satisfies type checker

    def _call_bidi_stream(
        self, method: MethodInfo, stream: Iterator[Any], options: CallOptions
    ) -> Iterator[Any]:
        """Internal method to call bidirectional streaming RPC."""
        timeout_ms = self._validate_and_get_timeout(options)
        try:
            return self._client.execute_bidi_stream(
                request=stream,
                method=method,
                headers=options.headers,
                timeout_ms=timeout_ms,
            )
        except httpx.TimeoutException as e:
            self._handle_timeout_error(e)
            raise  # Unreachable, but satisfies type checker
