import http.client as httplib
import json

from . import errors


class ConnecpyException(Exception):
    """Base exception class for Connecpy."""

    pass


class ConnecpyServerException(httplib.HTTPException):
    """
    Exception class for Connecpy server errors.

    Attributes:
        code (errors.Errors): The error code associated with the exception.
        message (str): The error message associated with the exception.
    """

    def __init__(self, *, code, message):
        """
        Initializes a new instance of the ConnecpyServerException class.

        Args:
            code (int): The error code.
            message (str): The error message.
        """
        try:
            self._code = errors.Errors(code)
        except ValueError:
            self._code = errors.Errors.Unknown
        self._message = message
        super(ConnecpyServerException, self).__init__(message)

    @property
    def code(self):
        if isinstance(self._code, errors.Errors):
            return self._code
        return errors.Errors.Unknown

    @property
    def message(self):
        return self._message

    def to_dict(self):
        return {"code": self._code.value, "msg": self._message}

    def to_json_bytes(self):
        return json.dumps(self.to_dict()).encode("utf-8")

    @staticmethod
    def from_json(err_dict):
        return ConnecpyServerException(
            code=err_dict.get("code", errors.Errors.Unknown),
            message=err_dict.get("msg", ""),
        )


def InvalidArgument(*args, argument, error):
    return ConnecpyServerException(
        code=errors.Errors.InvalidArgument,
        message="{} {}".format(argument, error),
    )


def RequiredArgument(*args, argument):
    return InvalidArgument(argument=argument, error="is required")


def connecpy_error_from_intermediary(status, reason, headers, body):
    if 300 <= status < 400:
        # connecpy uses POST which should not redirect
        code = errors.Errors.Internal
        location = headers.get("location")
        message = f'unexpected HTTP status code {status} "{reason}" received, Location="{location}"'

    else:
        code = {
            400: errors.Errors.Internal,  # JSON response should have been returned
            401: errors.Errors.Unauthenticated,
            403: errors.Errors.PermissionDenied,
            404: errors.Errors.BadRoute,
            429: errors.Errors.ResourceExhausted,
            502: errors.Errors.Unavailable,
            503: errors.Errors.Unavailable,
            504: errors.Errors.Unavailable,
        }.get(status, errors.Errors.Unknown)

        message = f'Error from intermediary with HTTP status code {status} "{reason}"'

    return ConnecpyServerException(code=code, message=message)
