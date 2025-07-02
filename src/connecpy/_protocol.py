from dataclasses import dataclass
from http import HTTPStatus
import json

import httpx

from .errors import Errors
from .exceptions import ConnecpyServerException


# Define a custom class for HTTP Status to allow adding 499 status code
@dataclass(frozen=True)
class ExtendedHTTPStatus:
    code: int
    reason: str

    @staticmethod
    def from_http_status(status: HTTPStatus) -> "ExtendedHTTPStatus":
        return ExtendedHTTPStatus(code=status.value, reason=status.phrase)


# Dedupe statuses that are mapped multiple times
_BAD_REQUEST = ExtendedHTTPStatus.from_http_status(HTTPStatus.BAD_REQUEST)
_CONFLICT = ExtendedHTTPStatus.from_http_status(HTTPStatus.CONFLICT)
_INTERNAL_SERVER_ERROR = ExtendedHTTPStatus.from_http_status(
    HTTPStatus.INTERNAL_SERVER_ERROR
)

_error_to_http_status = {
    Errors.Canceled: ExtendedHTTPStatus(499, "Client Closed Request"),
    Errors.Unknown: _INTERNAL_SERVER_ERROR,
    Errors.InvalidArgument: _BAD_REQUEST,
    Errors.DeadlineExceeded: ExtendedHTTPStatus.from_http_status(
        HTTPStatus.GATEWAY_TIMEOUT
    ),
    Errors.NotFound: ExtendedHTTPStatus.from_http_status(HTTPStatus.NOT_FOUND),
    Errors.AlreadyExists: _CONFLICT,
    Errors.PermissionDenied: ExtendedHTTPStatus.from_http_status(HTTPStatus.FORBIDDEN),
    Errors.ResourceExhausted: ExtendedHTTPStatus.from_http_status(
        HTTPStatus.TOO_MANY_REQUESTS
    ),
    Errors.FailedPrecondition: _BAD_REQUEST,
    Errors.Aborted: _CONFLICT,
    Errors.OutOfRange: _BAD_REQUEST,
    Errors.Unimplemented: ExtendedHTTPStatus.from_http_status(
        HTTPStatus.NOT_IMPLEMENTED
    ),
    Errors.Internal: _INTERNAL_SERVER_ERROR,
    Errors.Unavailable: ExtendedHTTPStatus.from_http_status(
        HTTPStatus.SERVICE_UNAVAILABLE
    ),
    Errors.DataLoss: _INTERNAL_SERVER_ERROR,
    Errors.Unauthenticated: ExtendedHTTPStatus.from_http_status(
        HTTPStatus.UNAUTHORIZED
    ),
    # Custom error codes not defined by Connect
    Errors.NoError: ExtendedHTTPStatus.from_http_status(HTTPStatus.OK),
    Errors.BadRoute: ExtendedHTTPStatus.from_http_status(HTTPStatus.NOT_FOUND),
    Errors.Malformed: _BAD_REQUEST,
}


_http_status_code_to_error = {
    400: Errors.Internal,
    401: Errors.Unauthenticated,
    403: Errors.PermissionDenied,
    404: Errors.Unimplemented,
    429: Errors.Unavailable,
    502: Errors.Unavailable,
    503: Errors.Unavailable,
    504: Errors.Unavailable,
}


@dataclass(frozen=True, kw_only=True)
class ConnectWireError:
    code: Errors
    message: str

    @staticmethod
    def from_exception(exc: Exception) -> "ConnectWireError":
        if isinstance(exc, ConnecpyServerException):
            return ConnectWireError(code=exc.code, message=exc.message)
        return ConnectWireError(code=Errors.Unknown, message=str(exc))

    @staticmethod
    def from_response(response: httpx.Response) -> "ConnectWireError":
        try:
            data = response.json()
        except Exception:
            data = None
        if isinstance(data, dict):
            code_str = data.get("code")
            if code_str:
                code = Errors.from_string(code_str)
            else:
                code = _http_status_code_to_error.get(
                    response.status_code, Errors.Unknown
                )
            message = data.get("message", "")
        else:
            code = _http_status_code_to_error.get(response.status_code, Errors.Unknown)
            try:
                http_status = HTTPStatus(response.status_code)
                message = http_status.phrase
            except ValueError:
                if response.status_code == 499:
                    message = "Client Closed Request"
                else:
                    message = ""
        return ConnectWireError(code=code, message=message)

    def to_exception(self) -> ConnecpyServerException:
        return ConnecpyServerException(code=self.code, message=self.message)

    def to_http_status(self) -> ExtendedHTTPStatus:
        return _error_to_http_status.get(self.code, _INTERNAL_SERVER_ERROR)

    def to_json_bytes(self) -> bytes:
        return json.dumps({"code": self.code.value, "message": self.message}).encode(
            "utf-8"
        )
