"""Simple gRPC server for testing the Transport API."""

import time
from concurrent import futures

try:
    import grpc
except ImportError:
    print("grpcio not installed. Install with: pip install grpcio")
    exit(1)

from google.protobuf import empty_pb2

from example import haberdasher_pb2, haberdasher_pb2_grpc


class HaberdasherServicer(haberdasher_pb2_grpc.HaberdasherServicer):
    """Implementation of the Haberdasher service."""

    def MakeHat(self, request, context):  # noqa: N802
        """Make a hat of a given size."""
        # Simple color selection based on size
        colors = ["red", "blue", "green", "yellow", "purple", "orange"]
        color = colors[request.inches % len(colors)]

        # Simple name based on size
        if request.inches < 10:
            name = "Small Cap"
        elif request.inches < 20:
            name = "Medium Hat"
        else:
            name = "Large Sombrero"

        return haberdasher_pb2.Hat(size=request.inches, color=color, name=name)

    def MakeFlexibleHat(self, request_iterator, context):  # noqa: N802
        """Make a hat from multiple size requests."""
        total_size = 0
        count = 0
        for size_request in request_iterator:
            total_size += size_request.inches
            count += 1

        avg_size = total_size // count if count > 0 else 12
        return haberdasher_pb2.Hat(
            size=avg_size, color="flexible", name=f"Average of {count} sizes"
        )

    def MakeSimilarHats(self, request, context):  # noqa: N802
        """Make multiple similar hats."""
        base_size = request.inches
        colors = ["red", "blue", "green"]

        for i, color in enumerate(colors):
            yield haberdasher_pb2.Hat(
                size=base_size + i, color=color, name=f"Hat #{i + 1}"
            )

    def MakeVariousHats(self, request_iterator, context):  # noqa: N802
        """Make various hats from multiple requests."""
        for i, size_request in enumerate(request_iterator):
            yield haberdasher_pb2.Hat(
                size=size_request.inches,
                color=f"color_{i}",
                name=f"Custom Hat #{i + 1}",
            )

    def ListParts(self, request, context):  # noqa: N802
        """List available hat parts."""
        parts = ["brim", "crown", "band", "feather", "buckle"]
        for part in parts:
            yield haberdasher_pb2.Hat.Part(id=part)

    def DoNothing(self, request, context):  # noqa: N802
        """Do nothing and return empty."""
        return empty_pb2.Empty()


def serve():
    """Start the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    haberdasher_pb2_grpc.add_HaberdasherServicer_to_server(
        HaberdasherServicer(), server
    )

    port = "50051"
    server.add_insecure_port(f"[::]:{port}")
    server.start()

    print(f"gRPC server started on port {port}")
    print("Press Ctrl+C to stop the server")

    try:
        while True:
            time.sleep(86400)  # Sleep for a day
    except KeyboardInterrupt:
        server.stop(0)
        print("\nServer stopped")


if __name__ == "__main__":
    serve()
