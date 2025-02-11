from connecpy.context import ClientContext
from connecpy.exceptions import ConnecpyException, ConnecpyServerException

import haberdasher_connecpy
import haberdasher_pb2


server_url = "http://localhost:3000"
timeout_s = 5


def create_large_request():
    """Create a request with a large description to test compression."""
    return haberdasher_pb2.Size(
        inches=12,
        description="A" * 2048,  # Add a 2KB string to ensure compression is worthwhile
    )


def main():
    client = haberdasher_connecpy.HaberdasherClient(server_url, timeout=timeout_s)

    # Example 1: POST request with gzip compression (large request)
    try:
        print("\nTesting POST request with gzip compression...")
        response = client.MakeHat(
            ctx=ClientContext(
                headers={
                    "Content-Encoding": "gzip",  # Request compression
                    "Accept-Encoding": "gzip",  # Response compression
                }
            ),
            request=create_large_request(),
        )
        print("POST with gzip compression successful:", response)
    except (ConnecpyException, ConnecpyServerException) as e:
        print("POST with gzip compression failed:", str(e))

    # Example 2: POST request with brotli compression (large request)
    try:
        print("\nTesting POST request with brotli compression...")
        response = client.MakeHat(
            ctx=ClientContext(
                headers={
                    "Content-Encoding": "br",  # Request compression
                    "Accept-Encoding": "br",  # Response compression
                }
            ),
            request=create_large_request(),
        )
        print("POST with brotli compression successful:", response)
    except (ConnecpyException, ConnecpyServerException) as e:
        print("POST with brotli compression failed:", str(e))

    # Example 3: GET request without compression
    try:
        print("\nTesting GET request without compression...")
        response = client.MakeHat(
            ctx=ClientContext(),  # No compression headers
            request=haberdasher_pb2.Size(inches=8),  # Small request
            use_get=True,
        )
        print("GET without compression successful:", response)
    except (ConnecpyException, ConnecpyServerException) as e:
        print("GET without compression failed:", str(e))

    # Example 4: GET request with ztstd compression (large request)
    try:
        print("\nTesting GET request with gzip compression...")
        response = client.MakeHat(
            ctx=ClientContext(
                headers={
                    "Accept-Encoding": "zstd",  # Response compression
                    "Content-Encoding": "zstd",  # Request compression
                }
            ),
            request=create_large_request(),
            use_get=True,
        )
        print("GET with zstd compression successful:", response)
    except (ConnecpyException, ConnecpyServerException) as e:
        print("GET with zstd compression failed:", str(e))

    # Example 5: Test multiple accepted encodings
    try:
        print("\nTesting POST with multiple accepted encodings...")
        response = client.MakeHat(
            ctx=ClientContext(
                headers={
                    "Content-Encoding": "br",  # Request compression
                    "Accept-Encoding": "gzip, br, zstd",  # Response compression (in order of preference)
                }
            ),
            request=create_large_request(),
        )
        print("POST with multiple encodings successful:", response)
    except (ConnecpyException, ConnecpyServerException) as e:
        print("POST with multiple encodings failed:", str(e))


if __name__ == "__main__":
    main()
