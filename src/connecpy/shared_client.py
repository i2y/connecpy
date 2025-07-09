import base64
from typing import Iterable, Optional

from httpx import Headers

from ._protocol import CONNECT_PROTOCOL_VERSION


# TODO: Embed package version correctly
_DEFAULT_CONNECT_USER_AGENT = "connecpy/0.0.0"


def prepare_headers(
    headers: Headers,
    timeout_ms: Optional[int],
    accept_compression: Optional[Iterable[str]],
    send_compression: Optional[str],
) -> Headers:
    if "user-agent" not in headers:
        headers["user-agent"] = _DEFAULT_CONNECT_USER_AGENT
    headers["connect-protocol-version"] = CONNECT_PROTOCOL_VERSION
    if accept_compression is not None:
        headers["accept-encoding"] = ", ".join(accept_compression)
    else:
        headers["accept-encoding"] = "gzip, br, zstd"
    if send_compression is not None:
        headers["content-encoding"] = send_compression
    else:
        headers.pop("content-encoding", None)
    headers["content-type"] = "application/proto"
    if timeout_ms is not None:
        headers["connect-timeout-ms"] = str(timeout_ms)
    return headers


def compress_request(request, headers, compression):
    request_data = request.SerializeToString()
    # If compression is requested
    if "content-encoding" in headers:
        compression_name = headers["content-encoding"].lower()
        compressor = compression.get_compressor(compression_name)
        if not compressor:
            raise Exception(f"Unsupported compression method: {compression_name}")
        try:
            compressed = compressor(request_data)
            if len(compressed) < len(request_data):
                # Optionally, log compression details
                request_data = compressed
            else:
                headers.pop("content-encoding", None)
        except Exception as e:
            raise Exception(
                f"Failed to compress request with {compression_name}: {str(e)}"
            )
    return request_data, headers


def prepare_get_params(request_data, headers):
    params = {}
    if request_data:
        params["message"] = base64.urlsafe_b64encode(request_data).decode("ascii")
        params["base64"] = "1"
        params["encoding"] = (
            "proto" if headers.get("content-type") == "application/proto" else "json"
        )
    if "content-encoding" in headers:
        params["compression"] = headers.pop("content-encoding")
    return params
