"""Tests for async retry policies in the Transport API."""

from unittest.mock import AsyncMock, patch

import pytest

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.method import IdempotencyLevel, MethodInfo
from connecpy.transport.client import CallOptions, ConnectTransportAsync, RetryPolicy


@pytest.mark.asyncio
async def test_async_retry_policy_defaults():
    """Test RetryPolicy with default values in async transport."""
    policy = RetryPolicy()
    assert policy.max_attempts == 3
    assert policy.initial_backoff_ms == 100
    assert policy.max_backoff_ms == 5000
    assert policy.backoff_multiplier == 2.0
    assert policy.retryable_codes == [Code.UNAVAILABLE, Code.DEADLINE_EXCEEDED]


@pytest.mark.asyncio
async def test_async_retry_success_after_failures():
    """Test async retry succeeds after transient failures."""
    transport = ConnectTransportAsync("https://example.com")
    policy = RetryPolicy(max_attempts=3, initial_backoff_ms=10)

    attempt_count = 0

    async def failing_func():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ConnecpyException(Code.UNAVAILABLE, "Service unavailable")
        return "success"

    # Test the retry mechanism
    result = await transport._execute_with_retry(failing_func, policy)
    assert result == "success"
    assert attempt_count == 3


@pytest.mark.asyncio
async def test_async_retry_non_retryable_error():
    """Test async retry fails immediately on non-retryable errors."""
    transport = ConnectTransportAsync("https://example.com")
    policy = RetryPolicy(max_attempts=3, initial_backoff_ms=10)

    attempt_count = 0

    async def non_retryable_func():
        nonlocal attempt_count
        attempt_count += 1
        raise ConnecpyException(Code.INVALID_ARGUMENT, "Bad request")

    with pytest.raises(ConnecpyException) as exc_info:
        await transport._execute_with_retry(non_retryable_func, policy)

    assert exc_info.value.code == Code.INVALID_ARGUMENT
    assert attempt_count == 1  # Should not retry


@pytest.mark.asyncio
async def test_async_retry_max_attempts_exceeded():
    """Test async retry fails when max attempts are exceeded."""
    transport = ConnectTransportAsync("https://example.com")
    policy = RetryPolicy(max_attempts=2, initial_backoff_ms=10)

    attempt_count = 0

    async def always_failing_func():
        nonlocal attempt_count
        attempt_count += 1
        raise ConnecpyException(Code.UNAVAILABLE, f"Attempt {attempt_count}")

    with pytest.raises(ConnecpyException) as exc_info:
        await transport._execute_with_retry(always_failing_func, policy)

    assert exc_info.value.code == Code.UNAVAILABLE
    assert attempt_count == 2  # Should have tried max_attempts times


@pytest.mark.asyncio
async def test_async_retry_exponential_backoff():
    """Test async retry uses exponential backoff correctly."""
    transport = ConnectTransportAsync("https://example.com")
    policy = RetryPolicy(
        max_attempts=4,
        initial_backoff_ms=100,
        max_backoff_ms=1000,
        backoff_multiplier=2.0,
    )

    backoff_times = []
    attempt_count = 0

    async def track_backoff_func():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 4:
            raise ConnecpyException(Code.UNAVAILABLE, "Service unavailable")
        return "success"

    # Patch asyncio.sleep to track backoff times
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        async def track_sleep(seconds):
            backoff_times.append(seconds * 1000)  # Convert to ms

        mock_sleep.side_effect = track_sleep

        result = await transport._execute_with_retry(track_backoff_func, policy)

    assert result == "success"
    assert len(backoff_times) == 3  # 3 retries before success

    # Check exponential backoff
    assert backoff_times[0] == 100  # initial_backoff_ms
    assert backoff_times[1] == 200  # 100 * 2
    assert backoff_times[2] == 400  # 200 * 2


