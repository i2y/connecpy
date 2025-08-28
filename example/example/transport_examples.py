"""Examples of using the Transport API with both Connect and gRPC protocols.

IMPORTANT: The Transport API automatically handles the RequestContext (ctx) parameter
for all RPC methods. When using clients created with create_client_sync() or
create_client(), you only need to pass the request message - the ctx parameter
is managed internally by the transport layer.
"""

import json
import ssl
from pathlib import Path

import grpc
import httpx
from connecpy.transport.client import ConnectTransport, GrpcTransport

# Import the service-specific create_client_sync function
from example.haberdasher_connecpy import create_client_sync
from example.haberdasher_pb2 import Size


def example_connect_insecure():
    """Example of using Connect transport with insecure connection."""
    # Create a Connect transport with HTTP
    transport = ConnectTransport("http://localhost:3000")

    # Create a client using the transport
    client = create_client_sync(transport)

    # Make a request
    # Note: The Transport API handles the RequestContext (ctx) parameter internally,
    # so we only need to pass the request message
    request = Size(inches=12)
    response = client.make_hat(request)  # ctx is handled automatically
    print(f"Connect (insecure) got hat: {response.color} (size: {response.size})")


def example_connect_secure():
    """Example of using Connect transport with TLS/HTTPS."""
    # Create a custom httpx client with TLS configuration
    # You can customize SSL context, certificates, etc.
    ssl_context = ssl.create_default_context()
    # Optionally load custom CA certificates
    # ssl_context.load_verify_locations("path/to/ca.pem")

    session = httpx.Client(
        verify=ssl_context,  # Or verify="path/to/ca.pem"
        cert=("path/to/client.crt", "path/to/client.key"),  # Client cert if needed
        timeout=30.0,
    )

    # Create a Connect transport with HTTPS and custom session
    transport = ConnectTransport(
        "https://api.example.com", session=session, timeout_ms=5000
    )

    # Create a client using the transport
    client = create_client_sync(transport)

    # Make a request
    request = Size(inches=12)
    response = client.make_hat(request)
    print(f"Connect (TLS) got hat: {response.color} (size: {response.size})")


def example_connect_with_compression():
    """Example of using Connect transport with compression."""
    transport = ConnectTransport(
        "http://localhost:3000",
        accept_compression=["gzip", "br"],  # Accept gzip and brotli
        send_compression="gzip",  # Send with gzip
    )

    client = create_client_sync(transport)

    request = Size(inches=12)
    response = client.make_hat(request)
    print(f"Connect (compressed) got hat: {response.color}")


def example_grpc_insecure():
    """Example of using gRPC transport with insecure connection."""
    # Create a gRPC transport without credentials (insecure)
    transport = GrpcTransport("localhost:50051")

    # Create a client using the transport
    client = create_client_sync(transport)

    # Make a request
    request = Size(inches=12)
    response = client.make_hat(request)
    print(f"gRPC (insecure) got hat: {response.color} (size: {response.size})")


def example_grpc_secure():
    """Example of using gRPC transport with TLS."""
    # Load TLS credentials
    ca_cert = Path("path/to/ca.pem").read_bytes()

    # Create channel credentials
    credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_cert
        # Optional: client certificate and key
        # private_key=client_key,
        # certificate_chain=client_cert,
    )

    # Create a gRPC transport with TLS
    transport = GrpcTransport(
        "api.example.com:443",
        credentials=credentials,
        options=[
            ("grpc.ssl_target_name_override", "api.example.com"),
            ("grpc.max_receive_message_length", 10 * 1024 * 1024),  # 10MB
        ],
    )

    # Create a client using the transport
    client = create_client_sync(transport)

    # Make a request
    request = Size(inches=12)
    response = client.make_hat(request)
    print(f"gRPC (TLS) got hat: {response.color} (size: {response.size})")


def example_grpc_with_retry():
    """Example of using gRPC transport with retry configuration."""
    # gRPC service config for retry
    service_config = {
        "methodConfig": [
            {
                "name": [{"service": "i2y.connecpy.example.Haberdasher"}],
                "retryPolicy": {
                    "maxAttempts": 5,
                    "initialBackoff": "0.1s",
                    "maxBackoff": "10s",
                    "backoffMultiplier": 2,
                    "retryableStatusCodes": ["UNAVAILABLE", "DEADLINE_EXCEEDED"],
                },
            }
        ]
    }

    transport = GrpcTransport(
        "localhost:50051", options=[("grpc.service_config", json.dumps(service_config))]
    )

    client = create_client_sync(transport)

    request = Size(inches=12)
    response = client.make_hat(request)
    print(f"gRPC (with retry) got hat: {response.color}")


def example_grpc_with_compression():
    """Example of using gRPC transport with compression."""
    transport = GrpcTransport(
        "localhost:50051",
        compression="gzip",  # or grpc.Compression.Gzip
    )

    client = create_client_sync(transport)

    request = Size(inches=12)
    response = client.make_hat(request)
    print(f"gRPC (compressed) got hat: {response.color}")


def example_switching_protocols():
    """Example showing how easy it is to switch between protocols."""

    def make_hat_with_transport(transport):
        """Make a hat using any transport."""
        client = create_client_sync(transport)
        request = Size(inches=12)
        return client.make_hat(request)

    # Try with Connect
    connect_transport = ConnectTransport("http://localhost:3000")
    hat1 = make_hat_with_transport(connect_transport)
    print(f"Connect hat: {hat1.color}")

    # Try with gRPC (same client code!)
    grpc_transport = GrpcTransport("localhost:50051")
    hat2 = make_hat_with_transport(grpc_transport)
    print(f"gRPC hat: {hat2.color}")


if __name__ == "__main__":
    # Run the examples that don't require external servers
    print("Transport API Examples")
    print("=" * 50)

    # These would work if servers are running:
    # example_connect_insecure()
    # example_grpc_insecure()
    # example_switching_protocols()

    print("\nTo run these examples, start the appropriate servers:")
    print("  Connect: uv run uvicorn --port 3000 example.server:app")
    print("  gRPC: uv run python example/grpc_server.py")
