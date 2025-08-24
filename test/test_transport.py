"""Tests for the Transport API."""

import pytest

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.transport import CallOptions, ConnectTransport, RetryPolicy


def test_call_options_creation():
    """Test creating CallOptions."""
    options = CallOptions(timeout_ms=5000, headers={"x-custom": "value"})
    assert options.timeout_ms == 5000
    assert options.headers["x-custom"] == "value"


def test_retry_policy_defaults():
    """Test RetryPolicy default values."""
    policy = RetryPolicy()
    assert policy.max_attempts == 3
    assert policy.initial_backoff_ms == 100
    assert policy.max_backoff_ms == 5000
    assert policy.backoff_multiplier == 2.0
    assert policy.retryable_codes is not None
    assert Code.UNAVAILABLE in policy.retryable_codes
    assert Code.DEADLINE_EXCEEDED in policy.retryable_codes


def test_retry_policy_custom():
    """Test custom RetryPolicy."""
    policy = RetryPolicy(
        max_attempts=5, initial_backoff_ms=200, retryable_codes=[Code.INTERNAL]
    )
    assert policy.max_attempts == 5
    assert policy.initial_backoff_ms == 200
    assert policy.retryable_codes == [Code.INTERNAL]


def test_call_options():
    """Test CallOptions."""
    options = CallOptions(timeout_ms=3000, headers={"x-request-id": "123"})
    assert options.timeout_ms == 3000
    assert options.headers["x-request-id"] == "123"


def test_create_connect_transport():
    """Test creating a Connect transport."""
    transport = ConnectTransport("https://example.com")
    assert isinstance(transport, ConnectTransport)
    assert transport.address == "https://example.com"

    # With timeout
    transport = ConnectTransport("https://example.com", timeout_ms=10000)
    assert transport.timeout_ms == 10000


def test_connect_transport_merge_options():
    """Test merging call options with transport defaults."""
    transport = ConnectTransport("https://example.com", timeout_ms=5000)

    # No call options - should use transport defaults
    merged = transport._merge_options(None)
    assert merged.timeout_ms == 5000

    # Call options override
    call_options = CallOptions(timeout_ms=3000, headers={"x-custom": "override"})
    merged = transport._merge_options(call_options)
    assert merged.timeout_ms == 3000
    assert merged.headers["x-custom"] == "override"


def test_connect_transport_retry_logic():
    """Test retry logic in ConnectTransport."""
    transport = ConnectTransport("https://example.com")
    policy = RetryPolicy(max_attempts=3, initial_backoff_ms=10)

    # Test successful retry
    attempt_count = 0

    def failing_func():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ConnecpyException(Code.UNAVAILABLE, "Service unavailable")
        return "success"

    result = transport._execute_with_retry(failing_func, policy)
    assert result == "success"
    assert attempt_count == 3

    # Test non-retryable error
    def non_retryable_func():
        raise ConnecpyException(Code.INVALID_ARGUMENT, "Bad request")

    with pytest.raises(ConnecpyException) as exc_info:
        transport._execute_with_retry(non_retryable_func, policy)
    assert exc_info.value.code == Code.INVALID_ARGUMENT

    # Test max attempts exceeded
    def always_failing_func():
        raise ConnecpyException(Code.UNAVAILABLE, "Always fails")

    with pytest.raises(ConnecpyException) as exc_info:
        transport._execute_with_retry(always_failing_func, policy)
    assert exc_info.value.code == Code.UNAVAILABLE