@pytest.mark.asyncio
async def test_async_retry_backoff_max_limit():
    """Test async retry respects max backoff limit."""
    transport = ConnectTransportAsync("https://example.com")
    policy = RetryPolicy(
        max_attempts=5,
        initial_backoff_ms=100,
        max_backoff_ms=300,  # Low max to test capping
        backoff_multiplier=3.0,
    )

    backoff_times = []

    async def always_failing():
        raise ConnecpyException(Code.UNAVAILABLE, "Service unavailable")

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        async def track_sleep(seconds):
            backoff_times.append(seconds * 1000)  # Convert to ms

        mock_sleep.side_effect = track_sleep

        with pytest.raises(ConnecpyException):
            await transport._execute_with_retry(always_failing, policy)

    assert len(backoff_times) == 4  # 4 retries before giving up
    assert backoff_times[0] == 100  # initial_backoff_ms
    assert backoff_times[1] == 300  # 100 * 3, but capped at max_backoff_ms
    assert backoff_times[2] == 300  # Capped at max_backoff_ms
    assert backoff_times[3] == 300  # Capped at max_backoff_ms


@pytest.mark.asyncio
async def test_async_retry_custom_retryable_codes():
    """Test async retry with custom retryable error codes."""
    transport = ConnectTransportAsync("https://example.com")
    policy = RetryPolicy(
        max_attempts=3,
        initial_backoff_ms=10,
        retryable_codes=[Code.INTERNAL, Code.UNKNOWN],  # Custom codes
    )

    # Test retryable error
    attempt_count = 0

    async def internal_error_func():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise ConnecpyException(Code.INTERNAL, "Internal error")
        return "recovered"

    result = await transport._execute_with_retry(internal_error_func, policy)
    assert result == "recovered"
    assert attempt_count == 2

    # Test non-retryable error (UNAVAILABLE not in custom list)
    async def unavailable_func():
        raise ConnecpyException(Code.UNAVAILABLE, "Service unavailable")

    with pytest.raises(ConnecpyException) as exc_info:
        await transport._execute_with_retry(unavailable_func, policy)

    assert exc_info.value.code == Code.UNAVAILABLE


@pytest.mark.asyncio
async def test_async_unary_with_retry_via_call_options():
    """Test async unary RPC with retry policy via CallOptions."""
    transport = ConnectTransportAsync("https://example.com")

    method = MethodInfo(
        name="TestMethod",
        service_name="TestService",
        input=type("TestInput", (), {}),
        output=type("TestOutput", (), {}),
        idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
    )

    # Mock the underlying client
    with patch.object(transport, "_client") as mock_client:
        attempt_count = 0

        async def failing_execute(*args, **kwargs):  # noqa: ARG001
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnecpyException(Code.UNAVAILABLE, "Temporary failure")
            return {"result": "success"}

        mock_client.execute_unary = AsyncMock(side_effect=failing_execute)

        # Call with retry policy
        call_options = CallOptions(
            retry_policy=RetryPolicy(max_attempts=3, initial_backoff_ms=10)
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):  # Skip actual sleep
            result = await transport.unary_unary(method, {"test": "data"}, call_options)

        assert result == {"result": "success"}
        assert attempt_count == 3


@pytest.mark.asyncio
async def test_async_stream_unary_with_retry():
    """Test async stream-unary RPC with retry policy."""
    transport = ConnectTransportAsync("https://example.com")

    method = MethodInfo(
        name="StreamMethod",
        service_name="TestService",
        input=type("TestInput", (), {}),
        output=type("TestOutput", (), {}),
        idempotency_level=IdempotencyLevel.UNKNOWN,
    )

    # Mock the underlying client
    with patch.object(transport, "_client") as mock_client:
        attempt_count = 0

        async def failing_stream_execute(*args, **kwargs):  # noqa: ARG001
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ConnecpyException(Code.DEADLINE_EXCEEDED, "Timeout")
            return {"aggregated": "result"}

        mock_client.execute_client_stream = AsyncMock(
            side_effect=failing_stream_execute
        )

        # Create an async stream
        async def input_stream():
            for i in range(3):
                yield {"data": i}

        # Call with retry policy
        call_options = CallOptions(
            retry_policy=RetryPolicy(
                max_attempts=2,
                initial_backoff_ms=10,
                retryable_codes=[Code.DEADLINE_EXCEEDED],
            )
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):  # Skip actual sleep
            result = await transport.stream_unary(method, input_stream(), call_options)

        assert result == {"aggregated": "result"}
        assert attempt_count == 2
