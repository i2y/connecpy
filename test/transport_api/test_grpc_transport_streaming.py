"""Integration tests for gRPC transport with streaming RPCs."""

from concurrent import futures
from unittest.mock import patch

import pytest

try:
    import grpc
    import grpc.aio
except ImportError:
    pytest.skip("grpc not available", allow_module_level=True)

from connecpy.method import IdempotencyLevel, MethodInfo
from connecpy.transport.client import GrpcTransport, GrpcTransportAsync
from example import haberdasher_pb2, haberdasher_pb2_grpc


class StreamingHaberdasherService(haberdasher_pb2_grpc.HaberdasherServicer):
    """Test service with streaming methods."""

    def MakeHat(self, request, context):  # noqa: N802
        """Unary-unary RPC."""
        return haberdasher_pb2.Hat(
            size=request.inches, color="test-color", name="test-hat"
        )

    def StreamHats(self, request, context):  # noqa: N802
        """Unary-stream RPC - Returns multiple hats for one size."""
        colors = ["red", "blue", "green"]
        for color in colors:
            yield haberdasher_pb2.Hat(
                size=request.inches, color=color, name=f"{color}-hat"
            )

    def MakeHatFromSizes(self, request_iterator, context):  # noqa: N802
        """Stream-unary RPC - Takes multiple sizes and returns one hat."""
        total_size = 0
        count = 0
        for size_request in request_iterator:
            total_size += size_request.inches
            count += 1
        avg_size = total_size // count if count > 0 else 0
        return haberdasher_pb2.Hat(
            size=avg_size, color="averaged", name=f"avg-{avg_size}-hat"
        )

    def StreamToStream(self, request_iterator, context):  # noqa: N802
        """Stream-stream RPC - Transforms each input size to a hat."""
        for size_request in request_iterator:
            yield haberdasher_pb2.Hat(
                size=size_request.inches,
                color=f"color-{size_request.inches}",
                name=f"hat-{size_request.inches}",
            )


