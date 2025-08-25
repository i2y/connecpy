"""Async Connect protocol transport implementation."""

from __future__ import annotations

import asyncio
import types
from collections.abc import AsyncIterator, Iterable
from typing import TYPE_CHECKING, Any

import httpx
from typing_extensions import Self

from connecpy.client import ConnecpyClient
from connecpy.exceptions import ConnecpyException
from connecpy.interceptor import Interceptor

from .base import CallOptions, RetryPolicy

if TYPE_CHECKING:
    from connecpy.method import MethodInfo


class ConnectTransportAsync:
    """Async transport implementation using the Connect protocol.

    This transport wraps the existing ConnecpyClient to provide
    a protocol-agnostic interface. It accepts all the same parameters
    as ConnecpyClient for full compatibility.
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
        interceptors: Iterable[Interceptor] = (),
        session: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the async Connect transport with all ConnecpyClient parameters.

        Args:
            address: The address of the server to connect to, including scheme
                (e.g., "http://localhost:3000" or "https://api.example.com")
            proto_json: Whether to use JSON for the protocol
            accept_compression: A list of compression algorithms to accept from the server
            send_compression: The compression algorithm to use for sending requests
            timeout_ms: The timeout for requests in milliseconds
            read_max_bytes: The maximum number of bytes to read from the response
            interceptors: A list of interceptors to apply to requests
            session: An httpx AsyncClient to use for requests (useful for custom TLS config)
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

        # Create the underlying async client
        self._client = ConnecpyClient(address, **self._client_kwargs)

        # Store for later use in create_client
        self.address = address
        self.proto_json = proto_json
        self.accept_compression = accept_compression
        self.send_compression = send_compression
        self.timeout_ms = timeout_ms
        self.read_max_bytes = read_max_bytes
        self.interceptors = interceptors
        self.session = session

    async def unary_unary(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Any:
        """Execute a unary-unary RPC with optional retry."""
        call_options = call_options or CallOptions()

        async def execute() -> Any:
            return await self._call_unary(method, request, call_options)

        if call_options.retry_policy:
            return await self._execute_with_retry(execute, call_options.retry_policy)
        return await execute()

    async def unary_stream(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> AsyncIterator[Any]:
        """Execute a unary-stream RPC."""
        call_options = call_options or CallOptions()
        return self._call_server_stream(method, request, call_options)

    async def stream_unary(
        self,
        method: MethodInfo,
        stream: AsyncIterator[Any],
        call_options: CallOptions | None = None,
    ) -> Any:
        """Execute a stream-unary RPC with optional retry."""
        call_options = call_options or CallOptions()

        async def execute() -> Any:
            return await self._call_client_stream(method, stream, call_options)

        if call_options.retry_policy:
            return await self._execute_with_retry(execute, call_options.retry_policy)
        return await execute()

    async def stream_stream(
        self,
        method: MethodInfo,
        stream: AsyncIterator[Any],
        call_options: CallOptions | None = None,
    ) -> AsyncIterator[Any]:
        """Execute a stream-stream RPC."""
        call_options = call_options or CallOptions()
        return self._call_bidi_stream(method, stream, call_options)

    async def close(self) -> None:
        """Close the underlying client."""
        await self._client.close()

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit the async context manager and close resources."""
        await self.close()

    async def _execute_with_retry(self, func: Any, retry_policy: RetryPolicy) -> Any:
        """Execute an async function with retry logic."""
        attempt = 0
        backoff_ms = retry_policy.initial_backoff_ms

        while attempt < retry_policy.max_attempts:
            try:
                return await func()
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
                await asyncio.sleep(backoff_ms / 1000.0)
                backoff_ms = min(
                    int(backoff_ms * retry_policy.backoff_multiplier),
                    retry_policy.max_backoff_ms,
                )
                attempt += 1

        # Should never reach here
        msg = "Retry loop exited unexpectedly"
        raise RuntimeError(msg)

    async def _call_unary(
        self, method: MethodInfo, request: Any, options: CallOptions
    ) -> Any:
        """Internal method to call unary RPC through the client."""
        # Use the client's public execute_unary method
        timeout_ms = options.timeout_ms or self.timeout_ms
        return await self._client.execute_unary(
            request=request,
            method=method,
            headers=options.headers,
            timeout_ms=timeout_ms,
        )

    def _call_server_stream(
        self, method: MethodInfo, request: Any, options: CallOptions
    ) -> AsyncIterator[Any]:
        """Internal method to call server streaming RPC."""
        timeout_ms = options.timeout_ms or self.timeout_ms
        return self._client.execute_server_stream(
            request=request,
            method=method,
            headers=options.headers,
            timeout_ms=timeout_ms,
        )

    async def _call_client_stream(
        self, method: MethodInfo, stream: AsyncIterator[Any], options: CallOptions
    ) -> Any:
        """Internal method to call client streaming RPC."""
        timeout_ms = options.timeout_ms or self.timeout_ms
        return await self._client.execute_client_stream(
            request=stream,
            method=method,
            headers=options.headers,
            timeout_ms=timeout_ms,
        )

    def _call_bidi_stream(
        self, method: MethodInfo, stream: AsyncIterator[Any], options: CallOptions
    ) -> AsyncIterator[Any]:
        """Internal method to call bidirectional streaming RPC."""
        timeout_ms = options.timeout_ms or self.timeout_ms
        return self._client.execute_bidi_stream(
            request=stream,
            method=method,
            headers=options.headers,
            timeout_ms=timeout_ms,
        )
