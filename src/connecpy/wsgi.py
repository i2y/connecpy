from collections import defaultdict
from typing import List, Mapping, Union
import base64
from urllib.parse import parse_qs
from functools import partial

from . import base
from . import context
from . import errors
from . import exceptions
from . import encoding
from . import compression


def normalize_wsgi_headers(environ) -> dict:
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


def reflect_header(key: str, value: Union[str, List[str]], headers: list) -> None:
    """Add a header to the WSGI response headers list.

    Args:
        key: Header name
        value: Header value or list of values
        headers: List of header tuples to append to
    """
    if isinstance(value, list):
        if value:  # Only add if there are values
            headers.append((key, str(value[0])))
    else:
        headers.append((key, str(value)))


def format_response_headers(
    base_headers: dict, compression_info: dict, trailers: dict
) -> list[tuple[str, str]]:
    """Format response headers into WSGI compatible format.

    Args:
        base_headers (dict): Base headers from encoder
        compression_info (dict): Compression related headers
        trailers (dict): Trailer headers

    Returns:
        list[tuple[str, str]]: List of header tuples in WSGI format
    """
    # Combine all headers
    headers = {}

    # Start with base headers
    for key, value in base_headers.items():
        if isinstance(value, list):
            headers[key] = value[0] if value else ""
        else:
            headers[key] = str(value)

    # Add compression headers
    headers.update(compression_info)

    # Add trailers with prefix
    for key, value in trailers.items():
        if isinstance(value, list):
            headers[f"trailer-{key.lower()}"] = value[0] if value else ""
        else:
            headers[f"trailer-{key.lower()}"] = str(value)

    # Convert to WSGI format
    return [(str(k).lower(), str(v)) for k, v in headers.items()]


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
    base_headers: dict,
    selected_encoding: str,
    compressed_size: int = None,
) -> tuple[dict, bool]:
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
        headers["content-type"] = "application/proto"

    if selected_encoding != "identity" and compressed_size is not None:
        headers["content-encoding"] = selected_encoding
        use_compression = True

    headers["vary"] = "Accept-Encoding"
    return headers, use_compression


def read_chunked(input_stream):
    body = b""
    while True:
        line = input_stream.readline()
        if not line:
            break

        chunk_size = int(line.strip(), 16)
        if chunk_size == 0:
            # Zero-sized chunk indicates the end
            break

        chunk = input_stream.read(chunk_size)
        body += chunk
        input_stream.read(2)  # CRLF
    return body


