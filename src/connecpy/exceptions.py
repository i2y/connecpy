__all__ = ["ConnecpyException"]


from typing import Iterable, Sequence

from google.protobuf.any import Any, pack
from google.protobuf.message import Message

from .code import Code


class ConnecpyException(Exception):
    def __init__(self, code: Code, message: str, details: Iterable[Message] = ()):
        """
        Initializes a new Connecpy exception. If raised in a server, the same exception
        will be raised in the client.

        Args:
            code: The error code.
            message: The error message.
            details: Additional details about the error.
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
