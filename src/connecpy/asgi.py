from collections import defaultdict
from http import HTTPStatus
from typing import Iterable, List, Mapping, Tuple, TYPE_CHECKING
from urllib.parse import parse_qs
import base64
from functools import partial

from . import base
from . import context
from . import errors
from . import exceptions
from . import encoding
from . import compression
from ._protocol import ConnectWireError, HTTPException


if TYPE_CHECKING:
    # We don't use asgiref code so only import from it for type checking
    from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, HTTPScope, Scope
else:
    ASGIReceiveCallable = "ASGIReceiveCallable"
    ASGISendCallable = "ASGISendCallable"
    HTTPScope = "HTTPScope"
    Scope = "Scope"


class ConnecpyASGIApp(base.ConnecpyBaseApp):
    """ASGI application for Connecpy."""

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
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
                raise HTTPException(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    [("allow", ", ".join(endpoint.allowed_methods))],
                )

            headers = _process_headers(scope.get("headers", ()))
            accept_encoding = _get_header_value(headers, "accept-encoding")
            selected_encoding = compression.select_encoding(accept_encoding)

            client = scope["client"]
            peer = f"{client[0]}:{client[1]}" if client else ""
            ctx = context.ConnecpyServiceContext(peer, headers)

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
                    headers["content-encoding"] = [selected_encoding]

            final_headers = {key: ", ".join(values) for key, values in headers.items()}

            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (k.lower().encode(), v.encode())
                        for k, v in final_headers.items()
                    ],
                    # TODO: Map trailers correctly if possible. Will be hard to do with unit tests
                    # due to poor support in Python ecosystem.
                    "trailers": False,
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": res_bytes,
                    "more_body": False,
                }
            )

        except Exception as e:
            await self._handle_error(e, scope, receive, send)

    async def _handle_get_request(
        self, scope: HTTPScope, ctx: context.ConnecpyServiceContext
    ):
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

    async def _handle_post_request(
        self, scope: HTTPScope, receive, ctx: context.ConnecpyServiceContext
    ):
        """Handle POST request with body."""
        # Get request body and endpoint
        endpoint = self._get_endpoint(scope["path"])
        req_body = await self._read_body(receive)

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

    async def _read_body(self, receive: ASGIReceiveCallable) -> bytes:
        """Read the body of the request."""
        chunks = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.Canceled,
                    message="Client disconnected before request completion",
                )
            else:
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.Unknown,
                    message="Unexpected message type",
                )
        return b"".join(chunks)

    async def _handle_error(
        self,
        exc,
        scope: HTTPScope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
    ) -> None:
        """Handle errors that occur during request processing."""
        if isinstance(exc, HTTPException):
            http_status = exc.status.value
            headers = [(k.encode("utf-8"), v.encode("utf-8")) for k, v in exc.headers]
            await send(
                {
                    "type": "http.response.start",
                    "status": http_status,
                    "headers": headers,
                    "trailers": False,
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"",
                    "more_body": False,
                }
            )
            return
        wire_error = ConnectWireError.from_exception(exc)
        http_status = wire_error.to_http_status()

        headers = [
            (b"content-type", b"application/json"),
        ]

        await send(
            {
                "type": "http.response.start",
                "status": http_status.code,
                "headers": headers,
                "trailers": False,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": wire_error.to_json_bytes(),
                "more_body": False,
            }
        )


def _process_headers(
    iterable: Iterable[Tuple[bytes, bytes]],
) -> Mapping[str, list[str]]:
    result = defaultdict(list)
    for key, value in iterable:
        result[key.decode("utf-8").lower()].append(value.decode("utf-8"))
    return result


def _get_header_value(headers: Mapping[str, list[str]], name: str) -> str:
    values = headers.get(name, ())
    if not values:
        return ""
    return values[0]
