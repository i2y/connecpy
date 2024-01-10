from typing import Any, Protocol, Mapping, MutableMapping, List
import time

from . import exceptions


class ClientContext:
    """Context object for storing context information of
    request currently being processed.

    Attributes:
        _values (Dict[str, Any]): Dictionary to store context key-value pairs.
        _headers (MutableMapping[str, str]): Request headers.
        _response_headers (MutableMapping[str, str]): Response headers.
    """

    def __init__(self, *, headers: MutableMapping[str, str] | None = None):
        """Create a new Context object

        Keyword arguments:
        headers (MutableMapping[str, str] | None): Headers for the request.
        """

        self._values = {}
        if headers is None:
            headers = {}
        self._headers = headers
        self._response_headers: MutableMapping[str, str] = {}

    def set(self, key: str, value: Any) -> None:
        """Set a Context value

        Args:
            key (str): Key for the context key-value pair.
            value (Any): Value to be stored.
        """

        self._values[key] = value

    def get(self, key: str) -> Any:
        """Get a Context value

        Args:
            key (str): Key for the context key-value pair.

        Returns:
            Any: The value associated with the key.
        """

        return self._values[key]

    def get_headers(self) -> MutableMapping[str, str]:
        """Get request headers that are currently stored.

        Returns:
            MutableMapping[str, str]: The request headers.
        """

        return self._headers

    def set_header(self, key: str, value: str) -> None:
        """Set a request header

        Args:
            key (str): Key for the header.
            value (str): Value for the header.
        """

        self._headers[key] = value

    def get_response_headers(self) -> MutableMapping[str, str]:
        """Get response headers that are currently stored.

        Returns:
            MutableMapping[str, str]: The response headers.
        """

        return self._response_headers

    def set_response_header(self, key: str, value: str) -> None:
        """Set a response header

        Args:
            key (str): Key for the header.
            value (str): Value for the header.
        """

        self._response_headers[key] = value


class ServiceContext(Protocol):
    """Represents the context of a service."""

    async def abort(self, code, message):
        """Abort the service with the given code and message.

        Args:
            code (int): The error code.
            message (str): The error message.
        """
        ...

    def code(self) -> int:
        """Get the error code.

        Returns:
            int: The error code.
        """
        ...

    def details(self) -> str:
        """Get the error details.

        Returns:
            str: The error details.
        """
        ...

    def invocation_metadata(self) -> Mapping[str, List[str]]:
        """Get the invocation metadata.

        Returns:
            Mapping[str, List[str]]: The invocation metadata.
        """
        ...

    def peer(self) -> str:
        """Get the peer information.

        Returns:
            str: The peer information.
        """
        ...

    def set_code(self, code: int) -> None:
        """Set the error code.

        Args:
            code (int): The error code.
        """
        ...

    def set_details(self, details: str) -> None:
        """Set the error details.

        Args:
            details (str): The error details.
        """
        ...

    def set_trailing_metadata(self, metadata: Mapping[str, List[str]]) -> None:
        """Set the trailing metadata.

        Args:
            metadata (Mapping[str, List[str]]): The trailing metadata.
        """
        ...

    def time_remaining(self) -> float | None:
        """Get the remaining time.

        Returns:
            float | None: The remaining time in seconds, or None if not applicable.
        """
        ...

    def trailing_metadata(self) -> Mapping[str, List[str]]:
        """Get the trailing metadata.

        Returns:
            Mapping[str, List[str]]: The trailing metadata.
        """
        ...


class ConnecpyServiceContext:
    """
    Represents the context of a Connecpy service.

    Attributes:
        _peer: The peer information of the service.
        _invocation_metadata: The invocation metadata of the service.
        _code: The response code of the service.
        _details: The response details of the service.
        _trailing_metadata: The trailing metadata of the service.
        _timeout_sec: The timeout duration in seconds.
        _start_time: The start time of the service.
    """

    def __init__(self, peer: str, invocation_metadata: Mapping[str, List[str]]):
        """
        Initialize a Context object.

        Args:
            peer (str): The peer information.
            invocation_metadata (Mapping[str, List[str]]): The invocation metadata.

        Returns:
            None
        """
        self._peer = peer
        self._invocation_metadata = invocation_metadata
        self._code = 200
        self._details = ""
        self._trailing_metadata = {}
        timeout_ms: str | None = invocation_metadata.get("connect-timeout-ms", [None])[
            0
        ]
        if timeout_ms is None:
            self._timeout_sec = None
        else:
            self._timeout_sec = float(timeout_ms) / 1000.0
            self._start_time = time.time()

    async def abort(self, code, message):
        """
        Abort the current request with the given code and message.

        :param code: The HTTP status code to return.
        :param message: The error message to include in the response.
        :raises: exceptions.ConnecpyServerException
        """
        raise exceptions.ConnecpyServerException(code=code, message=message)

    def code(self) -> int:
        """
        Get the status code associated with the context.

        Returns:
            int: The status code associated with the context.
        """
        return self._code

    def details(self) -> str:
        """
        Returns the details of the context.

        :return: The details of the context.
        :rtype: str
        """
        return self._details

    def invocation_metadata(self) -> Mapping[str, List[str]]:
        """
        Returns the invocation metadata associated with the context.

        :return: A mapping of metadata keys to lists of metadata values.
        """
        return self._invocation_metadata

    def peer(self):
        """
        Returns the peer associated with the context.
        """
        return self._peer

    def set_code(self, code: int) -> None:
        """
        Set the status code for the context.

        Args:
            code (int): The code to set.

        Returns:
            None
        """
        self._code = code

    def set_details(self, details: str) -> None:
        """
        Set the details of the context.

        Args:
            details (str): The details to be set.

        Returns:
            None
        """
        self._details = details

    def set_trailing_metadata(self, metadata: Mapping[str, List[str]]) -> None:
        """
        Sets the trailing metadata for the context.

        Args:
            metadata (Mapping[str, List[str]]): A mapping of metadata keys to lists of values.

        Returns:
            None
        """
        self._trailing_metadata = metadata

    def time_remaining(self) -> float | None:
        """
        Calculate the remaining time until the timeout.

        Returns:
            float | None: The remaining time in seconds, or None if no timeout is set.
        """
        if self._timeout_sec is None:
            return None
        return self._timeout_sec - (time.time() - self._start_time)

    def trailing_metadata(self) -> Mapping[str, List[str]]:
        """
        Returns the trailing metadata associated with the context.

        :return: A mapping of metadata keys to lists of metadata values.
        :rtype: Mapping[str, List[str]]
        """
        return self._trailing_metadata
