"""Integration test for gRPC transport."""

from concurrent import futures

import pytest

try:
    import grpc  # type: ignore[import-untyped]
except ImportError:
    pytest.skip("grpc not available", allow_module_level=True)

from connecpy.method import IdempotencyLevel, MethodInfo
from connecpy.transport.client import GrpcTransport

from . import haberdasher_pb2

try:
    from . import haberdasher_pb2_grpc  # type: ignore[import-not-found]
except ImportError:
    # haberdasher_pb2_grpc might not be generated, create a minimal stub
    class HaberdasherServicer:
        """Minimal servicer stub."""

        def MakeHat(self, request, context):  # noqa: N802
            pass

    haberdasher_pb2_grpc = type(
        "Module",
        (),
        {
            "HaberdasherServicer": HaberdasherServicer,
            "add_HaberdasherServicer_to_server": lambda _service, _server: None,
        },
    )


class SimpleHaberdasherService(haberdasher_pb2_grpc.HaberdasherServicer):  # type: ignore[name-defined]
    """Simple test service."""

    def MakeHat(self, request, context):  # noqa: N802
        return haberdasher_pb2.Hat(
            size=request.inches, color="test-color", name="test-hat"
        )


@pytest.fixture
def grpc_server():
    """Start a gRPC server for testing."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    service = SimpleHaberdasherService()
    haberdasher_pb2_grpc.add_HaberdasherServicer_to_server(service, server)  # type: ignore[attr-defined]
    port = server.add_insecure_port("[::]:0")
    server.start()
    yield port
    server.stop(grace=0)


def test_grpc_transport_basic(grpc_server):
    """Test basic gRPC transport functionality."""
    transport = GrpcTransport(f"localhost:{grpc_server}")

    method = MethodInfo(
        name="MakeHat",
        service_name="i2y.connecpy.example.Haberdasher",
        input=haberdasher_pb2.Size,
        output=haberdasher_pb2.Hat,
        idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
    )

    request = haberdasher_pb2.Size(inches=10, description="Test")
    response = transport.unary_unary(method, request)

    assert response.size == 10
    assert response.color == "test-color"
    assert response.name == "test-hat"

    transport.close()
