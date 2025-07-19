from connecpy.exceptions import ConnecpyException, ConnecpyServerException

from . import haberdasher_connecpy
from . import haberdasher_pb2


server_url = "http://localhost:3000"
timeout_ms = 5000


def create_large_request():
    """Create a request with a large description to test compression."""
    return haberdasher_pb2.Size(
        inches=12,
        description="A" * 2048,  # Add a 2KB string to ensure compression is worthwhile
    )


def main():
    # Example 1: POST request with gzip compression (large request)
    with haberdasher_connecpy.HaberdasherClientSync(
        server_url,
        timeout_ms=timeout_ms,
        send_compression="gzip",
        accept_compression=("gzip",),
    ) as client:
        try:
            print("\nTesting POST request with gzip compression...")
            response = client.MakeHat(
                request=create_large_request(),
            )
            print("POST with gzip compression successful:", response)
        except (ConnecpyException, ConnecpyServerException) as e:
            print("POST with gzip compression failed:", str(e))

    # Example 2: POST request with brotli compression (large request)
    with haberdasher_connecpy.HaberdasherClientSync(
        server_url,
        timeout_ms=timeout_ms,
        send_compression="br",
        accept_compression=("br",),
    ) as client:
        try:
            print("\nTesting POST request with brotli compression...")
            response = client.MakeHat(
                request=create_large_request(),
            )
            print("POST with brotli compression successful:", response)
        except (ConnecpyException, ConnecpyServerException) as e:
            print("POST with brotli compression failed:", str(e))

    # Example 3: GET request without compression
    with haberdasher_connecpy.HaberdasherClientSync(
        server_url, timeout_ms=timeout_ms, accept_compression=()
    ) as client:
        try:
            print("\nTesting GET request without compression...")
            response = client.MakeHat(
                request=haberdasher_pb2.Size(inches=8),  # Small request
                use_get=True,
            )
            print("GET without compression successful:", response)
        except (ConnecpyException, ConnecpyServerException) as e:
            print("GET without compression failed:", str(e))

    # Example 4: GET request with ztstd compression (large request)
    with haberdasher_connecpy.HaberdasherClientSync(
        server_url,
        timeout_ms=timeout_ms,
        send_compression="zstd",
        accept_compression=("zstd",),
    ) as client:
        try:
            print("\nTesting GET request with gzip compression...")
            response = client.MakeHat(
                request=create_large_request(),
                use_get=True,
            )
            print("GET with zstd compression successful:", response)
        except (ConnecpyException, ConnecpyServerException) as e:
            print("GET with zstd compression failed:", str(e))

    # Example 5: Test multiple accepted encodings
    with haberdasher_connecpy.HaberdasherClientSync(
        server_url,
        timeout_ms=timeout_ms,
        send_compression="br",
    ) as client:
        try:
            print("\nTesting POST with multiple accepted encodings...")
            response = client.MakeHat(
                request=create_large_request(),
            )
            print("POST with multiple encodings successful:", response)
        except (ConnecpyException, ConnecpyServerException) as e:
            print("POST with multiple encodings failed:", str(e))


if __name__ == "__main__":
    main()
