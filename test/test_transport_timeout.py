"""Tests for timeout validation in the Transport API."""

import pytest

from connecpy.method import IdempotencyLevel, MethodInfo
from connecpy.transport import (
    CallOptions,
    ConnectTransport,
    ConnectTransportAsync,
    GrpcTransport,
    GrpcTransportAsync,
)


def test_connect_timeout_validation():
    """Test timeout validation for Connect transport."""
    transport = ConnectTransport("http://localhost:3000")

    method = MethodInfo(
        name="TestMethod",
        service_name="TestService",
        input=type("TestInput", (), {}),
        output=type("TestOutput", (), {}),
        idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
    )

    # Test valid timeout values
    # 100 days in milliseconds = 8,640,000,000 ms
    valid_timeouts = [
        1000,  # 1 second
        60000,  # 1 minute
        3600000,  # 1 hour
        86400000,  # 1 day
        8640000000,  # 100 days (max allowed)
    ]

    for timeout_ms in valid_timeouts:
        call_options = CallOptions(timeout_ms=timeout_ms)
        # Should not raise any exception
        try:
            # We need to mock the actual call to avoid network errors
            from unittest.mock import patch  # noqa: PLC0415  # noqa: PLC0415

            with patch.object(transport._client, "execute_unary") as mock:
                mock.return_value = {"result": "ok"}
                transport.unary_unary(method, {"test": "data"}, call_options)
        except ValueError as e:
            if "Timeout" in str(e):
                pytest.fail(
                    f"Timeout {timeout_ms}ms should be valid but got error: {e}"
                )

    # Test invalid timeout values
    invalid_timeouts = [
        0,  # Zero timeout
        -1000,  # Negative timeout
        8640000001,  # Just over 100 days
        10000000000,  # Way over 100 days
    ]

    for timeout_ms in invalid_timeouts:
        call_options = CallOptions(timeout_ms=timeout_ms)
        with pytest.raises(ValueError, match="Timeout"):
            # Mock to isolate timeout validation
            from unittest.mock import patch  # noqa: PLC0415  # noqa: PLC0415

            with patch.object(transport._client, "execute_unary") as mock:
                mock.return_value = {"result": "ok"}
                transport.unary_unary(method, {"test": "data"}, call_options)


@pytest.mark.asyncio
async def test_connect_async_timeout_validation():
    """Test timeout validation for async Connect transport."""
    transport = ConnectTransportAsync("http://localhost:3000")

    method = MethodInfo(
        name="TestMethod",
        service_name="TestService",
        input=type("TestInput", (), {}),
        output=type("TestOutput", (), {}),
        idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
    )

    # Test that 100 days is allowed
    call_options = CallOptions(timeout_ms=8640000000)  # 100 days

    from unittest.mock import AsyncMock, patch  # noqa: PLC0415

    with patch.object(
        transport._client, "execute_unary", new_callable=AsyncMock
    ) as mock:
        mock.return_value = {"result": "ok"}
        result = await transport.unary_unary(method, {"test": "data"}, call_options)
        assert result == {"result": "ok"}

    # Test that just over 100 days is rejected
    call_options = CallOptions(timeout_ms=8640000001)

    with pytest.raises(ValueError, match="max is 100 days"):  # noqa: SIM117
        with patch.object(
            transport._client, "execute_unary", new_callable=AsyncMock
        ) as mock:
            mock.return_value = {"result": "ok"}
            await transport.unary_unary(method, {"test": "data"}, call_options)


def test_grpc_timeout_validation():
    """Test timeout validation for gRPC transport."""
    # Skip if grpc not available
    pytest.importorskip("grpc")

    transport = GrpcTransport("localhost:50051")

    method = MethodInfo(
        name="TestMethod",
        service_name="TestService",
        input=type("TestInput", (), {}),
        output=type("TestOutput", (), {}),
        idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
    )

    # Test 100 days timeout
    call_options = CallOptions(timeout_ms=8640000000)

    from unittest.mock import MagicMock, patch  # noqa: PLC0415

    with patch.object(transport, "_get_or_create_stub") as mock_stub:
        mock_call = MagicMock(return_value={"result": "ok"})
        mock_stub.return_value = mock_call

        # Should not raise ValueError for timeout
        result = transport.unary_unary(method, {"test": "data"}, call_options)
        assert result == {"result": "ok"}

        # Check that the timeout was converted correctly (ms to seconds)
        mock_call.assert_called_once()
        _, kwargs = mock_call.call_args
        assert kwargs["timeout"] == 8640000.0  # 100 days in seconds

    # Test invalid timeout (over 100 days)
    call_options = CallOptions(timeout_ms=8640000001)

    with pytest.raises(ValueError, match="max is 100 days"):  # noqa: SIM117
        with patch.object(transport, "_get_or_create_stub") as mock_stub:
            mock_stub.return_value = MagicMock()
            transport.unary_unary(method, {"test": "data"}, call_options)


@pytest.mark.asyncio
async def test_grpc_async_timeout_validation():
    """Test timeout validation for async gRPC transport."""
    # Skip if grpc not available
    pytest.importorskip("grpc")

    transport = GrpcTransportAsync("localhost:50051")

    method = MethodInfo(
        name="TestMethod",
        service_name="TestService",
        input=type("TestInput", (), {}),
        output=type("TestOutput", (), {}),
        idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
    )

    # Test valid 50-day timeout (within 100-day limit)
    call_options = CallOptions(timeout_ms=4320000000)  # 50 days

    from unittest.mock import AsyncMock, patch  # noqa: PLC0415

    with patch.object(transport, "_get_or_create_stub") as mock_stub:
        mock_call = AsyncMock(return_value={"result": "ok"})
        mock_stub.return_value = mock_call

        result = await transport.unary_unary(method, {"test": "data"}, call_options)
        assert result == {"result": "ok"}

        # Verify timeout was passed correctly
        mock_call.assert_called_once()
        _, kwargs = mock_call.call_args
        assert kwargs["timeout"] == 4320000.0  # 50 days in seconds

    # Test edge case: exactly 100 days
    call_options = CallOptions(timeout_ms=8640000000)

    with patch.object(transport, "_get_or_create_stub") as mock_stub:
        mock_call = AsyncMock(return_value={"result": "ok"})
        mock_stub.return_value = mock_call

        result = await transport.unary_unary(method, {"test": "data"}, call_options)
        assert result == {"result": "ok"}

    # Test negative timeout
    call_options = CallOptions(timeout_ms=-1000)

    with pytest.raises(ValueError, match="must be positive"):  # noqa: SIM117
        with patch.object(transport, "_get_or_create_stub") as mock_stub:
            mock_stub.return_value = AsyncMock()
            await transport.unary_unary(method, {"test": "data"}, call_options)


def test_none_timeout_means_infinite():
    """Test that None timeout means infinite timeout (no timeout)."""
    transport = ConnectTransport("http://localhost:3000")

    method = MethodInfo(
        name="TestMethod",
        service_name="TestService",
        input=type("TestInput", (), {}),
        output=type("TestOutput", (), {}),
        idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
    )

    # CallOptions with no timeout specified
    call_options = CallOptions()
    assert call_options.timeout_ms is None

    from unittest.mock import patch  # noqa: PLC0415

    with patch.object(transport._client, "execute_unary") as mock:
        mock.return_value = {"result": "ok"}
        transport.unary_unary(method, {"test": "data"}, call_options)

        # Verify that None was passed as timeout (infinite timeout)
        mock.assert_called_once()
        _, kwargs = mock.call_args
        assert kwargs.get("timeout_ms") is None
