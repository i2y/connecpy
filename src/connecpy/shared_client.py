import base64


def prepare_headers(ctx, kwargs, timeout):
    headers = {k.lower(): v for k, v in ctx.get_headers().items()}
    if "headers" in kwargs:
        headers.update({k.lower(): v for k, v in kwargs.pop("headers").items()})
    # Ensure consistent header casing
    if "content-type" in headers:
        headers["content-type"] = headers.pop("content-type")
    if "content-encoding" in headers:
        headers["content-encoding"] = headers.pop("content-encoding")
    if "accept-encoding" in headers:
        headers["accept-encoding"] = headers.pop("accept-encoding")
    # Set default headers
    if "content-type" not in headers:
        headers["content-type"] = "application/proto"
    if "accept-encoding" not in headers:
        headers["accept-encoding"] = "gzip, br, zstd"
    if "timeout" not in kwargs:
        kwargs["timeout"] = timeout
        headers["connect-timeout-ms"] = str(timeout * 1000)
    kwargs["headers"] = headers
    return headers, kwargs


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
