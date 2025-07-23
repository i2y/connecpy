from collections import defaultdict
from http import HTTPStatus
from typing import Any, Iterable, List, Mapping, Optional
import base64
from urllib.parse import parse_qs
from wsgiref.types import WSGIEnvironment, StartResponse

from . import _server_shared
from . import errors
from . import exceptions
from ._codec import Codec, get_codec
from . import _compression
from ._protocol import (
    CONNECT_UNARY_CONTENT_TYPE_PREFIX,
    ConnectWireError,
    HTTPException,
    codec_name_from_content_type,
)


def _normalize_wsgi_headers(environ: WSGIEnvironment) -> dict:
    """Extract and normalize HTTP headers from WSGI environment."""
    headers = {}
    if "CONTENT_TYPE" in environ:
        headers["content-type"] = environ["CONTENT_TYPE"].lower()
    if "CONTENT_LENGTH" in environ:
        headers["content-length"] = environ["CONTENT_LENGTH"].lower()

    for key, value in environ.items():
        if key.startswith("HTTP_"):
            header = key[5:].replace("_", "-").lower()
            headers[header] = value
    return headers


def convert_to_mapping(headers: dict) -> Mapping[str, List[str]]:
    """Convert headers dictionary to the expected mapping format."""
    result = defaultdict(list)
    for key, value in headers.items():
        key = key.lower()
        if isinstance(value, (list, tuple)):
            result[key].extend(str(v) for v in value)
        else:
            result[key] = [str(value)]
    return result


def extract_metadata_from_query_params(query_string: str) -> dict:
    """Extract metadata from query parameters into a dictionary."""
    return parse_qs(query_string) if query_string else {}


def validate_request_headers(headers: dict) -> tuple[str, str]:
    """Validate and normalize request headers.

    Args:
        headers: Dictionary of request headers

    Returns:
        tuple[str, str]: Normalized content type and content encoding
    """
    # Get content type
    content_type = headers.get("content-type", "application/json").lower()
    if content_type not in ["application/json", "application/proto"]:
        raise exceptions.ConnecpyServerException(
            code=errors.Errors.InvalidArgument,
            message=f"Unsupported Content-Type: {content_type}",
        )

    # Get content encoding
    content_encoding = headers.get("content-encoding", "identity").lower()
    if content_encoding not in ["identity", "gzip", "br", "zstd"]:
        raise exceptions.ConnecpyServerException(
            code=errors.Errors.Unimplemented,
            message=f"Unsupported Content-Encoding: {content_encoding}",
        )

    return content_type, content_encoding


def prepare_response_headers(
    base_headers: dict[str, list[str]],
    selected_encoding: str,
    compressed_size: Optional[int] = None,
) -> tuple[dict[str, list[str]], bool]:
    """Prepare response headers and determine if compression should be used.

    Args:
        base_headers: Base response headers
        selected_encoding: Selected compression encoding
        compressed_size: Size of compressed content (if compression was attempted)

    Returns:
        tuple[dict, bool]: Final headers and whether to use compression
    """
    headers = base_headers.copy()
    use_compression = False

    if "content-type" not in headers:
        headers["content-type"] = ["application/proto"]

    if selected_encoding != "identity" and compressed_size is not None:
        headers["content-encoding"] = [selected_encoding]
        use_compression = True

    headers["vary"] = ["Accept-Encoding"]
    return headers, use_compression


def read_chunked(input_stream):
    chunks = []
    while True:
        line = input_stream.readline()
        if not line:
            break

        chunk_size = int(line.strip(), 16)
        if chunk_size == 0:
            # Zero-sized chunk indicates the end
            break

        chunk = input_stream.read(chunk_size)
        chunks.append(chunk)
        input_stream.read(2)  # CRLF
    return b"".join(chunks)