class ConnecpyWSGIApp(base.ConnecpyBaseApp):
    """WSGI application for Connecpy."""

    def __init__(self, interceptors=None):
        """Initialize the WSGI application."""
        super().__init__(interceptors=interceptors or ())

    def add_service(self, svc):
        """Add a service to the application.

        Args:
            svc: Service instance to add
        """
        # Store the service with its full path prefix
        self._services[svc._prefix] = svc

    def _get_endpoint(self, path_info):
        """Find endpoint for given path.

        Args:
            path_info: The request path

        Returns:
            Endpoint instance matching the path

        Raises:
            ConnecpyServerException: If endpoint not found or path invalid
        """
        if not path_info:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.BadRoute,
                message="Empty path",
            )

        if path_info.startswith("/"):
            path_info = path_info[1:]

        # Split path into service path and method
        try:
            service_path, method_name = path_info.rsplit("/", 1)
        except ValueError:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.BadRoute,
                message=f"Invalid path format: {path_info}",
            )

        # Look for service
        service = self._services.get(f"/{service_path}")
        if service is None:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.BadRoute,
                message=f"No service found for path: {service_path}",
            )

        # Get endpoint from service
        endpoint = service._endpoints.get(method_name)
        if endpoint is None:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.BadRoute,
                message=f"Method not found: {method_name}",
            )

        return endpoint

    def handle_error(self, exc, environ, start_response):
        """Handle and log errors with detailed information."""
        if isinstance(exc, exceptions.ConnecpyServerException):
            status = {
                errors.Errors.InvalidArgument: "400 Bad Request",
                errors.Errors.BadRoute: "404 Not Found",
                errors.Errors.Unimplemented: "501 Not Implemented",
            }.get(exc.code, "500 Internal Server Error")

            headers = [("Content-Type", "application/json")]
            start_response(status, headers)
            return [exc.to_json_bytes()]
        else:

            headers = [("Content-Type", "application/json")]
            error = exceptions.ConnecpyServerException(
                code=errors.Errors.Internal,
                message=str(exc),
            )
            start_response("500 Internal Server Error", headers)
            return [error.to_json_bytes()]

    def _handle_post_request(self, environ, endpoint, ctx):
        """Handle POST request with body."""
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
            content_encoding = environ.get("HTTP_CONTENT_ENCODING", "identity").lower()
            if content_encoding != "identity":
                decompressor = compression.get_decompressor(content_encoding)
                if not decompressor:
                    raise exceptions.ConnecpyServerException(
                        code=errors.Errors.Unimplemented,
                        message=f"Unsupported compression: {content_encoding}",
                    )
                try:
                    req_body = decompressor(req_body)
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
                ctx = context.ConnecpyServiceContext(
                    environ.get("REMOTE_ADDR"),
                    convert_to_mapping({"content-type": ["application/proto"]}),
                )

            decoder = encoding.get_decoder_by_name(
                "proto" if content_type == "application/proto" else "json"
            )
            if not decoder:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.Unimplemented,
                    message=f"Unsupported encoding: {content_type}",
                )

            decoder = partial(decoder, data_obj=endpoint.input)
            try:
                request = decoder(req_body)
                return request
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

    def _handle_get_request(self, environ, endpoint, ctx):
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
                decompressor = compression.get_decompressor(params["compression"][0])
                if decompressor:
                    try:
                        message = decompressor(message)
                    except Exception as e:
                        raise exceptions.ConnecpyServerException(
                            code=errors.Errors.InvalidArgument,
                            message=f"Failed to decompress message: {str(e)}",
                        )

            # Handle GET request with proto decoder
            try:
                # TODO - Use content type from queryparam
                request = encoding.get_decoder_by_name("proto")(
                    message, data_obj=endpoint.input
                )
                return request
            except Exception as e:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.InvalidArgument,
                    message=f"Failed to decode proto message: {str(e)}",
                )

        except Exception as e:
            if not isinstance(e, exceptions.ConnecpyServerException):
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.Internal,
                    message=str(e),
                )
            raise

    def __call__(self, environ, start_response):
        """Handle incoming WSGI requests."""
        try:
            request_headers = normalize_wsgi_headers(environ)
            request_method = environ.get("REQUEST_METHOD")
            if request_method == "POST":
                ctx = context.ConnecpyServiceContext(
                    environ.get("REMOTE_ADDR"), convert_to_mapping(request_headers)
                )
            else:
                metadata = {}
                metadata.update(
                    extract_metadata_from_query_params(environ.get("QUERY_STRING"))
                )
                ctx = context.ConnecpyServiceContext(
                    environ.get("REMOTE_ADDR"), convert_to_mapping(metadata)
                )
            endpoint = self._get_endpoint(environ.get("PATH_INFO"))
            request_method = environ.get("REQUEST_METHOD")
            if request_method not in endpoint.allowed_methods:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.BadRoute,
                    message=f"unsupported method {request_method}",
                )
            # Handle request based on method
            if request_method == "GET":
                request = self._handle_get_request(environ, endpoint, ctx)
            else:
                request = self._handle_post_request(environ, endpoint, ctx)

            # Process request
            proc = endpoint.make_proc()
            response = proc(request, ctx)

            # Encode response
            encoder = encoding.get_encoder(endpoint, ctx.content_type())
            res_bytes, base_headers = encoder(response)

            # Handle compression if accepted
            accept_encoding = request_headers.get("accept-encoding", "identity")
            selected_encoding = compression.select_encoding(accept_encoding)
            compressed_bytes = None
            if selected_encoding != "identity":
                compressor = compression.get_compressor(selected_encoding)
                if compressor:
                    compressed_bytes = compressor(res_bytes)
            response_headers, use_compression = prepare_response_headers(
                base_headers,
                selected_encoding,
                len(compressed_bytes) if compressor is not None else None,
            )

            # Convert headers to WSGI format
            wsgi_headers = []
            for key, value in response_headers.items():
                if isinstance(value, list):
                    if value:  # Only add if there are values
                        wsgi_headers.append((key, str(value[0])))
                else:
                    wsgi_headers.append((key, str(value)))

            start_response("200 OK", wsgi_headers)
            final_response = compressed_bytes if use_compression else res_bytes
            return [final_response]
        except Exception as e:
            return self.handle_error(e, environ, start_response)
