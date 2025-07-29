from typing import Iterable, Sequence

from google.protobuf.any import Any, pack
from google.protobuf.message import Message

from .code import Code

__all__ = ["ConnecpyException"]


class ConnecpyException(Exception):
    """
    Exception class for Connecpy server errors.

    Attributes:
        code (errors.Errors): The error code associated with the exception.
        message (str): The error message associated with the exception.
    """

    def __init__(self, code: Code, message: str, details: Iterable[Message] = ()):
        """
        Initializes a new instance of the ConnecpyException class.

        Args:
            code (int): The error code.
            message (str): The error message.
        """
        super(ConnecpyException, self).__init__(message)
        try:
            self._code = Code(code)
        except ValueError:
            self._code = Code.UNKNOWN
        self._message = message

        self._details = (
            [m if isinstance(m, Any) else pack(m) for m in details] if details else ()
        )

    @property
    def code(self):
        return self._code

    @property
    def message(self):
        return self._message

    @property
    def details(self) -> Sequence[Any]:
        return self._details
