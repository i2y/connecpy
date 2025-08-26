"""Tests for streaming RPCs with the Transport API."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from connecpy.method import IdempotencyLevel, MethodInfo
from connecpy.transport import ConnectTransport, ConnectTransportAsync


class TestConnectTransportStreaming(unittest.TestCase):
    """Test Connect transport with streaming RPCs."""

    @patch("connecpy.transport.connect.ConnecpyClientSync")
    def test_unary_stream(self, mock_client_class):
        """Test unary-stream RPC."""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock the execute_server_stream method to return an iterator
        mock_stream = iter([{"result": 1}, {"result": 2}, {"result": 3}])
        mock_client.execute_server_stream.return_value = mock_stream

        transport = ConnectTransport("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="StreamMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
        )

        # Test unary-stream call
        request = {"test": "data"}
        result_stream = transport.unary_stream(method, request)

        # Consume the stream
        results = list(result_stream)

        # Verify the client was called correctly
        mock_client.execute_server_stream.assert_called_once()
        assert len(results) == 3
        assert results[0] == {"result": 1}
        assert results[1] == {"result": 2}
        assert results[2] == {"result": 3}

    @patch("connecpy.transport.connect.ConnecpyClientSync")
    def test_stream_unary(self, mock_client_class):
        """Test stream-unary RPC."""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_client_stream.return_value = {"combined": "result"}

        transport = ConnectTransport("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="ClientStreamMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        # Test stream-unary call
        request_stream = iter([{"data": 1}, {"data": 2}, {"data": 3}])
        result = transport.stream_unary(method, request_stream)

        # Verify the client was called correctly
        mock_client.execute_client_stream.assert_called_once()
        assert result == {"combined": "result"}

    @patch("connecpy.transport.connect.ConnecpyClientSync")
    def test_stream_stream(self, mock_client_class):
        """Test stream-stream RPC."""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock the execute_bidi_stream method to return an iterator
        mock_response_stream = iter([{"response": 1}, {"response": 2}])
        mock_client.execute_bidi_stream.return_value = mock_response_stream

        transport = ConnectTransport("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="BidiStreamMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        # Test stream-stream call
        request_stream = iter([{"request": 1}, {"request": 2}])
        result_stream = transport.stream_stream(method, request_stream)

        # Consume the stream
        results = list(result_stream)

        # Verify the client was called correctly
        mock_client.execute_bidi_stream.assert_called_once()
        assert len(results) == 2
        assert results[0] == {"response": 1}
        assert results[1] == {"response": 2}


class TestConnectTransportAsyncStreaming(unittest.IsolatedAsyncioTestCase):
    """Test async Connect transport with streaming RPCs."""

    @patch("connecpy.transport.connect_async.ConnecpyClient")
    async def test_unary_stream_async(self, mock_client_class):
        """Test async unary-stream RPC."""
        # Setup mock client
        mock_client = MagicMock()  # Use MagicMock instead of AsyncMock
        mock_client_class.return_value = mock_client

        # Create an async generator for the response stream
        async def mock_stream():
            for i in range(3):
                yield {"result": i + 1}

        mock_client.execute_server_stream.return_value = mock_stream()

        transport = ConnectTransportAsync("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="StreamMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
        )

        # Test unary-stream call
        request = {"test": "data"}
        result_stream = transport.unary_stream(method, request)

        # Consume the stream
        results = []
        async for result in result_stream:
            results.append(result)

        # Verify the client was called correctly
        mock_client.execute_server_stream.assert_called_once()
        assert len(results) == 3
        assert results[0] == {"result": 1}

    @patch("connecpy.transport.connect_async.ConnecpyClient")
    async def test_stream_unary_async(self, mock_client_class):
        """Test async stream-unary RPC."""
        # Setup mock client
        mock_client = (
            AsyncMock()
        )  # Keep AsyncMock for stream_unary since it returns a single value
        mock_client_class.return_value = mock_client
        mock_client.execute_client_stream.return_value = {"combined": "result"}

        transport = ConnectTransportAsync("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="ClientStreamMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        # Test stream-unary call
        async def request_stream():
            for i in range(3):
                yield {"data": i + 1}

        result = await transport.stream_unary(method, request_stream())

        # Verify the client was called correctly
        mock_client.execute_client_stream.assert_called_once()
        assert result == {"combined": "result"}

    @patch("connecpy.transport.connect_async.ConnecpyClient")
    async def test_stream_stream_async(self, mock_client_class):
        """Test async stream-stream RPC."""
        # Setup mock client
        mock_client = MagicMock()  # Use MagicMock instead of AsyncMock
        mock_client_class.return_value = mock_client

        # Create an async generator for the response stream
        async def mock_response_stream():
            for i in range(2):
                yield {"response": i + 1}

        mock_client.execute_bidi_stream.return_value = mock_response_stream()

        transport = ConnectTransportAsync("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="BidiStreamMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        # Test stream-stream call
        async def request_stream():
            for i in range(2):
                yield {"request": i + 1}

        result_stream = transport.stream_stream(method, request_stream())

        # Consume the stream
        results = []
        async for result in result_stream:
            results.append(result)

        # Verify the client was called correctly
        mock_client.execute_bidi_stream.assert_called_once()
        assert len(results) == 2
        assert results[0] == {"response": 1}


if __name__ == "__main__":
    unittest.main()
