from base64 import b64decode, b64encode
from dataclasses import dataclass
from http import HTTPStatus
from typing import cast, Optional
import json

import httpx
from google.protobuf.any_pb2 import Any

from .errors import Errors
from .exceptions import ConnecpyServerException


CONNECT_PROTOCOL_VERSION = "1"


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
    details: Optional[list[Any]]

    @staticmethod
    def from_exception(exc: Exception) -> "ConnectWireError":
        if isinstance(exc, ConnecpyServerException):
            return ConnectWireError(
                code=exc.code, message=exc.message, details=list(exc.details)
            )
        return ConnectWireError(code=Errors.Unknown, message=str(exc), details=None)

    @staticmethod
    def from_response(response: httpx.Response) -> "ConnectWireError":
        try:
            data = response.json()
        except Exception:
            data = None
        details: Optional[list[Any]] = None
        if isinstance(data, dict):
            code_str = data.get("code")
            if code_str:
                code = Errors.from_string(code_str)
            else:
                code = _http_status_code_to_error.get(
                    response.status_code, Errors.Unknown
                )
            message = data.get("message", "")
            details_json = cast(Optional[list[dict[str, str]]], data.get("details"))
            if details_json:
                details = []
                for detail in details_json:
                    detail_type = detail.get("type")
                    detail_value = detail.get("value")
                    if detail_type is None or detail_value is None:
                        # Ignore malformed details
                        continue
                    details.append(
                        Any(
                            type_url="type.googleapis.com/" + detail_type,
                            value=b64decode(detail_value + "==="),
                        )
                    )
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
        return ConnectWireError(code=code, message=message, details=details)

    def to_exception(self) -> ConnecpyServerException:
        return ConnecpyServerException(
            code=self.code, message=self.message, details=self.details
        )

    def to_http_status(self) -> ExtendedHTTPStatus:
        return _error_to_http_status.get(self.code, _INTERNAL_SERVER_ERROR)

    def to_json_bytes(self) -> bytes:
        data: dict = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.details:
            details: list[dict[str, str]] = []
            for detail in self.details:
                if detail.type_url.startswith("type.googleapis.com/"):
                    detail_type = detail.type_url[len("type.googleapis.com/") :]
                else:
                    detail_type = detail.type_url
                details.append(
                    {
                        "type": detail_type,
                        "value": b64encode(detail.value).decode("utf-8"),
                    }
                )
            data["details"] = details
        return json.dumps(data).encode("utf-8")


class HTTPException(Exception):
    """An HTTP exception returned directly before starting the connect protocol."""

    def __init__(self, status: HTTPStatus, headers: list[tuple[str, str]]):
        self.status = status
        self.headers = headers