class ConnecpyWSGIApplication:
    """WSGI application for Connecpy."""

    def __init__(self, *, path: str, endpoints: Mapping[str, _server_shared.Endpoint]):
        """Initialize the WSGI application."""
        super().__init__()
        self._path = path
        self._endpoints = endpoints

    @property
    def path(self) -> str:
        """Get the path to mount the application to."""
        return self._path

    def __call__(
        self, environ: WSGIEnvironment, start_response: StartResponse
    ) -> Iterable[bytes]:
        """Handle incoming WSGI requests."""
        try:
            request_headers = _normalize_wsgi_headers(environ)
            request_method = environ.get("REQUEST_METHOD")
            if request_method == "POST":
                ctx = _server_shared.ServiceContext(
                    environ.get("REMOTE_ADDR", ""), convert_to_mapping(request_headers)
                )
            else:
                metadata = {}
                metadata.update(
                    extract_metadata_from_query_params(environ.get("QUERY_STRING", ""))
                )
                ctx = _server_shared.ServiceContext(
                    environ.get("REMOTE_ADDR", ""), convert_to_mapping(metadata)
                )

            path = environ["PATH_INFO"]
            if not path:
                path = "/"

            endpoint = self._endpoints.get(path)
            if not endpoint and environ["SCRIPT_NAME"] == self._path:
                # The application was mounted at the service's path so we reconstruct
                # the full URL.
                endpoint = self._endpoints.get(self._path + path)

            if not endpoint:
                raise HTTPException(HTTPStatus.NOT_FOUND, [])

            request_method = environ["REQUEST_METHOD"]
            if request_method not in endpoint.allowed_methods:
                raise HTTPException(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    [("Allow", ", ".join(endpoint.allowed_methods))],
                )
            # Handle request based on method
            if request_method == "GET":
                request, codec = self._handle_get_request(environ, endpoint, ctx)
            else:
                request, codec = self._handle_post_request(
                    environ, endpoint, ctx, request_headers
                )

            # Process request
            proc = endpoint.make_proc()
            response = proc(request, ctx)

            # Encode response
            res_bytes = codec.encode(response)
            base_headers = {
                "content-type": [f"{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{codec.name()}"]
            }

            # Handle compression if accepted
            accept_encoding = request_headers.get("accept-encoding", "identity")
            selected_encoding = _compression.select_encoding(accept_encoding)
            compressed_bytes = None
            if selected_encoding != "identity":
                compression = _compression.get_compression(selected_encoding)
                if compression:
                    compressed_bytes = compression.compress(res_bytes)
            response_headers, use_compression = prepare_response_headers(
                base_headers,
                selected_encoding,
                len(compressed_bytes) if compressed_bytes is not None else None,
            )

            # Convert headers to WSGI format
            wsgi_headers: list[tuple[str, str]] = []
            for key, values in response_headers.items():
                for value in values:
                    wsgi_headers.append((key.lower(), value))
            wsgi_headers.extend(
                (key.lower(), value) for key, value in ctx.response_headers()
            )
            for key, value in ctx.response_trailers():
                wsgi_headers.append((f"trailer-{key.lower()}", value))

            start_response("200 OK", wsgi_headers)
            final_response = (
                compressed_bytes if use_compression and compressed_bytes else res_bytes
            )
            return [final_response]
        except Exception as e:
            return self._handle_error(e, environ, start_response)

    def _handle_post_request(
        self,
        environ: WSGIEnvironment,
        endpoint: _server_shared.Endpoint,
        ctx: _server_shared.ServiceContext,
        request_headers: dict[str, str],
    ) -> tuple[Any, Codec]:
        """Handle POST request with body."""

        codec_name = codec_name_from_content_type(
            request_headers.get("content-type", "")
        )
        codec = get_codec(codec_name)
        if not codec:
            raise HTTPException(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                [("Accept-Post", "application/json, application/proto")],
            )

        try:
            content_length = environ.get("CONTENT_LENGTH")
            if not content_length:
                content_length = 0
            else:
                content_length = int(content_length)
            if content_length > 0:
                req_body = environ["wsgi.input"].read(content_length)
            else:
                input_stream = environ["wsgi.input"]
                req_body = read_chunked(input_stream)

            # Handle compression if specified
            compression_name = environ.get("HTTP_CONTENT_ENCODING", "identity").lower()
            if compression_name != "identity":
                compression = _compression.get_compression(compression_name)
                if not compression:
                    raise exceptions.ConnecpyServerException(
                        code=errors.Errors.Unimplemented,
                        message=f"unknown compression: '{compression_name}': supported encodings are {', '.join(_compression.get_available_compressions())}",
                    )
                try:
                    req_body = compression.decompress(req_body)
                except Exception as e:
                    raise exceptions.ConnecpyServerException(
                        code=errors.Errors.InvalidArgument,
                        message=f"Failed to decompress request body: {str(e)}",
                    )

            # Get decoder based on content type
            content_type = ctx.content_type()

            # Default to proto if not specified
            if content_type not in ["application/json", "application/proto"]:
                content_type = "application/proto"
                ctx = _server_shared.ServiceContext(
                    environ.get("REMOTE_ADDR", ""),
                    convert_to_mapping({"content-type": ["application/proto"]}),
                )

            try:
                return codec.decode(req_body, endpoint.input()), codec
            except Exception as e:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.InvalidArgument,
                    message=f"Failed to decode request body: {str(e)}",
                )

        except Exception as e:
            if not isinstance(e, exceptions.ConnecpyServerException):
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.Internal,
                    message=str(e),  # TODO
                )
            raise

    def _handle_get_request(self, environ, endpoint, ctx) -> tuple[Any, Codec]:
        """Handle GET request with query parameters."""
        try:
            query_string = environ.get("QUERY_STRING", "")
            params = parse_qs(query_string)

            if "message" not in params:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.InvalidArgument,
                    message="'message' parameter is required for GET requests",
                )

            message = params["message"][0]

            if "base64" in params and params["base64"][0] == "1":
                try:
                    message = base64.urlsafe_b64decode(message.encode("ascii"))
                except Exception as e:
                    raise exceptions.ConnecpyServerException(
                        code=errors.Errors.InvalidArgument,
                        message=f"Invalid base64 encoding: {str(e)}",
                    )
            else:
                message = message.encode("utf-8")

            # Handle compression if specified
            if "compression" in params:
                compression_name = params["compression"][0]
                compression = _compression.get_compression(compression_name)
                if not compression:
                    raise exceptions.ConnecpyServerException(
                        code=errors.Errors.Unimplemented,
                        message=f"unknown compression: '{compression_name}': supported encodings are {', '.join(_compression.get_available_compressions())}",
                    )
                message = compression.decompress(message)

            codec_name = params.get("encoding", ("",))[0]
            codec = get_codec(codec_name)
            if not codec:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.Unimplemented,
                    message=f"invalid message encoding: '{codec_name}'",
                )
            # Handle GET request with proto decoder
            try:
                # TODO - Use content type from queryparam
                request = codec.decode(message, endpoint.input())
                return request, codec
            except Exception as e:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.InvalidArgument,
                    message=f"Failed to decode message: {str(e)}",
                )

        except Exception as e:
            if not isinstance(e, exceptions.ConnecpyServerException):
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.Internal,
                    message=str(e),
                )
            raise

    def _handle_error(self, exc, _environ, start_response):
        """Handle and log errors with detailed information."""
        if isinstance(exc, HTTPException):
            start_response(
                f"{exc.status.value} {exc.status.phrase}",
                exc.headers,
            )
            return []
        wire_error = ConnectWireError.from_exception(exc)
        http_status = wire_error.to_http_status()
        status = f"{http_status.code} {http_status.reason}"
        headers = [("Content-Type", "application/json")]
        start_response(status, headers)
        return [wire_error.to_json_bytes()]