@pytest.fixture
def grpc_server():
    """Start a gRPC server with streaming support for testing."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    service = StreamingHaberdasherService()
    haberdasher_pb2_grpc.add_HaberdasherServicer_to_server(service, server)
    port = server.add_insecure_port("[::]:0")
    server.start()
    yield port
    server.stop(grace=0)


def test_grpc_unary_stream(grpc_server):
    """Test unary-stream RPC with gRPC transport."""
    transport = GrpcTransport(f"localhost:{grpc_server}")

    # Mock the method to return stream output type
    method = MethodInfo(
        name="StreamHats",
        service_name="i2y.connecpy.example.Haberdasher",
        input=haberdasher_pb2.Size,
        output=haberdasher_pb2.Hat,
        idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
    )

    # Since the actual service doesn't have StreamHats, we need to mock it
    with patch.object(transport, "_get_or_create_stub") as mock_stub:
        # Create a mock that returns an iterator
        def mock_stream_call(request, metadata=None, timeout=None):  # noqa: ARG001
            colors = ["red", "blue", "green"]
            for color in colors:
                yield haberdasher_pb2.Hat(
                    size=request.inches, color=color, name=f"{color}-hat"
                )

        mock_stub.return_value = mock_stream_call

        request = haberdasher_pb2.Size(inches=12, description="Test")
        response_stream = transport.unary_stream(method, request)

        # Consume the stream
        hats = list(response_stream)

        assert len(hats) == 3
        assert hats[0].color == "red"
        assert hats[1].color == "blue"
        assert hats[2].color == "green"
        assert all(hat.size == 12 for hat in hats)

    transport.close()


def test_grpc_stream_unary(grpc_server):
    """Test stream-unary RPC with gRPC transport."""
    transport = GrpcTransport(f"localhost:{grpc_server}")

    method = MethodInfo(
        name="MakeHatFromSizes",
        service_name="i2y.connecpy.example.Haberdasher",
        input=haberdasher_pb2.Size,
        output=haberdasher_pb2.Hat,
        idempotency_level=IdempotencyLevel.UNKNOWN,
    )

    # Mock the stub to handle stream input
    with patch.object(transport, "_get_or_create_stub") as mock_stub:

        def mock_stream_unary_call(request_stream, metadata=None, timeout=None):  # noqa: ARG001
            total_size = 0
            count = 0
            for size_request in request_stream:
                total_size += size_request.inches
                count += 1
            avg_size = total_size // count if count > 0 else 0
            return haberdasher_pb2.Hat(
                size=avg_size, color="averaged", name=f"avg-{avg_size}-hat"
            )

        mock_stub.return_value = mock_stream_unary_call

        # Create a stream of sizes
        def size_stream():
            for inches in [10, 12, 14]:
                yield haberdasher_pb2.Size(inches=inches, description=f"Size {inches}")

        response = transport.stream_unary(method, size_stream())

        assert response.size == 12  # Average of 10, 12, 14
        assert response.color == "averaged"
        assert response.name == "avg-12-hat"

    transport.close()


def test_grpc_stream_stream(grpc_server):
    """Test stream-stream RPC with gRPC transport."""
    transport = GrpcTransport(f"localhost:{grpc_server}")

    method = MethodInfo(
        name="StreamToStream",
        service_name="i2y.connecpy.example.Haberdasher",
        input=haberdasher_pb2.Size,
        output=haberdasher_pb2.Hat,
        idempotency_level=IdempotencyLevel.UNKNOWN,
    )

    # Mock the stub to handle bidirectional streaming
    with patch.object(transport, "_get_or_create_stub") as mock_stub:

        def mock_stream_stream_call(request_stream, metadata=None, timeout=None):  # noqa: ARG001
            for size_request in request_stream:
                yield haberdasher_pb2.Hat(
                    size=size_request.inches,
                    color=f"color-{size_request.inches}",
                    name=f"hat-{size_request.inches}",
                )

        mock_stub.return_value = mock_stream_stream_call

        # Create a stream of sizes
        def size_stream():
            for inches in [8, 10, 12]:
                yield haberdasher_pb2.Size(inches=inches, description=f"Size {inches}")

        response_stream = transport.stream_stream(method, size_stream())

        # Consume the response stream
        hats = list(response_stream)

        assert len(hats) == 3
        assert hats[0].size == 8
        assert hats[0].color == "color-8"
        assert hats[1].size == 10
        assert hats[1].color == "color-10"
        assert hats[2].size == 12
        assert hats[2].color == "color-12"

    transport.close()


@pytest.mark.asyncio
async def test_grpc_async_unary_stream(grpc_server):
    """Test async unary-stream RPC with gRPC transport."""
    transport = GrpcTransportAsync(f"localhost:{grpc_server}")

    method = MethodInfo(
        name="StreamHats",
        service_name="i2y.connecpy.example.Haberdasher",
        input=haberdasher_pb2.Size,
        output=haberdasher_pb2.Hat,
        idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
    )

    # Mock the async stub
    with patch.object(transport, "_get_or_create_stub") as mock_stub:

        async def async_stream():
            colors = ["red", "blue", "green"]
            for color in colors:
                yield haberdasher_pb2.Hat(size=12, color=color, name=f"{color}-hat")

        def mock_stream_call(request, metadata=None, timeout=None):  # noqa: ARG001
            return async_stream()

        mock_stub.return_value = mock_stream_call

        request = haberdasher_pb2.Size(inches=12, description="Test")
        response_stream = transport.unary_stream(method, request)

        # Consume the async stream
        hats = []
        async for hat in response_stream:
            hats.append(hat)

        assert len(hats) == 3
        assert hats[0].color == "red"
        assert hats[1].color == "blue"
        assert hats[2].color == "green"

    await transport.close()


@pytest.mark.asyncio
async def test_grpc_async_stream_unary(grpc_server):
    """Test async stream-unary RPC with gRPC transport."""
    transport = GrpcTransportAsync(f"localhost:{grpc_server}")

    method = MethodInfo(
        name="MakeHatFromSizes",
        service_name="i2y.connecpy.example.Haberdasher",
        input=haberdasher_pb2.Size,
        output=haberdasher_pb2.Hat,
        idempotency_level=IdempotencyLevel.UNKNOWN,
    )

    # Mock the async stub
    with patch.object(transport, "_get_or_create_stub") as mock_stub:

        async def mock_stream_unary_call(request_stream, metadata=None, timeout=None):  # noqa: ARG001
            total_size = 0
            count = 0
            async for size_request in request_stream:
                total_size += size_request.inches
                count += 1
            avg_size = total_size // count if count > 0 else 0
            return haberdasher_pb2.Hat(
                size=avg_size, color="averaged", name=f"avg-{avg_size}-hat"
            )

        mock_stub.return_value = mock_stream_unary_call

        # Create an async stream of sizes
        async def size_stream():
            for inches in [10, 12, 14]:
                yield haberdasher_pb2.Size(inches=inches, description=f"Size {inches}")

        response = await transport.stream_unary(method, size_stream())

        assert response.size == 12  # Average of 10, 12, 14
        assert response.color == "averaged"

    await transport.close()


@pytest.mark.asyncio
async def test_grpc_async_stream_stream(grpc_server):
    """Test async stream-stream RPC with gRPC transport."""
    transport = GrpcTransportAsync(f"localhost:{grpc_server}")

    method = MethodInfo(
        name="StreamToStream",
        service_name="i2y.connecpy.example.Haberdasher",
        input=haberdasher_pb2.Size,
        output=haberdasher_pb2.Hat,
        idempotency_level=IdempotencyLevel.UNKNOWN,
    )

    # Mock the async stub
    with patch.object(transport, "_get_or_create_stub") as mock_stub:

        async def mock_stream_stream_gen(request_stream, metadata=None, timeout=None):  # noqa: ARG001
            async for size_request in request_stream:
                yield haberdasher_pb2.Hat(
                    size=size_request.inches,
                    color=f"color-{size_request.inches}",
                    name=f"hat-{size_request.inches}",
                )

        def mock_stream_stream_call(request_stream, metadata=None, timeout=None):
            return mock_stream_stream_gen(request_stream, metadata, timeout)

        mock_stub.return_value = mock_stream_stream_call

        # Create an async stream of sizes
        async def size_stream():
            for inches in [8, 10, 12]:
                yield haberdasher_pb2.Size(inches=inches, description=f"Size {inches}")

        response_stream = transport.stream_stream(method, size_stream())

        # Consume the async response stream
        hats = []
        async for hat in response_stream:
            hats.append(hat)

        assert len(hats) == 3
        assert hats[0].size == 8
        assert hats[1].size == 10
        assert hats[2].size == 12

    await transport.close()
