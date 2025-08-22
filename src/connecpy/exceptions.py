__all__ = ["ConnecpyException"]


from collections.abc import Iterable, Sequence

from google.protobuf.any import Any, pack
from google.protobuf.message import Message

from .code import Code


class ConnecpyException(Exception):
    """An exception in a Connect RPC.

    If a server raises a ConnecpyException, the same exception content will be
    raised on the client as well. Errors surfacing on the client side such as
    timeouts will also be raised as a ConnecpyException with an appropriate
    code.
    """

    def __init__(
        self, code: Code, message: str, details: Iterable[Message] = ()
    ) -> None:
        """
        Creates a new Connecpy exception.

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
