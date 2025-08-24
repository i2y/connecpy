"""Tests for the Transport API and create_client functionality."""

import unittest
from unittest.mock import MagicMock, Mock, patch

from connecpy.method import IdempotencyLevel, MethodInfo
from connecpy.transport import CallOptions, ConnectTransport, GrpcTransport
from connecpy.transport.client import create_client_sync


class TestConnectTransport(unittest.TestCase):
    """Test the ConnectTransport class."""

    def test_connect_transport_init(self):
        """Test ConnectTransport initialization with all parameters."""
        transport = ConnectTransport(
            "http://localhost:3000",
            proto_json=True,
            accept_compression=["gzip"],
            send_compression="gzip",
            timeout_ms=5000,
            read_max_bytes=1000000,
            interceptors=[],
            session=None,
        )

        assert transport.address == "http://localhost:3000"
        assert transport.proto_json is True
        assert transport.accept_compression == ["gzip"]
        assert transport.send_compression == "gzip"
        assert transport.timeout_ms == 5000
        assert transport.read_max_bytes == 1000000

    @patch("connecpy.transport.connect.ConnecpyClientSync")
    def test_connect_transport_unary_call(self, mock_client_class):
        """Test ConnectTransport unary_unary method."""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_unary.return_value = {"result": "test"}

        transport = ConnectTransport("http://localhost:3000")

        # Create test method info
        method = MethodInfo(
            name="TestMethod",
            service_name="TestService",
            input=type("TestInput", (), {}),
            output=type("TestOutput", (), {}),
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        # Test unary call
        request = {"test": "data"}
        call_options = CallOptions(headers={"x-test": "header"}, timeout_ms=1000)

        result = transport.unary_unary(method, request, call_options)

        # Verify the client was called correctly
        mock_client.execute_unary.assert_called_once()
        assert result == {"result": "test"}

    def test_connect_transport_close(self):
        """Test ConnectTransport close method."""
        with patch(
            "connecpy.transport.connect.ConnecpyClientSync"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            transport = ConnectTransport("http://localhost:3000")
            transport.close()

            mock_client.close.assert_called_once()


class TestGrpcTransport(unittest.TestCase):
    """Test the GrpcTransport class."""

    @patch("connecpy.transport.grpc.GRPC_AVAILABLE", True)
    @patch("connecpy.transport.grpc.grpc")
    def test_grpc_transport_init_insecure(self, mock_grpc):
        """Test GrpcTransport initialization with insecure channel."""
        mock_grpc.insecure_channel.return_value = MagicMock()

        transport = GrpcTransport("localhost:50051")

        mock_grpc.insecure_channel.assert_called_once_with(
            "localhost:50051", options=[]
        )
        assert transport._target == "localhost:50051"

    @patch("connecpy.transport.grpc.GRPC_AVAILABLE", True)
    @patch("connecpy.transport.grpc.grpc")
    def test_grpc_transport_init_secure(self, mock_grpc):
        """Test GrpcTransport initialization with secure channel."""
        mock_grpc.secure_channel.return_value = MagicMock()
        mock_credentials = MagicMock()

        _ = GrpcTransport(
            "api.example.com:443",
            credentials=mock_credentials,
            options=[("grpc.max_receive_message_length", 10000000)],
        )

        mock_grpc.secure_channel.assert_called_once_with(
            "api.example.com:443",
            mock_credentials,
            options=[("grpc.max_receive_message_length", 10000000)],
        )

    @patch("connecpy.transport.grpc.GRPC_AVAILABLE", True)
    @patch("connecpy.transport.grpc.grpc")
    def test_grpc_transport_with_compression(self, mock_grpc):
        """Test GrpcTransport with compression."""
        mock_grpc.insecure_channel.return_value = MagicMock()

        _ = GrpcTransport("localhost:50051", compression="gzip")

        # Check that compression was added to options
        call_args = mock_grpc.insecure_channel.call_args
        options = call_args[1]["options"]
        # The transport converts "gzip" to the numeric value 2
        assert ("grpc.default_compression_algorithm", 2) in options

    @patch("connecpy.transport.grpc.GRPC_AVAILABLE", True)
    @patch("connecpy.transport.grpc.grpc")
    def test_grpc_transport_unary_call(self, mock_grpc):
        """Test GrpcTransport unary_unary method."""
        mock_channel = MagicMock()
        mock_grpc.insecure_channel.return_value = mock_channel

        # Setup mock stub
        mock_stub = MagicMock()
        mock_stub.return_value = {"result": "test"}
        mock_channel.unary_unary.return_value = mock_stub

        transport = GrpcTransport("localhost:50051")

        # Create test method info with type mocks
        input_type = type("TestInput", (), {"SerializeToString": lambda _: b"test"})
        output_type = type(
            "TestOutput", (), {"FromString": classmethod(lambda _, x: {"parsed": x})}
        )
        method = MethodInfo(
            name="TestMethod",
            service_name="TestService",
            input=input_type,
            output=output_type,
            idempotency_level=IdempotencyLevel.UNKNOWN,
        )

        # Test unary call
        request = Mock(SerializeToString=lambda: b"test_request")
        call_options = CallOptions(headers={"x-test": "header"}, timeout_ms=1000)

        result = transport.unary_unary(method, request, call_options)

        # Verify stub was called
        mock_stub.assert_called_once_with(
            request, metadata=[("x-test", "header")], timeout=1.0
        )
        assert result == {"result": "test"}


class TestCreateClientSync(unittest.TestCase):
    """Test the create_client_sync function."""

    @patch("importlib.import_module")
    def test_create_client_with_connect_transport(self, mock_import):
        """Test creating a client with ConnectTransport."""
        # Setup mock module with client class
        mock_module = MagicMock()
        mock_client_class = MagicMock()
        mock_module.TestServiceClientSync = mock_client_class
        mock_import.return_value = mock_module

        # Create mock service class
        service_class = type(
            "TestService", (), {"__module__": "test.module", "__name__": "TestService"}
        )

        # Create transport
        transport = ConnectTransport("http://localhost:3000")

        # Create client
        client = create_client_sync(service_class, transport)  # noqa: F841

        # Verify client was created with correct parameters
        mock_client_class.assert_called_once_with(
            address="http://localhost:3000",
            proto_json=False,
            accept_compression=None,
            send_compression=None,
            timeout_ms=None,
            read_max_bytes=None,
            interceptors=(),
            session=None,
        )

    @patch("importlib.import_module")
    @patch("connecpy.transport.grpc.GRPC_AVAILABLE", True)
    @patch("connecpy.transport.grpc.grpc")
    def test_create_client_with_grpc_transport(self, mock_grpc, mock_import):
        """Test creating a client with GrpcTransport."""
        # Setup mock channel
        mock_channel = MagicMock()
        mock_grpc.insecure_channel.return_value = mock_channel

        # Setup mock service module with wrapper class
        mock_service_module = MagicMock()
        mock_wrapper_class = MagicMock()
        mock_wrapper_instance = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper_instance
        mock_service_module.TestServiceGrpcWrapperSync = mock_wrapper_class

        # Setup mock grpc module with stub class
        mock_grpc_module = MagicMock()
        mock_stub_class = MagicMock()
        mock_stub_instance = MagicMock()
        mock_stub_class.return_value = mock_stub_instance
        mock_grpc_module.TestServiceStub = mock_stub_class

        # Mock the import to return appropriate modules
        def import_side_effect(name):
            if name.endswith("_pb2_grpc"):
                return mock_grpc_module
            return mock_service_module

        mock_import.side_effect = import_side_effect

        # Create mock service class
        service_class = type(
            "TestService",
            (),
            {"__module__": "test.module.service_connecpy", "__name__": "TestService"},
        )

        # Create transport
        transport = GrpcTransport("localhost:50051")

        # Create client
        client = create_client_sync(service_class, transport)

        # Verify stub was created with the channel
        mock_stub_class.assert_called_once_with(mock_channel)

        # Verify wrapper was created with the stub
        mock_wrapper_class.assert_called_once_with(mock_stub_instance)

        # Verify we got the wrapper instance
        assert client == mock_wrapper_instance


if __name__ == "__main__":
    unittest.main()
