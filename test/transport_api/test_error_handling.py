"""Test error handling across Connect and gRPC transports."""

import unittest
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.method import IdempotencyLevel, MethodInfo
from connecpy.transport.client import CallOptions, ConnectTransport, GrpcTransport


class TestGrpcErrorHandling(unittest.TestCase):
    """Test error handling in GrpcTransport."""

    @patch("connecpy.transport.client.grpc.GRPC_AVAILABLE", True)
    @patch("connecpy.transport.client.grpc.grpc")
    def test_unary_unary_error_without_retry(self, mock_grpc):
        """Test that unary_unary properly converts gRPC errors without retry."""
        # Setup mock channel and stub
        mock_channel = MagicMock()
        mock_grpc.insecure_channel.return_value = mock_channel

        # Create a custom RpcError class and instance
        class MockRpcError(Exception):
            def __init__(self):
                super().__init__()
                self.code = lambda: mock_grpc.StatusCode.UNAVAILABLE
                self.details = lambda: "Service unavailable"

        # Setup the mock StatusCode enum
        mock_grpc.StatusCode.UNAVAILABLE = "UNAVAILABLE"
        mock_grpc.RpcError = MockRpcError

        # Setup the stub to raise an error
        mock_stub = MagicMock(side_effect=MockRpcError())
        mock_channel.unary_unary.return_value = mock_stub

        # Create transport
        transport = GrpcTransport("localhost:50051")

        # Create test method info
        method = MethodInfo(
            name="TestMethod",
            service_name="TestService",
            input=type("TestInput", (), {"SerializeToString": lambda _: b"test"}),
            output=type(
                "TestOutput", (), {"FromString": classmethod(lambda _, _x: {})}
            ),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        # Test that error is properly converted
        request = Mock()
        request.SerializeToString = lambda: b"test"

        with pytest.raises(ConnecpyException) as context:
            transport.unary_unary(method, request, CallOptions())

        # Verify the exception has correct code
        assert context.value.code == Code.UNAVAILABLE
        assert "Service unavailable" in str(context.value)

    @patch("connecpy.transport.client.grpc.GRPC_AVAILABLE", True)
    @patch("connecpy.transport.client.grpc.grpc")
    def test_stream_unary_error_without_retry(self, mock_grpc):
        """Test that stream_unary properly converts gRPC errors without retry."""
        # Setup mock channel and stub
        mock_channel = MagicMock()
        mock_grpc.insecure_channel.return_value = mock_channel

        # Create a custom RpcError class and instance
        class MockRpcError(Exception):
            def __init__(self):
                super().__init__()
                self.code = lambda: mock_grpc.StatusCode.DEADLINE_EXCEEDED
                self.details = lambda: "Deadline exceeded"

        # Setup the mock StatusCode enum
        mock_grpc.StatusCode.DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
        mock_grpc.RpcError = MockRpcError

        # Setup the stub to raise an error
        mock_stub = MagicMock(side_effect=MockRpcError())
        mock_channel.stream_unary.return_value = mock_stub

        # Create transport
        transport = GrpcTransport("localhost:50051")

        # Create test method info
        method = MethodInfo(
            name="TestMethod",
            service_name="TestService",
            input=type("TestInput", (), {"SerializeToString": lambda _: b"test"}),
            output=type(
                "TestOutput", (), {"FromString": classmethod(lambda _, _x: {})}
            ),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        # Create a mock stream
        mock_stream = iter([Mock(SerializeToString=lambda: b"test")])

        with pytest.raises(ConnecpyException) as context:
            transport.stream_unary(method, mock_stream, CallOptions())

        # Verify the exception has correct code
        assert context.value.code == Code.DEADLINE_EXCEEDED
        assert "Deadline exceeded" in str(context.value)

    @patch("connecpy.transport.client.grpc.GRPC_AVAILABLE", True)
    @patch("connecpy.transport.client.grpc.grpc")
    def test_grpc_status_code_mapping(self, mock_grpc):
        """Test that all gRPC status codes are properly mapped."""
        mock_channel = MagicMock()
        mock_grpc.insecure_channel.return_value = mock_channel

        # Setup mock StatusCode enum values - must match exactly what's in grpc.py
        mock_grpc.StatusCode.CANCELLED = MagicMock()
        mock_grpc.StatusCode.UNKNOWN = MagicMock()
        mock_grpc.StatusCode.INVALID_ARGUMENT = MagicMock()
        mock_grpc.StatusCode.DEADLINE_EXCEEDED = MagicMock()
        mock_grpc.StatusCode.NOT_FOUND = MagicMock()
        mock_grpc.StatusCode.ALREADY_EXISTS = MagicMock()
        mock_grpc.StatusCode.PERMISSION_DENIED = MagicMock()
        mock_grpc.StatusCode.RESOURCE_EXHAUSTED = MagicMock()
        mock_grpc.StatusCode.FAILED_PRECONDITION = MagicMock()
        mock_grpc.StatusCode.ABORTED = MagicMock()
        mock_grpc.StatusCode.OUT_OF_RANGE = MagicMock()
        mock_grpc.StatusCode.UNIMPLEMENTED = MagicMock()
        mock_grpc.StatusCode.INTERNAL = MagicMock()
        mock_grpc.StatusCode.UNAVAILABLE = MagicMock()
        mock_grpc.StatusCode.DATA_LOSS = MagicMock()
        mock_grpc.StatusCode.UNAUTHENTICATED = MagicMock()

        transport = GrpcTransport("localhost:50051")

        # Test status code mappings
        status_mappings = [
            (mock_grpc.StatusCode.CANCELLED, Code.CANCELED),
            (mock_grpc.StatusCode.UNKNOWN, Code.UNKNOWN),
            (mock_grpc.StatusCode.INVALID_ARGUMENT, Code.INVALID_ARGUMENT),
            (mock_grpc.StatusCode.DEADLINE_EXCEEDED, Code.DEADLINE_EXCEEDED),
            (mock_grpc.StatusCode.NOT_FOUND, Code.NOT_FOUND),
            (mock_grpc.StatusCode.ALREADY_EXISTS, Code.ALREADY_EXISTS),
            (mock_grpc.StatusCode.PERMISSION_DENIED, Code.PERMISSION_DENIED),
            (mock_grpc.StatusCode.RESOURCE_EXHAUSTED, Code.RESOURCE_EXHAUSTED),
            (mock_grpc.StatusCode.FAILED_PRECONDITION, Code.FAILED_PRECONDITION),
            (mock_grpc.StatusCode.ABORTED, Code.ABORTED),
            (mock_grpc.StatusCode.OUT_OF_RANGE, Code.OUT_OF_RANGE),
            (mock_grpc.StatusCode.UNIMPLEMENTED, Code.UNIMPLEMENTED),
            (mock_grpc.StatusCode.INTERNAL, Code.INTERNAL),
            (mock_grpc.StatusCode.UNAVAILABLE, Code.UNAVAILABLE),
            (mock_grpc.StatusCode.DATA_LOSS, Code.DATA_LOSS),
            (mock_grpc.StatusCode.UNAUTHENTICATED, Code.UNAUTHENTICATED),
        ]

        for grpc_status, expected_code in status_mappings:
            result = transport._grpc_status_to_code(grpc_status)
            assert result == expected_code


class TestConnectErrorHandling(unittest.TestCase):
    """Test error handling in ConnectTransport."""

    @patch("connecpy.transport.client.connect.ConnecpyClientSync")
    def test_unary_timeout_error(self, mock_client_class):
        """Test that timeout errors are properly converted to DEADLINE_EXCEEDED."""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Make execute_unary raise a timeout exception
        mock_client.execute_unary.side_effect = httpx.TimeoutException(
            "Request timeout"
        )

        transport = ConnectTransport("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="TestMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        request = {"test": "data"}
        call_options = CallOptions(timeout_ms=1000)

        with pytest.raises(ConnecpyException) as context:
            transport.unary_unary(method, request, call_options)

        # Verify the exception has correct code
        assert context.value.code == Code.DEADLINE_EXCEEDED
        assert "timeout" in str(context.value).lower()

    @patch("connecpy.transport.client.connect.ConnecpyClientSync")
    def test_server_stream_timeout_error(self, mock_client_class):
        """Test that server stream timeout errors are properly converted."""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Make execute_server_stream raise a timeout exception
        mock_client.execute_server_stream.side_effect = httpx.TimeoutException(
            "Stream timeout"
        )

        transport = ConnectTransport("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="TestMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        request = {"test": "data"}
        call_options = CallOptions()

        with pytest.raises(ConnecpyException) as context:
            # Since unary_stream returns an iterator, we need to trigger the actual call
            transport.unary_stream(method, request, call_options)
            # The actual exception would be raised when we consume the iterator
            # but in our mock setup, it raises immediately

        assert context.value.code == Code.DEADLINE_EXCEEDED
        assert "timeout" in str(context.value).lower()

    @patch("connecpy.transport.client.connect.ConnecpyClientSync")
    def test_client_stream_timeout_error(self, mock_client_class):
        """Test that client stream timeout errors are properly converted."""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Make execute_client_stream raise a timeout exception
        mock_client.execute_client_stream.side_effect = httpx.TimeoutException(
            "Client stream timeout"
        )

        transport = ConnectTransport("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="TestMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        stream = iter([{"test": "data1"}, {"test": "data2"}])
        call_options = CallOptions()

        with pytest.raises(ConnecpyException) as context:
            transport.stream_unary(method, stream, call_options)

        assert context.value.code == Code.DEADLINE_EXCEEDED
        assert "timeout" in str(context.value).lower()

    @patch("connecpy.transport.client.connect.ConnecpyClientSync")
    def test_bidi_stream_timeout_error(self, mock_client_class):
        """Test that bidirectional stream timeout errors are properly converted."""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Make execute_bidi_stream raise a timeout exception
        mock_client.execute_bidi_stream.side_effect = httpx.TimeoutException(
            "Bidi stream timeout"
        )

        transport = ConnectTransport("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="TestMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        stream = iter([{"test": "data1"}, {"test": "data2"}])
        call_options = CallOptions()

        with pytest.raises(ConnecpyException) as context:
            # Since stream_stream returns an iterator, we need to trigger the actual call
            transport.stream_stream(method, stream, call_options)

        assert context.value.code == Code.DEADLINE_EXCEEDED
        assert "timeout" in str(context.value).lower()


class TestConsistentErrorHandling(unittest.TestCase):
    """Test that errors are handled consistently across transports."""

    @patch("connecpy.transport.client.grpc.GRPC_AVAILABLE", True)
    @patch("connecpy.transport.client.grpc.grpc")
    @patch("connecpy.transport.client.connect.ConnecpyClientSync")
    def test_timeout_error_consistency(self, mock_connect_client, mock_grpc):
        """Test that both transports handle timeout errors consistently."""
        # Setup gRPC transport to raise DEADLINE_EXCEEDED
        mock_grpc_channel = MagicMock()
        mock_grpc.insecure_channel.return_value = mock_grpc_channel

        # Create a custom RpcError class and instance
        class MockRpcError(Exception):
            def __init__(self):
                super().__init__()
                self.code = lambda: mock_grpc.StatusCode.DEADLINE_EXCEEDED
                self.details = lambda: "Deadline exceeded"

        # Setup the mock StatusCode enum
        mock_grpc.StatusCode.DEADLINE_EXCEEDED = MagicMock()
        mock_grpc.RpcError = MockRpcError

        mock_grpc_stub = MagicMock(side_effect=MockRpcError())
        mock_grpc_channel.unary_unary.return_value = mock_grpc_stub

        # Setup Connect transport to raise timeout
        mock_connect = MagicMock()
        mock_connect_client.return_value = mock_connect
        mock_connect.execute_unary.side_effect = httpx.TimeoutException("Timeout")

        # Create both transports
        grpc_transport = GrpcTransport("localhost:50051")
        connect_transport = ConnectTransport("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="TestMethod",
            service_name="TestService",
            input=type("TestInput", (), {"SerializeToString": lambda _: b"test"}),
            output=type(
                "TestOutput", (), {"FromString": classmethod(lambda _, _x: {})}
            ),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        request = Mock(SerializeToString=lambda: b"test")

        # Test gRPC transport
        with pytest.raises(ConnecpyException) as grpc_context:
            grpc_transport.unary_unary(method, request, CallOptions())

        # Test Connect transport
        with pytest.raises(ConnecpyException) as connect_context:
            connect_transport.unary_unary(method, request, CallOptions())

        # Both should have the same error code
        assert grpc_context.value.code == Code.DEADLINE_EXCEEDED
        assert connect_context.value.code == Code.DEADLINE_EXCEEDED

        # Both should be ConnecpyException
        assert isinstance(grpc_context.value, ConnecpyException)
        assert isinstance(connect_context.value, ConnecpyException)


if __name__ == "__main__":
    unittest.main()
