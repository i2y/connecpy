from collections import defaultdict
from typing import Iterable, List, Mapping, Tuple

from . import base
from . import context
from . import errors
from . import exceptions


class ConnecpyWSGIApp(base.ConnecpyBaseApp):
    """WSGI application for Connecpy."""

    def __call__(self, environ, start_response):
        """
        Handle incoming WSGI requests.

        Args:
            environ (dict): The WSGI environment.
            start_response (callable): The WSGI start_response function.
        """
        try:
            if environ.get("REQUEST_METHOD") != "POST":
                raise exceptions.ConnecpyServerException(
                    code=errors.Errors.BadRoute,
                    message=f"unsupported method {environ.get('REQUEST_METHOD')} (only POST is allowed)",
                )
            ctx = context.ConnecpyServiceContext(
                environ.get("REMOTE_ADDR"), convert_to_mapping(extract_headers(environ))
            )
            endpoint = self._get_endpoint(environ.get("PATH_INFO"))
            encoder, decoder = self._get_encoder_decoder(endpoint, ctx.content_type())

            try:
                content_length = int(environ.get("CONTENT_LENGTH", "0"))
            except ValueError:
                content_length = 0
            req_body = environ["wsgi.input"].read(content_length)
            request = decoder(req_body)

            proc = endpoint.make_proc()
            response_data = proc(request, ctx)

            res_bytes, headers = encoder(response_data)
            combined_headers = dict(
                add_trailer_prefix(ctx.trailing_metadata()), **headers
            )
            final_headers = convert_to_single_string(combined_headers)

            start_response("200 OK", list(final_headers.items()))
            return [res_bytes]
        except Exception as e:
            print(e)
            return self.handle_error(e, environ, start_response)

    def handle_error(self, exc, environ, start_response):
        """
        Handle errors that occur during request processing.

        Args:
            exc (Exception): The exception that occurred.
            environ (dict): The WSGI environment.
            start_response (callable): The WSGI start_response function.
        """
        status = 500
        body_bytes = b"{}"
        try:
            if not isinstance(exc, exceptions.ConnecpyServerException):
                exc = exceptions.ConnecpyServerException(
                    code=errors.Errors.Internal, message="Internal non-Connecpy Error"
                )
            body_bytes = exc.to_json_bytes()
            status_code = errors.Errors.get_status_code(exc.code)
            status = f"{status_code} Error"  # Minimal status text representation.
        except Exception:
            exc = exceptions.ConnecpyServerException(
                code=errors.Errors.Internal,
                message="There was an error but it could not be serialized into JSON",
            )
            body_bytes = exc.to_json_bytes()
        headers = [("Content-Type", "application/json")]
        start_response(status, headers)
        return [body_bytes]


def extract_headers(environ) -> Iterable[Tuple[bytes, bytes]]:
    # Extract HTTP headers from the WSGI environment.
    headers = []
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            header = key[5:].replace("_", "-").lower().encode("utf-8")
            headers.append((header, value.encode("utf-8")))
    return headers


def convert_to_mapping(
    iterable: Iterable[Tuple[bytes, bytes]],
) -> Mapping[str, List[str]]:
    # Convert headers bytes to string and group them
    mapping = defaultdict(list)
    for key, value in iterable:
        mapping[key.decode("utf-8")].append(value.decode("utf-8"))
    return mapping


def convert_to_single_string(mapping: Mapping[str, List[str]]) -> Mapping[str, str]:
    # Join header values into a single string
    return {key: ", ".join(values) for key, values in mapping.items()}


def add_trailer_prefix(trailers: Mapping[str, List[str]]) -> Mapping[str, List[str]]:
    # Prefix trailer headers with "trailer-"
    return {f"trailer-{key}": value for key, value in trailers.items()}
