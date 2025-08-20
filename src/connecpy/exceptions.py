__all__ = ["ConnecpyException"]


from collections.abc import Iterable, Sequence

from google.protobuf.any import Any, pack
from google.protobuf.message import Message

from .code import Code


class ConnecpyException(Exception):
    def __init__(
        self, code: Code, message: str, details: Iterable[Message] = ()
    ) -> None:
        """
        Initializes a new Connecpy exception. If raised in a server, the same exception
        will be raised in the client.

        Args:
            code: The error code.
            message: The error message.
            details: Additional details about the error.
        """
        super().__init__(message)
        self._code = code
        self._message = message

        self._details = (
            [m if isinstance(m, Any) else pack(m) for m in details] if details else ()
        )

    @property
    def code(self) -> Code:
        return self._code

    @property
    def message(self) -> str:
        return self._message

    @property
    def details(self) -> Sequence[Any]:
        return self._details
