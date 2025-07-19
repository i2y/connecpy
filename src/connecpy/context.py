from http import HTTPStatus
from typing import Mapping, Iterable, List, Optional, Union
import time

from . import errors
from . import exceptions
from ._protocol import HTTPException


class ServiceContext:
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

    _response_headers: Optional[list[tuple[str, str]]] = None
    _response_trailers: Optional[list[tuple[str, str]]] = None

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

        # We don't require connect-protocol-version header. connect-go provides an option
        # to require it but it's almost never used in practice.
        connect_protocol_version = self._invocation_metadata.get(
            "connect-protocol-version", ["1"]
        )[0]
        if connect_protocol_version != "1":
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.InvalidArgument,
                message=f"connect-protocol-version must be '1': got '{connect_protocol_version}'",
            )
        self._connect_protocol_version = connect_protocol_version

        ctype = self._invocation_metadata.get("content-type", ["application/proto"])[0]
        if ctype not in ("application/proto", "application/json"):
            raise HTTPException(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                [("Accept-Post", "application/json, application/proto")],
            )
        self._content_type = ctype

        timeout_ms: Union[str, None] = invocation_metadata.get(
            "connect-timeout-ms", [None]
        )[0]
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

    def content_type(self) -> str:
        """
        Returns the content type associated with the context.

        :return: The content type associated with the context.
        :rtype: str
        """
        return self._content_type

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

    def response_headers(self) -> Iterable[tuple[str, str]]:
        """
        Returns the response headers that will be sent before the response.
        """
        if self._response_headers is None:
            return ()
        return self._response_headers

    def add_response_header(self, key: str, value: str) -> None:
        """
        Add a response header to send before the response.

        Args:
            key (str): The header key.
            value (str): The header value.

        Returns:
            None
        """
        if self._response_headers is None:
            self._response_headers = []
        self._response_headers.append((key, value))

    def response_trailers(self) -> Iterable[tuple[str, str]]:
        """
        Returns the response trailers that will be sent after the response.
        """
        if self._response_trailers is None:
            return ()
        return self._response_trailers

    def add_response_trailer(self, key: str, value: str) -> None:
        """
        Add a response trailer to send after the response.

        Args:
            key (str): The header key.
            value (str): The header value.

        Returns:
            None
        """
        if self._response_trailers is None:
            self._response_trailers = []
        self._response_trailers.append((key, value))

    def time_remaining(self) -> Union[float, None]:
        """
        Calculate the remaining time until the timeout.

        Returns:
            float | None: The remaining time in seconds, or None if no timeout is set.
        """
        if self._timeout_sec is None:
            return None
        return self._timeout_sec - (time.time() - self._start_time)
