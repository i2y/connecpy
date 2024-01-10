import traceback
from collections import defaultdict
from typing import Iterable, List, Mapping, Tuple

from starlette.requests import Request
from starlette.responses import Response

from . import base
from . import context
from . import errors
from . import exceptions


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
        ctx = context.ConnecpyServiceContext(
            scope["client"], convert_to_mapping(scope["headers"])
        )
        try:
            http_method = scope["method"]
            if http_method != "POST":
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.BadRoute,
                    message=f"unsupported method {http_method} (only POST is allowed)",
                )

            endpoint = self._get_endpoint(scope["path"])
            invocation_metadata = ctx.invocation_metadata()
            ctype = invocation_metadata.get("content-type", ["application/proto"])[0]
            encoder, decoder = self._get_encoder_decoder(endpoint, ctype)

            req_body = await Request(scope, receive).body()
            request = decoder(req_body)

            proc = endpoint.make_async_proc(self._interceptors)

            response_data = await proc(request, ctx)

            res_bytes, headers = encoder(response_data)
            headers = dict(add_trailer_prefix(ctx.trailing_metadata()), **headers)
            response = Response(res_bytes, headers=convert_to_single_string(headers))
            await response(scope, receive, send)
        except Exception as e:
            await self.handle_error(e, scope, receive, send)

    async def handle_error(self, exc, scope, receive, send):
        """
        Handle errors that occur during request processing.

        Args:
            exc (Exception): The exception that occurred.
            scope (dict): The ASGI scope.
            receive (callable): The ASGI receive function.
            send (callable): The ASGI send function.
        """
        status = 500
        body_bytes = b"{}"
        error_data = {}
        try:
            if not isinstance(exc, exceptions.ConnecpyServerException):
                error_data["raw_error"] = str(exc)
                error_data["raw_trace"] = traceback.format_exc()
                exc = exceptions.ConnecpyServerException(
                    code=errors.Errors.Internal, message="Internal non-Connecpy Error"
                )

            body_bytes = exc.to_json_bytes()
            status = errors.Errors.get_status_code(exc.code)
        except Exception as e:
            exc = exceptions.ConnecpyServerException(
                code=errors.Errors.Internal,
                message="There was an error but it could not be serialized into JSON",
            )
            error_data["raw_error"] = str(exc)
            error_data["raw_trace"] = traceback.format_exc()
            body_bytes = exc.to_json_bytes()

        response = Response(
            body_bytes, status_code=status, media_type="application/json"
        )
        await response(scope, receive, send)


def convert_to_mapping(
    iterable: Iterable[Tuple[bytes, bytes]]
) -> Mapping[str, List[str]]:
    result = defaultdict(list)
    for key, value in iterable:
        result[key.decode("utf-8")].append(value.decode("utf-8"))
    return dict(result)


def convert_to_single_string(mapping: Mapping[str, List[str]]) -> Mapping[str, str]:
    return {key: ", ".join(values) for key, values in mapping.items()}


def add_trailer_prefix(trailers: Mapping[str, List[str]]) -> Mapping[str, List[str]]:
    return {f"trailer-{key}": values for key, values in trailers.items()}
