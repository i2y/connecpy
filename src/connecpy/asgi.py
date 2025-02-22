from collections import defaultdict
from typing import Iterable, List, Mapping, Tuple
from urllib.parse import parse_qs
import base64
from functools import partial

from starlette.requests import Request

from . import base
from . import context
from . import errors
from . import exceptions
from . import encoding
from . import compression


class ConnecpyASGIApp(base.ConnecpyBaseApp):
    """ASGI application for Connecpy."""

    async def __call__(self, scope, receive, send):
        """
        Handle incoming ASGI requests.

        Args:
            scope (dict): The ASGI scope.
            receive (callable): The ASGI receive function.
            send (callable): The ASGI send function.
        """
        assert scope["type"] == "http"
        try:
            http_method = scope["method"]
            endpoint = self._get_endpoint(scope["path"])
            if http_method not in endpoint.allowed_methods:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.BadRoute,
                    message=f"unsupported method {http_method}",
                )

            headers = scope.get("headers", [])
            accept_encoding = compression.extract_header_value(
                headers, b"accept-encoding"
            )
            selected_encoding = compression.select_encoding(accept_encoding)

            ctx = context.ConnecpyServiceContext(
                scope["client"], convert_to_mapping(headers)
            )

            if http_method == "GET":
                request = await self._handle_get_request(scope, ctx)
            else:
                request = await self._handle_post_request(scope, receive, ctx)

            proc = endpoint.make_async_proc(self._interceptors)
            response_data = await proc(request, ctx)

            encoder = encoding.get_encoder(endpoint, ctx.content_type())
            res_bytes, headers = encoder(response_data)

            # Compress response if needed
            if selected_encoding != "identity":
                compressor = compression.get_compressor(selected_encoding)
                if compressor:
                    res_bytes = compressor(res_bytes)
                    headers["Content-Encoding"] = [selected_encoding]

            combined_headers = dict(
                add_trailer_prefix(ctx.trailing_metadata()), **headers
            )
            final_headers = convert_to_single_string(combined_headers)

            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (k.lower().encode(), v.encode())
                        for k, v in final_headers.items()
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": res_bytes,
                }
            )

        except Exception as e:
            await self.handle_error(e, scope, receive, send)

    async def _handle_get_request(self, scope, ctx):
        """Handle GET request with query parameters."""
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)

        # Validation
        if "message" not in params:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.InvalidArgument,
                message="'message' parameter is required for GET requests",
            )

        # Get and decode message
        message = params["message"][0]
        is_base64 = "base64" in params and params["base64"][0] == "1"

        if is_base64:
            try:
                message = base64.urlsafe_b64decode(message)
            except Exception:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.InvalidArgument,
                    message="Invalid base64 encoding",
                )
        else:
            message = message.encode("utf-8")

        # Handle encoding
        encoding_name = params.get("encoding", ["json"])[0]
        decoder = encoding.get_decoder_by_name(encoding_name)
        if not decoder:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unimplemented,
                message=f"Unsupported encoding: {encoding_name}",
            )

        # Handle compression
        compression_name = params.get("compression", ["identity"])[0]
        decompressor = compression.get_decompressor(compression_name)
        if not decompressor:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unimplemented,
                message=f"Unsupported compression: {compression_name}",
            )

        # Decompress and decode message
        if message:  # Don't decompress empty messages
            message = decompressor(message)

        # Get the appropriate decoder for the endpoint
        endpoint = self._get_endpoint(scope["path"])
        decoder = partial(decoder, data_obj=endpoint.input)
        return decoder(message)

    async def _handle_post_request(self, scope, receive, ctx):
        """Handle POST request with body."""
        # Get request body and endpoint
        request = Request(scope, receive)
        endpoint = self._get_endpoint(scope["path"])
        req_body = await request.body()

        if len(req_body) > self._max_receive_message_length:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.InvalidArgument,
                message=f"Request body exceeds maximum size of {self._max_receive_message_length} bytes",
            )

        # Handle compression if specified
        compression_header = (
            dict(scope["headers"]).get(b"content-encoding", b"identity").decode("ascii")
        )
        decompressor = compression.get_decompressor(compression_header)
        if not decompressor:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unimplemented,
                message=f"Unsupported compression: {compression_header}",
            )

        if req_body:  # Don't decompress empty body
            req_body = decompressor(req_body)

        # Get the decoder based on content type
        base_decoder = encoding.get_decoder_by_name(
            "proto" if ctx.content_type() == "application/proto" else "json"
        )
        if not base_decoder:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unimplemented,
                message=f"Unsupported encoding: {ctx.content_type()}",
            )

        decoder = partial(base_decoder, data_obj=endpoint.input)
        return decoder(req_body)

    async def handle_error(self, exc, scope, receive, send):
        """Handle errors that occur during request processing."""
        if not isinstance(exc, exceptions.ConnecpyServerException):
            exc = exceptions.ConnecpyServerException(
                code=errors.Errors.Internal,
                message=str(exc),
            )

        status = errors.Errors.get_status_code(exc.code)
        headers = [
            (b"content-type", b"application/json"),
        ]

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": exc.to_json_bytes(),
            }
        )


def convert_to_mapping(
    iterable: Iterable[Tuple[bytes, bytes]],
) -> Mapping[str, List[str]]:
    result = defaultdict(list)
    for key, value in iterable:
        result[key.decode("utf-8")].append(value.decode("utf-8"))
    return dict(result)


def convert_to_single_string(mapping: Mapping[str, List[str]]) -> Mapping[str, str]:
    return {key: ", ".join(values) for key, values in mapping.items()}


def add_trailer_prefix(trailers: Mapping[str, List[str]]) -> Mapping[str, List[str]]:
    return {f"trailer-{key}": values for key, values in trailers.items()}
